"""
照片服务 - 高性能版
"""
from werkzeug.utils import secure_filename
from typing import Tuple, Optional, List
import uuid
import os
import logging

from models.base import db
from models.photo import Photo, Vote
from models.user import User
from models.settings import Settings
from services.cache_service import cache, cached, CacheStrategies, invalidate_photo_cache

logger = logging.getLogger(__name__)


class PhotoService:
    """高性能照片服务"""
    
    @staticmethod
    def upload_photo(file, user_id, title: str = None, ip_address: str = None) -> Tuple[Optional[Photo], str]:
        """
        高效照片上传处理
        """
        try:
            # 1. 获取用户信息
            user = User.get_by_id(user_id)
            if not user or not user.is_active:
                return None, '用户不存在或已禁用'
            
            # 2. 检查上传权限
            settings = Settings.get_current()
            if not settings.is_upload_allowed():
                return None, '当前不允许上传'
            
            # 3. 验证文件
            if not file or not file.filename:
                return None, '请选择文件'
            
            # 4. 验证文件类型
            if not PhotoService._is_allowed_file(file.filename):
                return None, '不支持的文件类型'
            
            # 5. 快速保存原文件
            filename = PhotoService._save_original_file(file)
            if not filename:
                return None, '文件保存失败'
            
            # 6. 创建数据库记录
            photo = Photo(
                url=f'/photo/uploads/{filename}',
                title=title or f'作品_{uuid.uuid4().hex[:8]}',
                class_name=user.class_name,
                student_name=user.real_name,
                user_id=user_id,
                status=0,  # 待审核
                metadata={'ip_address': ip_address, 'original_filename': file.filename}
            )
            
            db.session.add(photo)
            db.session.commit()
            
            # 7. 异步处理图片（缩略图、水印等）
            PhotoService._schedule_image_processing(photo.id)
            
            # 8. 清除相关缓存
            invalidate_photo_cache()
            cache.delete(f'user_photos:{user_id}')
            
            return photo, '上传成功，正在处理'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"照片上传失败: {e}")
            return None, f'上传失败: {str(e)}'
    
    @staticmethod
    def _is_allowed_file(filename: str) -> bool:
        """检查文件类型"""
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    @staticmethod
    def _save_original_file(file) -> Optional[str]:
        """保存原始文件"""
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            
            upload_path = os.path.join('photo/uploads', unique_filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            file.save(upload_path)
            
            return unique_filename
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return None
    
    @staticmethod
    def _schedule_image_processing(photo_id):
        """调度图片处理任务"""
        try:
            # 尝试使用Celery异步处理
            from tasks.image_tasks import process_image
            process_image.delay(str(photo_id))
        except ImportError:
            # Celery不可用时同步处理
            PhotoService._process_image_sync(photo_id)
    
    @staticmethod
    def _process_image_sync(photo_id):
        """同步图片处理（备用方案）"""
        try:
            from utils.image_utils import create_thumbnail, add_watermark
            
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return
            
            original_path = photo.url.lstrip('/')
            
            # 生成缩略图
            thumb_filename = create_thumbnail(original_path)
            if thumb_filename:
                photo.thumb_url = f'/photo/thumbs/{thumb_filename}'
            
            # 添加水印
            settings = Settings.get_current()
            if settings.watermark_enabled:
                watermark_filename = add_watermark(original_path, photo.student_name, photo.class_name)
                if watermark_filename:
                    photo.url = f'/photo/uploads/{watermark_filename}'
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"同步图片处理失败: {e}")
    
    @staticmethod
    @cached(timeout=CacheStrategies.PHOTO_LIST_TIMEOUT, key_prefix='photos_approved')
    def get_approved_photos(limit: int = 50, offset: int = 0) -> List[Photo]:
        """获取已审核照片（带缓存）"""
        return Photo.get_approved(limit=limit, offset=offset)
    
    @staticmethod
    @cached(timeout=CacheStrategies.PHOTO_LIST_TIMEOUT, key_prefix='photos_pending')
    def get_pending_photos(limit: int = 50) -> List[Photo]:
        """获取待审核照片（带缓存）"""
        return Photo.get_pending(limit=limit)
    
    @staticmethod
    @cached(timeout=CacheStrategies.RANKING_CACHE_TIMEOUT, key_prefix='ranking')
    def get_photo_rankings(limit: int = 10) -> List[Photo]:
        """获取照片排行榜（带缓存）"""
        return Photo.get_top_voted(limit=limit)
    
    @staticmethod
    @cached(timeout=CacheStrategies.SEARCH_CACHE_TIMEOUT, key_prefix='search')
    def search_photos(search_term: str, limit: int = 20) -> List[Photo]:
        """高性能搜索"""
        if not search_term or len(search_term.strip()) < 2:
            return []
        
        # 使用PostgreSQL全文搜索
        return Photo.search(search_term.strip(), limit=limit)
    
    @staticmethod
    def approve_photo(photo_id, admin_user_id) -> Tuple[bool, str]:
        """审核通过照片"""
        try:
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return False, '照片不存在'
            
            if photo.status != 0:
                return False, '照片已处理'
            
            photo.approve()
            db.session.commit()
            
            # 清除相关缓存
            invalidate_photo_cache(photo_id)
            
            return True, '审核通过'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"审核照片失败: {e}")
            return False, '审核失败'
    
    @staticmethod
    def reject_photo(photo_id, admin_user_id, reason: str = None) -> Tuple[bool, str]:
        """拒绝照片"""
        try:
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return False, '照片不存在'
            
            if photo.status != 0:
                return False, '照片已处理'
            
            photo.reject()
            if reason:
                photo.set_metadata_value('reject_reason', reason)
            
            db.session.commit()
            
            # 清除相关缓存
            invalidate_photo_cache(photo_id)
            
            return True, '已拒绝'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"拒绝照片失败: {e}")
            return False, '操作失败'
    
    @staticmethod
    def delete_photo(photo_id, user_id) -> Tuple[bool, str]:
        """删除照片"""
        try:
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return False, '照片不存在'
            
            # 权限检查
            user = User.get_by_id(user_id)
            if not user:
                return False, '用户不存在'
            
            if photo.user_id != user_id and not user.is_admin():
                return False, '没有删除权限'
            
            # 软删除
            photo.delete_photo()
            db.session.commit()
            
            # 清除相关缓存
            invalidate_photo_cache(photo_id)
            cache.delete(f'user_photos:{photo.user_id}')
            
            return True, '删除成功'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除照片失败: {e}")
            return False, '删除失败'
    
    @staticmethod
    @cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user_photos')
    def get_user_photos(user_id, include_deleted: bool = False) -> List[Photo]:
        """获取用户照片"""
        return Photo.get_by_user(user_id, include_deleted=include_deleted)
    
    @staticmethod
    @cached(timeout=CacheStrategies.STATS_CACHE_TIMEOUT, key_prefix='photo_stats')
    def get_photo_statistics() -> dict:
        """获取照片统计信息"""
        return Photo.get_statistics()
    
    @staticmethod
    def batch_approve_photos(photo_ids: List, admin_user_id) -> Tuple[int, str]:
        """批量审核照片"""
        try:
            success_count = 0
            
            for photo_id in photo_ids:
                photo = Photo.get_by_id(photo_id)
                if photo and photo.status == 0:
                    photo.approve()
                    success_count += 1
            
            db.session.commit()
            
            # 清除相关缓存
            invalidate_photo_cache()
            
            return success_count, f'成功审核 {success_count} 张照片'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量审核失败: {e}")
            return 0, '批量审核失败'
    
    @staticmethod
    def get_recent_photos(days: int = 7, limit: int = 20) -> List[Photo]:
        """获取最近照片"""
        return Photo.get_recent(days=days, limit=limit)
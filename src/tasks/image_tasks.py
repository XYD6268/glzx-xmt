"""
图片处理异步任务
"""
from tasks.celery_app import celery
from models.base import db
from models.photo import Photo
from models.settings import Settings
import logging
import os
from PIL import Image, ImageDraw, ImageFont
import uuid

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='tasks.image_tasks.process_image')
def process_image(self, photo_id):
    """
    异步处理图片 - 生成缩略图和水印
    """
    try:
        photo = Photo.get_by_id(photo_id)
        if not photo:
            logger.error(f"照片不存在: {photo_id}")
            return False
        
        original_path = photo.url.lstrip('/')
        
        if not os.path.exists(original_path):
            logger.error(f"原始文件不存在: {original_path}")
            return False
        
        success = True
        
        # 生成缩略图
        thumb_result = create_thumbnail_task(original_path)
        if thumb_result:
            photo.thumb_url = f'/static/thumbs/{thumb_result}'
        else:
            success = False
        
        # 添加水印
        settings = Settings.get_current()
        if settings and settings.watermark_enabled:
            watermark_result = add_watermark_task(
                original_path, 
                photo.student_name, 
                photo.class_name,
                settings
            )
            if watermark_result:
                photo.url = f'/static/uploads/{watermark_result}'
            else:
                success = False
        
        # 更新数据库
        db.session.commit()
        
        logger.info(f"图片处理完成: {photo_id}")
        return success
        
    except Exception as e:
        logger.error(f"图片处理失败 {photo_id}: {e}")
        db.session.rollback()
        
        # 重试机制
        if self.request.retries < 3:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return False


def create_thumbnail_task(original_path, size=(180, 120), quality=85):
    """创建缩略图"""
    try:
        # 确保缩略图目录存在
        thumb_dir = 'static/thumbs'
        os.makedirs(thumb_dir, exist_ok=True)
        
        # 打开原图
        with Image.open(original_path) as img:
            # 转换为RGB模式（如果是RGBA）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 计算缩略图尺寸（保持比例）
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # 生成缩略图文件名
            filename = f"thumb_{uuid.uuid4().hex}.jpg"
            thumb_path = os.path.join(thumb_dir, filename)
            
            # 保存缩略图
            img.save(thumb_path, 'JPEG', quality=quality, optimize=True)
            
            logger.info(f"缩略图生成成功: {thumb_path}")
            return filename
            
    except Exception as e:
        logger.error(f"缩略图生成失败 {original_path}: {e}")
        return None


def add_watermark_task(original_path, student_name, class_name, settings):
    """添加水印"""
    try:
        # 生成水印文本
        watermark_text = settings.watermark_text.format(
            contest_title=settings.contest_title,
            student_name=student_name,
            class_name=class_name,
            qq_number=""  # 从照片元数据获取
        )
        
        # 打开原图
        with Image.open(original_path) as img:
            # 转换为RGBA模式支持透明度
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 创建水印层
            watermark_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)
            
            # 尝试加载字体
            font = get_watermark_font(settings.watermark_font_size)
            
            # 计算文本尺寸
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 计算水印位置
            x, y = calculate_watermark_position(
                img.size, text_width, text_height, settings.watermark_position
            )
            
            # 计算透明度
            alpha = int(255 * settings.watermark_opacity)
            text_color = (255, 255, 255, alpha)
            
            # 绘制水印
            draw.text((x, y), watermark_text, font=font, fill=text_color)
            
            # 合并图层
            watermarked = Image.alpha_composite(img, watermark_layer)
            
            # 转换回RGB模式
            watermarked = watermarked.convert('RGB')
            
            # 生成新文件名
            filename = f"watermarked_{uuid.uuid4().hex}.jpg"
            watermarked_path = os.path.join('static/uploads', filename)
            
            # 保存带水印的图片
            watermarked.save(watermarked_path, 'JPEG', quality=90, optimize=True)
            
            logger.info(f"水印添加成功: {watermarked_path}")
            return filename
            
    except Exception as e:
        logger.error(f"水印添加失败 {original_path}: {e}")
        return None


def get_watermark_font(font_size):
    """获取水印字体"""
    font_paths = [
        '/System/Library/Fonts/STHeiti Light.ttc',  # macOS
        'C:/Windows/Fonts/msyh.ttc',  # Windows
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    ]
    
    # 尝试加载系统字体
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, font_size)
        except Exception:
            continue
    
    # 降级到默认字体
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def calculate_watermark_position(img_size, text_width, text_height, position):
    """计算水印位置"""
    img_width, img_height = img_size
    margin = 20
    
    positions = {
        'top_left': (margin, margin),
        'top_right': (img_width - text_width - margin, margin),
        'bottom_left': (margin, img_height - text_height - margin),
        'bottom_right': (img_width - text_width - margin, img_height - text_height - margin),
        'center': ((img_width - text_width) // 2, (img_height - text_height) // 2)
    }
    
    return positions.get(position, positions['bottom_right'])


@celery.task(name='tasks.image_tasks.batch_process_images')
def batch_process_images(photo_ids):
    """批量处理图片"""
    results = []
    
    for photo_id in photo_ids:
        try:
            result = process_image.delay(photo_id)
            results.append({
                'photo_id': photo_id,
                'task_id': result.id,
                'status': 'queued'
            })
        except Exception as e:
            logger.error(f"批量处理图片失败 {photo_id}: {e}")
            results.append({
                'photo_id': photo_id,
                'task_id': None,
                'status': 'failed',
                'error': str(e)
            })
    
    return results


@celery.task(name='tasks.image_tasks.cleanup_temp_files')
def cleanup_temp_files():
    """清理临时文件"""
    try:
        import tempfile
        import shutil
        import time
        
        temp_dir = tempfile.gettempdir()
        current_time = time.time()
        
        cleaned_count = 0
        
        # 清理超过24小时的临时文件
        for filename in os.listdir(temp_dir):
            if filename.startswith('glzx_xmt_'):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > 86400:  # 24小时
                        os.remove(file_path)
                        cleaned_count += 1
        
        logger.info(f"清理临时文件完成，删除 {cleaned_count} 个文件")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"清理临时文件失败: {e}")
        return 0


@celery.task(name='tasks.image_tasks.optimize_images')
def optimize_images():
    """优化存储的图片"""
    try:
        # 获取所有需要优化的照片
        photos = Photo.query.filter_by(status=1).limit(100).all()
        
        optimized_count = 0
        
        for photo in photos:
            try:
                original_path = photo.url.lstrip('/')
                
                if not os.path.exists(original_path):
                    continue
                
                # 检查文件大小
                file_size = os.path.getsize(original_path)
                
                # 只优化大于1MB的文件
                if file_size > 1024 * 1024:
                    optimized = optimize_single_image(original_path)
                    if optimized:
                        optimized_count += 1
                        
            except Exception as e:
                logger.warning(f"优化图片失败 {photo.id}: {e}")
                continue
        
        logger.info(f"图片优化完成，优化 {optimized_count} 张图片")
        return optimized_count
        
    except Exception as e:
        logger.error(f"批量优化图片失败: {e}")
        return 0


def optimize_single_image(image_path, max_width=1920, quality=85):
    """优化单张图片"""
    try:
        with Image.open(image_path) as img:
            # 检查是否需要缩放
            if img.width > max_width:
                # 计算新尺寸
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                
                # 缩放图片
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 保存优化后的图片
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            
            return True
            
    except Exception as e:
        logger.error(f"优化图片失败 {image_path}: {e}")
        return False
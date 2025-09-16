"""
投票服务 - 高性能版
"""
from typing import Tuple, Optional
from datetime import datetime, timedelta
import logging

from app.models.base import db
from app.models.photo import Photo, Vote
from app.models.user import User
from app.models.settings import Settings
from app.services.cache_service import cache, cached, CacheStrategies, invalidate_photo_cache
from app.services.security_service import SecurityService

logger = logging.getLogger(__name__)


class VoteService:
    """高性能投票服务"""
    
    @staticmethod
    def vote_for_photo(user_id, photo_id, ip_address: str) -> Tuple[bool, str]:
        """
        为照片投票 - 高性能版
        """
        try:
            # 1. 增强的IP安全检查
            is_secure, message = SecurityService.check_ip_security(ip_address)
            if not is_secure:
                SecurityService.record_security_event('vote_blocked', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': message, 'photo_id': photo_id})
                return False, message or '投票安全检查失败'
            
            # 2. 检查投票权限
            settings = Settings.get_current()
            if not settings.is_voting_allowed():
                SecurityService.record_security_event('vote_blocked', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': 'voting_not_allowed', 'photo_id': photo_id})
                return False, '当前不允许投票'
            
            # 3. 获取用户和照片
            user = User.get_by_id(user_id)
            if not user or not user.is_active:
                SecurityService.record_security_event('vote_failed', ip_address=ip_address,
                                                  details={'reason': 'user_not_found', 'photo_id': photo_id})
                return False, '用户不存在或已禁用'
            
            photo = Photo.get_by_id(photo_id)
            if not photo or not photo.is_approved:
                SecurityService.record_security_event('vote_failed', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': 'photo_not_found', 'photo_id': photo_id})
                return False, '照片不存在或未审核'
            
            # 4. 检查是否已投票
            if Vote.has_voted(user_id, photo_id):
                SecurityService.record_security_event('vote_failed', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': 'already_voted', 'photo_id': photo_id})
                return False, '您已经投过票了'
            
            # 5. 检查是否为自己的照片
            if photo.user_id == user_id:
                SecurityService.record_security_event('vote_failed', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': 'own_photo', 'photo_id': photo_id})
                return False, '不能为自己的作品投票'
            
            # 6. 增强的风控检查
            if not VoteService._check_vote_security(user_id, ip_address, settings):
                SecurityService.record_security_event('vote_blocked', user_id=user_id, ip_address=ip_address,
                                                  details={'reason': 'security_check_failed', 'photo_id': photo_id})
                return False, '投票过于频繁，请稍后再试'
            
            # 7. 检查每人只投一票限制
            if settings.one_vote_per_user:
                user_vote_count = Vote.query.filter_by(user_id=user_id).count()
                if user_vote_count > 0:
                    SecurityService.record_security_event('vote_failed', user_id=user_id, ip_address=ip_address,
                                                      details={'reason': 'one_vote_limit', 'photo_id': photo_id})
                    return False, '每人只能投一票'
            
            # 8. 创建投票记录
            vote = Vote(
                user_id=user_id,
                photo_id=photo_id,
                ip_address=ip_address
            )
            
            db.session.add(vote)
            
            # 9. 更新照片投票数
            photo.increment_vote_count()
            
            db.session.commit()
            
            # 10. 记录投票活动（用于风控）
            VoteService._record_vote_activity(user_id, ip_address)
            
            # 11. 清除相关缓存
            invalidate_photo_cache(photo_id)
            cache.delete(f'user_votes:{user_id}')
            
            # 12. 记录安全事件
            SecurityService.record_security_event('vote_success', user_id=user_id, ip_address=ip_address,
                                              details={'photo_id': photo_id})
            
            return True, '投票成功'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"投票失败: {e}")
            return False, '投票失败，请稍后再试'
    
    @staticmethod
    def cancel_vote(user_id, photo_id) -> Tuple[bool, str]:
        """取消投票"""
        try:
            # 1. 检查投票是否存在
            vote = Vote.get_user_vote(user_id, photo_id)
            if not vote:
                return False, '您还没有投票'
            
            # 2. 获取照片
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return False, '照片不存在'
            
            # 3. 删除投票记录
            db.session.delete(vote)
            
            # 4. 减少照片投票数
            photo.decrement_vote_count()
            
            db.session.commit()
            
            # 5. 清除相关缓存
            invalidate_photo_cache(photo_id)
            cache.delete(f'user_votes:{user_id}')
            
            return True, '取消投票成功'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"取消投票失败: {e}")
            return False, '取消失败'
    
    @staticmethod
    def _check_vote_security(user_id, ip_address: str, settings: Settings) -> bool:
        """投票安全检查"""
        try:
            # 1. 检查IP投票频率
            ip_vote_count = cache.get(f'vote_ip:{ip_address}', 0)
            if ip_vote_count >= settings.max_votes_per_ip:
                return False
            
            # 2. 检查用户投票频率
            user_vote_count = cache.get(f'vote_user:{user_id}', 0)
            if user_vote_count >= 10:  # 用户每小时最多投10票
                return False
            
            # 3. 检查时间窗口内的投票数量
            recent_votes = VoteService._get_recent_vote_count(user_id, hours=1)
            if recent_votes >= 5:  # 1小时内最多5票
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"投票安全检查失败: {e}")
            return True  # 检查失败时允许投票
    
    @staticmethod
    def _record_vote_activity(user_id, ip_address: str):
        """记录投票活动"""
        try:
            # 更新缓存计数器
            cache.increment(f'vote_ip:{ip_address}', timeout=3600)  # 1小时
            cache.increment(f'vote_user:{user_id}', timeout=3600)   # 1小时
            
        except Exception as e:
            logger.warning(f"记录投票活动失败: {e}")
    
    @staticmethod
    @cached(timeout=300, key_prefix='recent_votes')
    def _get_recent_vote_count(user_id, hours: int = 1) -> int:
        """获取最近投票数量"""
        try:
            time_threshold = datetime.utcnow() - timedelta(hours=hours)
            return Vote.query.filter(
                Vote.user_id == user_id,
                Vote.created_at >= time_threshold
            ).count()
        except Exception:
            return 0
    
    @staticmethod
    @cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user_votes')
    def get_user_votes(user_id, limit: int = 50):
        """获取用户投票记录"""
        return Vote.get_user_votes(user_id, limit=limit)
    
    @staticmethod
    @cached(timeout=CacheStrategies.PHOTO_CACHE_TIMEOUT, key_prefix='photo_votes')
    def get_photo_votes(photo_id, limit: int = 50):
        """获取照片投票记录"""
        return Vote.get_photo_votes(photo_id, limit=limit)
    
    @staticmethod
    def check_user_vote_status(user_id, photo_id) -> bool:
        """检查用户是否已投票"""
        return Vote.has_voted(user_id, photo_id)
    
    @staticmethod
    @cached(timeout=CacheStrategies.STATS_CACHE_TIMEOUT, key_prefix='vote_stats')
    def get_vote_statistics(photo_id: Optional[str] = None) -> dict:
        """获取投票统计"""
        return Vote.get_vote_statistics(photo_id=photo_id)
    
    @staticmethod
    def get_ip_vote_status(ip_address: str) -> dict:
        """获取IP投票状态"""
        try:
            settings = Settings.get_current()
            current_count = cache.get(f'vote_ip:{ip_address}', 0)
            
            return {
                'current_votes': current_count,
                'max_votes': settings.max_votes_per_ip,
                'remaining_votes': max(0, settings.max_votes_per_ip - current_count),
                'can_vote': current_count < settings.max_votes_per_ip
            }
        except Exception as e:
            logger.error(f"获取IP投票状态失败: {e}")
            return {
                'current_votes': 0,
                'max_votes': 10,
                'remaining_votes': 10,
                'can_vote': True
            }
    
    @staticmethod
    def admin_reset_photo_votes(photo_id, admin_user_id) -> Tuple[bool, str]:
        """管理员重置照片投票"""
        try:
            photo = Photo.get_by_id(photo_id)
            if not photo:
                return False, '照片不存在'
            
            # 删除所有投票记录
            Vote.query.filter_by(photo_id=photo_id).delete()
            
            # 重置投票数
            photo.vote_count = 0
            
            db.session.commit()
            
            # 清除缓存
            invalidate_photo_cache(photo_id)
            
            return True, '投票已重置'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"重置投票失败: {e}")
            return False, '重置失败'
    
    @staticmethod
    def get_user_vote_summary(user_id) -> dict:
        """获取用户投票摘要"""
        try:
            user_votes = Vote.query.filter_by(user_id=user_id).count()
            recent_votes = VoteService._get_recent_vote_count(user_id, hours=24)
            
            settings = Settings.get_current()
            can_vote_more = True
            
            if settings.one_vote_per_user and user_votes > 0:
                can_vote_more = False
            
            return {
                'total_votes': user_votes,
                'recent_votes_24h': recent_votes,
                'can_vote_more': can_vote_more,
                'one_vote_limit': settings.one_vote_per_user
            }
            
        except Exception as e:
            logger.error(f"获取用户投票摘要失败: {e}")
            return {
                'total_votes': 0,
                'recent_votes_24h': 0,
                'can_vote_more': True,
                'one_vote_limit': False
            }
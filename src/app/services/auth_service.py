"""
认证服务 - 精简高效版
"""
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from typing import Tuple, Optional
import logging

from app.models.base import db
from app.models.user import User, LoginRecord, IpBanRecord, IpWhitelist, UserWhitelist
from app.services.cache_service import cache, cached, CacheStrategies
from app.services.security_service import SecurityService

logger = logging.getLogger(__name__)


class AuthService:
    """精简高效的认证服务"""
    
    @staticmethod
    def login_user(username: str, password: str, ip_address: str, user_agent: str = None) -> Tuple[Optional[User], str]:
        """
        用户登录 - 简化流程，保证性能
        
        Returns:
            Tuple[User|None, message]: 用户对象和消息
        """
        try:
            # 1. 增强的IP安全检查（优先级最高）
            is_secure, message = SecurityService.check_ip_security(ip_address)
            if not is_secure:
                SecurityService.record_security_event('login_blocked', ip_address=ip_address, 
                                                   details={'reason': message, 'username': username})
                return None, message or '登录异常，请稍后再试'
            
            # 2. 缓存查询用户（性能优化）
            user = AuthService._get_user_cached(username)
            if not user or not user.is_active:
                SecurityService.record_security_event('login_failed', ip_address=ip_address, 
                                                  details={'reason': 'user_not_found', 'username': username})
                return None, '用户不存在或已禁用'
            
            # 3. 验证密码
            if not user.check_password(password):
                # 记录失败尝试
                AuthService._record_failed_login(ip_address, username)
                SecurityService.record_security_event('login_failed', ip_address=ip_address, 
                                                  details={'reason': 'password_error', 'username': username})
                return None, '密码错误'
            
            # 4. 增强的用户级安全检查
            is_secure, message = SecurityService.check_user_security(user.id, ip_address)
            if not is_secure:
                SecurityService.record_security_event('login_blocked', ip_address=ip_address, 
                                                   details={'reason': message, 'username': username})
                return None, message or '账户安全检查失败'
            
            # 5. 记录成功登录（异步）
            AuthService._record_successful_login(user.id, ip_address, user_agent)
            
            # 6. 清除失败计数
            cache.delete(f"login_fail:{ip_address}")
            
            # 7. 记录安全事件
            SecurityService.record_security_event('login_success', user_id=user.id, ip_address=ip_address)
            
            return user, '登录成功'
            
        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            return None, '系统错误，请稍后再试'
    
    @staticmethod
    def _check_ip_security(ip_address: str) -> bool:
        """IP安全检查 - 高性能版"""
        try:
            # 1. 检查IP白名单（最高优先级）
            if IpWhitelist.is_whitelisted(ip_address):
                return True
            
            # 2. 检查IP封禁状态
            if IpBanRecord.is_banned(ip_address):
                return False
            
            # 3. 检查登录频率（缓存优化）
            fail_count = cache.get(f"login_fail:{ip_address}", 0)
            if fail_count >= 10:  # 10次失败后临时封禁
                return False
            
            # 4. 检查登录频率（更严格的检查）
            login_count = cache.get(f"login_attempts:{ip_address}", 0)
            if login_count > 20:  # 20次尝试/小时
                return False
            
            # 5. 更新登录尝试计数
            cache.increment(f"login_attempts:{ip_address}", timeout=3600)
            
            return True
            
        except Exception as e:
            logger.warning(f"IP安全检查失败 {ip_address}: {e}")
            return True  # 安全检查失败时允许通过，避免误杀
    
    @staticmethod
    def _check_user_security(user: User, ip_address: str) -> bool:
        """用户安全检查"""
        try:
            # 1. 检查用户白名单
            if UserWhitelist.is_whitelisted(user.id):
                return True
            
            # 2. 检查用户状态
            if not user.is_active:
                return False
            
            # 3. 检查IP登录账号数限制（24小时内）
            unique_users_key = f"ip_users:{ip_address}"
            cached_users = cache.get(unique_users_key, set())
            
            if isinstance(cached_users, set):
                cached_users.add(str(user.id))
                if len(cached_users) > 5:  # 单IP最多5个账号
                    return False
                cache.set(unique_users_key, cached_users, timeout=86400)  # 24小时
            
            return True
            
        except Exception as e:
            logger.warning(f"用户安全检查失败 {user.id}: {e}")
            return True  # 默认允许
    
    @staticmethod
    @cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user_login')
    def _get_user_cached(username: str) -> Optional[User]:
        """缓存用户查询"""
        return User.get_by_name(username)
    
    @staticmethod
    def _record_failed_login(ip_address: str, username: str):
        """记录失败登录"""
        try:
            # 增加失败计数
            fail_count = cache.increment(f"login_fail:{ip_address}", timeout=3600)
            
            # 严重失败时记录日志
            if fail_count >= 5:
                logger.warning(f"IP {ip_address} 登录失败次数: {fail_count}, 用户名: {username}")
            
            # 自动封禁处理
            if fail_count >= 15:
                IpBanRecord.ban_ip(ip_address, f"登录失败次数过多: {fail_count}")
                logger.warning(f"自动封禁IP: {ip_address}")
                
        except Exception as e:
            logger.error(f"记录失败登录出错: {e}")
    
    @staticmethod
    def _record_successful_login(user_id, ip_address: str, user_agent: str = None):
        """记录成功登录 - 异步优化"""
        try:
            # 使用Celery异步处理（如果可用）
            try:
                from app.tasks.auth_tasks import record_login
                record_login.delay(str(user_id), ip_address, user_agent)
            except ImportError:
                # Celery不可用时直接记录
                login_record = LoginRecord(
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                db.session.add(login_record)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"记录登录出错: {e}")
    
    @staticmethod
    def register_user(username: str, password: str, school_id: str, qq_number: str, 
                     class_name: str, ip_address: str) -> Tuple[Optional[User], str]:
        """
        用户注册 - 精简版
        """
        try:
            # 1. 基础验证
            if not username or len(username) < 2:
                return None, '用户名太短'
            
            if not password or len(password) < 6:
                return None, '密码至少6位'
            
            # 2. 检查用户名唯一性
            if User.get_by_name(username):
                return None, '用户名已存在'
            
            # 3. 检查学号唯一性（如果提供）
            if school_id:
                existing_user = User.query.filter_by(school_id=school_id).first()
                if existing_user:
                    return None, '学号已存在'
            
            # 4. IP注册限制检查
            if not AuthService._check_registration_limit(ip_address):
                return None, '注册过于频繁，请稍后再试'
            
            # 5. 创建用户
            user = User(
                real_name=username,
                school_id=school_id if school_id else None,
                qq_number=qq_number,
                class_name=class_name
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # 6. 记录注册
            cache.increment(f"register_count:{ip_address}", timeout=86400)
            
            # 7. 清除相关缓存
            cache.clear_pattern("user_login:*")
            
            return user, '注册成功'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"注册失败: {e}")
            return None, '注册失败，请稍后再试'
    
    @staticmethod
    def _check_registration_limit(ip_address: str) -> bool:
        """检查注册限制"""
        try:
            # IP白名单跳过限制
            if IpWhitelist.is_whitelisted(ip_address):
                return True
            
            # 检查24小时内注册次数
            count = cache.get(f"register_count:{ip_address}", 0)
            return count < 3  # 每IP每天最多3次注册
            
        except Exception as e:
            logger.warning(f"注册限制检查失败: {e}")
            return True
    
    @staticmethod
    def change_password(user_id, old_password: str, new_password: str) -> Tuple[bool, str]:
        """修改密码"""
        try:
            user = User.get_by_id(user_id)
            if not user:
                return False, '用户不存在'
            
            if not user.check_password(old_password):
                return False, '原密码错误'
            
            if len(new_password) < 6:
                return False, '新密码至少6位'
            
            user.set_password(new_password)
            db.session.commit()
            
            # 清除用户缓存
            cache.clear_pattern(f"user_login:*{user.real_name}*")
            
            return True, '密码修改成功'
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"修改密码失败: {e}")
            return False, '修改失败'
    
    @staticmethod
    def get_login_history(user_id, limit: int = 10):
        """获取登录历史"""
        try:
            return LoginRecord.get_recent_logins(user_id, hours=24*7)[:limit]
        except Exception as e:
            logger.error(f"获取登录历史失败: {e}")
            return []
    
    @staticmethod
    def is_user_active(user_id) -> bool:
        """检查用户是否活跃（缓存版）"""
        try:
            user = AuthService._get_user_by_id_cached(user_id)
            return user and user.is_active
        except Exception:
            return False
    
    @staticmethod
    @cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user_by_id')
    def _get_user_by_id_cached(user_id) -> Optional[User]:
        """通过ID缓存获取用户"""
        return User.get_by_id(user_id)
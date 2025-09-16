"""
安全服务 - 增强版
"""
from typing import Tuple, Optional
import logging
import re
from datetime import datetime, timedelta

from app.models.base import db
from app.models.user import User, IpBanRecord, IpWhitelist, UserWhitelist
from app.models.photo import Vote
from app.models.settings import Settings
from app.services.cache_service import cache

logger = logging.getLogger(__name__)


class SecurityService:
    """增强的安全服务"""
    
    @staticmethod
    def check_ip_security(ip_address: str) -> Tuple[bool, str]:
        """
        增强的IP安全检查
        
        Returns:
            Tuple[bool, str]: (是否通过检查, 错误消息)
        """
        try:
            # 1. 检查IP白名单（最高优先级）
            if IpWhitelist.is_whitelisted(ip_address):
                return True, ""
            
            # 2. 检查IP封禁状态
            if IpBanRecord.is_banned(ip_address):
                return False, "IP地址已被封禁"
            
            # 3. 检查登录频率（缓存优化）
            fail_count = cache.get(f"login_fail:{ip_address}", 0)
            if fail_count >= 10:  # 10次失败后临时封禁
                return False, "登录失败次数过多，请稍后再试"
            
            # 4. 检查登录频率（更严格的检查）
            login_count = cache.get(f"login_attempts:{ip_address}", 0)
            if login_count > 20:  # 20次尝试/小时
                return False, "登录尝试过于频繁，请稍后再试"
            
            # 5. 检查注册频率
            register_count = cache.get(f"register_count:{ip_address}", 0)
            if register_count > 5:  # 每IP每天最多5次注册
                return False, "注册过于频繁，请稍后再试"
            
            # 6. 检查投票频率
            vote_count = cache.get(f"vote_attempts:{ip_address}", 0)
            settings = Settings.get_current()
            if vote_count >= settings.max_votes_per_ip:
                return False, "投票次数已达上限"
            
            return True, ""
            
        except Exception as e:
            logger.warning(f"IP安全检查失败 {ip_address}: {e}")
            return True, ""  # 安全检查失败时允许通过，避免误杀
    
    @staticmethod
    def check_user_security(user_id, ip_address: str) -> Tuple[bool, str]:
        """
        增强的用户安全检查
        
        Returns:
            Tuple[bool, str]: (是否通过检查, 错误消息)
        """
        try:
            user = User.get_by_id(user_id)
            if not user:
                return False, "用户不存在"
            
            # 1. 检查用户白名单
            if UserWhitelist.is_whitelisted(user_id):
                return True, ""
            
            # 2. 检查用户状态
            if not user.is_active:
                return False, "账户已被禁用"
            
            # 3. 检查IP登录账号数限制（24小时内）
            unique_users_key = f"ip_users_24h:{ip_address}"
            cached_users = cache.get(unique_users_key, set())
            
            if isinstance(cached_users, set):
                cached_users.add(str(user_id))
                if len(cached_users) > 5:  # 单IP最多5个账号
                    return False, "账户安全检查失败：IP关联账号过多"
                cache.set(unique_users_key, cached_users, timeout=86400)  # 24小时
            
            return True, ""
            
        except Exception as e:
            logger.warning(f"用户安全检查失败 {user_id}: {e}")
            return True, ""  # 默认允许
    
    @staticmethod
    def record_security_event(event_type: str, user_id=None, ip_address: str = None, 
                           details: dict = None):
        """
        记录安全事件
        """
        try:
            event_data = {
                'event_type': event_type,
                'user_id': str(user_id) if user_id else None,
                'ip_address': ip_address,
                'timestamp': datetime.utcnow().isoformat(),
                'details': details or {}
            }
            
            # 记录到缓存用于实时分析
            event_key = f"security_event:{event_type}:{ip_address or 'unknown'}"
            cache.append_list(event_key, event_data, timeout=3600)  # 1小时过期
            
            # 记录到数据库（异步）
            # 这里可以添加数据库记录逻辑
            
            logger.info(f"安全事件记录: {event_type} - {ip_address}")
            
        except Exception as e:
            logger.error(f"记录安全事件失败: {e}")
    
    @staticmethod
    def analyze_security_risks(ip_address: str) -> dict:
        """
        分析安全风险
        """
        try:
            risks = {
                'risk_level': 'low',
                'risk_factors': [],
                'recommendations': []
            }
            
            # 检查登录失败次数
            fail_count = cache.get(f"login_fail:{ip_address}", 0)
            if fail_count > 5:
                risks['risk_level'] = 'medium' if fail_count <= 10 else 'high'
                risks['risk_factors'].append(f"登录失败次数: {fail_count}")
                risks['recommendations'].append("建议限制该IP的登录尝试")
            
            # 检查注册频率
            register_count = cache.get(f"register_count:{ip_address}", 0)
            if register_count > 3:
                risks['risk_level'] = 'medium' if risks['risk_level'] == 'low' else risks['risk_level']
                risks['risk_factors'].append(f"注册次数: {register_count}")
                risks['recommendations'].append("建议审核该IP的注册请求")
            
            # 检查投票频率
            vote_count = cache.get(f"vote_attempts:{ip_address}", 0)
            settings = Settings.get_current()
            if vote_count > settings.max_votes_per_ip * 0.8:
                risks['risk_level'] = 'medium' if risks['risk_level'] == 'low' else risks['risk_level']
                risks['risk_factors'].append(f"投票次数: {vote_count}")
                risks['recommendations'].append("建议监控该IP的投票行为")
            
            return risks
            
        except Exception as e:
            logger.error(f"分析安全风险失败: {e}")
            return {
                'risk_level': 'unknown',
                'risk_factors': ['分析失败'],
                'recommendations': ['无法评估风险']
            }
    
    @staticmethod
    def auto_ban_ip(ip_address: str, reason: str, duration_hours: int = 24):
        """
        自动封禁IP
        """
        try:
            # 封禁IP
            ban_record = IpBanRecord(
                ip_address=ip_address,
                ban_reason=f"自动封禁: {reason}"
            )
            db.session.add(ban_record)
            db.session.commit()
            
            # 记录安全事件
            SecurityService.record_security_event(
                'auto_ban',
                ip_address=ip_address,
                details={'reason': reason, 'duration_hours': duration_hours}
            )
            
            logger.warning(f"自动封禁IP: {ip_address} - 原因: {reason}")
            
        except Exception as e:
            logger.error(f"自动封禁IP失败: {e}")
    
    @staticmethod
    def validate_input(data: str, input_type: str) -> Tuple[bool, str]:
        """
        输入验证
        
        Args:
            data: 要验证的数据
            input_type: 数据类型 (username, password, email, phone, etc.)
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        try:
            if input_type == 'username':
                # 用户名验证
                if not data or len(data) < 2:
                    return False, "用户名至少2个字符"
                if len(data) > 50:
                    return False, "用户名不能超过50个字符"
                if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', data):
                    return False, "用户名只能包含字母、数字、下划线和中文"
                    
            elif input_type == 'password':
                # 密码验证
                if not data or len(data) < 6:
                    return False, "密码至少6个字符"
                if len(data) > 128:
                    return False, "密码不能超过128个字符"
                # 检查密码复杂度
                if not re.search(r'[a-zA-Z]', data):
                    return False, "密码必须包含字母"
                if not re.search(r'\d', data):
                    return False, "密码必须包含数字"
                    
            elif input_type == 'school_id':
                # 学号验证
                if data and (len(data) < 4 or len(data) > 20):
                    return False, "学号长度应在4-20个字符之间"
                if data and not re.match(r'^[a-zA-Z0-9]+$', data):
                    return False, "学号只能包含字母和数字"
                    
            elif input_type == 'qq_number':
                # QQ号验证
                if not data or len(data) < 5 or len(data) > 15:
                    return False, "QQ号长度应在5-15个字符之间"
                if not re.match(r'^[1-9][0-9]{4,14}$', data):
                    return False, "请输入有效的QQ号"
                    
            elif input_type == 'class_name':
                # 班级名称验证
                if not data or len(data) < 2:
                    return False, "班级名称至少2个字符"
                if len(data) > 50:
                    return False, "班级名称不能超过50个字符"
                    
            elif input_type == 'photo_title':
                # 照片标题验证
                if data and len(data) > 100:
                    return False, "照片标题不能超过100个字符"
                if data and re.search(r'[<>"\']', data):
                    return False, "照片标题不能包含特殊字符"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"输入验证失败: {e}")
            return False, "输入验证错误"
    
    @staticmethod
    def sanitize_input(data: str) -> str:
        """
        输入清理
        """
        try:
            if not data:
                return ""
            
            # 移除HTML标签
            data = re.sub(r'<[^>]*>', '', data)
            
            # 移除危险字符
            data = re.sub(r'[<>"\']', '', data)
            
            # 限制长度
            return data[:500]  # 最大500字符
            
        except Exception as e:
            logger.error(f"输入清理失败: {e}")
            return ""
    
    @staticmethod
    def check_brute_force(ip_address: str, event_type: str) -> bool:
        """
        检查暴力破解攻击
        """
        try:
            key = f"brute_force_check:{event_type}:{ip_address}"
            attempts = cache.get(key, 0)
            
            # 如果尝试次数超过阈值，认为是暴力破解
            if attempts > 10:
                # 自动封禁IP
                SecurityService.auto_ban_ip(ip_address, f"暴力破解检测: {event_type}")
                return True
            
            # 增加尝试次数
            cache.increment(key, timeout=3600)  # 1小时过期
            return False
            
        except Exception as e:
            logger.error(f"暴力破解检查失败: {e}")
            return False
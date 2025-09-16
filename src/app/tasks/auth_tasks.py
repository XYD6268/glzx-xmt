"""
认证相关异步任务
"""
from app.tasks.celery_app import celery
from app.models.user import LoginRecord, User
from app.models.base import db
import logging

logger = logging.getLogger(__name__)


@celery.task(name='tasks.auth_tasks.record_login')
def record_login(user_id: str, ip_address: str, user_agent: str = None):
    """
    记录用户登录 - 异步任务
    """
    try:
        logger.info(f"记录用户登录: user_id={user_id}, ip={ip_address}")
        
        # 创建登录记录
        login_record = LoginRecord(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(login_record)
        db.session.commit()
        
        logger.info(f"用户登录记录完成: user_id={user_id}")
        return True
        
    except Exception as e:
        logger.error(f"记录用户登录失败: {e}")
        db.session.rollback()
        return False


@celery.task(name='tasks.auth_tasks.cleanup_old_login_records')
def cleanup_old_login_records(days: int = 90):
    """
    清理旧的登录记录
    """
    try:
        from datetime import datetime, timedelta
        
        logger.info(f"开始清理 {days} 天前的登录记录")
        
        # 计算时间阈值
        time_threshold = datetime.utcnow() - timedelta(days=days)
        
        # 删除旧记录
        deleted_count = LoginRecord.query.filter(
            LoginRecord.created_at < time_threshold
        ).delete()
        
        db.session.commit()
        
        logger.info(f"清理旧登录记录完成，删除了 {deleted_count} 条记录")
        return deleted_count
        
    except Exception as e:
        logger.error(f"清理旧登录记录失败: {e}")
        db.session.rollback()
        return 0


@celery.task(name='tasks.auth_tasks.send_welcome_email')
def send_welcome_email(user_id: str):
    """
    发送欢迎邮件 - 异步任务
    """
    try:
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"用户不存在: {user_id}")
            return False
        
        # 这里可以实现实际的邮件发送逻辑
        # 例如使用SMTP或其他邮件服务
        
        logger.info(f"欢迎邮件发送完成: {user.real_name} ({user.email})")
        return True
        
    except Exception as e:
        logger.error(f"发送欢迎邮件失败: {e}")
        return False
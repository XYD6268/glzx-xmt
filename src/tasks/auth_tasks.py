"""
认证相关异步任务
"""
from tasks.celery_app import celery
from models.base import db
from models.user import LoginRecord
import logging

logger = logging.getLogger(__name__)


@celery.task(name='tasks.auth_tasks.record_login')
def record_login(user_id, ip_address, user_agent=None):
    """记录用户登录"""
    try:
        login_record = LoginRecord(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(login_record)
        db.session.commit()
        
        logger.info(f"登录记录已保存: {user_id} from {ip_address}")
        return True
        
    except Exception as e:
        logger.error(f"保存登录记录失败: {e}")
        db.session.rollback()
        return False


@celery.task(name='tasks.auth_tasks.cleanup_old_login_records')
def cleanup_old_login_records(days=30):
    """清理旧的登录记录"""
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted_count = LoginRecord.query.filter(
            LoginRecord.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        
        logger.info(f"清理登录记录完成，删除 {deleted_count} 条记录")
        return deleted_count
        
    except Exception as e:
        logger.error(f"清理登录记录失败: {e}")
        db.session.rollback()
        return 0
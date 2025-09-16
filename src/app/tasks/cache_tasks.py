"""
缓存维护任务
"""
from app.tasks.celery_app import celery
from app.services.cache_service import cache
import logging

logger = logging.getLogger(__name__)


@celery.task(name='tasks.cache_tasks.cleanup_expired_cache')
def cleanup_expired_cache():
    """
    清理过期缓存
    """
    try:
        logger.info("开始清理过期缓存")
        
        # 对于Redis缓存，过期键会自动清理
        # 这里可以添加其他缓存清理逻辑
        
        logger.info("过期缓存清理完成")
        return True
        
    except Exception as e:
        logger.error(f"清理过期缓存失败: {e}")
        return False


@celery.task(name='tasks.cache_tasks.warm_up_cache')
def warm_up_cache():
    """
    预热缓存
    """
    try:
        logger.info("开始缓存预热")
        
        # 预热常用数据
        # 这里可以调用服务层的预热函数
        
        logger.info("缓存预热完成")
        return True
        
    except Exception as e:
        logger.error(f"缓存预热失败: {e}")
        return False


@celery.task(name='tasks.cache_tasks.clear_cache_pattern')
def clear_cache_pattern(pattern: str):
    """
    清理匹配模式的缓存
    """
    try:
        logger.info(f"开始清理匹配模式的缓存: {pattern}")
        
        # 清理匹配模式的缓存
        cleared_count = cache.clear_pattern(pattern)
        
        logger.info(f"清理匹配模式的缓存完成，清理了 {cleared_count} 个键")
        return cleared_count
        
    except Exception as e:
        logger.error(f"清理匹配模式的缓存失败: {e}")
        return 0
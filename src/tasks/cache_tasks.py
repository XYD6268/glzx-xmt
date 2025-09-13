"""
缓存维护异步任务
"""
from tasks.celery_app import celery
from services.cache_service import cache
import logging

logger = logging.getLogger(__name__)


@celery.task(name='tasks.cache_tasks.warm_cache')
def warm_cache():
    """预热缓存"""
    try:
        from services.cache_service import warm_up_cache
        warm_up_cache()
        
        logger.info("缓存预热完成")
        return True
        
    except Exception as e:
        logger.error(f"缓存预热失败: {e}")
        return False


@celery.task(name='tasks.cache_tasks.clear_expired_cache')
def clear_expired_cache():
    """清理过期缓存"""
    try:
        # Redis会自动清理过期键，这里主要是统计
        if hasattr(cache, 'redis_client') and cache.redis_client:
            info = cache.redis_client.info('keyspace')
            logger.info(f"缓存信息: {info}")
        
        return True
        
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        return False


@celery.task(name='tasks.cache_tasks.cache_stats')
def cache_stats():
    """收集缓存统计信息"""
    try:
        stats = {}
        
        if hasattr(cache, 'redis_client') and cache.redis_client:
            redis_info = cache.redis_client.info()
            stats['redis'] = {
                'used_memory': redis_info.get('used_memory_human'),
                'connected_clients': redis_info.get('connected_clients'),
                'total_commands_processed': redis_info.get('total_commands_processed'),
                'keyspace_hits': redis_info.get('keyspace_hits'),
                'keyspace_misses': redis_info.get('keyspace_misses')
            }
            
            # 计算命中率
            hits = redis_info.get('keyspace_hits', 0)
            misses = redis_info.get('keyspace_misses', 0)
            total = hits + misses
            
            if total > 0:
                stats['redis']['hit_rate'] = round((hits / total) * 100, 2)
            else:
                stats['redis']['hit_rate'] = 0
        
        logger.info(f"缓存统计: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"收集缓存统计失败: {e}")
        return {}
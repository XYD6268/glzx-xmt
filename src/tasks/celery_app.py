"""
Celery配置和初始化
"""
from celery import Celery
from config.base import get_config
import os


def make_celery(app=None):
    """创建Celery实例"""
    config = get_config()
    
    celery = Celery(
        'glzx_xmt',
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        include=[
            'tasks.image_tasks',
            'tasks.cache_tasks', 
            'tasks.auth_tasks'
        ]
    )
    
    # Celery配置
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        
        # 任务路由
        task_routes={
            'tasks.image_tasks.*': {'queue': 'image_processing'},
            'tasks.cache_tasks.*': {'queue': 'cache_maintenance'},
            'tasks.auth_tasks.*': {'queue': 'auth_processing'},
        },
        
        # 性能优化
        worker_prefetch_multiplier=4,
        task_compression='gzip',
        result_compression='gzip',
        
        # 任务超时
        task_soft_time_limit=300,  # 5分钟软超时
        task_time_limit=600,       # 10分钟硬超时
        
        # 重试配置
        task_acks_late=True,
        worker_disable_rate_limits=True,
        
        # 结果过期时间
        result_expires=3600,  # 1小时
    )
    
    if app is not None:
        # Flask应用上下文
        class ContextTask(celery.Task):
            """带Flask应用上下文的任务基类"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery


# 创建全局Celery实例
celery = make_celery()
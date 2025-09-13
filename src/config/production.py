"""
生产环境专用配置 - PostgreSQL高性能优化
"""
from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """生产环境PostgreSQL高性能配置"""
    DEBUG = False
    TESTING = False
    
    # PostgreSQL生产环境连接池优化
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 100,  # 大连接池
        'max_overflow': 50,  # 允许大量溢出连接
        'pool_timeout': 90,  # 更长等待时间
        'pool_recycle': 1800,  # 30分钟回收连接
        'pool_pre_ping': True,
        'echo': False,
        # PostgreSQL特定优化
        'connect_args': {
            'server_settings': {
                'application_name': 'glzx_xmt_production',
                'tcp_keepalives_idle': '600',
                'tcp_keepalives_interval': '30',
                'tcp_keepalives_count': '3',
            }
        }
    }
    
    # Redis集群配置（如果使用）
    REDIS_CLUSTER_NODES = [
        {"host": "redis-node-1", "port": 6379},
        {"host": "redis-node-2", "port": 6379}, 
        {"host": "redis-node-3", "port": 6379}
    ]
    
    # 缓存优化配置
    CACHE_DEFAULT_TIMEOUT = 1800  # 30分钟缓存
    CACHE_THRESHOLD = 10000  # 缓存阈值
    
    # Celery生产环境优化
    CELERY_TASK_ROUTES = {
        'tasks.image_tasks.*': {'queue': 'image_processing'},
        'tasks.cache_tasks.*': {'queue': 'cache_maintenance'},
    }
    CELERY_WORKER_PREFETCH_MULTIPLIER = 4
    CELERY_TASK_COMPRESSION = 'gzip'
    
    # 图片处理优化
    IMAGE_QUALITY = 90  # 生产环境高质量
    IMAGE_PROCESSING_TIMEOUT = 30
    PILLOW_SIMD_ENABLED = True
    
    # 监控和日志配置
    LOG_LEVEL = 'INFO'
    SENTRY_DSN = None  # 配置Sentry用于错误监控
    
    # 安全强化
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_DOMAIN = None  # 设置为实际域名
    PREFERRED_URL_SCHEME = 'https'
    
    # 性能监控
    PERFORMANCE_MONITORING = True
    SLOW_QUERY_THRESHOLD = 1.0  # 慢查询阈值（秒）
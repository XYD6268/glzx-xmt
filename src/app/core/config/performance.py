"""
性能优化配置
"""
import os


class PerformanceConfig:
    """性能优化配置类"""
    
    # 数据库连接池优化
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 50,          # 连接池大小
        'pool_timeout': 60,       # 连接超时时间（秒）
        'pool_recycle': 1800,     # 连接回收时间（秒）
        'max_overflow': 20,       # 最大溢出连接数
        'pool_pre_ping': True,    # 连接前检查
        'echo': False             # 是否显示SQL语句
    }
    
    # 缓存配置
    CACHE_DEFAULT_TIMEOUT = 600      # 默认缓存超时时间（秒）
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Celery配置
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Celery性能优化配置
    CELERY_CONFIG = {
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'Asia/Shanghai',
        'enable_utc': True,
        
        # 任务路由
        'task_routes': {
            'tasks.image_tasks.*': {'queue': 'image_processing'},
            'tasks.cache_tasks.*': {'queue': 'cache_maintenance'},
            'tasks.auth_tasks.*': {'queue': 'auth_processing'},
            'tasks.security_tasks.*': {'queue': 'security_monitoring'},
        },
        
        # 性能优化
        'worker_prefetch_multiplier': 4,    # 预取任务数
        'task_compression': 'gzip',         # 任务压缩
        'result_compression': 'gzip',       # 结果压缩
        
        # 任务超时
        'task_soft_time_limit': 300,        # 软超时（秒）
        'task_time_limit': 600,             # 硬超时（秒）
        
        # 重试配置
        'task_acks_late': True,             # 延迟确认
        'worker_disable_rate_limits': True, # 禁用速率限制
        
        # 结果过期时间
        'result_expires': 3600,             # 结果过期时间（秒）
    }
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大上传文件大小（16MB）
    
    # JSON序列化优化
    JSON_ENCODER = 'orjson'  # 使用orjson加速JSON序列化
    
    # 压缩配置
    COMPRESS_MIMETYPES = [
        'text/html', 
        'text/css', 
        'text/xml', 
        'application/json',
        'application/javascript'
    ]
    
    # 并发配置
    CONCURRENT_REQUESTS = 100    # 最大并发请求数
    REQUEST_TIMEOUT = 30         # 请求超时时间（秒）
    
    # 缓存策略
    CACHE_STRATEGIES = {
        'user': {
            'timeout': 300,        # 5分钟
            'key_prefix': 'user'
        },
        'photo': {
            'timeout': 300,        # 5分钟
            'key_prefix': 'photo'
        },
        'settings': {
            'timeout': 1800,       # 30分钟
            'key_prefix': 'settings'
        },
        'stats': {
            'timeout': 600,        # 10分钟
            'key_prefix': 'stats'
        }
    }
    
    # 图片处理优化
    IMAGE_PROCESSING = {
        'max_workers': 4,          # 最大处理工作进程数
        'quality': 100,            # 图片质量
        'thumbnail_size': (2560, 1440),  # 缩略图尺寸
        'max_size': (3840, 2160),        # 最大图片尺寸
        'optimize': True,          # 是否优化图片
        'progressive': True        # 是否使用渐进式JPEG
    }
    
    # 安全配置
    SECURITY_CONFIG = {
        'rate_limit': {
            'login': {'max_requests': 20, 'window': 300},      # 登录频率限制
            'register': {'max_requests': 10, 'window': 600},   # 注册频率限制
            'vote': {'max_requests': 100, 'window': 3600},     # 投票频率限制
            'change_password': {'max_requests': 5, 'window': 300}  # 修改密码频率限制
        },
        'brute_force_protection': True,    # 是否启用暴力破解保护
        'auto_ban_threshold': 10,          # 自动封禁阈值
        'ban_duration': 86400              # 封禁持续时间（秒，24小时）
    }
    
    # 监控配置
    MONITORING_CONFIG = {
        'enable_profiling': False,         # 是否启用性能分析
        'profile_sample_rate': 0.1,        # 性能分析采样率
        'log_slow_queries': True,          # 是否记录慢查询
        'slow_query_threshold': 1.0,       # 慢查询阈值（秒）
        'enable_metrics_collection': True  # 是否启用指标收集
    }


# 高性能生产环境配置
class HighPerformanceConfig(PerformanceConfig):
    """高性能生产环境配置"""
    
    # 增加数据库连接池
    SQLALCHEMY_ENGINE_OPTIONS = {
        **PerformanceConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 100,          # 增加连接池大小
        'max_overflow': 50,        # 增加最大溢出连接数
        'pool_timeout': 120,       # 增加连接超时时间
        'pool_recycle': 3600,      # 增加连接回收时间
    }
    
    # 增加Celery工作进程
    CELERY_CONFIG = {
        **PerformanceConfig.CELERY_CONFIG,
        'worker_prefetch_multiplier': 8,   # 增加预取任务数
        'task_soft_time_limit': 600,       # 增加软超时
        'task_time_limit': 1200,           # 增加硬超时
    }
    
    # 增加并发处理能力
    CONCURRENT_REQUESTS = 500              # 增加最大并发请求数
    
    # 延长缓存时间
    CACHE_DEFAULT_TIMEOUT = 1800           # 延长默认缓存超时时间（30分钟）
    
    # 图片处理优化
    IMAGE_PROCESSING = {
        **PerformanceConfig.IMAGE_PROCESSING,
        'max_workers': 8,                  # 增加最大处理工作进程数
    }


# 开发环境性能配置
class DevelopmentPerformanceConfig(PerformanceConfig):
    """开发环境性能配置"""
    
    # 减少资源使用
    SQLALCHEMY_ENGINE_OPTIONS = {
        **PerformanceConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 10,           # 减少连接池大小
        'max_overflow': 5,         # 减少最大溢出连接数
    }
    
    # 简化Celery配置
    CELERY_CONFIG = {
        **PerformanceConfig.CELERY_CONFIG,
        'worker_prefetch_multiplier': 1,   # 减少预取任务数
    }
    
    # 减少并发处理能力
    CONCURRENT_REQUESTS = 20               # 减少最大并发请求数
    
    # 缩短缓存时间
    CACHE_DEFAULT_TIMEOUT = 300            # 缩短默认缓存超时时间（5分钟）
    
    # 启用调试功能
    MONITORING_CONFIG = {
        **PerformanceConfig.MONITORING_CONFIG,
        'enable_profiling': True,          # 启用性能分析
        'log_slow_queries': True,          # 记录慢查询
    }


# 配置映射
performance_configs = {
    'default': PerformanceConfig,
    'production': HighPerformanceConfig,
    'development': DevelopmentPerformanceConfig,
    'testing': DevelopmentPerformanceConfig
}


def get_performance_config(config_name: str = None):
    """
    获取性能配置
    
    Args:
        config_name: 配置名称
        
    Returns:
        PerformanceConfig: 性能配置类
    """
    if config_name is None:
        config_name = os.environ.get('PERFORMANCE_ENV', 'default')
    return performance_configs.get(config_name, PerformanceConfig)
"""
生产环境专用配置 - SQLite简化版
"""
from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """生产环境SQLite配置"""
    DEBUG = False
    TESTING = False
    
    # SQLite生产环境配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'echo': False,
    }
    
    # 内存缓存配置
    CACHE_DEFAULT_TIMEOUT = 1800  # 30分钟缓存
    CACHE_THRESHOLD = 1000  # 缓存阈值
    
    # 图片处理配置
    IMAGE_QUALITY = 90  # 生产环境高质量
    IMAGE_PROCESSING_TIMEOUT = 30
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    
    # 安全强化
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_DOMAIN = None  # 设置为实际域名
    PREFERRED_URL_SCHEME = 'https'
    
    # 性能监控
    PERFORMANCE_MONITORING = True
    SLOW_QUERY_THRESHOLD = 1.0  # 慢查询阈值（秒）
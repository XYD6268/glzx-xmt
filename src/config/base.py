"""
基础配置类 - PostgreSQL高性能优化
"""
import os
from typing import Optional


def _getenv_bool(name: str, default: bool = False) -> bool:
    """环境变量布尔值转换"""
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    """基础配置"""
    
    # Flask核心配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # PostgreSQL数据库配置
    POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password') 
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
    POSTGRES_DB = os.environ.get('POSTGRES_DB', 'glzx_xmt')
    
    # 构建PostgreSQL连接URL
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # SQLAlchemy优化配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'echo': _getenv_bool('SQL_ECHO', False)
    }
    
    # Redis缓存配置
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'RedisCache' if REDIS_URL else 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_REDIS_URL = REDIS_URL
    
    # Celery异步任务配置
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '../photo/uploads')
    THUMB_FOLDER = os.environ.get('THUMB_FOLDER', '../photo/thumbs') 
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # 性能优化配置
    JSON_ENCODER = 'orjson'  # 使用orjson加速JSON序列化
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml', 'application/json',
        'application/javascript'
    ]
    
    # 安全配置
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = _getenv_bool('SESSION_COOKIE_SECURE', False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 图片处理配置
    IMAGE_QUALITY = 100
    THUMBNAIL_SIZE = (2560, 1440)
    WATERMARK_ENABLED = _getenv_bool('WATERMARK_ENABLED', True)


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'echo': True,  # 开发环境显示SQL
        'pool_size': 5  # 开发环境减少连接池大小
    }


class ProductionConfig(BaseConfig):
    """生产环境PostgreSQL高性能配置"""
    DEBUG = False
    
    # 生产环境数据库连接池优化
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 50,  # 增大连接池
        'max_overflow': 20,  # 允许溢出连接
        'pool_timeout': 60,
        'pool_recycle': 1800,  # 30分钟回收连接
        'pool_pre_ping': True,
        'echo': False
    }
    
    # 生产环境缓存配置
    CACHE_DEFAULT_TIMEOUT = 600  # 增长缓存时间
    
    # 安全强化
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_TIME_LIMIT = 3600


class TestingConfig(BaseConfig):
    """测试环境配置"""
    TESTING = True
    POSTGRES_DB = os.environ.get('POSTGRES_TEST_DB', 'glzx_xmt_test')
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+asyncpg://{BaseConfig.POSTGRES_USER}:{BaseConfig.POSTGRES_PASSWORD}@"
        f"{BaseConfig.POSTGRES_HOST}:{BaseConfig.POSTGRES_PORT}/{POSTGRES_DB}"
    )
    WTF_CSRF_ENABLED = False


# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> BaseConfig:
    """获取配置类"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    return config.get(config_name, DevelopmentConfig)
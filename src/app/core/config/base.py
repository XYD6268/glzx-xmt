"""
基础配置类 - SQLite简化版
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
    
    # SQLite数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///../instance/photos.db')
    
    # SQLAlchemy优化配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'echo': _getenv_bool('SQL_ECHO', False)
    }
    
    # 内存缓存配置
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '../photo/uploads')
    THUMB_FOLDER = os.environ.get('THUMB_FOLDER', '../photo/thumbs') 
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # 性能优化配置
    JSON_ENCODER = 'orjson'  # 使用orjson加速JSON序列化
    
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
    }


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    DEBUG = False
    
    # 安全强化
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_TIME_LIMIT = 3600


class TestingConfig(BaseConfig):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///../instance/test_photos.db')
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
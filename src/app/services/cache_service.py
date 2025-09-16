"""
简单缓存服务 - SQLite简化版
"""
from flask_caching import Cache
import hashlib
from functools import wraps
from typing import Any, Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class SmartCache:
    """简单缓存服务"""
    
    def __init__(self, app=None):
        self.cache = Cache()
        self._app = None
        
    def init_app(self, app):
        """初始化缓存系统"""
        self._app = app
        
        # 使用内存缓存
        self.cache.init_app(app, config={
            'CACHE_TYPE': 'SimpleCache',
            'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300),
            'CACHE_THRESHOLD': 1000
        })
        logger.info("使用内存缓存")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        try:
            return self.cache.get(key, default)
        except Exception as e:
            logger.warning(f"缓存获取失败 {key}: {e}")
        return default
    
    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """设置缓存值"""
        try:
            return self.cache.set(key, value, timeout=timeout)
        except Exception as e:
            logger.warning(f"缓存设置失败 {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            return self.cache.delete(key)
        except Exception as e:
            logger.warning(f"缓存删除失败 {key}: {e}")
            return False
    
    def clear(self) -> bool:
        """清除所有缓存"""
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.warning(f"清除缓存失败: {e}")
            return False


# 全局缓存实例
cache = SmartCache()


def make_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    # 创建一个唯一的缓存键
    key_parts = []
    
    # 添加位置参数
    for arg in args:
        if hasattr(arg, 'id'):
            key_parts.append(f"{type(arg).__name__}:{arg.id}")
        else:
            key_parts.append(str(arg))
    
    # 添加关键字参数
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}:{value}")
    
    key_string = ":".join(key_parts)
    
    # 如果键太长，使用哈希
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"hash:{key_hash}"
    
    return key_string


def cached(timeout: int = 300, key_prefix: Optional[str] = None, 
          unless: Optional[callable] = None):
    """缓存装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 检查是否跳过缓存
            if unless and unless():
                return f(*args, **kwargs)
            
            # 生成缓存键
            if key_prefix:
                cache_key = f"{key_prefix}:{make_cache_key(*args, **kwargs)}"
            else:
                cache_key = f"{f.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # 检查缓存
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数并缓存结果
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        
        # 添加清除缓存的方法
        def clear_cache(*args, **kwargs):
            if key_prefix:
                cache_key = f"{key_prefix}:{make_cache_key(*args, **kwargs)}"
            else:
                cache_key = f"{f.__name__}:{make_cache_key(*args, **kwargs)}"
            return cache.delete(cache_key)
        
        wrapper.clear_cache = clear_cache
        return wrapper
    return decorator


# 缓存策略
class CacheStrategies:
    """缓存策略集合"""
    
    # 用户相关缓存
    USER_CACHE_TIMEOUT = 600  # 10分钟
    USER_LIST_TIMEOUT = 300   # 5分钟
    
    # 照片相关缓存
    PHOTO_CACHE_TIMEOUT = 300     # 5分钟
    PHOTO_LIST_TIMEOUT = 180      # 3分钟
    RANKING_CACHE_TIMEOUT = 120   # 2分钟
    
    # 设置相关缓存
    SETTINGS_CACHE_TIMEOUT = 1800  # 30分钟


# 应用级缓存函数
@cached(timeout=CacheStrategies.PHOTO_LIST_TIMEOUT, key_prefix='photos')
def get_approved_photos_cached(limit: int = 50, offset: int = 0):
    """缓存已审核照片列表"""
    from app.models.photo import Photo
    return Photo.get_approved(limit=limit, offset=offset)


@cached(timeout=CacheStrategies.RANKING_CACHE_TIMEOUT, key_prefix='ranking')
def get_photo_rankings_cached(limit: int = 10):
    """缓存照片排行榜"""
    from app.models.photo import Photo
    return Photo.get_top_voted(limit=limit)


@cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user')
def get_user_cached(user_id):
    """缓存用户信息"""
    from app.models.user import User
    return User.get_by_id(user_id)


@cached(timeout=CacheStrategies.SETTINGS_CACHE_TIMEOUT, key_prefix='settings')
def get_settings_cached():
    """缓存系统设置"""
    from app.models.settings import Settings
    return Settings.get_current()


def invalidate_user_cache(user_id):
    """清除用户相关缓存"""
    # 简化实现，清除所有缓存
    cache.clear()


def invalidate_photo_cache(photo_id=None):
    """清除照片相关缓存"""
    # 简化实现，清除所有缓存
    cache.clear()


def invalidate_settings_cache():
    """清除设置缓存"""
    # 简化实现，清除所有缓存
    cache.clear()

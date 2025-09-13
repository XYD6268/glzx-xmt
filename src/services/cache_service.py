"""
智能缓存服务 - 平衡性能和复杂度
"""
from flask_caching import Cache
import redis
import orjson
import hashlib
from functools import wraps
from typing import Any, Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class SmartCache:
    """智能缓存服务 - 高性能Redis集成"""
    
    def __init__(self, app=None):
        self.cache = Cache()
        self.redis_client = None
        self._app = None
        
    def init_app(self, app):
        """初始化缓存系统"""
        self._app = app
        
        # 根据环境选择缓存后端
        if app.config.get('REDIS_URL'):
            # 生产环境使用Redis
            self.cache.init_app(app, config={
                'CACHE_TYPE': 'RedisCache',
                'CACHE_REDIS_URL': app.config['REDIS_URL'],
                'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300),
                'CACHE_KEY_PREFIX': 'glzx_xmt:',
                'CACHE_OPTIONS': {
                    'socket_connect_timeout': 5,
                    'socket_timeout': 5,
                    'connection_pool_kwargs': {
                        'max_connections': 50,
                        'retry_on_timeout': True
                    }
                }
            })
            try:
                self.redis_client = redis.from_url(
                    app.config['REDIS_URL'],
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    max_connections=50
                )
                # 测试连接
                self.redis_client.ping()
                logger.info("Redis缓存连接成功")
            except Exception as e:
                logger.warning(f"Redis连接失败，降级到内存缓存: {e}")
                self._init_simple_cache(app)
        else:
            # 开发环境使用内存缓存
            self._init_simple_cache(app)
    
    def _init_simple_cache(self, app):
        """初始化简单内存缓存"""
        self.cache.init_app(app, config={
            'CACHE_TYPE': 'SimpleCache',
            'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300),
            'CACHE_THRESHOLD': 1000
        })
        self.redis_client = None
        logger.info("使用内存缓存")
    
    def _serialize_value(self, value: Any) -> bytes:
        """高性能序列化"""
        try:
            return orjson.dumps(value, default=str)
        except Exception as e:
            logger.warning(f"序列化失败: {e}, 使用备用方案")
            import pickle
            return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """高性能反序列化"""
        try:
            return orjson.loads(data)
        except Exception:
            try:
                import pickle
                return pickle.loads(data)
            except Exception as e:
                logger.error(f"反序列化失败: {e}")
                return None
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        try:
            if self.redis_client:
                data = self.redis_client.get(f"glzx_xmt:{key}")
                if data:
                    return self._deserialize_value(data)
            else:
                return self.cache.get(key, default)
        except Exception as e:
            logger.warning(f"缓存获取失败 {key}: {e}")
        return default
    
    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """设置缓存值"""
        try:
            if self.redis_client:
                serialized = self._serialize_value(value)
                return self.redis_client.setex(f"glzx_xmt:{key}", timeout, serialized)
            else:
                return self.cache.set(key, value, timeout=timeout)
        except Exception as e:
            logger.warning(f"缓存设置失败 {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(f"glzx_xmt:{key}"))
            else:
                return self.cache.delete(key)
        except Exception as e:
            logger.warning(f"缓存删除失败 {key}: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """批量清除缓存"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(f"glzx_xmt:{pattern}")
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # SimpleCache不支持模式匹配，清除所有
                self.cache.clear()
                return 1
        except Exception as e:
            logger.warning(f"批量清除缓存失败 {pattern}: {e}")
            return 0
    
    def increment(self, key: str, delta: int = 1, timeout: int = 300) -> int:
        """原子递增"""
        try:
            if self.redis_client:
                pipeline = self.redis_client.pipeline()
                pipeline.incr(f"glzx_xmt:{key}", delta)
                pipeline.expire(f"glzx_xmt:{key}", timeout)
                result = pipeline.execute()
                return result[0]
            else:
                # 简单缓存的原子递增实现
                current = self.get(key, 0)
                new_value = current + delta
                self.set(key, new_value, timeout)
                return new_value
        except Exception as e:
            logger.warning(f"缓存递增失败 {key}: {e}")
            return 0
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        result = {}
        try:
            if self.redis_client:
                prefixed_keys = [f"glzx_xmt:{key}" for key in keys]
                values = self.redis_client.mget(prefixed_keys)
                for i, value in enumerate(values):
                    if value:
                        result[keys[i]] = self._deserialize_value(value)
            else:
                for key in keys:
                    value = self.cache.get(key)
                    if value is not None:
                        result[key] = value
        except Exception as e:
            logger.warning(f"批量获取缓存失败: {e}")
        return result
    
    def set_many(self, mapping: Dict[str, Any], timeout: int = 300) -> bool:
        """批量设置缓存"""
        try:
            if self.redis_client:
                pipeline = self.redis_client.pipeline()
                for key, value in mapping.items():
                    serialized = self._serialize_value(value)
                    pipeline.setex(f"glzx_xmt:{key}", timeout, serialized)
                pipeline.execute()
                return True
            else:
                for key, value in mapping.items():
                    self.cache.set(key, value, timeout=timeout)
                return True
        except Exception as e:
            logger.warning(f"批量设置缓存失败: {e}")
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
    """智能缓存装饰器"""
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


def cache_response(timeout: int = 300, key_prefix: str = "response"):
    """HTTP响应缓存装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request, make_response
            
            # 生成基于请求的缓存键
            cache_key = f"{key_prefix}:{request.endpoint}:{make_cache_key(*args, **kwargs)}"
            
            # 检查缓存
            cached_response = cache.get(cache_key)
            if cached_response:
                return make_response(cached_response)
            
            # 执行函数并缓存响应
            response = f(*args, **kwargs)
            if hasattr(response, 'get_data'):
                cache.set(cache_key, response.get_data(as_text=True), timeout)
            
            return response
        return wrapper
    return decorator


# 预定义的缓存策略
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
    
    # 统计数据缓存
    STATS_CACHE_TIMEOUT = 600     # 10分钟
    
    # 搜索结果缓存
    SEARCH_CACHE_TIMEOUT = 300    # 5分钟


# 应用级缓存函数
@cached(timeout=CacheStrategies.PHOTO_LIST_TIMEOUT, key_prefix='photos')
def get_approved_photos_cached(limit: int = 50, offset: int = 0):
    """缓存已审核照片列表"""
    from models.photo import Photo
    return Photo.get_approved(limit=limit, offset=offset)


@cached(timeout=CacheStrategies.RANKING_CACHE_TIMEOUT, key_prefix='ranking')
def get_photo_rankings_cached(limit: int = 10):
    """缓存照片排行榜"""
    from models.photo import Photo
    return Photo.get_top_voted(limit=limit)


@cached(timeout=CacheStrategies.USER_CACHE_TIMEOUT, key_prefix='user')
def get_user_cached(user_id):
    """缓存用户信息"""
    from models.user import User
    return User.get_by_id(user_id)


@cached(timeout=CacheStrategies.SETTINGS_CACHE_TIMEOUT, key_prefix='settings')
def get_settings_cached():
    """缓存系统设置"""
    from models.settings import Settings
    return Settings.get_current()


@cached(timeout=CacheStrategies.STATS_CACHE_TIMEOUT, key_prefix='stats')
def get_photo_statistics_cached():
    """缓存照片统计信息"""
    from models.photo import Photo
    return Photo.get_statistics()


def invalidate_user_cache(user_id):
    """清除用户相关缓存"""
    cache.clear_pattern(f"user:*{user_id}*")
    cache.clear_pattern("users:*")


def invalidate_photo_cache(photo_id=None):
    """清除照片相关缓存"""
    cache.clear_pattern("photos:*")
    cache.clear_pattern("ranking:*")
    cache.clear_pattern("stats:*")
    if photo_id:
        cache.clear_pattern(f"photo:*{photo_id}*")


def invalidate_settings_cache():
    """清除设置缓存"""
    cache.clear_pattern("settings:*")


def warm_up_cache():
    """预热缓存"""
    try:
        # 预热常用数据
        get_settings_cached()
        get_approved_photos_cached()
        get_photo_rankings_cached()
        get_photo_statistics_cached()
        logger.info("缓存预热完成")
    except Exception as e:
        logger.warning(f"缓存预热失败: {e}")
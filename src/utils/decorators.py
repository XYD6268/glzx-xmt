"""
装饰器工具 - 高性能版
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from services.cache_service import cache
from models.user import User
import time
import logging

logger = logging.getLogger(__name__)


def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        # 检查用户状态（缓存优化）
        user = get_current_user()
        if not user or not user.is_active:
            session.clear()
            flash('账户已被禁用，请联系管理员', 'error')
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user or not user.is_active:
            session.clear()
            flash('账户已被禁用', 'error')
            return redirect(url_for('auth.login'))
        elif not user.is_admin():
            flash('需要管理员权限', 'error')
            return redirect(url_for('photos.index'))
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests: int = 10, window: int = 60):
    """频率限制装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            key = f"rate_limit:{f.__name__}:{ip}"
            
            current_requests = cache.get(key, 0)
            if current_requests >= max_requests:
                abort(429)  # Too Many Requests
            
            cache.increment(key, timeout=window)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user():
    """获取当前用户（缓存版）"""
    if 'user_id' not in session:
        return None
    
    user_id = session['user_id']
    cache_key = f"current_user:{user_id}"
    
    user = cache.get(cache_key)
    if user is None:
        user = User.get_by_id(user_id)
        if user:
            cache.set(cache_key, user, timeout=300)  # 5分钟缓存
    
    return user
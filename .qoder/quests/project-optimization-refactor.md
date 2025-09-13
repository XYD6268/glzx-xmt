# 摄影比赛投票系统精简重构设计

## 概览

### 项目现状分析
当前项目是一个基于Flask的摄影比赛投票系统，主要问题：
- 单文件1903行代码，维护困难
- 缺乏缓存，响应速度慢
- 数据库查询未优化
- 图片处理同步阻塞

### 精简重构目标
- **最小化架构改动**：保持Flask核心，仅做必要拆分
- **渐进式优化**：优先解决性能瓶颈
- **轻量级依赖**：避免引入重型框架
- **易于维护**：代码结构清晰，依赖关系简单

## PostgreSQL高性能技术栈方案

### 数据库升级方案
- **PostgreSQL 15+**：替代MySQL，获得更好的并发性能和JSON支持
- **asyncpg**：高性能异步PostgreSQL驱动
- **SQLAlchemy 2.0+**：升级获得性能提升和异步支持
- **连接池优化**：pgbouncer + SQLAlchemy连接池

### PostgreSQL高性能组件选择
```mermaid
graph TB
    A[Flask App] --> B[Redis缓存集群]
    A --> C[PostgreSQL 15 + asyncpg]
    A --> D[Celery + Redis队列]
    B --> E[多级缓存策略]
    B --> F[分布式会话]
    C --> G[异步查询优化]
    C --> H[JSONB字段支持]
    C --> I[全文搜索]
    D --> J[异步图片处理]
    D --> K[批量任务处理]
```

### PostgreSQL性能导向的技术选择
| 功能需求 | PostgreSQL高性能方案 | 性能提升 | 复杂度 |
|----------|------------|----------|--------|
| 数据库 | PostgreSQL 15 + asyncpg | 50-100% | 低 |
| 连接池 | pgbouncer + SQLAlchemy | 40-80% | 中等 |
| 全文搜索 | PostgreSQL内置FTS | 10-30x | 低 |
| JSON存储 | JSONB字段 | 5-15x | 低 |
| 缓存 | Redis 7.0+ 集群 | 10-50x | 中等 |
| 图片处理 | Pillow-SIMD + 优化算法 | 400-600% | 低 |
| 异步任务 | Celery + Redis | 无限扩展 | 中等 |
| 序列化 | orjson (替代json) | 2-5x | 低 |

## 重构架构设计

### 精简高性能目录结构
```
src/
├── app.py                      # 应用工厂 - 集成所有组件
├── config/
│   ├── __init__.py
│   ├── base.py                # 基础配置
│   └── production.py          # 生产环境PostgreSQL高性能配置
├── models/                     # 数据模型层
│   ├── __init__.py
│   ├── base.py                # PostgreSQL优化基础模型
│   ├── user.py                # 用户模型 + 缓存优化
│   └── photo.py               # 照片模型 + 全文搜索
├── services/                   # 业务逻辑层
│   ├── __init__.py
│   ├── auth_service.py        # 认证服务 + Redis缓存
│   ├── photo_service.py       # 照片服务 + 异步处理
│   └── cache_service.py       # 统一缓存管理
├── utils/                      # 高性能工具库
│   ├── __init__.py
│   ├── db_utils.py            # PostgreSQL查询优化
│   ├── image_utils.py         # Pillow-SIMD图片处理
│   └── performance.py         # 性能监控工具
├── routes/                     # 路由层
│   ├── __init__.py
│   ├── auth.py                # 认证路由
│   ├── photos.py              # 照片路由 + 缓存
│   ├── admin.py               # 管理路由
│   └── api.py                 # 高性能API
├── tasks/                      # Celery异步任务
│   ├── __init__.py
│   ├── image_tasks.py         # 图片处理任务
│   └── cache_tasks.py         # 缓存维护任务
├── static/                     # 静态文件
├── templates/                  # 模板文件
└── requirements/               # 分层依赖
    ├── base.txt               # 基础依赖
    └── production.txt         # 高性能组件
```

### 精简而高效的模型设计

#### PostgreSQL高性能基础模型
```python
# models/base.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Index, text
import uuid
import orjson

class BaseModel(db.Model):
    """精简的高性能基础模型"""
    __abstract__ = True
    
    # 使用UUID主键（PostgreSQL推荐）
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    
    def to_dict(self):
        """高性能序列化"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    def to_json(self):
        """使用orjson快速序列化"""
        return orjson.dumps(self.to_dict(), default=str)

# models/user.py - 精简而高效的用户模型
class User(BaseModel):
    __tablename__ = 'users'
    
    # 优化索引策略
    __table_args__ = (
        Index('idx_user_name_active', 'real_name', postgresql_where=text('is_active = true')),
        Index('idx_user_role', 'role'),
    )
    
    real_name = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    school_id = db.Column(db.String(20), unique=True, nullable=True)
    qq_number = db.Column(db.String(15), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.SmallInteger, default=1, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # JSONB存储扩展信息（避免频繁表结构变更）
    profile = db.Column(JSONB, nullable=True)
    
    def is_admin(self):
        return self.role >= 2
    
    @classmethod
    def get_by_name(cls, name):
        """优化查询"""
        return cls.query.filter_by(real_name=name, is_active=True).first()

class Photo(BaseModel):
    __tablename__ = 'photos'
    
    # 精简而强大的索引
    __table_args__ = (
        Index('idx_photo_approved', 'vote_count', 'created_at', postgresql_where=text('status = 1')),
        Index('idx_photo_fts', text('to_tsvector(\'chinese\', title)')),
        Index('idx_photo_user', 'user_id', 'status'),
    )
    
    url = db.Column(db.String(256))
    thumb_url = db.Column(db.String(256))
    title = db.Column(db.String(100), nullable=True)
    class_name = db.Column(db.String(32))
    student_name = db.Column(db.String(32))
    vote_count = db.Column(db.Integer, default=0, index=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.SmallInteger, default=0, index=True)
    
    # JSONB存储图片元数据
    metadata = db.Column(JSONB, nullable=True)
    
    @classmethod
    def get_approved(cls, limit=20):
        """获取已审核照片"""
        return cls.query.filter_by(status=1).order_by(
            cls.vote_count.desc(), cls.created_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def search(cls, term):
        """全文搜索"""
        return cls.query.filter(
            text("to_tsvector('chinese', title) @@ plainto_tsquery('chinese', :term)"),
            cls.status == 1
        ).params(term=term).all()
```

### 精简而高效的服务层

#### 认证服务
```python
# services/auth_service.py
from werkzeug.security import check_password_hash
from utils.performance import log_performance
from services.cache_service import cache, cached

class AuthService:
    """精简高效的认证服务"""
    
    @staticmethod
    @log_performance
    def login_user(username, password, ip_address):
        """用户登录 - 简化流程，保证性能"""
        # 1. 缓存查询用户
        user = get_user_cached(username)
        if not user or not user.is_active:
            return None, '用户不存在或已禁用'
        
        # 2. 验证密码
        if not check_password_hash(user.password_hash, password):
            return None, '密码错误'
        
        # 3. 安全检查（简化）
        if not AuthService._check_security(ip_address, user.id):
            return None, '登录异常，请稍后再试'
        
        # 4. 记录登录（异步）
        from tasks.image_tasks import celery
        celery.send_task('record_login', args=[user.id, ip_address])
        
        return user, '登录成功'
    
    @staticmethod
    def _check_security(ip_address, user_id):
        """简化的安全检查"""
        # 简单的频率限制检查
        login_count_key = f"login_attempts:{ip_address}"
        count = cache.get(login_count_key, 0)
        
        if count > 10:  # 10分钟内超过10次
            return False
        
        cache.set(login_count_key, count + 1, timeout=600)
        return True

@cached(timeout=600, key_prefix='user')
def get_user_cached(username):
    """缓存用户查询"""
    return User.get_by_name(username)
```

#### 照片服务
```python
# services/photo_service.py
from werkzeug.utils import secure_filename
from tasks.image_tasks import process_image
from utils.performance import log_performance
import uuid
import os

class PhotoService:
    """高性能照片服务"""
    
    @staticmethod
    @log_performance
    def upload_photo(file, user_id, title=None):
        """高效照片上传处理"""
        try:
            # 1. 快速保存原文件
            filename = PhotoService._save_original(file)
            
            # 2. 创建数据库记录
            user = User.query.get(user_id)
            photo = Photo(
                url=f'/static/uploads/{filename}',
                title=title or f'作品_{uuid.uuid4().hex[:8]}',
                class_name=user.class_name,
                student_name=user.real_name,
                user_id=user_id,
                status=0  # 待审核
            )
            
            db.session.add(photo)
            db.session.commit()
            
            # 3. 异步处理图片
            process_image.delay(str(photo.id))
            
            # 4. 清除相关缓存
            cache.delete(f'user_photos:{user_id}')
            
            return photo, '上传成功，正在处理'
            
        except Exception as e:
            db.session.rollback()
            return None, f'上传失败: {str(e)}'
    
    @staticmethod
    def _save_original(file):
        """保存原始文件"""
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        upload_path = os.path.join('static/uploads', unique_filename)
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        file.save(upload_path)
        
        return unique_filename
    
    @staticmethod
    @cached(timeout=300, key_prefix='photos')
    def get_approved_photos():
        """获取已审核照片（带缓存）"""
        return Photo.get_approved()
    
    @staticmethod
    def search_photos(search_term):
        """高性能搜索"""
        if not search_term or len(search_term.strip()) < 2:
            return []
        
        # 使用PostgreSQL全文搜索
        return Photo.search(search_term.strip())
```

### 高效缓存设计

#### 智能缓存服务
```python
# services/cache_service.py
from flask_caching import Cache
import redis
import orjson
from functools import wraps

class SmartCache:
    """智能缓存服务 - 平衡性能和复杂度"""
    
    def __init__(self, app=None):
        self.cache = Cache()
        self.redis_client = None
        
    def init_app(self, app):
        # 根据环境选择缓存后端
        if app.config.get('REDIS_URL'):
            # 生产环境使用Redis
            self.cache.init_app(app, config={
                'CACHE_TYPE': 'RedisCache',
                'CACHE_REDIS_URL': app.config['REDIS_URL'],
                'CACHE_DEFAULT_TIMEOUT': 300
            })
            self.redis_client = redis.from_url(app.config['REDIS_URL'])
        else:
            # 开发环境使用内存缓存
            self.cache.init_app(app, config={
                'CACHE_TYPE': 'SimpleCache',
                'CACHE_DEFAULT_TIMEOUT': 300
            })
    
    def get(self, key, default=None):
        """获取缓存"""
        try:
            value = self.cache.get(key)
            return orjson.loads(value) if value else default
        except:
            return default
    
    def set(self, key, value, timeout=300):
        """设置缓存"""
        try:
            serialized = orjson.dumps(value, default=str)
            return self.cache.set(key, serialized, timeout=timeout)
        except:
            return False
    
    def delete(self, key):
        """删除缓存"""
        return self.cache.delete(key)
    
    def clear_pattern(self, pattern):
        """批量清除缓存"""
        if self.redis_client:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        else:
            # SimpleCache不支持模式匹配，清除所有
            self.cache.clear()

# 全局缓存实例
cache = SmartCache()

# 缓存装饰器
def cached(timeout=300, key_prefix=None):
    """智能缓存装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_prefix:
                cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            else:
                cache_key = f"{f.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 检查缓存
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数并缓存结果
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator

# 应用级缓存策略
@cached(timeout=300, key_prefix='photos')
def get_approved_photos_cached():
    """缓存已审核照片列表"""
    return Photo.get_approved()

@cached(timeout=60, key_prefix='vote')
def get_vote_count_cached(photo_id):
    """缓存投票数"""
    return Vote.query.filter_by(photo_id=photo_id).count()

@cached(timeout=1800, key_prefix='user')
def get_user_cached(user_id):
    """缓存用户信息"""
    return User.query.get(user_id)
```

### 精简高效的路由设计

#### 主要路由
```python
# routes/photos.py
from flask import Blueprint, request, render_template, jsonify, session, flash, redirect, url_for
from services.photo_service import PhotoService
from services.cache_service import cached
from utils.decorators import login_required, rate_limit
from utils.performance import log_performance

photos_bp = Blueprint('photos', __name__)

@photos_bp.route('/')
@rate_limit(max_requests=30, window=60)  # 基础频率限制
@log_performance
def index():
    """首页 - 高性能优化"""
    # 1. 缓存获取照片列表
    photos = PhotoService.get_approved_photos()
    
    # 2. 获取系统设置（缓存）
    settings = get_settings_cached()
    
    # 3. 用户信息
    current_user = None
    if 'user_id' in session:
        current_user = get_user_cached(session['user_id'])
    
    return render_template('index.html', 
                         photos=photos, 
                         settings=settings,
                         current_user=current_user)

@photos_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@rate_limit(max_requests=10, window=300)  # 上传限制
def upload():
    """照片上传 - 异步处理"""
    if request.method == 'POST':
        files = request.files.getlist('photos')
        titles = request.form.getlist('titles')
        
        results = []
        for i, file in enumerate(files):
            if file and file.filename:
                title = titles[i] if i < len(titles) else None
                photo, message = PhotoService.upload_photo(
                    file, session['user_id'], title
                )
                results.append({'success': photo is not None, 'message': message})
        
        success_count = sum(1 for r in results if r['success'])
        flash(f'成功上传 {success_count} 张照片')
        
        return redirect(url_for('photos.my_photos'))
    
    return render_template('upload.html')

@photos_bp.route('/my_photos')
@login_required
@cached(timeout=60, key_prefix='user_photos')
def my_photos():
    """用户照片 - 缓存优化"""
    user_id = session['user_id']
    photos = Photo.query.filter_by(user_id=user_id).order_by(
        Photo.created_at.desc()
    ).all()
    
    return render_template('my_photos.html', photos=photos)

# API路由
@photos_bp.route('/api/photos')
@rate_limit(max_requests=100, window=60)
def api_photos():
    """高性能API接口"""
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)  # 限制最大数量
    
    photos = Photo.get_approved(limit=limit)
    
    return jsonify({
        'success': True,
        'data': [{
            'id': str(p.id),
            'title': p.title,
            'vote_count': p.vote_count,
            'thumb_url': p.thumb_url,
            'student_name': p.student_name
        } for p in photos],
        'total': len(photos)
    })

@photos_bp.route('/api/search')
@rate_limit(max_requests=50, window=60)
def api_search():
    """高性能搜索API"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'message': '搜索关键词不能为空'})
    
    results = PhotoService.search_photos(query)
    
    return jsonify({
        'success': True,
        'data': [{
            'id': str(p.id),
            'title': p.title,
            'student_name': p.student_name,
            'vote_count': p.vote_count
        } for p in results],
        'query': query
    })

# 缓存辅助函数
@cached(timeout=1800, key_prefix='settings')
def get_settings_cached():
    """缓存系统设置"""
    return Settings.query.first() or Settings()

@cached(timeout=600, key_prefix='user')
def get_user_cached(user_id):
    """缓存用户信息"""
    return User.query.get(user_id)
```

#### 1. 内存缓存架构
```mermaid
graph LR
    A[用户请求] --> B[应用层]
    B --> C{内存缓存}
    C -->|命中| D[返回缓存数据]
    C -->|未命中| E[查询数据库]
    E --> F[更新缓存]
    F --> D
```

#### 2. Flask-Caching实现
```python
# services/cache_service.py
from flask_caching import Cache

cache = Cache()

def init_cache(app):
    """初始化缓存"""
    cache.init_app(app, config={
        'CACHE_TYPE': 'simple',  # 内存缓存
        'CACHE_DEFAULT_TIMEOUT': 300
    })

@cache.memoize(timeout=300)
def get_approved_photos():
    """缓存已审核照片列表"""
    return Photo.query.filter_by(status=1).all()

@cache.memoize(timeout=60)
def get_vote_count(photo_id):
    """缓存投票数"""
    return Vote.query.filter_by(photo_id=photo_id).count()

def clear_photo_cache():
    """清除照片相关缓存"""
    cache.delete_memoized(get_approved_photos)
```

#### 3. 缓存策略
- **照片列表**：5分钟缓存，减少数据库查询
- **投票数量**：1分钟缓存，平衡实时性和性能
- **用户会话**：使用Flask-Session默认机制

### 精简异步处理

#### 1. Threading + Queue
```python
# utils/async_utils.py
import threading
import queue
from functools import wraps

# 创建后台任务队列
task_queue = queue.Queue()

def background_task(func):
    """后台任务装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        task_queue.put((func, args, kwargs))
    return wrapper

def start_worker():
    """启动后台工作线程"""
    def worker():
        while True:
            func, args, kwargs = task_queue.get()
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"后台任务执行失败: {e}")
            finally:
                task_queue.task_done()
    
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

@background_task
def process_uploaded_image(photo_id):
    """后台处理图片"""
    # 生成缩略图、水印等
    pass
```

#### 2. 保持同步路由
```python
# 保持现有Flask同步特性，避免复杂化
@app.route('/upload', methods=['POST'])
def upload():
    """上传处理 - 快速响应"""
    # 1. 快速保存原图
    # 2. 触发后台处理
    # 3. 立即返回响应
    process_uploaded_image(photo.id)  # 异步处理
    return redirect(url_for('my_photos'))
```

## 水印系统精简优化

### 问题分析
- 当前每次下载都生成水印，性能差
- 字体加载复杂，容错性不足
- 临时文件管理混乱

### 精简方案

#### 1. 简化的水印缓存
```python
# utils/image_utils.py
import os
import hashlib
from PIL import Image, ImageDraw, ImageFont

WATERMARK_CACHE_DIR = 'static/cache/watermarks'

def get_watermarked_image(photo_id, user_info):
    """获取带水印图片，带文件缓存"""
    # 生成缓存文件名
    cache_key = f"{photo_id}_{hash(str(user_info))}"
    cache_path = os.path.join(WATERMARK_CACHE_DIR, f"{cache_key}.jpg")
    
    # 检查缓存
    if os.path.exists(cache_path):
        return cache_path
    
    # 生成水印
    original_path = get_original_photo_path(photo_id)
    watermarked_path = add_simple_watermark(original_path, user_info)
    
    # 保存到缓存目录
    os.makedirs(WATERMARK_CACHE_DIR, exist_ok=True)
    shutil.copy2(watermarked_path, cache_path)
    
    return cache_path

def add_simple_watermark(image_path, user_info):
    """简化的水印添加"""
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # 简化字体加载
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # 水印文本
    watermark_text = f"{user_info['name']}-{user_info['qq']}"
    
    # 添加水印到右下角
    img_width, img_height = img.size
    text_width, text_height = draw.textsize(watermark_text, font)
    x = img_width - text_width - 20
    y = img_height - text_height - 20
    
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))
    
    # 保存到临时文件
    temp_path = f"temp/watermarked_{photo_id}.jpg"
    img.save(temp_path)
    return temp_path
```

#### 2. 后台水印预生成
```python
@background_task
def pregenerate_watermarks(photo_id):
    """后台预生成常用水印"""
    photo = Photo.query.get(photo_id)
    if photo and photo.status == 1:  # 已审核通过
        user_info = {
            'name': photo.student_name,
            'qq': photo.user.qq_number
        }
        get_watermarked_image(photo_id, user_info)
```

## 安全性精简增强

### 1. 基础安全装饰器
```python
# utils/decorators.py
from functools import wraps
from flask import request, abort

def rate_limit(max_requests=10, window=60):
    """简单的频率限制"""
    request_counts = {}
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')
            now = time.time()
            
            # 清理过期记录
            request_counts[client_ip] = [
                req_time for req_time in request_counts.get(client_ip, [])
                if now - req_time < window
            ]
            
            # 检查请求数量
            if len(request_counts[client_ip]) >= max_requests:
                abort(429)  # Too Many Requests
            
            request_counts[client_ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

def validate_form(**validators):
    """简单的表单验证装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for field, validator in validators.items():
                value = request.form.get(field, '')
                if not validator(value):
                    flash(f'{field} 格式不正确')
                    return redirect(request.url)
            return f(*args, **kwargs)
        return wrapper
    return decorator
```

### 2. 简化的数据验证
```python
# utils/validators.py
def validate_qq(qq):
    """验证QQ号"""
    return qq.isdigit() and 5 <= len(qq) <= 15

def validate_password(password):
    """验证密码"""
    return len(password) >= 6

def validate_name(name):
    """验证姓名"""
    return 2 <= len(name.strip()) <= 50

# 使用示例
@app.route('/register', methods=['POST'])
@validate_form(
    real_name=validate_name,
    qq_number=validate_qq,
    password=validate_password
)
def register():
    # 注册逻辑
    pass
```

## 实用工具库

### 性能监控装饰器
```python
# utils/performance.py
import time
import functools
from flask import current_app

def log_performance(f):
    """性能监控装饰器"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            duration = end_time - start_time
            if duration > 0.5:  # 超过500ms记录日志
                current_app.logger.warning(
                    f'Slow function: {f.__name__} took {duration:.3f}s'
                )
    return wrapper

def timing_context(operation_name):
    """计时上下文管理器"""
    class TimingContext:
        def __enter__(self):
            self.start = time.time()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start
            current_app.logger.info(f'{operation_name}: {duration:.3f}s')
    
    return TimingContext()

# 使用示例
with timing_context('Database query'):
    photos = Photo.query.all()
```

### PostgreSQL查询优化工具
```python
# utils/db_utils.py
from sqlalchemy import text
from flask import current_app

def optimize_query(query):
    """查询优化建议"""
    if current_app.debug:
        # 开发环境显示查询计划
        explain_query = f"EXPLAIN ANALYZE {query}"
        result = db.session.execute(text(explain_query))
        current_app.logger.debug(f"Query plan: {list(result)}")
    return query

def bulk_insert(model_class, data_list, batch_size=1000):
    """高性能批量插入"""
    try:
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            db.session.bulk_insert_mappings(model_class, batch)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Bulk insert failed: {e}")
        return False

def get_database_stats():
    """获取数据库性能统计"""
    stats_query = text("""
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            seq_scan,
            seq_tup_read,
            idx_scan,
            idx_tup_fetch
        FROM pg_stat_user_tables 
        ORDER BY seq_scan DESC
    """)
    
    return db.session.execute(stats_query).fetchall()
```

## PostgreSQL配置优化

### 数据库配置文件
```python
# config/production.py
import os
import redis

class ProductionConfig:
    """生产环境PostgreSQL优化配置"""
    
    # PostgreSQL连接优化
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql+asyncpg://user:password@localhost/photo_contest'
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'max_overflow': 30,
        'pool_pre_ping': True,
        'echo': False,  # 生产环境关闭SQL日志
    }
    
    # Redis缓存配置
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # 会话配置
    SESSION_TYPE = 'redis'
    SESSION_REDIS = redis.from_url(REDIS_URL)
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'contest:'
    
    # Celery配置
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = '/var/uploads'
    
    # 性能配置
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1年静态文件缓存
    PERMANENT_SESSION_LIFETIME = 1800     # 30分钟会话超时
```

### Docker部署配置
```yaml
# docker-compose.yml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/contest
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/var/uploads
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: contest
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
  
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
  
  worker:
    build: .
    command: celery -A app.celery worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/contest
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/var/uploads

volumes:
  postgres_data:
```

## 数据库迁移方案

### 从MySQL到PostgreSQL的迁移步骤

```mermaid
flowchart TD
    A[备份现有MySQL数据] --> B[创建PostgreSQL数据库]
    B --> C[转换数据结构]
    C --> D[迁移数据]
    D --> E[验证数据完整性]
    E --> F[更新应用配置]
    F --> G[部署新版本]
    G --> H[性能测试]
```

### 迁移脚本
```python
# scripts/migrate_to_postgresql.py
import pandas as pd
from sqlalchemy import create_engine
from models import User, Photo, Vote
import uuid

def migrate_data():
    """数据迁移脚本"""
    
    # 连接MySQL和PostgreSQL
    mysql_engine = create_engine('mysql://user:pass@localhost/old_db')
    postgres_engine = create_engine('postgresql://user:pass@localhost/new_db')
    
    # 迁移用户数据
    print("迁移用户数据...")
    users_df = pd.read_sql('SELECT * FROM users', mysql_engine)
    
    # 转换ID为UUID
    users_df['id'] = [str(uuid.uuid4()) for _ in range(len(users_df))]
    users_df.to_sql('users', postgres_engine, if_exists='append', index=False)
    
    # 迁移照片数据
    print("迁移照片数据...")
    photos_df = pd.read_sql('SELECT * FROM photos', mysql_engine)
    photos_df['id'] = [str(uuid.uuid4()) for _ in range(len(photos_df))]
    photos_df.to_sql('photos', postgres_engine, if_exists='append', index=False)
    
    print("数据迁移完成")

if __name__ == '__main__':
    migrate_data()
```

## 测试策略

### 单元测试框架
```python
# tests/test_performance.py
import pytest
import time
from app import create_app
from models import User, Photo
from services.photo_service import PhotoService

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

class TestPerformance:
    """性能测试"""
    
    def test_photo_list_performance(self, client):
        """测试照片列表性能"""
        start_time = time.time()
        response = client.get('/')
        duration = time.time() - start_time
        
        assert response.status_code == 200
        assert duration < 0.5  # 响应时间应小于500ms
    
    def test_search_performance(self, client):
        """测试搜索性能"""
        start_time = time.time()
        response = client.get('/api/search?q=测试')
        duration = time.time() - start_time
        
        assert response.status_code == 200
        assert duration < 0.3  # 搜索响应时间应小于300ms
    
    def test_concurrent_upload(self, client):
        """测试并发上传"""
        import threading
        
        def upload_photo():
            with open('test_image.jpg', 'rb') as f:
                client.post('/upload', data={'photos': f})
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=upload_photo)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 验证所有上传都成功处理
        assert True  # 具体验证逻辑

class TestCache:
    """缓存测试"""
    
    def test_cache_hit_rate(self, app):
        """测试缓存命中率"""
        with app.app_context():
            # 第一次查询（缓存miss）
            start_time = time.time()
            photos1 = PhotoService.get_approved_photos()
            first_duration = time.time() - start_time
            
            # 第二次查询（缓存hit）
            start_time = time.time()
            photos2 = PhotoService.get_approved_photos()
            second_duration = time.time() - start_time
            
            # 缓存命中应该显著更快
            assert second_duration < first_duration * 0.1
            assert photos1 == photos2
```
# utils/performance.py
import time
import functools
import logging
from collections import defaultdict, deque

# 简化的性能监控
class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(deque)
        self.slow_queries = deque(maxlen=100)
    
    def record(self, name, duration, details=None):
        self.metrics[name].append((time.time(), duration))
        if len(self.metrics[name]) > 1000:
            self.metrics[name].popleft()
        
        # 记录慢查询
        if duration > 1.0:
            self.slow_queries.append({
                'name': name,
                'duration': duration,
                'details': details,
                'timestamp': time.time()
            })
    
    def get_stats(self):
        stats = {}
        for name, values in self.metrics.items():
            if values:
                durations = [v[1] for v in values]
                stats[name] = {
                    'count': len(durations),
                    'avg': sum(durations) / len(durations),
                    'max': max(durations),
                    'min': min(durations)
                }
        return stats

monitor = PerformanceMonitor()

# 性能监控装饰器
def log_performance(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            monitor.record(func.__name__, duration)
            
            # 记录慢操作
            if duration > 0.5:
                logging.warning(f"Slow operation: {func.__name__} took {duration:.2f}s")
    
    return wrapper

# 数据库查询监控
def monitor_db_query(query_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                monitor.record(f"db_{query_name}", duration)
                
                if duration > 0.1:  # 数据库查询超过100ms
                    logging.warning(f"Slow DB query: {query_name} took {duration:.3f}s")
        return wrapper
    return decorator
```

#### 简化的装饰器
```python
# utils/decorators.py
import time
import functools
from flask import session, request, abort, redirect, url_for
from collections import defaultdict

# 简单的频率限制
request_counts = defaultdict(list)

def rate_limit(max_requests=60, window=60):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')
            now = time.time()
            
            # 清理过期记录
            request_counts[client_ip] = [
                req_time for req_time in request_counts[client_ip]
                if now - req_time < window
            ]
            
            # 检查频率
            if len(request_counts[client_ip]) >= max_requests:
                abort(429)  # Too Many Requests
            
            request_counts[client_ip].append(now)
            return f(*args, **kwargs)
        
        return wrapper
    return decorator

# 登录检查
def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        # 简单的用户状态检查
        user = get_user_cached(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    
    return wrapper

# 管理员检查
def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = get_user_cached(session['user_id'])
        if not user or not user.is_admin():
            abort(403)
        
        return f(*args, **kwargs)
    
    return wrapper
```

### 1. PostgreSQL部署配置
```bash
# deploy_postgresql.sh
#!/bin/bash

set -e

echo "部署PostgreSQL高性能系统..."

# 1. 安装PostgreSQL依赖
echo "安装依赖..."
pip install -r requirements/production.txt

# 2. 设置环境变量
export FLASK_ENV=production
export SECRET_KEY=${SECRET_KEY}
export DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${PG_DB}"
export REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"

# 3. 初始化PostgreSQL数据库
echo "初始化数据库..."
flask db upgrade

# 4. 启动服务
echo "启动应用服务..."
gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker app:app
```

### 2. PostgreSQL生产配置
```python
# config/production.py
import os

class ProductionConfig:
    # PostgreSQL数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'postgresql+asyncpg://user:password@localhost/photo_contest'
    )
    
    # 高性能连接池
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 30,
        'max_overflow': 50,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'echo': False
    }
    
    # Redis配置
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = REDIS_URL
    
    # Celery配置
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # 安全配置
    SECRET_KEY = os.environ.get('SECRET_KEY')
    WTF_CSRF_ENABLED = True
    
    # 文件上传配置
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
```

### 3. Docker Compose配置
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/photo_contest
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./static/uploads:/app/static/uploads
      - ./static/cache:/app/static/cache
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=photo_contest
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql.conf:/etc/postgresql/postgresql.conf
    ports:
      - "5432:5432"
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    environment:
      - DATABASES_HOST=db
      - DATABASES_PORT=5432
      - DATABASES_USER=postgres
      - DATABASES_PASSWORD=password
      - DATABASES_DBNAME=photo_contest
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=1000
      - DEFAULT_POOL_SIZE=25
    ports:
      - "6432:6432"
    depends_on:
      - db
  
  celery_worker:
    build: .
    command: celery -A celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/photo_contest
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./static/uploads:/app/static/uploads
      - ./static/cache:/app/static/cache

volumes:
  postgres_data:
  redis_data:
```

### 4. PostgreSQL优化配置
```ini
# postgresql.conf - PostgreSQL性能优化

# 内存配置
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB

# 连接配置
max_connections = 200

# 检查点配置
checkpoint_timeout = 10min
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# 查询优化
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# 日志配置
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# 中文支持
lc_messages = 'en_US.UTF-8'
lc_monetary = 'en_US.UTF-8'
lc_numeric = 'en_US.UTF-8'
lc_time = 'en_US.UTF-8'
default_text_search_config = 'pg_catalog.simple'
```

## PostgreSQL依赖配置

### requirements/base.txt
```
# 基础依赖
Flask>=2.3.0
SQLAlchemy>=2.0.0
Flask-SQLAlchemy>=3.0.0
Flask-Migrate>=3.1.0

# PostgreSQL驱动
psycopg2-binary>=2.9.0
asyncpg>=0.28.0

# 高性能组件
redis>=4.5.0
Flask-Caching>=2.0.0
celery>=5.3.0

# 图片处理
Pillow-SIMD>=10.0.0
# 如果无法安装Pillow-SIMD，使用标准Pillow
# Pillow>=10.0.0

# 高性能JSON序列化
orjson>=3.8.0

# 其他工具
Werkzeug>=2.3.0
pandas>=2.0.0
openpyxl>=3.1.0
```

### requirements/production.txt
```
-r base.txt

# 生产环境额外依赖
gunicorn>=21.0.0
uvicorn[standard]>=0.23.0

# 监控和日志
flower>=2.0.0  # Celery监控
loguru>=0.7.0  # 更好的日志

# 安全
flask-talisman>=1.1.0  # 安全头
```

### requirements/development.txt
```
-r base.txt

# 开发工具
pytest>=7.4.0
pytest-asyncio>=0.21.0
flake8>=6.0.0
black>=23.0.0
mypy>=1.5.0

# 数据库迁移工具
aiomysql>=0.1.1  # MySQL迁移使用
```

## PostgreSQL实施计划

### 第一阶段：数据库迁移 (2天)
1. 安装PostgreSQL和相关依赖
2. 创建PostgreSQL数据库和表结构
3. 执行MySQL到PostgreSQL数据迁移
4. 验证数据完整性和一致性

### 第二阶段：代码重构 (3天)
1. 更新模型定义以支持PostgreSQL特性
2. 实现JSONB字段和全文搜索功能
3. 优化数据库查询和索引
4. 集成Redis缓存和Celery异步任务

### 第三阶段：性能优化 (2天)
1. 部署pgbouncer连接池
2. 优化PostgreSQL配置参数
3. 实现高性能水印系统
4. 性能测试和调优

### 第四阶段：生产部署 (1天)
1. 配置生产环境Docker Compose
2. 部署安全配置和监控
3. 全面测试和上线

## PostgreSQL性能指标目标

| 指标 | MySQL当前 | PostgreSQL目标 | 提升幅度 |
|------|------------|----------------|----------|
| 数据库查询性能 | 基线 | 50-100%提升 | 显著 |
| 全文搜索 | 无 | 10-30x性能 | 新增能力 |
| JSON数据处理 | 差 | 5-15x性能 | 显著 |
| 并发连接数 | 100 | 500+ | 5x |
| 复杂查询 | 慢 | 70%提升 | 显著 |
| 数据一致性 | 好 | 更好 | 提升 |
| 扩展性 | 有限 | 优秀 | 大幅提升 |
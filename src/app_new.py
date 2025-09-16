"""
应用工厂模式 - PostgreSQL高性能版
"""
from flask import Flask
from config.base import get_config
from models.base import db
from services.cache_service import cache
import logging
import os


def create_app(config_name=None):
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 配置应用
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)
    
    # 初始化扩展
    init_extensions(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 设置日志
    setup_logging(app)
    
    # 应用启动钩子
    setup_app_hooks(app)
    
    return app


def init_extensions(app):
    """初始化扩展"""
    # 初始化数据库
    db.init_app(app)
    
    # 初始化缓存
    cache.init_app(app)
    
    # 测试模式下跳过性能监控和Celery初始化
    if not app.config.get('TESTING'):
        # 初始化性能监控
        from utils.performance import init_performance_monitoring
        init_performance_monitoring(app)
        
        # 初始化Celery
        from tasks.celery_app import make_celery
        celery = make_celery(app)
        app.celery = celery
        
        # PostgreSQL优化设置
        with app.app_context():
            setup_database_optimizations()


def register_blueprints(app):
    """注册路由蓝图"""
    from routes.auth import auth_bp
    from routes.photos import photos_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(photos_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')


def setup_logging(app):
    """设置日志"""
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler('logs/app.log'),
                logging.StreamHandler()
            ]
        )


def setup_app_hooks(app):
    """设置应用钩子"""
    @app.before_request
    def initialize_app():
        """应用请求前初始化"""
        # 预热缓存 (测试模式下跳过)
        if not app.config.get('TESTING') and not hasattr(app, '_cache_warmed'):
            from services.cache_service import warm_up_cache
            warm_up_cache()
            app._cache_warmed = True
    
    @app.teardown_appcontext
    def close_session(error):
        """请求结束后清理"""
        if error:
            db.session.rollback()
        db.session.remove()


def setup_database_optimizations():
    """设置数据库优化（仅在非测试模式下执行）"""
    # PostgreSQL扩展启用（生产环境）
    try:
        from sqlalchemy import text
        db.session.execute(text('CREATE EXTENSION IF NOT EXISTS pg_stat_statements'))
        db.session.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
        db.session.execute(text('CREATE EXTENSION IF NOT EXISTS unaccent'))
        db.session.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        db.session.commit()
    except Exception as e:
        print(f"启用PostgreSQL扩展失败: {e}")


# 创建应用实例
app = create_app()
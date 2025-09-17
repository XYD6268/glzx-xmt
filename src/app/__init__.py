"""
摄影比赛投票系统 - SQLite简化版
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.core.config.base import get_config
from app.services.cache_service import cache
import os

# 创建全局扩展实例
db = SQLAlchemy()
cache = cache

def create_app(config_name=None):
    """应用工厂函数"""
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, '..', 'templates')
    static_dir = os.path.join(base_dir, '..', 'static')
    
    # 创建应用实例，指定模板和静态文件目录
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # 加载配置
    config = get_config(config_name)
    app.config.from_object(config)
    
    # 初始化扩展
    db.init_app(app)
    cache.init_app(app)
    
    # 创建数据库表
    with app.app_context():
        from app.models.user import User
        from app.models.photo import Photo, Vote
        from app.models.settings import Settings
        db.create_all()
    
    # 注册蓝图或路由
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app
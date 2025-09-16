"""
摄影比赛投票系统 - SQLite简化版
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.core.config.base import get_config
from app.services.cache_service import cache

# 创建应用实例
db = SQLAlchemy()
app = Flask(__name__)

def create_app(config_name=None):
    """应用工厂函数"""
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

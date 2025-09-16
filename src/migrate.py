#!/usr/bin/env python3
"""
摄影比赛投票系统 - PostgreSQL高性能重构迁移脚本
"""
import os
import sys
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from config.base import get_config
from models.base import db
from models.user import User, LoginRecord, IpBanRecord, IpWhitelist, UserWhitelist
from models.photo import Photo, Vote
from models.settings import Settings, Agreement, UserAgreementRecord
from utils.db_utils import QueryOptimizer, create_database_extensions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_from_mysql():
    """从MySQL迁移到PostgreSQL"""
    logger.info("开始从MySQL迁移到PostgreSQL...")
    
    try:
        # 1. 创建所有表
        logger.info("创建数据库表...")
        db.create_all()
        
        # 2. 创建PostgreSQL扩展
        logger.info("创建PostgreSQL扩展...")
        create_database_extensions()
        
        # 3. 创建自定义索引
        logger.info("创建优化索引...")
        QueryOptimizer.create_custom_indexes()
        
        # 4. 如果有旧数据，执行迁移
        # 这里可以添加具体的数据迁移逻辑
        
        # 5. 初始化默认设置
        logger.info("初始化默认设置...")
        init_default_settings()
        
        # 6. 优化数据库
        logger.info("优化数据库...")
        QueryOptimizer.optimize_all_tables()
        
        logger.info("迁移完成！")
        return True
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False


def init_default_settings():
    """初始化默认设置"""
    try:
        # 检查是否已存在设置
        if Settings.query.first():
            logger.info("设置已存在，跳过初始化")
            return
        
        # 创建默认设置
        settings = Settings(
            contest_title="2025年摄影比赛",
            allow_upload=True,
            allow_vote=True,
            one_vote_per_user=False,
            show_rankings=True,
            risk_control_enabled=True,
            max_votes_per_ip=10,
            vote_time_window=60,
            max_accounts_per_ip=5,
            account_time_window=1440,
            watermark_enabled=True,
            watermark_text="{contest_title}-{student_name}-{qq_number}",
            watermark_opacity=0.3,
            watermark_position="bottom_right",
            watermark_font_size=20
        )
        
        db.session.add(settings)
        db.session.commit()
        
        logger.info("默认设置已初始化")
        
    except Exception as e:
        logger.error(f"初始化设置失败: {e}")
        db.session.rollback()


def create_admin_user():
    """创建管理员用户"""
    try:
        # 检查是否已存在管理员
        admin = User.query.filter_by(role=3).first()
        if admin:
            logger.info("管理员已存在")
            return
        
        # 创建系统管理员
        admin_user = User(
            real_name="系统管理员",
            qq_number="10000",
            class_name="管理班级",
            role=3,  # 系统管理员
            is_active=True
        )
        admin_user.set_password("admin123456")  # 默认密码，需要修改
        
        db.session.add(admin_user)
        db.session.commit()
        
        logger.info("系统管理员已创建，用户名: 系统管理员, 密码: admin123456")
        logger.warning("请立即修改默认密码！")
        
    except Exception as e:
        logger.error(f"创建管理员失败: {e}")
        db.session.rollback()


def check_environment():
    """检查环境配置"""
    logger.info("检查环境配置...")
    
    # 检查必要的环境变量
    required_vars = [
        'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST', 
        'POSTGRES_PORT', 'POSTGRES_DB'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"缺少环境变量: {', '.join(missing_vars)}")
        return False
    
    # 检查目录
    required_dirs = ['../photo/uploads', '../photo/thumbs', 'logs']
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"创建目录: {dir_path}")
    
    logger.info("环境检查完成")
    return True


def performance_tuning():
    """性能调优"""
    logger.info("执行性能调优...")
    
    try:
        from utils.db_utils import setup_postgresql_optimizations
        setup_postgresql_optimizations()
        
        # 优化所有表
        QueryOptimizer.optimize_all_tables()
        
        logger.info("性能调优完成")
        
    except Exception as e:
        logger.error(f"性能调优失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("摄影比赛投票系统 - PostgreSQL高性能重构")
    print("=" * 60)
    
    # 检查环境
    if not check_environment():
        print("❌ 环境检查失败")
        sys.exit(1)
    
    # 创建Flask应用上下文
    from app_new import create_app
    app = create_app('production')
    
    with app.app_context():
        print("\n📦 开始迁移...")
        
        # 执行迁移
        if migrate_from_mysql():
            print("✅ 数据库迁移成功")
        else:
            print("❌ 数据库迁移失败")
            sys.exit(1)
        
        # 创建管理员
        print("\n👤 创建管理员用户...")
        create_admin_user()
        
        # 性能调优
        print("\n⚡ 执行性能调优...")
        performance_tuning()
        
        print("\n🎉 重构完成！")
        print("\n📋 后续步骤:")
        print("1. 修改管理员默认密码")
        print("2. 配置Redis缓存服务器")
        print("3. 配置Celery异步任务队列")
        print("4. 启动应用: python app_new.py")
        print("5. 访问系统并测试功能")


if __name__ == '__main__':
    main()
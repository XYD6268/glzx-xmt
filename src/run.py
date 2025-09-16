"""
应用入口文件 - SQLite简化版
"""
import os
from app import create_app
from app.models.user import User
from app.models.settings import Settings
from werkzeug.security import generate_password_hash
from app.models.base import db

# 创建应用
app = create_app('development')

def create_default_admin():
    """创建默认管理员账户"""
    with app.app_context():
        # 检查是否已存在管理员
        admin = User.query.filter_by(role=3).first()
        if not admin:
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
            
            print("系统管理员已创建，用户名: 系统管理员, 密码: admin123456")
            print("请立即修改默认密码！")

def create_default_settings():
    """创建默认设置"""
    with app.app_context():
        # 检查是否已存在设置
        settings = Settings.query.first()
        if not settings:
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
            
            print("默认设置已创建")

if __name__ == '__main__':
    # 确保目录存在
    os.makedirs('../photo/uploads', exist_ok=True)
    os.makedirs('../photo/thumbs', exist_ok=True)
    os.makedirs('../instance', exist_ok=True)
    
    # 创建默认数据
    create_default_admin()
    create_default_settings()
    
    # 运行应用
    app.run(debug=True, host='127.0.0.1', port=5000)
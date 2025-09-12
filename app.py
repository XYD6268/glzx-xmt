from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, send_file, make_response, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw, ImageFont
import os
import pandas as pd
import zipfile
import tempfile
import shutil
from io import BytesIO
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://用户�?密码@localhost/数据库名'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['THUMB_FOLDER'] = 'static/thumbs'
app.config['SECRET_KEY'] = 'your-secret-key-here'
# 禁用默认静态文件路由中的uploads目录访问
app.static_folder = 'static'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    real_name = db.Column(db.String(50), unique=True, nullable=False)  # 真实姓名，现在用作登录账号，必须唯一
    password_hash = db.Column(db.String(120), nullable=False)
    school_id = db.Column(db.String(20), unique=True, nullable=True)  # 校学号，改为可�?
    qq_number = db.Column(db.String(15), nullable=False)  # QQ�?
    class_name = db.Column(db.String(50), nullable=False)  # 班级
    role = db.Column(db.Integer, default=1)  # 1=普通用�? 2=普通管理员, 3=系统管理�?
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 关系定义
    photos = db.relationship('Photo', backref='user', lazy=True)
    votes = db.relationship('Vote', backref='user', lazy=True)
    login_records = db.relationship('LoginRecord', backref='user', lazy=True)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(128))
    thumb_url = db.Column(db.String(128))
    title = db.Column(db.String(100), nullable=True)  # 作品名称
    class_name = db.Column(db.String(32))
    student_name = db.Column(db.String(32))
    vote_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.Integer, default=0)  # 0=待审�? 1=已通过, 2=已拒�?
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 关系定义
    votes = db.relationship('Vote', backref='photo', lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    ip_address = db.Column(db.String(45), nullable=True)  # 记录投票IP

class LoginRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    login_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_agent = db.Column(db.String(500), nullable=True)

class IpBanRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, unique=True)
    banned_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    ban_reason = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contest_title = db.Column(db.String(100), default="2025年摄影比�?)
    allow_upload = db.Column(db.Boolean, default=True)
    allow_vote = db.Column(db.Boolean, default=True)
    one_vote_per_user = db.Column(db.Boolean, default=False)  # 限制每个用户只能投一次票
    vote_start_time = db.Column(db.DateTime, nullable=True)  # 投票开始时�?
    vote_end_time = db.Column(db.DateTime, nullable=True)    # 投票结束时间
    
    # 排行榜设�?
    show_rankings = db.Column(db.Boolean, default=True)  # 是否显示排行�?
    
    # ICP备案�?
    icp_number = db.Column(db.String(100), nullable=True)  # ICP备案�?
    
    # 风控设置
    risk_control_enabled = db.Column(db.Boolean, default=True)  # 是否启用风控
    max_votes_per_ip = db.Column(db.Integer, default=10)  # 单IP最大投票次�?
    vote_time_window = db.Column(db.Integer, default=60)  # 投票时间窗口（分钟）
    max_accounts_per_ip = db.Column(db.Integer, default=5)  # 单IP最大登录账号数
    account_time_window = db.Column(db.Integer, default=1440)  # 账号登录时间窗口（分钟，默认24小时�?
    
    # 水印设置
    watermark_enabled = db.Column(db.Boolean, default=True)  # 是否启用水印
    watermark_text = db.Column(db.String(200), default="{contest_title}-{student_name}-{qq_number}")  # 水印文本格式
    watermark_opacity = db.Column(db.Float, default=0.3)  # 水印透明�?(0.1-1.0)
    watermark_position = db.Column(db.String(20), default="bottom_right")  # 水印位置
    watermark_font_size = db.Column(db.Integer, default=20)  # 水印字体大小

class Agreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # 协议标题
    content = db.Column(db.Text, nullable=False)  # 协议内容（HTML格式�?
    agreement_type = db.Column(db.String(20), nullable=False)  # 协议类型：register, upload
    min_read_time = db.Column(db.Integer, default=10)  # 最小阅读时间（秒）
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

class UserAgreementRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # 用户ID，注册时可能为空
    agreement_id = db.Column(db.Integer, db.ForeignKey('agreement.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)  # IP地址
    read_time = db.Column(db.Integer, nullable=False)  # 实际阅读时间（秒�?
    agreed_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    session_id = db.Column(db.String(100), nullable=True)  # 会话ID，用于注册前的协议记�?

# 权限装饰�?
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # 检查用户是否仍然活�?
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理�?)
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理�?)
            return redirect(url_for('login'))
        elif user.role < 2:
            flash('需要管理员权限')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理�?)
            return redirect(url_for('login'))
        elif user.role < 3:
            flash('需要系统管理员权限')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
        db.session.add(settings)
        db.session.commit()
    return settings

def add_watermark_to_image(image_path, photo_id):
    """为图片添加水�?""
    try:
        # 获取设置和照片信�?
        settings = get_settings()
        if not settings.watermark_enabled:
            return image_path
        
        photo = Photo.query.get(photo_id)
        if not photo:
            return image_path
        
        user = db.session.get(User, photo.user_id)
        if not user:
            return image_path
        
        # 格式化水印文�?
        watermark_text = settings.watermark_text.format(
            contest_title=settings.contest_title,
            student_name=photo.student_name,
            qq_number=user.qq_number,
            class_name=photo.class_name,
            title=photo.title or '作品'
        )
        
        # 打开原始图片
        img = Image.open(image_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 创建水印�?
        watermark = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)
        
        # 尝试加载字体，优先使用中文字�?
        font = None
        font_candidates = []
        
        # Windows字体路径
        if os.name == 'nt':  # Windows
            font_candidates.extend([
                "C:/Windows/Fonts/HarmonyOS_Sans_SC_Regular.ttf",  # 鸿蒙字体
                "C:/Windows/Fonts/HarmonyOS_Sans_Regular.ttf",     # 鸿蒙字体英文�?
                "C:/Windows/Fonts/msyh.ttc",                      # 微软雅黑
                "C:/Windows/Fonts/msyhbd.ttc",                    # 微软雅黑加粗
                "C:/Windows/Fonts/simsun.ttc",                    # 宋体
                "C:/Windows/Fonts/simhei.ttf",                    # 黑体
                "C:/Windows/Fonts/arial.ttf",                     # Arial
            ])
        else:  # Linux/Unix
            font_candidates.extend([
                "/usr/share/fonts/truetype/HarmonyOS/HarmonyOS_Sans_SC_Regular.ttf",  # 鸿蒙字体
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",            # Noto Sans CJK
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                   # DejaVu Sans
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",   # Liberation Sans
                "/System/Library/Fonts/PingFang.ttc",                               # macOS 苹方字体
                "/System/Library/Fonts/Helvetica.ttc",                              # macOS Helvetica
            ])
        
        # 尝试加载字体
        for font_path in font_candidates:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, settings.watermark_font_size)
                    print(f"成功加载字体: {font_path}")
                    break
            except Exception as e:
                print(f"加载字体失败 {font_path}: {e}")
                continue
        
        # 如果所有字体都加载失败，使用默认字�?
        if font is None:
            try:
                font = ImageFont.load_default()
                print("使用默认字体")
            except:
                # 最后的备选方案，创建一个简单的字体
                font = ImageFont.load_default()
                print("使用系统默认字体")
        
        # 获取文本尺寸
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 计算水印位置
        margin = 20
        if settings.watermark_position == "top_left":
            x, y = margin, margin
        elif settings.watermark_position == "top_right":
            x, y = img.width - text_width - margin, margin
        elif settings.watermark_position == "bottom_left":
            x, y = margin, img.height - text_height - margin
        elif settings.watermark_position == "center":
            x, y = (img.width - text_width) // 2, (img.height - text_height) // 2
        else:  # bottom_right (默认)
            x, y = img.width - text_width - margin, img.height - text_height - margin
        
        # 绘制水印文字
        alpha = int(255 * settings.watermark_opacity)
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, alpha))
        
        # 合并图片和水�?
        watermarked = Image.alpha_composite(img, watermark)
        watermarked = watermarked.convert('RGB')
        
        # 生成临时文件路径
        temp_dir = tempfile.mkdtemp()
        temp_filename = f"watermarked_{photo_id}_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # 保存带水印的图片
        watermarked.save(temp_path, "JPEG", quality=85)
        
        return temp_path
        
    except Exception as e:
        print(f"水印添加失败: {e}")
        return image_path

def is_voting_time():
    """检查当前时间是否在投票时间范围�?""
    settings = get_settings()
    if not settings.allow_vote:
        return False, "投票功能已关�?
    
    from datetime import datetime
    now = datetime.now()
    
    # 检查投票开始时�?
    if settings.vote_start_time and now < settings.vote_start_time:
        return False, f"投票将于 {settings.vote_start_time.strftime('%Y-%m-%d %H:%M')} 开�?
    
    # 检查投票结束时�?
    if settings.vote_end_time and now > settings.vote_end_time:
        return False, f"投票已于 {settings.vote_end_time.strftime('%Y-%m-%d %H:%M')} 结束"
    
    return True, "可以投票"

def get_client_ip():
    """获取客户端真实IP地址"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.environ.get('REMOTE_ADDR', '127.0.0.1')

def check_ip_ban(ip_address):
    """检查IP是否被封�?""
    ban_record = IpBanRecord.query.filter_by(ip_address=ip_address, is_active=True).first()
    return ban_record is not None, ban_record

def ban_ip(ip_address, reason):
    """封禁IP地址"""
    existing_ban = IpBanRecord.query.filter_by(ip_address=ip_address).first()
    if existing_ban:
        existing_ban.is_active = True
        existing_ban.ban_reason = reason
        existing_ban.banned_at = db.func.current_timestamp()
    else:
        ban_record = IpBanRecord(ip_address=ip_address, ban_reason=reason)
        db.session.add(ban_record)
    db.session.commit()

def check_vote_frequency(ip_address):
    """检查IP投票频率是否超限"""
    settings = get_settings()
    if not settings.risk_control_enabled:
        return False, ""
    
    from datetime import datetime, timedelta
    time_threshold = datetime.now() - timedelta(minutes=settings.vote_time_window)
    
    # 统计该IP在时间窗口内的投票次�?
    vote_count = Vote.query.filter(
        Vote.ip_address == ip_address,
        Vote.created_at >= time_threshold
    ).count()
    
    if vote_count >= settings.max_votes_per_ip:
        return True, f"IP {ip_address} �?{settings.vote_time_window} 分钟内投票次数超�?{settings.max_votes_per_ip} �?
    
    return False, ""

def check_login_frequency(ip_address, user_id):
    """检查IP登录账号数量是否超限"""
    settings = get_settings()
    if not settings.risk_control_enabled:
        return False, ""
    
    from datetime import datetime, timedelta
    time_threshold = datetime.now() - timedelta(minutes=settings.account_time_window)
    
    # 统计该IP在时间窗口内登录的不同账号数�?
    unique_accounts = db.session.query(LoginRecord.user_id).filter(
        LoginRecord.ip_address == ip_address,
        LoginRecord.login_time >= time_threshold
    ).distinct().count()
    
    if unique_accounts >= settings.max_accounts_per_ip:
        return True, f"IP {ip_address} �?{settings.account_time_window} 分钟内登录账号数超过 {settings.max_accounts_per_ip} �?
    
    return False, ""

def auto_ban_users_by_ip(ip_address, reason):
    """根据IP自动封禁相关用户（管理员除外�?""
    from datetime import datetime, timedelta
    settings = get_settings()
    time_threshold = datetime.now() - timedelta(minutes=max(settings.vote_time_window, settings.account_time_window))
    
    # 获取该IP相关的所有用户（最近活动的�?
    related_users = db.session.query(User).join(LoginRecord).filter(
        LoginRecord.ip_address == ip_address,
        LoginRecord.login_time >= time_threshold,
        User.role < 2  # 排除管理�?
    ).distinct().all()
    
    banned_users = []
    for user in related_users:
        if user.is_active:
            user.is_active = False
            banned_users.append(user.real_name)
    
    if banned_users:
        db.session.commit()
    
    return banned_users

@app.route('/')
def index():
    photos = Photo.query.filter_by(status=1).all()  # 只显示已审核通过的照�?
    settings = get_settings()
    current_user = None
    user_has_voted = False
    user_voted_photo_id = None
    
    # 检查投票时�?
    can_vote_now, vote_message = is_voting_time()
    
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        # 检查用户是否仍然活�?
        if current_user and not current_user.is_active:
            session.clear()  # 清除session
            current_user = None
        elif current_user:
            # 检查用户是否已经投过票
            if settings.one_vote_per_user:
                existing_vote = Vote.query.filter_by(user_id=current_user.id).first()
                if existing_vote:
                    user_has_voted = True
                    user_voted_photo_id = existing_vote.photo_id
    
    return render_template('index.html', 
                         contest_title=settings.contest_title, 
                         photos=photos, 
                         current_user=current_user,
                         allow_vote=settings.allow_vote,
                         can_vote_now=can_vote_now,
                         vote_message=vote_message,
                         one_vote_per_user=settings.one_vote_per_user,
                         user_has_voted=user_has_voted,
                         user_voted_photo_id=user_voted_photo_id,
                         vote_start_time=settings.vote_start_time,
                         vote_end_time=settings.vote_end_time,
                         show_rankings=settings.show_rankings,
                         settings=settings)

# 添加所有其他路由函数（与app_test.py相同�?
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        real_name = request.form['real_name']
        password = request.form['password']
        client_ip = get_client_ip()
        
        # 检查IP是否被封�?
        is_banned, ban_record = check_ip_ban(client_ip)
        if is_banned:
            flash(f'该IP地址已被封禁：{ban_record.ban_reason}')
            return render_template('login.html')
        
        user = User.query.filter_by(real_name=real_name).first()
        
        if user:
            if not user.is_active:
                flash('账户已被禁用，请联系管理�?)
            elif check_password_hash(user.password_hash, password):
                # 记录登录信息
                login_record = LoginRecord(
                    user_id=user.id,
                    ip_address=client_ip,
                    user_agent=request.headers.get('User-Agent', '')
                )
                db.session.add(login_record)
                
                # 检查登录频率（仅对非管理员用户�?
                if user.role < 2:  # 非管理员
                    is_over_limit, limit_reason = check_login_frequency(client_ip, user.id)
                    if is_over_limit:
                        # 自动封禁相关用户和IP
                        banned_users = auto_ban_users_by_ip(client_ip, limit_reason)
                        ban_ip(client_ip, limit_reason)
                        
                        flash(f'检测到异常登录行为，已自动封禁相关账户：{", ".join(banned_users)}')
                        return render_template('login.html')
                
                db.session.commit()
                session['user_id'] = user.id
                session['school_id'] = user.school_id
                session['role'] = user.role
                return redirect(url_for('index'))
            else:
                flash('密码错误')
        else:
            flash('用户不存�?)
    
    settings = get_settings()
    return render_template('login.html', settings=settings)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name = request.form['real_name']
        school_id = request.form.get('school_id', '').strip()
        qq_number = request.form['qq_number']
        password = request.form['password']
        class_name = request.form['class_name']
        
        # 验证校学号（如果填写了）
        if school_id and not school_id.isdigit():
            flash('校学号必须为纯数�?)
            return render_template('register.html')
        
        # 验证QQ号是否为纯数字且长度合理
        if not qq_number.isdigit() or len(qq_number) < 5 or len(qq_number) > 15:
            flash('QQ号必须为5-15位数�?)
            return render_template('register.html')
        
        # 检查校学号是否已存在（如果填写了）
        if school_id and User.query.filter_by(school_id=school_id).first():
            flash('校学号已存在')
            return render_template('register.html')
        
        # 检查真实姓名是否已存在（因为现在用作登录账号）
        if User.query.filter_by(real_name=real_name).first():
            flash('真实姓名已存在，请使用不同的姓名')
            return render_template('register.html')
        
        user = User(
            real_name=real_name,
            school_id=school_id if school_id else None,
            qq_number=qq_number,
            password_hash=generate_password_hash(password),
            class_name=class_name,
            role=1  # 默认为普通用�?
        )
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        user = db.session.get(User, session['user_id'])
        
        # 验证当前密码
        if not check_password_hash(user.password_hash, current_password):
            flash('当前密码错误')
            return render_template('change_password.html')
        
        # 验证新密码长�?
        if len(new_password) < 6:
            flash('新密码长度至�?�?)
            return render_template('change_password.html')
        
        # 验证新密码确�?
        if new_password != confirm_password:
            flash('两次输入的新密码不一�?)
            return render_template('change_password.html')
        
        # 检查新密码与旧密码是否相同
        if check_password_hash(user.password_hash, new_password):
            flash('新密码不能与当前密码相同')
            return render_template('change_password.html')
        
        # 更新密码
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        flash('密码修改成功')
        return redirect(url_for('my_photos'))
    
    return render_template('change_password.html')

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    # 检查投票时�?
    can_vote_now, vote_message = is_voting_time()
    if not can_vote_now:
        return jsonify({'error': vote_message}), 403
        
    client_ip = get_client_ip()
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    
    # 检查IP是否被封�?
    is_banned, ban_record = check_ip_ban(client_ip)
    if is_banned:
        return jsonify({'error': f'该IP地址已被封禁：{ban_record.ban_reason}'}), 403
    
    # 检查投票频率（仅对非管理员用户�?
    if user.role < 2:  # 非管理员
        is_over_limit, limit_reason = check_vote_frequency(client_ip)
        if is_over_limit:
            # 自动封禁相关用户和IP
            banned_users = auto_ban_users_by_ip(client_ip, limit_reason)
            ban_ip(client_ip, limit_reason)
            
            return jsonify({
                'error': f'检测到异常投票行为，已自动封禁相关账户：{", ".join(banned_users)}'
            }), 403
        
    settings = get_settings()
    data = request.get_json()
    photo_id = data.get('photo_id')
    
    # 检查是否已经对此照片投过票
    existing_vote = Vote.query.filter_by(user_id=user_id, photo_id=photo_id).first()
    if existing_vote:
        return jsonify({'error': '您已经为此作品投过票�?}), 400
    
    # 如果启用�?每人只能投一�?限制，检查用户是否已经投过任何票
    if settings.one_vote_per_user:
        any_vote = Vote.query.filter_by(user_id=user_id).first()
        if any_vote:
            return jsonify({'error': '您已经投过票了，每人只能投一次票'}), 400
    
    photo = Photo.query.get(photo_id)
    if photo and photo.status == 1:  # 只能给已审核通过的照片投�?
        # 创建投票记录（包含IP地址�?
        vote = Vote(user_id=user_id, photo_id=photo_id, ip_address=client_ip)
        db.session.add(vote)
        
        # 更新票数
        photo.vote_count += 1
        db.session.commit()
        return jsonify({'vote_count': photo.vote_count})
    return jsonify({'error': 'not found'}), 404

@app.route('/cancel_vote', methods=['POST'])
@login_required
def cancel_vote():
    data = request.get_json()
    photo_id = data.get('photo_id')
    user_id = session['user_id']
    
    vote = Vote.query.filter_by(user_id=user_id, photo_id=photo_id).first()
    if vote:
        photo = Photo.query.get(photo_id)
        if photo:
            photo.vote_count -= 1
            db.session.delete(vote)
            db.session.commit()
            return jsonify({'vote_count': photo.vote_count})
    return jsonify({'error': 'not found'}), 404

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        files = request.files.getlist('photos')
        titles = request.form.getlist('titles')  # 获取作品名称列表
        user_id = session.get('user_id')
        
        if not user_id:
            flash('请先登录')
            return redirect(url_for('login'))
        
        # 从当前用户获取班级和姓名
        current_user = db.session.get(User, user_id)
        if not current_user:
            flash('用户不存�?)
            return redirect(url_for('login'))
            
        class_name = current_user.class_name
        student_name = current_user.real_name
        
        uploaded_count = 0
        for i, file in enumerate(files):
            if file and file.filename:
                # 获取对应的作品名称，如果没有提供则使用默认名�?
                title = titles[i] if i < len(titles) and titles[i].strip() else f"作品{i+1}"
                
                filename = secure_filename(file.filename)
                # 为每个文件生成唯一的文件名
                import time
                timestamp = str(int(time.time() * 1000))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}_{uploaded_count}{ext}"
                
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(save_path)
                
                # 生成缩略�?
                thumb_path = os.path.join(app.config['THUMB_FOLDER'], unique_filename)
                img = Image.open(save_path)
                img.thumbnail((180, 120))
                img.save(thumb_path)
                
                # 写入数据�?
                photo = Photo(
                    url='/' + save_path.replace('\\', '/'), 
                    thumb_url='/' + thumb_path.replace('\\', '/'), 
                    title=title,  # 添加作品名称
                    class_name=class_name, 
                    student_name=student_name,
                    user_id=user_id,
                    status=0  # 待审核状�?
                )
                db.session.add(photo)
                uploaded_count += 1
        
        db.session.commit()
        flash('照片上传成功，等待审�?)
        return redirect(url_for('index'))
    
    # GET请求时，传递用户信息到模板
    user_id = session.get('user_id')
    if user_id:
        current_user = db.session.get(User, user_id)
        return render_template('upload.html', current_user=current_user)
    else:
        flash('请先登录')
        return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    all_photos = Photo.query.order_by(Photo.vote_count.desc()).all()
    settings = get_settings()
    return render_template('admin.html', all_photos=all_photos, settings=settings)

@app.route('/admin/review')
@admin_required
def admin_review():
    pending_photos = Photo.query.filter_by(status=0).order_by(Photo.created_at.desc()).all()
    return render_template('admin_review.html', pending_photos=pending_photos)

@app.route('/approve_photo/<int:photo_id>')
@admin_required
def approve_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.status = 1
    db.session.commit()
    flash('照片审核通过')
    return redirect(request.referrer or url_for('admin_review'))

@app.route('/reject_photo/<int:photo_id>')
@admin_required
def reject_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.status = 2
    db.session.commit()
    flash('照片审核拒绝')
    return redirect(request.referrer or url_for('admin_review'))

@app.route('/admin_delete_photo/<int:photo_id>')
@admin_required
def admin_delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    
    # 删除文件
    if os.path.exists(photo.url[1:]):
        os.remove(photo.url[1:])
    if os.path.exists(photo.thumb_url[1:]):
        os.remove(photo.thumb_url[1:])
    
    # 删除投票记录
    Vote.query.filter_by(photo_id=photo_id).delete()
    
    # 删除照片记录
    db.session.delete(photo)
    db.session.commit()
    flash('照片删除成功')
    return redirect(request.referrer or url_for('admin'))

@app.route('/my_photos')
@login_required
def my_photos():
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id)
    my_photos = Photo.query.filter_by(user_id=user_id).order_by(Photo.created_at.desc()).all()
    return render_template('my_photos.html', my_photos=my_photos, current_user=current_user)

# 新增：排行榜页面
@app.route('/rankings')
@login_required
def rankings():
    settings = get_settings()
    
    # 检查是否允许查看排行榜
    if not settings.show_rankings:
        flash('排行榜功能已关闭')
        return redirect(url_for('index'))
    
    # 获取当前用户信息
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
    
    # 获取已通过审核的照片，按票数排�?
    photos = Photo.query.filter_by(status=1).order_by(Photo.vote_count.desc()).all()
    
    # 计算排名（处理并列情况）
    ranked_photos = []
    current_rank = 1
    prev_votes = None
    
    for index, photo in enumerate(photos):
        if prev_votes is not None and photo.vote_count != prev_votes:
            current_rank = index + 1
        
        ranked_photos.append({
            'rank': current_rank,
            'photo': photo,
            'is_tied': prev_votes == photo.vote_count if prev_votes is not None else False
        })
        
        prev_votes = photo.vote_count
    
    return render_template('rankings.html', 
                         contest_title=settings.contest_title,
                         ranked_photos=ranked_photos,
                         total_photos=len(photos),
                         current_user=current_user,
                         settings=settings)

# 协议管理相关路由
@app.route('/agreement_management')
@super_admin_required
def agreement_management():
    agreements = Agreement.query.all()
    return render_template('agreement_management.html', agreements=agreements)

@app.route('/add_agreement', methods=['GET', 'POST'])
@super_admin_required
def add_agreement():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        agreement_type = request.form['agreement_type']
        min_read_time = int(request.form.get('min_read_time', 10))
        
        agreement = Agreement(
            title=title,
            content=content,
            agreement_type=agreement_type,
            min_read_time=min_read_time
        )
        db.session.add(agreement)
        db.session.commit()
        
        flash('协议添加成功')
        return redirect(url_for('agreement_management'))
    
    return render_template('edit_agreement.html', agreement=None)

@app.route('/edit_agreement/<int:agreement_id>', methods=['GET', 'POST'])
@super_admin_required
def edit_agreement(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    
    if request.method == 'POST':
        agreement.title = request.form['title']
        agreement.content = request.form['content']
        agreement.agreement_type = request.form['agreement_type']
        agreement.min_read_time = int(request.form.get('min_read_time', 10))
        agreement.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('协议更新成功')
        return redirect(url_for('agreement_management'))
    
    return render_template('edit_agreement.html', agreement=agreement)

@app.route('/delete_agreement/<int:agreement_id>')
@super_admin_required
def delete_agreement(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    
    # 删除相关的用户协议记�?
    UserAgreementRecord.query.filter_by(agreement_id=agreement_id).delete()
    
    db.session.delete(agreement)
    db.session.commit()
    
    flash('协议删除成功')
    return redirect(url_for('agreement_management'))

@app.route('/view_agreement/<int:agreement_id>')
def view_agreement(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    if not agreement.is_active:
        return jsonify({'error': '协议不可�?}), 404
    
    # 传递用户信息以供防护逻辑使用
    return render_template('view_agreement.html', agreement=agreement)

@app.route('/api/record_agreement', methods=['POST'])
def record_agreement():
    """记录用户阅读协议"""
    data = request.get_json()
    agreement_id = data.get('agreement_id')
    read_time = data.get('read_time', 0)
    
    agreement = Agreement.query.get_or_404(agreement_id)
    
    # 检查阅读时间是否足�?
    if read_time < agreement.min_read_time:
        return jsonify({
            'success': False, 
            'message': f'需要阅读至少{agreement.min_read_time}�?,
            'required_time': agreement.min_read_time
        })
    
    # 记录协议阅读
    client_ip = get_client_ip()
    session_id = session.get('session_id')
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
    
    record = UserAgreementRecord(
        user_id=session.get('user_id'),
        agreement_id=agreement_id,
        ip_address=client_ip,
        read_time=read_time,
        session_id=session_id
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/check_agreement/<agreement_type>')
def check_agreement(agreement_type):
    """检查用户是否需要阅读协�?""
    agreement = Agreement.query.filter_by(
        agreement_type=agreement_type, 
        is_active=True
    ).first()
    
    if not agreement:
        return jsonify({'required': False})
    
    # 检查用户是否已经同意过协议
    client_ip = get_client_ip()
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    
    # 查找已有的协议记�?
    query = UserAgreementRecord.query.filter_by(agreement_id=agreement.id)
    
    if user_id:
        # 登录用户：检查用户ID
        query = query.filter_by(user_id=user_id)
    else:
        # 未登录用户：检查IP和session
        query = query.filter(
            (UserAgreementRecord.ip_address == client_ip) |
            (UserAgreementRecord.session_id == session_id)
        )
    
    existing_record = query.first()
    
    if existing_record:
        return jsonify({'required': False})
    
    return jsonify({
        'required': True,
        'agreement': {
            'id': agreement.id,
            'title': agreement.title,
            'content': agreement.content,
            'min_read_time': agreement.min_read_time
        }
    })

# 新增：导出Excel功能
@app.route('/admin/export_excel')
@admin_required
def export_excel():
    try:
        # 获取所有照片数�?
        photos = Photo.query.join(User, Photo.user_id == User.id).order_by(Photo.vote_count.desc()).all()
        
        # 准备数据
        data = []
        for photo in photos:
            data.append({
                '照片ID': photo.id,
                '作品名称': photo.title or '未命�?,
                '学生姓名': photo.student_name,
                '班级': photo.class_name,
                '票数': photo.vote_count,
                '上传时间': photo.created_at.strftime('%Y-%m-%d %H:%M:%S') if photo.created_at else '',
                '用户QQ�?: photo.user.qq_number,
                '校学�?: photo.user.school_id
            })
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='照片数据', index=False)
            
            # 获取工作表并设置列宽
            worksheet = writer.sheets['照片数据']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # 生成文件�?
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'photo_data_export_{timestamp}.xlsx'
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        flash(f'导出失败：{str(e)}')
        return redirect(url_for('admin'))

# 新增：单个图片下�?
@app.route('/admin/download_photo/<int:photo_id>')
@admin_required
def download_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    try:
        file_path = photo.url[1:]  # 去掉开头的 '/'
        if os.path.exists(file_path):
            # 获取原始文件名和扩展�?
            original_filename = os.path.basename(file_path)
            name, ext = os.path.splitext(original_filename)
            
            # 生成新的文件名：作品名称_学生姓名_照片ID.扩展�?
            safe_title = "".join(c for c in (photo.title or '未命�?) if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = "".join(c for c in photo.student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            download_filename = f"{safe_title}_{safe_name}_{photo.id}{ext}"
            
            return send_file(file_path, as_attachment=True, download_name=download_filename)
        else:
            flash('文件不存�?)
            return redirect(url_for('admin'))
    except Exception as e:
        flash(f'下载失败：{str(e)}')
        return redirect(url_for('admin'))

# 新增：全体图片打包下�?
@app.route('/admin/download_all_photos')
@admin_required
def download_all_photos():
    try:
        # 获取所有已通过审核的照�?
        photos = Photo.query.filter_by(status=1).all()
        
        if not photos:
            flash('没有可下载的照片')
            return redirect(url_for('admin'))
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'all_photos.zip')
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for photo in photos:
                    file_path = photo.url[1:]  # 去掉开头的 '/'
                    if os.path.exists(file_path):
                        # 生成ZIP内的文件�?
                        original_filename = os.path.basename(file_path)
                        name, ext = os.path.splitext(original_filename)
                        
                        safe_title = "".join(c for c in (photo.title or '未命�?) if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_name = "".join(c for c in photo.student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        zip_filename = f"{safe_title}_{safe_name}_{photo.id}{ext}"
                        
                        zipf.write(file_path, zip_filename)
            
            # 生成下载文件�?
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_filename = f'all_photos_{timestamp}.zip'
            
            def remove_temp_dir():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            response = send_file(zip_path, as_attachment=True, download_name=download_filename)
            # 注册清理函数（在响应发送后清理临时文件�?
            response.call_on_close(remove_temp_dir)
            
            return response
            
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e
            
    except Exception as e:
        flash(f'打包下载失败：{str(e)}')
        return redirect(url_for('admin'))

# 新增：批量选择图片下载
@app.route('/admin/download_selected_photos', methods=['POST'])
@admin_required
def download_selected_photos():
    try:
        # 获取选中的照片ID列表
        photo_ids = request.form.getlist('photo_ids')
        
        if not photo_ids:
            flash('请选择要下载的照片')
            return redirect(url_for('admin'))
        
        # 获取选中的照�?
        photos = Photo.query.filter(Photo.id.in_(photo_ids)).all()
        
        if not photos:
            flash('未找到选中的照�?)
            return redirect(url_for('admin'))
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'selected_photos.zip')
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for photo in photos:
                    file_path = photo.url[1:]  # 去掉开头的 '/'
                    if os.path.exists(file_path):
                        # 生成ZIP内的文件�?
                        original_filename = os.path.basename(file_path)
                        name, ext = os.path.splitext(original_filename)
                        
                        safe_title = "".join(c for c in (photo.title or '未命�?) if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_name = "".join(c for c in photo.student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        zip_filename = f"{safe_title}_{safe_name}_{photo.id}{ext}"
                        
                        zipf.write(file_path, zip_filename)
            
            # 生成下载文件�?
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_filename = f'selected_photos_{len(photos)}_items_{timestamp}.zip'
            
            def remove_temp_dir():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            response = send_file(zip_path, as_attachment=True, download_name=download_filename)
            response.call_on_close(remove_temp_dir)
            
            return response
            
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e
            
    except Exception as e:
        flash(f'批量下载失败：{str(e)}')
        return redirect(url_for('admin'))

# 新增：设置页�?
@app.route('/settings', methods=['GET', 'POST'])
@super_admin_required
def settings():
    settings = get_settings()
    
    if request.method == 'POST':
        from datetime import datetime
        
        settings.contest_title = request.form['contest_title']
        settings.allow_upload = 'allow_upload' in request.form
        settings.allow_vote = 'allow_vote' in request.form
        settings.one_vote_per_user = 'one_vote_per_user' in request.form
        settings.show_rankings = 'show_rankings' in request.form
        settings.icp_number = request.form.get('icp_number', '').strip()
        
        # 处理投票开始时�?
        vote_start_str = request.form.get('vote_start_time')
        if vote_start_str:
            try:
                settings.vote_start_time = datetime.strptime(vote_start_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('投票开始时间格式错�?)
                return redirect(url_for('settings'))
        else:
            settings.vote_start_time = None
        
        # 处理投票结束时间
        vote_end_str = request.form.get('vote_end_time')
        if vote_end_str:
            try:
                settings.vote_end_time = datetime.strptime(vote_end_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('投票结束时间格式错误')
                return redirect(url_for('settings'))
        else:
            settings.vote_end_time = None
        
        # 验证时间逻辑
        if settings.vote_start_time and settings.vote_end_time:
            if settings.vote_start_time >= settings.vote_end_time:
                flash('投票开始时间必须早于结束时�?)
                return redirect(url_for('settings'))
        
        # 处理风控设置
        settings.risk_control_enabled = 'risk_control_enabled' in request.form
        
        try:
            settings.max_votes_per_ip = int(request.form.get('max_votes_per_ip', 5))
            settings.vote_time_window = int(request.form.get('vote_time_window', 60))
            settings.max_accounts_per_ip = int(request.form.get('max_accounts_per_ip', 3))
            settings.account_time_window = int(request.form.get('account_time_window', 60))
        except ValueError:
            flash('风控参数必须为正整数')
            return redirect(url_for('settings'))
        
        # 验证风控参数
        if settings.max_votes_per_ip <= 0 or settings.vote_time_window <= 0 or \
           settings.max_accounts_per_ip <= 0 or settings.account_time_window <= 0:
            flash('风控参数必须为正整数')
            return redirect(url_for('settings'))
        
        # 处理水印设置
        settings.watermark_enabled = 'watermark_enabled' in request.form
        settings.watermark_text = request.form.get('watermark_text', '{contest_title}-{student_name}-{qq_number}')
        settings.watermark_position = request.form.get('watermark_position', 'bottom_right')
        
        try:
            settings.watermark_opacity = float(request.form.get('watermark_opacity', 0.3))
            settings.watermark_font_size = int(request.form.get('watermark_font_size', 20))
        except ValueError:
            flash('水印参数格式错误')
            return redirect(url_for('settings'))
        
        # 验证水印参数
        if not (0.1 <= settings.watermark_opacity <= 1.0):
            flash('水印透明度必须在0.1-1.0之间')
            return redirect(url_for('settings'))
        
        if settings.watermark_font_size <= 0 or settings.watermark_font_size > 100:
            flash('水印字体大小必须�?-100之间')
            return redirect(url_for('settings'))
        
        db.session.commit()
        flash('设置保存成功')
        return redirect(url_for('settings'))
    
    return render_template('settings.html', settings=settings)

# 安全的文件访问路�?- 保护uploads和thumbs目录
@app.route('/image/<int:photo_id>')
def get_image(photo_id):
    """获取带水印的原图 - 允许未登录用户访�?""
    photo = Photo.query.get_or_404(photo_id)
    
    # 只能查看已审核通过的照�?
    if photo.status != 1:
        return '', 404
    
    try:
        # 获取原始图片路径
        original_path = photo.url[1:]  # 去掉开头的 '/'
        
        if not os.path.exists(original_path):
            return '', 404
        
        # 生成带水印的图片
        watermarked_path = add_watermark_to_image(original_path, photo_id)
        
        def cleanup_temp_file():
            try:
                if watermarked_path != original_path and os.path.exists(watermarked_path):
                    os.remove(watermarked_path)
                    # 也删除临时目录（如果为空�?
                    temp_dir = os.path.dirname(watermarked_path)
                    try:
                        os.rmdir(temp_dir)
                    except:
                        pass
            except:
                pass
        
        response = send_file(watermarked_path, mimetype='image/jpeg')
        response.call_on_close(cleanup_temp_file)
        return response
        
    except Exception as e:
        print(f"获取水印图片失败: {e}")
        return '', 500

@app.route('/thumb/<int:photo_id>')
def get_thumb(photo_id):
    """获取不带水印的缩略图 - 允许未登录用户访�?""
    photo = Photo.query.get_or_404(photo_id)
    
    # 只能查看已审核通过的照�?
    if photo.status != 1:
        return '', 404
    
    try:
        # 获取缩略图路�?
        thumb_path = photo.thumb_url[1:]  # 去掉开头的 '/'
        
        if not os.path.exists(thumb_path):
            return '', 404
        
        # 直接返回缩略图，不添加水�?
        return send_file(thumb_path, mimetype='image/jpeg')
        
    except Exception as e:
        print(f"获取缩略图失�? {e}")
        return '', 500

@app.route('/static/uploads/<path:filename>')
def secure_uploaded_file(filename):
    if not session.get('user_id'):
        flash('请先登录')
        return redirect(url_for('login'))
    
    # 查找对应的照片记�?
    file_path = f'static/uploads/{filename}'
    photo = Photo.query.filter_by(url=f'/{file_path}').first()
    
    if not photo:
        flash('文件不存�?)
        return redirect(url_for('index'))
    
    current_user = db.session.get(User, session['user_id'])
    
    # 检查权限：管理员可以访问所有文件，普通用户只能访问自己的文件
    if current_user.role >= 2:  # 管理员或系统管理�?
        return send_file(file_path)
    elif photo.user_id == current_user.id:  # 用户只能访问自己的照�?
        return send_file(file_path)
    else:
        flash('您没有权限访问此文件')
        return redirect(url_for('index'))

@app.route('/static/thumbs/<path:filename>')
def secure_thumb_file(filename):
    if not session.get('user_id'):
        flash('请先登录')
        return redirect(url_for('login'))
    
    # 查找对应的照片记�?
    thumb_path = f'static/thumbs/{filename}'
    photo = Photo.query.filter_by(thumb_url=f'/{thumb_path}').first()
    
    if not photo:
        flash('文件不存�?)
        return redirect(url_for('index'))
    
    current_user = db.session.get(User, session['user_id'])
    
    # 检查权限：管理员可以访问所有缩略图，普通用户只能访问自己的缩略�?
    if current_user.role >= 2:  # 管理员或系统管理�?
        return send_file(thumb_path)
    elif photo.user_id == current_user.id:  # 用户只能访问自己的照片缩略图
        return send_file(thumb_path)
    else:
        flash('您没有权限访问此文件')
        return redirect(url_for('index'))

# 为用户添加下载自己照片的功能
@app.route('/download_my_photo/<int:photo_id>')
@login_required
def download_my_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    current_user = db.session.get(User, session['user_id'])
    
    # 检查权限：管理员可以下载所有照片，普通用户只能下载自己的照片
    if current_user.role < 2 and photo.user_id != current_user.id:
        flash('您只能下载自己的照片')
        return redirect(url_for('my_photos'))
    
    try:
        file_path = photo.url[1:]  # 去掉开头的 '/'
        if os.path.exists(file_path):
            # 生成安全的下载文件名
            original_filename = os.path.basename(file_path)
            name, ext = os.path.splitext(original_filename)
            
            # 生成新的文件名：作品名称_学生姓名_照片ID.扩展�?
            safe_title = "".join(c for c in (photo.title or '我的作品') if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = "".join(c for c in photo.student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            download_filename = f"{safe_title}_{safe_name}_{photo.id}{ext}"
            
            return send_file(file_path, as_attachment=True, download_name=download_filename)
        else:
            flash('文件不存�?)
            return redirect(url_for('my_photos'))
    except Exception as e:
        flash(f'下载失败：{str(e)}')
        return redirect(url_for('my_photos'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['THUMB_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
        
        # 创建预制管理员账�?
        admin_accounts = [
            {
                'real_name': '冯怀�?,
                'school_id': '24960023',
                'qq_number': '2069528060',
                'password': 'admin123',
                'class_name': '管理�?,
                'role': 3  # 系统管理�?
            }
        ]
        
        for admin_data in admin_accounts:
            if not User.query.filter_by(real_name=admin_data['real_name']).first():
                admin = User(
                    real_name=admin_data['real_name'],
                    school_id=admin_data['school_id'],
                    qq_number=admin_data['qq_number'],
                    password_hash=generate_password_hash(admin_data['password']),
                    class_name=admin_data['class_name'],
                    role=admin_data['role']
                )
                db.session.add(admin)
        
        # 创建默认协议
        if Agreement.query.count() == 0:
            # 用户注册协议
            register_agreement = Agreement(
                title="用户注册协议",
                agreement_type="register",
                content="""
<h2>用户注册协议</h2>
<p>欢迎您注册本摄影比赛平台！在使用本平台服务前，请您仔细阅读并同意以下条款�?/p>

<h3>1. 服务条款</h3>
<p>本平台为摄影爱好者提供作品展示和比赛参与服务。注册即表示您同意遵守平台的所有规则和条款�?/p>

<h3>2. 用户义务</h3>
<p>2.1 您需要提供真实、准确的个人信息�?/p>
<p>2.2 保护好您的账户密码，不得与他人共享；</p>
<p>2.3 遵守法律法规，不得发布违法违规内容�?/p>

<h3>3. 隐私保护</h3>
<p>我们将保护您的个人隐私，不会将您的个人信息泄露给第三方�?/p>

<h3>4. 免责声明</h3>
<p>平台不对因不可抗力因素导致的服务中断承担责任�?/p>

<p><strong>请您仔细阅读上述条款，注册即表示您完全同意并接受本协议的所有内容�?/strong></p>
                """.strip(),
                min_read_time=30,
                is_active=True
            )
            
            # 投稿协议
            upload_agreement = Agreement(
                title="作品投稿协议",
                agreement_type="upload",
                content="""
<h2>摄影作品投稿协议</h2>
<p>感谢您参与本次摄影比赛！在投稿前，请您仔细阅读并同意以下条款�?/p>

<h3>1. 作品要求</h3>
<p>1.1 投稿作品必须为您本人原创摄影作品�?/p>
<p>1.2 作品内容健康向上，不得包含违法违规内容；</p>
<p>1.3 作品格式为JPG、PNG等常见图片格式�?/p>

<h3>2. 版权声明</h3>
<p>2.1 您保证拥有投稿作品的完整版权�?/p>
<p>2.2 投稿即授权平台用于比赛展示、宣传等用途；</p>
<p>2.3 平台不会将您的作品用于商业用途�?/p>

<h3>3. 比赛规则</h3>
<p>3.1 评选结果由专业评委团队评定�?/p>
<p>3.2 比赛结果公布后不接受申诉�?/p>
<p>3.3 获奖作品将获得相应奖励�?/p>

<h3>4. 其他条款</h3>
<p>4.1 平台有权对违规作品进行处理；</p>
<p>4.2 参赛者需承担作品可能引起的法律责任�?/p>

<p><strong>投稿即表示您完全同意并接受本协议的所有内容，祝您在比赛中取得好成绩！</strong></p>
                """.strip(),
                min_read_time=45,
                is_active=True
            )
            
            db.session.add(register_agreement)
            db.session.add(upload_agreement)
        
        db.session.commit()
    app.run(debug=True)

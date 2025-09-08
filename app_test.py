from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import os
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///photos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['THUMB_FOLDER'] = 'static/thumbs'
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    real_name = db.Column(db.String(50), unique=True, nullable=False)  # 真实姓名，现在用作登录账号，必须唯一
    password_hash = db.Column(db.String(120), nullable=False)
    school_id = db.Column(db.String(20), unique=True, nullable=False)  # 校学号
    qq_number = db.Column(db.String(15), nullable=False)  # QQ号
    class_name = db.Column(db.String(50), nullable=False)  # 班级
    role = db.Column(db.Integer, default=1)  # 1=普通用户, 2=普通管理员, 3=系统管理员
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 关系定义
    photos = db.relationship('Photo', backref='user', lazy=True)
    votes = db.relationship('Vote', backref='user', lazy=True)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(128))
    thumb_url = db.Column(db.String(128))
    title = db.Column(db.String(100), nullable=True)  # 作品名称
    class_name = db.Column(db.String(32))
    student_name = db.Column(db.String(32))
    vote_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.Integer, default=0)  # 0=待审核, 1=已通过, 2=已拒绝
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
    contest_title = db.Column(db.String(100), default="2025年摄影比赛")
    allow_upload = db.Column(db.Boolean, default=True)
    allow_vote = db.Column(db.Boolean, default=True)
    one_vote_per_user = db.Column(db.Boolean, default=False)  # 限制每个用户只能投一次票
    vote_start_time = db.Column(db.DateTime, nullable=True)  # 投票开始时间
    vote_end_time = db.Column(db.DateTime, nullable=True)    # 投票结束时间
    
    # 风控设置
    risk_control_enabled = db.Column(db.Boolean, default=True)  # 是否启用风控
    max_votes_per_ip = db.Column(db.Integer, default=10)  # 单IP最大投票次数
    vote_time_window = db.Column(db.Integer, default=60)  # 投票时间窗口（分钟）
    max_accounts_per_ip = db.Column(db.Integer, default=5)  # 单IP最大登录账号数
    account_time_window = db.Column(db.Integer, default=1440)  # 账号登录时间窗口（分钟，默认24小时）

# 权限装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role < 2:
            flash('需要管理员权限')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role < 3:
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

def is_voting_time():
    """检查当前时间是否在投票时间范围内"""
    settings = get_settings()
    if not settings.allow_vote:
        return False, "投票功能已关闭"
    
    from datetime import datetime
    now = datetime.now()
    
    # 检查投票开始时间
    if settings.vote_start_time and now < settings.vote_start_time:
        return False, f"投票将于 {settings.vote_start_time.strftime('%Y-%m-%d %H:%M')} 开始"
    
    # 检查投票结束时间
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
    """检查IP是否被封禁"""
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
    
    # 统计该IP在时间窗口内的投票次数
    vote_count = Vote.query.filter(
        Vote.ip_address == ip_address,
        Vote.created_at >= time_threshold
    ).count()
    
    if vote_count >= settings.max_votes_per_ip:
        return True, f"IP {ip_address} 在 {settings.vote_time_window} 分钟内投票次数超过 {settings.max_votes_per_ip} 次"
    
    return False, ""

def check_login_frequency(ip_address, user_id):
    """检查IP登录账号数量是否超限"""
    settings = get_settings()
    if not settings.risk_control_enabled:
        return False, ""
    
    from datetime import datetime, timedelta
    time_threshold = datetime.now() - timedelta(minutes=settings.account_time_window)
    
    # 统计该IP在时间窗口内登录的不同账号数量
    unique_accounts = db.session.query(LoginRecord.user_id).filter(
        LoginRecord.ip_address == ip_address,
        LoginRecord.login_time >= time_threshold
    ).distinct().count()
    
    if unique_accounts >= settings.max_accounts_per_ip:
        return True, f"IP {ip_address} 在 {settings.account_time_window} 分钟内登录账号数超过 {settings.max_accounts_per_ip} 个"
    
    return False, ""

def auto_ban_users_by_ip(ip_address, reason):
    """根据IP自动封禁相关用户（管理员除外）"""
    from datetime import datetime, timedelta
    settings = get_settings()
    time_threshold = datetime.now() - timedelta(minutes=max(settings.vote_time_window, settings.account_time_window))
    
    # 获取该IP相关的所有用户（最近活动的）
    related_users = db.session.query(User).join(LoginRecord).filter(
        LoginRecord.ip_address == ip_address,
        LoginRecord.login_time >= time_threshold,
        User.role < 2  # 排除管理员
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
    photos = Photo.query.filter_by(status=1).all()  # 只显示已审核通过的照片
    settings = get_settings()
    current_user = None
    user_has_voted = False
    user_voted_photo_id = None
    
    # 检查投票时间
    can_vote_now, vote_message = is_voting_time()
    
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
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
                         vote_end_time=settings.vote_end_time)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        real_name = request.form['real_name']
        password = request.form['password']
        client_ip = get_client_ip()
        
        # 检查IP是否被封禁
        is_banned, ban_record = check_ip_ban(client_ip)
        if is_banned:
            flash(f'该IP地址已被封禁：{ban_record.ban_reason}')
            return render_template('login.html')
        
        user = User.query.filter_by(real_name=real_name).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            # 记录登录信息
            login_record = LoginRecord(
                user_id=user.id,
                ip_address=client_ip,
                user_agent=request.headers.get('User-Agent', '')
            )
            db.session.add(login_record)
            
            # 检查登录频率（仅对非管理员用户）
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
            flash('真实姓名或密码错误')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name = request.form['real_name']
        school_id = request.form['school_id']
        qq_number = request.form['qq_number']
        password = request.form['password']
        class_name = request.form['class_name']
        
        # 验证校学号是否为纯数字
        if not school_id.isdigit():
            flash('校学号必须为纯数字')
            return render_template('register.html')
        
        # 验证QQ号是否为纯数字且长度合理
        if not qq_number.isdigit() or len(qq_number) < 5 or len(qq_number) > 15:
            flash('QQ号必须为5-15位数字')
            return render_template('register.html')
        
        if User.query.filter_by(school_id=school_id).first():
            flash('校学号已存在')
            return render_template('register.html')
        
        # 检查真实姓名是否已存在（因为现在用作登录账号）
        if User.query.filter_by(real_name=real_name).first():
            flash('真实姓名已存在，请使用不同的姓名')
            return render_template('register.html')
        
        user = User(
            real_name=real_name,
            school_id=school_id,
            qq_number=qq_number,
            password_hash=generate_password_hash(password),
            class_name=class_name,
            role=1  # 默认为普通用户
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

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    # 检查投票时间
    can_vote_now, vote_message = is_voting_time()
    if not can_vote_now:
        return jsonify({'error': vote_message}), 403
        
    client_ip = get_client_ip()
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # 检查IP是否被封禁
    is_banned, ban_record = check_ip_ban(client_ip)
    if is_banned:
        return jsonify({'error': f'该IP地址已被封禁：{ban_record.ban_reason}'}), 403
    
    # 检查投票频率（仅对非管理员用户）
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
        return jsonify({'error': '您已经为此作品投过票了'}), 400
    
    # 如果启用了"每人只能投一票"限制，检查用户是否已经投过任何票
    if settings.one_vote_per_user:
        any_vote = Vote.query.filter_by(user_id=user_id).first()
        if any_vote:
            return jsonify({'error': '您已经投过票了，每人只能投一次票'}), 400
    
    photo = Photo.query.get(photo_id)
    if photo and photo.status == 1:  # 只能给已审核通过的照片投票
        # 创建投票记录（包含IP地址）
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
@login_required
def upload():
    settings = get_settings()
    if not settings.allow_upload:
        flash('上传功能已关闭')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        files = request.files.getlist('photos')
        titles = request.form.getlist('titles')  # 获取作品名称列表
        user_id = session['user_id']
        
        # 从当前用户获取班级和姓名
        current_user = User.query.get(user_id)
        class_name = current_user.class_name
        student_name = current_user.real_name
        
        uploaded_count = 0
        for i, file in enumerate(files):
            if file and file.filename:
                # 获取对应的作品名称，如果没有提供则使用默认名称
                title = titles[i] if i < len(titles) and titles[i].strip() else f"作品{i+1}"
                
                filename = secure_filename(file.filename)
                # 为每个文件生成唯一的文件名
                import time
                timestamp = str(int(time.time() * 1000))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}_{uploaded_count}{ext}"
                
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(save_path)
                
                # 生成缩略图
                thumb_path = os.path.join(app.config['THUMB_FOLDER'], unique_filename)
                img = Image.open(save_path)
                img.thumbnail((180, 120))
                img.save(thumb_path)
                
                # 写入数据库
                photo = Photo(
                    url='/' + save_path.replace('\\', '/'), 
                    thumb_url='/' + thumb_path.replace('\\', '/'), 
                    title=title,  # 添加作品名称
                    class_name=class_name, 
                    student_name=student_name,
                    user_id=user_id,
                    status=0  # 待审核状态
                )
                db.session.add(photo)
                uploaded_count += 1
        
        db.session.commit()
        flash('照片上传成功，等待审核')
        return redirect(url_for('my_photos'))
    
    # GET请求时，传递用户信息到模板
    user_id = session['user_id']
    current_user = User.query.get(user_id)
    return render_template('upload.html', current_user=current_user)

@app.route('/my_photos')
@login_required
def my_photos():
    user_id = session.get('user_id')
    my_photos = Photo.query.filter_by(user_id=user_id).order_by(Photo.created_at.desc()).all()
    return render_template('my_photos.html', my_photos=my_photos)

@app.route('/delete_photo/<int:photo_id>')
@login_required
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    user = User.query.get(session['user_id'])
    
    # 只允许照片所有者或管理员删除
    if photo.user_id == user.id or user.role >= 2:
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
    else:
        flash('无权限删除此照片')
    
    return redirect(url_for('my_photos'))

@app.route('/admin')
@admin_required
def admin():
    all_photos = Photo.query.order_by(Photo.vote_count.desc()).all()
    return render_template('admin.html', all_photos=all_photos)

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
        
        # 处理投票开始时间
        vote_start_str = request.form.get('vote_start_time')
        if vote_start_str:
            try:
                settings.vote_start_time = datetime.strptime(vote_start_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('投票开始时间格式错误')
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
                flash('投票开始时间必须早于结束时间')
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
        
        db.session.commit()
        flash('设置保存成功')
        return redirect(url_for('settings'))
    
    return render_template('settings.html', settings=settings)

@app.route('/manage_users')
@super_admin_required
def manage_users():
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
@super_admin_required
def add_user():
    if request.method == 'POST':
        real_name = request.form['real_name']
        school_id = request.form['school_id']
        qq_number = request.form['qq_number']
        password = request.form['password']
        class_name = request.form['class_name']
        role = int(request.form['role'])
        
        # 验证校学号是否为纯数字
        if not school_id.isdigit():
            flash('校学号必须为纯数字')
            return render_template('add_user.html')
        
        # 验证QQ号是否为纯数字且长度合理
        if not qq_number.isdigit() or len(qq_number) < 5 or len(qq_number) > 15:
            flash('QQ号必须为5-15位数字')
            return render_template('add_user.html')
        
        # 检查真实姓名是否已存在（因为现在用作登录账号）
        if User.query.filter_by(real_name=real_name).first():
            flash('真实姓名已存在，请使用不同的姓名')
            return render_template('add_user.html')
        
        # 创建新用户
        user = User(
            real_name=real_name,
            school_id=school_id,
            qq_number=qq_number,
            password_hash=generate_password_hash(password),
            class_name=class_name,
            role=role,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        flash(f'用户 {real_name}({school_id}) 添加成功')
        return redirect(url_for('manage_users'))
    
    return render_template('add_user.html')

@app.route('/change_user_role/<int:user_id>/<int:new_role>')
@super_admin_required
def change_user_role(user_id, new_role):
    user = User.query.get_or_404(user_id)
    if new_role in [1, 2, 3]:
        user.role = new_role
        db.session.commit()
        flash(f'用户 {user.real_name}({user.school_id}) 角色已更改')
    return redirect(url_for('manage_users'))

@app.route('/toggle_user_status/<int:user_id>')
@super_admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = '激活' if user.is_active else '禁用'
    flash(f'用户 {user.real_name}({user.school_id}) 已{status}')
    return redirect(url_for('manage_users'))

@app.route('/delete_user/<int:user_id>')
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 不能删除系统管理员
    if user.role == 3:
        flash('不能删除系统管理员')
        return redirect(url_for('manage_users'))
    
    # 不能删除自己
    current_user = User.query.get(session['user_id'])
    if user.id == current_user.id:
        flash('不能删除自己')
        return redirect(url_for('manage_users'))
    
    # 删除用户的照片和投票记录
    for photo in user.photos:
        # 删除照片文件
        if os.path.exists(photo.url[1:]):
            os.remove(photo.url[1:])
        if os.path.exists(photo.thumb_url[1:]):
            os.remove(photo.thumb_url[1:])
        # 删除相关投票记录
        Vote.query.filter_by(photo_id=photo.id).delete()
    
    # 删除用户的投票记录
    Vote.query.filter_by(user_id=user_id).delete()
    
    # 删除用户的照片记录
    Photo.query.filter_by(user_id=user_id).delete()
    
    # 删除用户
    username = f'{user.real_name}({user.school_id})'
    db.session.delete(user)
    db.session.commit()
    
    flash(f'用户 {username} 已删除')
    return redirect(url_for('manage_users'))

@app.route('/batch_user_action', methods=['POST'])
@super_admin_required
def batch_user_action():
    action = request.form.get('action')
    user_ids = request.form.getlist('user_ids')
    
    if not user_ids:
        flash('请选择要操作的用户')
        return redirect(url_for('manage_users'))
    
    user_ids = [int(uid) for uid in user_ids]
    current_user_id = session['user_id']
    
    if action == 'activate':
        count = 0
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and not user.is_active:
                user.is_active = True
                count += 1
        db.session.commit()
        flash(f'已激活 {count} 个用户')
        
    elif action == 'deactivate':
        count = 0
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and user.is_active and user.id != current_user_id:
                user.is_active = False
                count += 1
        db.session.commit()
        flash(f'已禁用 {count} 个用户')
        
    elif action == 'delete':
        count = 0
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and user.role != 3 and user.id != current_user_id:
                # 删除用户相关数据
                for photo in user.photos:
                    if os.path.exists(photo.url[1:]):
                        os.remove(photo.url[1:])
                    if os.path.exists(photo.thumb_url[1:]):
                        os.remove(photo.thumb_url[1:])
                    Vote.query.filter_by(photo_id=photo.id).delete()
                
                Vote.query.filter_by(user_id=user_id).delete()
                Photo.query.filter_by(user_id=user_id).delete()
                db.session.delete(user)
                count += 1
        db.session.commit()
        flash(f'已删除 {count} 个用户')
    
    return redirect(url_for('manage_users'))

@app.route('/ip_management')
@admin_required
def ip_management():
    from datetime import datetime, timedelta
    
    # 获取统计数据
    banned_ips_count = IpBanRecord.query.filter_by(is_active=True).count()
    total_login_records = LoginRecord.query.count()
    
    # 近24小时投票统计
    yesterday = datetime.now() - timedelta(days=1)
    recent_votes_count = Vote.query.filter(Vote.created_at >= yesterday).count()
    
    # 活跃IP数统计
    unique_ips_count = db.session.query(LoginRecord.ip_address).distinct().count()
    
    # 获取封禁IP列表
    banned_ips = IpBanRecord.query.order_by(IpBanRecord.banned_at.desc()).all()
    
    # 获取最近登录记录
    login_records = LoginRecord.query.join(User).order_by(LoginRecord.login_time.desc()).limit(100).all()
    
    # 投票分析数据
    vote_analysis_query = db.session.query(
        Vote.ip_address,
        db.func.count(Vote.id).label('vote_count'),
        db.func.max(Vote.created_at).label('last_vote_time'),
        db.func.count(db.func.distinct(Vote.user_id)).label('user_count')
    ).group_by(Vote.ip_address).order_by(db.func.count(Vote.id).desc()).all()
    
    vote_analysis = []
    for row in vote_analysis_query:
        vote_analysis.append({
            'ip_address': row.ip_address,
            'vote_count': row.vote_count,
            'last_vote_time': row.last_vote_time,
            'user_count': row.user_count
        })
    
    settings = get_settings()
    
    return render_template('ip_management.html',
                         banned_ips_count=banned_ips_count,
                         total_login_records=total_login_records,
                         recent_votes_count=recent_votes_count,
                         unique_ips_count=unique_ips_count,
                         banned_ips=banned_ips,
                         login_records=login_records,
                         vote_analysis=vote_analysis,
                         settings=settings)

@app.route('/ban_ip', methods=['POST'])
@admin_required
def ban_ip_route():
    ip_address = request.form['ip_address']
    reason = request.form['reason']
    
    ban_ip(ip_address, reason)
    
    # 封禁相关用户
    banned_users = auto_ban_users_by_ip(ip_address, reason)
    
    if banned_users:
        flash(f'IP {ip_address} 已封禁，同时封禁了相关账户：{", ".join(banned_users)}')
    else:
        flash(f'IP {ip_address} 已封禁')
    
    return redirect(url_for('ip_management'))

@app.route('/unban_ip/<int:ip_id>', methods=['POST'])
@admin_required
def unban_ip(ip_id):
    ban_record = IpBanRecord.query.get_or_404(ip_id)
    ban_record.is_active = False
    db.session.commit()
    
    flash(f'IP {ban_record.ip_address} 已解封')
    return redirect(url_for('ip_management'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['THUMB_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
        
        # 创建预制管理员账号
        admin_accounts = [
            {
                'real_name': '冯怀智',
                'school_id': '24960023',
                'qq_number': '2069528060',
                'password': 'admin123',
                'class_name': '管理组',
                'role': 3  # 系统管理员
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
        
        db.session.commit()
    app.run(debug=True)

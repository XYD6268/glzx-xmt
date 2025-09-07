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
    real_name = db.Column(db.String(50), nullable=False)  # 真实姓名
    password_hash = db.Column(db.String(120), nullable=False)
    school_id = db.Column(db.String(20), unique=True, nullable=False)  # 校学号作为登录账号
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

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contest_title = db.Column(db.String(100), default="2025年摄影比赛")
    allow_upload = db.Column(db.Boolean, default=True)
    allow_vote = db.Column(db.Boolean, default=True)
    one_vote_per_user = db.Column(db.Boolean, default=False)  # 限制每个用户只能投一次票

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

@app.route('/')
def index():
    photos = Photo.query.filter_by(status=1).all()  # 只显示已审核通过的照片
    settings = get_settings()
    current_user = None
    user_has_voted = False
    user_voted_photo_id = None
    
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
                         one_vote_per_user=settings.one_vote_per_user,
                         user_has_voted=user_has_voted,
                         user_voted_photo_id=user_voted_photo_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        school_id = request.form['school_id']
        password = request.form['password']
        user = User.query.filter_by(school_id=school_id).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            session['user_id'] = user.id
            session['school_id'] = user.school_id
            session['role'] = user.role
            return redirect(url_for('index'))
        else:
            flash('校学号或密码错误')
    
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
    settings = get_settings()
    if not settings.allow_vote:
        return jsonify({'error': '投票已关闭'}), 403
        
    data = request.get_json()
    photo_id = data.get('photo_id')
    user_id = session['user_id']
    
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
        # 创建投票记录
        vote = Vote(user_id=user_id, photo_id=photo_id)
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
        settings.contest_title = request.form['contest_title']
        settings.allow_upload = 'allow_upload' in request.form
        settings.allow_vote = 'allow_vote' in request.form
        settings.one_vote_per_user = 'one_vote_per_user' in request.form
        db.session.commit()
        flash('设置保存成功')
        return redirect(url_for('settings'))
    
    return render_template('settings.html', settings=settings)

@app.route('/manage_users')
@super_admin_required
def manage_users():
    users = User.query.all()
    return render_template('manage_users.html', users=users)

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

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['THUMB_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
        
        # 创建预制管理员账号
        admin_accounts = [
            {
                'real_name': '系统管理员',
                'school_id': '24960023',
                'qq_number': '2069528060',
                'password': 'admin123',
                'class_name': '管理组',
                'role': 3  # 系统管理员
            }
        ]
        
        for admin_data in admin_accounts:
            if not User.query.filter_by(school_id=admin_data['school_id']).first():
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

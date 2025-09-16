"""
路由定义 - SQLite简化版
"""
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid
from datetime import datetime
from functools import wraps
from app.models.user import User
from app.models.photo import Photo, Vote
from app.models.settings import Settings
from app.services.cache_service import (
    get_settings_cached, get_approved_photos_cached, 
    get_photo_rankings_cached, get_user_cached,
    invalidate_settings_cache, invalidate_photo_cache, invalidate_user_cache
)

bp = Blueprint('main', __name__)

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTO_UPLOAD_DIR = os.path.join(BASE_DIR, 'photo', 'uploads')
PHOTO_THUMB_DIR = os.path.join(BASE_DIR, 'photo', 'thumbs')

# 确保目录存在
os.makedirs(PHOTO_UPLOAD_DIR, exist_ok=True)
os.makedirs(PHOTO_THUMB_DIR, exist_ok=True)

# 权限装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login'))
        
        # 检查用户是否仍然活跃
        user = get_user_cached(session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理员')
            return redirect(url_for('main.login'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login'))
        
        user = get_user_cached(session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理员')
            return redirect(url_for('main.login'))
        elif user.role < 2:
            flash('需要管理员权限')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login'))
        
        user = get_user_cached(session['user_id'])
        if not user or not user.is_active:
            session.clear()  # 清除session
            flash('账户已被禁用，请联系管理员')
            return redirect(url_for('main.login'))
        elif user.role < 3:
            flash('需要系统管理员权限')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_settings():
    """获取系统设置"""
    return get_settings_cached()

def is_voting_time():
    """检查当前时间是否在投票时间范围内"""
    settings = get_settings()
    if not settings.allow_vote:
        return False, "投票功能已关闭"
    
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

@bp.route('/')
def index():
    photos = get_approved_photos_cached()
    settings = get_settings()
    current_user = None
    user_has_voted = False
    user_voted_photo_id = None
    
    # 检查投票时间
    can_vote_now, vote_message = is_voting_time()
    
    if 'user_id' in session:
        current_user = get_user_cached(session['user_id'])
        # 检查用户是否仍然活跃
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

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        real_name = request.form['real_name']
        password = request.form['password']
        client_ip = get_client_ip()
        
        user = User.query.filter_by(real_name=real_name).first()
        
        if user:
            if not user.is_active:
                flash('账户已被禁用，请联系管理员')
                return render_template('login.html')
            elif check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['school_id'] = user.school_id
                session['role'] = user.role
                return redirect(url_for('main.index'))
            else:
                flash('密码错误')
        else:
            flash('用户不存在')
    
    settings = get_settings()
    return render_template('login.html', settings=settings)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name = request.form['real_name']
        school_id = request.form.get('school_id', '').strip()
        qq_number = request.form['qq_number']
        password = request.form['password']
        class_name = request.form['class_name']
        
        # 验证校学号（如果填写了）
        if school_id and not school_id.isdigit():
            flash('校学号必须为纯数字')
            return render_template('register.html')
        
        # 验证QQ号是否为纯数字且长度合理
        if not qq_number.isdigit() or len(qq_number) < 5 or len(qq_number) > 15:
            flash('QQ号必须为5-15位数字')
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
            role=1  # 默认为普通用户
        )
        from app.models.base import db
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        from app.models.base import db
        user = User.query.get(session['user_id'])
        
        # 验证当前密码
        if not check_password_hash(user.password_hash, current_password):
            flash('当前密码错误')
            return render_template('change_password.html')
        
        # 验证新密码长度
        if len(new_password) < 6:
            flash('新密码长度至少6位')
            return render_template('change_password.html')
        
        # 验证新密码确认
        if new_password != confirm_password:
            flash('两次输入的新密码不一致')
            return render_template('change_password.html')
        
        # 检查新密码与旧密码是否相同
        if check_password_hash(user.password_hash, new_password):
            flash('新密码不能与当前密码相同')
            return render_template('change_password.html')
        
        # 更新密码
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        flash('密码修改成功')
        return redirect(url_for('main.my_photos'))
    
    return render_template('change_password.html')

@bp.route('/vote', methods=['POST'])
@login_required
def vote():
    # 检查投票时间
    can_vote_now, vote_message = is_voting_time()
    if not can_vote_now:
        return jsonify({'error': vote_message}), 403
        
    client_ip = get_client_ip()
    user_id = session['user_id']
    user = User.query.get(user_id)
    
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
        from app.models.base import db
        db.session.add(vote)
        
        # 更新票数
        photo.vote_count += 1
        db.session.commit()
        
        # 清除相关缓存
        invalidate_photo_cache()
        
        return jsonify({'vote_count': photo.vote_count})
    return jsonify({'error': 'not found'}), 404

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    settings = get_settings()
    if not settings.allow_upload:
        flash('上传功能已关闭')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        files = request.files.getlist('photos')
        titles = request.form.getlist('titles')  # 获取作品名称列表
        user_id = session['user_id']
        
        # 从当前用户获取班级和姓名
        current_user = User.query.get(user_id)
        class_name = current_user.class_name
        student_name = current_user.real_name
        
        uploaded_count = 0
        from app.models.base import db
        for i, file in enumerate(files):
            if file and file.filename:
                # 获取对应的作品名称，如果没有提供则使用默认名称
                title = titles[i] if i < len(titles) and titles[i].strip() else f"作品{i+1}"
                
                filename = secure_filename(file.filename)
                # 为每个文件生成唯一的文件名
                name, ext = os.path.splitext(filename)
                
                # 生成安全的标题和姓名
                safe_title = "".join(c for c in (title or '未命名') if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                
                # 使用与下载时一致的命名规则：作品名称_学生姓名_唯一标识.扩展名
                unique_id = uuid.uuid4().hex[:8]  # 使用UUID的一部分确保唯一性
                unique_filename = f"{safe_title}_{safe_name}_{unique_id}{ext}"
                
                save_path = os.path.join(PHOTO_UPLOAD_DIR, unique_filename)
                file.save(save_path)
                
                # 生成缩略图
                thumb_path = os.path.join(PHOTO_THUMB_DIR, unique_filename)
                img = Image.open(save_path)
                img.thumbnail((2560, 1440))
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
        
        # 清除相关缓存
        invalidate_photo_cache()
        
        flash('照片上传成功，等待审核')
        return redirect(url_for('main.my_photos'))
    
    # GET请求时，传递用户信息到模板
    user_id = session['user_id']
    current_user = User.query.get(user_id)
    return render_template('upload.html', current_user=current_user)

@bp.route('/my_photos')
@login_required
def my_photos():
    user_id = session.get('user_id')
    current_user = User.query.get(user_id)
    my_photos = Photo.query.filter_by(user_id=user_id).order_by(Photo.created_at.desc()).all()
    return render_template('my_photos.html', my_photos=my_photos, current_user=current_user)

@bp.route('/rankings')
@login_required
def rankings():
    settings = get_settings()
    
    # 检查是否允许查看排行榜
    if not settings.show_rankings:
        flash('排行榜功能已关闭')
        return redirect(url_for('main.index'))
    
    # 获取当前用户信息
    current_user = None
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
    
    # 获取已通过审核的照片，按票数排序
    photos = get_photo_rankings_cached()
    
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

@bp.route('/delete_photo/<int:photo_id>')
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
        from app.models.base import db
        db.session.delete(photo)
        db.session.commit()
        
        # 清除相关缓存
        invalidate_photo_cache(photo_id)
        
        flash('照片删除成功')
    else:
        flash('无权限删除此照片')
    
    return redirect(url_for('main.my_photos'))

@bp.route('/admin')
@admin_required
def admin():
    all_photos = Photo.query.order_by(Photo.vote_count.desc()).all()
    settings = get_settings()
    return render_template('admin.html', all_photos=all_photos, settings=settings)

@bp.route('/admin/review')
@admin_required
def admin_review():
    pending_photos = Photo.query.filter_by(status=0).order_by(Photo.created_at.desc()).all()
    return render_template('admin_review.html', pending_photos=pending_photos)

@bp.route('/approve_photo/<int:photo_id>')
@admin_required
def approve_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.status = 1
    from app.models.base import db
    db.session.commit()
    
    # 清除相关缓存
    invalidate_photo_cache()
    
    flash('照片审核通过')
    return redirect(request.referrer or url_for('main.admin_review'))

@bp.route('/reject_photo/<int:photo_id>')
@admin_required
def reject_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.status = 2
    from app.models.base import db
    db.session.commit()
    
    # 清除相关缓存
    invalidate_photo_cache()
    
    flash('照片审核拒绝')
    return redirect(request.referrer or url_for('main.admin_review'))

@bp.route('/admin_delete_photo/<int:photo_id>')
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
    from app.models.base import db
    db.session.delete(photo)
    db.session.commit()
    
    # 清除相关缓存
    invalidate_photo_cache(photo_id)
    
    flash('照片删除成功')
    return redirect(request.referrer or url_for('main.admin'))
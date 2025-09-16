"""
认证路由 - 高性能版
"""
from flask import Blueprint, request, session, flash, redirect, url_for, render_template
from services.auth_service import AuthService
from utils.decorators import login_required, rate_limit

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@rate_limit(max_requests=20, window=300)  # 5分钟内最多20次尝试
def login():
    """用户登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        user, message = AuthService.login_user(username, password, ip_address, user_agent)
        
        if user:
            session['user_id'] = str(user.id)
            session['user_name'] = user.real_name
            session['user_role'] = user.role
            flash(message, 'success')
            return redirect(url_for('photos.index'))
        else:
            flash(message, 'error')
    
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@rate_limit(max_requests=10, window=600)  # 10分钟内最多10次注册
def register():
    """用户注册"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        school_id = request.form.get('school_id', '').strip()
        qq_number = request.form.get('qq_number', '').strip()
        class_name = request.form.get('class_name', '').strip()
        ip_address = request.remote_addr
        
        user, message = AuthService.register_user(
            username, password, school_id, qq_number, class_name, ip_address
        )
        
        if user:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'error')
    
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('photos.index'))


@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
@rate_limit(max_requests=5, window=300)
def change_password():
    """修改密码"""
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        
        success, message = AuthService.change_password(
            session['user_id'], old_password, new_password
        )
        
        if success:
            flash(message, 'success')
            return redirect(url_for('photos.index'))
        else:
            flash(message, 'error')
    
    return render_template('change_password.html')
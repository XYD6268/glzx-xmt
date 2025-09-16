"""
认证路由 - 高性能版
"""
from flask import Blueprint, request, session, flash, redirect, url_for, render_template
from app.services.auth_service import AuthService
from app.services.security_service import SecurityService
from app.utils.decorators import login_required, rate_limit

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
        
        # 输入验证
        is_valid, message = SecurityService.validate_input(username, 'username')
        if not is_valid:
            flash(message, 'error')
            return render_template('login.html')
        
        is_valid, message = SecurityService.validate_input(password, 'password')
        if not is_valid:
            flash(message, 'error')
            return render_template('login.html')
        
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
        
        # 输入验证
        is_valid, message = SecurityService.validate_input(username, 'username')
        if not is_valid:
            flash(message, 'error')
            return render_template('register.html')
        
        is_valid, message = SecurityService.validate_input(password, 'password')
        if not is_valid:
            flash(message, 'error')
            return render_template('register.html')
        
        is_valid, message = SecurityService.validate_input(school_id, 'school_id')
        if not is_valid:
            flash(message, 'error')
            return render_template('register.html')
        
        is_valid, message = SecurityService.validate_input(qq_number, 'qq_number')
        if not is_valid:
            flash(message, 'error')
            return render_template('register.html')
        
        is_valid, message = SecurityService.validate_input(class_name, 'class_name')
        if not is_valid:
            flash(message, 'error')
            return render_template('register.html')
        
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
        
        # 输入验证
        is_valid, message = SecurityService.validate_input(new_password, 'password')
        if not is_valid:
            flash(message, 'error')
            return render_template('change_password.html')
        
        success, message = AuthService.change_password(
            session['user_id'], old_password, new_password
        )
        
        if success:
            # 记录安全事件
            SecurityService.record_security_event('password_changed', 
                                             user_id=session['user_id'], 
                                             ip_address=request.remote_addr)
            flash(message, 'success')
            return redirect(url_for('photos.index'))
        else:
            flash(message, 'error')
    
    return render_template('change_password.html')
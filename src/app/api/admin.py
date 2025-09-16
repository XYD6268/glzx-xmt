"""
管理员路由 - 高性能版
"""
from flask import Blueprint, request, render_template, jsonify, session, flash, redirect, url_for, send_file
from app.services.photo_service import PhotoService
from app.services.auth_service import AuthService
from app.models.user import User
from app.models.settings import Settings
from app.utils.decorators import admin_required, rate_limit
import tempfile
import zipfile
import os

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@admin_required
def dashboard():
    """管理员仪表板"""
    # 获取统计信息
    photo_stats = PhotoService.get_photo_statistics()
    
    # 获取待审核照片数量
    pending_photos = PhotoService.get_pending_photos(limit=10)
    
    # 获取最近用户
    recent_users = User.get_active_users(limit=10)
    
    return render_template('admin.html',
                         stats=photo_stats,
                         pending_photos=pending_photos,
                         recent_users=recent_users)


@admin_bp.route('/review')
@admin_required
def review_photos():
    """照片审核"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 获取待审核照片
    pending_photos = PhotoService.get_pending_photos(limit=per_page)
    
    return render_template('admin_review.html', photos=pending_photos)


@admin_bp.route('/approve/<photo_id>', methods=['POST'])
@admin_required
@rate_limit(max_requests=100, window=60)
def approve_photo(photo_id):
    """审核通过照片"""
    success, message = PhotoService.approve_photo(photo_id, session['user_id'])
    
    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': success, 'message': message})
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.review_photos'))


@admin_bp.route('/reject/<photo_id>', methods=['POST'])
@admin_required
@rate_limit(max_requests=100, window=60)
def reject_photo(photo_id):
    """拒绝照片"""
    reason = request.form.get('reason', '')
    success, message = PhotoService.reject_photo(photo_id, session['user_id'], reason)
    
    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': success, 'message': message})
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.review_photos'))


@admin_bp.route('/batch_approve', methods=['POST'])
@admin_required
def batch_approve():
    """批量审核"""
    photo_ids = request.form.getlist('photo_ids')
    
    if not photo_ids:
        flash('请选择要审核的照片', 'warning')
        return redirect(url_for('admin.review_photos'))
    
    success_count, message = PhotoService.batch_approve_photos(photo_ids, session['user_id'])
    
    flash(message, 'success' if success_count > 0 else 'error')
    return redirect(url_for('admin.review_photos'))


@admin_bp.route('/users')
@admin_required
def manage_users():
    """用户管理"""
    search = request.args.get('search', '').strip()
    
    if search:
        users = User.search_users(search, limit=50)
    else:
        users = User.get_active_users(limit=50)
    
    return render_template('manage_users.html', users=users, search=search)


@admin_bp.route('/users/<user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """切换用户状态"""
    try:
        user = User.get_by_id(user_id)
        if not user:
            flash('用户不存在', 'error')
            return redirect(url_for('admin.manage_users'))
        
        user.is_active = not user.is_active
        user.save()
        
        status = '启用' if user.is_active else '禁用'
        flash(f'已{status}用户: {user.real_name}', 'success')
        
    except Exception as e:
        flash(f'操作失败: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def system_settings():
    """系统设置"""
    settings = Settings.get_current()
    
    if request.method == 'POST':
        try:
            # 更新基础设置
            settings.contest_title = request.form.get('contest_title', '').strip()
            settings.allow_upload = 'allow_upload' in request.form
            settings.allow_vote = 'allow_vote' in request.form
            settings.one_vote_per_user = 'one_vote_per_user' in request.form
            settings.show_rankings = 'show_rankings' in request.form
            settings.icp_number = request.form.get('icp_number', '').strip()
            
            # 更新风控设置
            settings.risk_control_enabled = 'risk_control_enabled' in request.form
            settings.max_votes_per_ip = int(request.form.get('max_votes_per_ip', 10))
            settings.vote_time_window = int(request.form.get('vote_time_window', 60))
            settings.max_accounts_per_ip = int(request.form.get('max_accounts_per_ip', 5))
            settings.account_time_window = int(request.form.get('account_time_window', 1440))
            
            # 更新水印设置
            settings.watermark_enabled = 'watermark_enabled' in request.form
            settings.watermark_text = request.form.get('watermark_text', '').strip()
            settings.watermark_opacity = float(request.form.get('watermark_opacity', 0.3))
            settings.watermark_position = request.form.get('watermark_position', 'bottom_right')
            settings.watermark_font_size = int(request.form.get('watermark_font_size', 20))
            
            settings.save()
            
            # 清除设置缓存
            from services.cache_service import invalidate_settings_cache
            invalidate_settings_cache()
            
            flash('设置已保存', 'success')
            
        except Exception as e:
            flash(f'保存失败: {str(e)}', 'error')
    
    return render_template('settings.html', settings=settings)


@admin_bp.route('/export/photos')
@admin_required
def export_photos():
    """导出照片数据"""
    try:
        # 获取所有已审核的照片
        photos = PhotoService.get_approved_photos(limit=1000)
        
        # 创建临时ZIP文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_file.name, 'w') as zipf:
            # 添加照片信息CSV
            csv_content = "ID,标题,学生姓名,班级,投票数,上传时间\n"
            for photo in photos:
                csv_content += f"{photo.id},{photo.title},{photo.student_name},{photo.class_name},{photo.vote_count},{photo.created_at}\n"
            
            zipf.writestr('photos.csv', csv_content.encode('utf-8'))
            
            # 可以选择性地添加实际图片文件
            # for photo in photos[:10]:  # 限制数量避免文件过大
            #     if os.path.exists(photo.url.lstrip('/')):
            #         zipf.write(photo.url.lstrip('/'), os.path.basename(photo.url))
        
        return send_file(temp_file.name, 
                        as_attachment=True, 
                        download_name='photos_export.zip',
                        mimetype='application/zip')
        
    except Exception as e:
        flash(f'导出失败: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/api/stats')
@admin_required
def get_stats():
    """获取统计数据API"""
    stats = PhotoService.get_photo_statistics()
    
    # 添加更多统计信息
    user_count = User.query.filter_by(is_active=True).count()
    total_users = User.query.count()
    
    stats.update({
        'active_users': user_count,
        'total_users': total_users,
        'inactive_users': total_users - user_count
    })
    
    return jsonify(stats)
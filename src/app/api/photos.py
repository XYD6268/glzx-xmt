"""
照片路由 - 高性能版
"""
from flask import Blueprint, request, render_template, jsonify, session, flash, redirect, url_for
from app.services.photo_service import PhotoService
from app.services.vote_service import VoteService
from app.services.cache_service import cached, cache_response
from app.utils.decorators import login_required, rate_limit, get_current_user
from app.models.settings import Settings

photos_bp = Blueprint('photos', __name__)


@photos_bp.route('/')
@rate_limit(max_requests=30, window=60)  # 基础频率限制
@cache_response(timeout=180, key_prefix='index')
def index():
    """首页 - 高性能优化"""
    # 1. 缓存获取照片列表
    photos = PhotoService.get_approved_photos(limit=50)
    
    # 2. 获取系统设置（缓存）
    settings = Settings.get_current()
    
    # 3. 获取排行榜（缓存）
    rankings = PhotoService.get_photo_rankings(limit=10)
    
    # 4. 用户信息
    current_user = get_current_user()
    
    # 5. 统计信息（缓存）
    stats = PhotoService.get_photo_statistics()
    
    return render_template('index.html', 
                         photos=photos, 
                         settings=settings,
                         rankings=rankings,
                         current_user=current_user,
                         stats=stats)


@photos_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@rate_limit(max_requests=10, window=300)  # 上传限制
def upload():
    """照片上传 - 异步处理"""
    if request.method == 'POST':
        files = request.files.getlist('photos')
        titles = request.form.getlist('titles')
        ip_address = request.remote_addr
        
        if not files or not files[0].filename:
            flash('请选择要上传的文件', 'error')
            return redirect(url_for('photos.upload'))
        
        results = []
        success_count = 0
        
        for i, file in enumerate(files):
            if file and file.filename:
                title = titles[i] if i < len(titles) else None
                photo, message = PhotoService.upload_photo(
                    file, session['user_id'], title, ip_address
                )
                results.append({'success': photo is not None, 'message': message})
                if photo:
                    success_count += 1
        
        if success_count > 0:
            flash(f'成功上传 {success_count} 张照片', 'success')
        else:
            flash('上传失败', 'error')
        
        return redirect(url_for('photos.my_photos'))
    
    # 检查上传权限
    settings = Settings.get_current()
    if not settings.is_upload_allowed():
        flash('当前不允许上传照片', 'warning')
        return redirect(url_for('photos.index'))
    
    return render_template('upload.html')


@photos_bp.route('/my_photos')
@login_required
@cached(timeout=60, key_prefix='user_photos')
def my_photos():
    """我的照片"""
    user_photos = PhotoService.get_user_photos(session['user_id'])
    return render_template('my_photos.html', photos=user_photos)


@photos_bp.route('/rankings')
@cache_response(timeout=120, key_prefix='rankings')
def rankings():
    """排行榜"""
    settings = Settings.get_current()
    
    if not settings.show_rankings:
        flash('排行榜暂不开放', 'info')
        return redirect(url_for('photos.index'))
    
    # 获取排行榜数据
    top_photos = PhotoService.get_photo_rankings(limit=50)
    
    # 获取统计信息
    stats = PhotoService.get_photo_statistics()
    
    return render_template('rankings.html', 
                         photos=top_photos, 
                         stats=stats,
                         settings=settings)


@photos_bp.route('/search')
@rate_limit(max_requests=20, window=60)
def search():
    """搜索照片"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return render_template('search.html', photos=[], query='')
    
    if len(query) < 2:
        flash('搜索关键词至少2个字符', 'warning')
        return render_template('search.html', photos=[], query=query)
    
    # 高性能搜索
    results = PhotoService.search_photos(query, limit=30)
    
    return render_template('search.html', 
                         photos=results, 
                         query=query,
                         result_count=len(results))


@photos_bp.route('/vote/<photo_id>', methods=['POST'])
@login_required
@rate_limit(max_requests=30, window=60)
def vote_photo(photo_id):
    """投票"""
    ip_address = request.remote_addr
    
    success, message = VoteService.vote_for_photo(
        session['user_id'], photo_id, ip_address
    )
    
    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': success, 'message': message})
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('photos.index'))


@photos_bp.route('/cancel_vote/<photo_id>', methods=['POST'])
@login_required
@rate_limit(max_requests=20, window=60)
def cancel_vote(photo_id):
    """取消投票"""
    success, message = VoteService.cancel_vote(session['user_id'], photo_id)
    
    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': success, 'message': message})
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('photos.index'))


@photos_bp.route('/delete/<photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    """删除照片"""
    success, message = PhotoService.delete_photo(photo_id, session['user_id'])
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('photos.my_photos'))


# AJAX API 路由
@photos_bp.route('/api/vote_status/<photo_id>')
@login_required
def get_vote_status(photo_id):
    """获取投票状态"""
    has_voted = VoteService.check_user_vote_status(session['user_id'], photo_id)
    return jsonify({'has_voted': has_voted})


@photos_bp.route('/api/ip_vote_status')
@rate_limit(max_requests=10, window=60)
def get_ip_vote_status():
    """获取IP投票状态"""
    ip_address = request.remote_addr
    status = VoteService.get_ip_vote_status(ip_address)
    return jsonify(status)


@photos_bp.route('/api/user_vote_summary')
@login_required
def get_user_vote_summary():
    """获取用户投票摘要"""
    summary = VoteService.get_user_vote_summary(session['user_id'])
    return jsonify(summary)
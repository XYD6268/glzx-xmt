"""
高性能API路由
"""
from flask import Blueprint, request, jsonify, session
from services.photo_service import PhotoService
from services.vote_service import VoteService
from services.auth_service import AuthService
from services.cache_service import cached
from utils.decorators import login_required, rate_limit
from models.settings import Settings
import logging

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


# 公开API
@api_bp.route('/photos')
@rate_limit(max_requests=60, window=60)
@cached(timeout=180, key_prefix='api_photos')
def get_photos():
    """获取照片列表API"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)  # 最大100
        offset = (page - 1) * limit
        
        photos = PhotoService.get_approved_photos(limit=limit, offset=offset)
        
        return jsonify({
            'success': True,
            'data': [photo.to_dict() for photo in photos],
            'pagination': {
                'page': page,
                'limit': limit,
                'has_more': len(photos) == limit
            }
        })
        
    except Exception as e:
        logger.error(f"API获取照片失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/photos/search')
@rate_limit(max_requests=30, window=60)
def search_photos():
    """搜索照片API"""
    try:
        query = request.args.get('q', '').strip()
        limit = min(request.args.get('limit', 20, type=int), 50)
        
        if not query or len(query) < 2:
            return jsonify({
                'success': False,
                'error': 'Search query must be at least 2 characters'
            }), 400
        
        results = PhotoService.search_photos(query, limit=limit)
        
        return jsonify({
            'success': True,
            'data': [photo.to_dict() for photo in results],
            'query': query,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"API搜索失败: {e}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500


@api_bp.route('/photos/rankings')
@rate_limit(max_requests=30, window=60)
@cached(timeout=120, key_prefix='api_rankings')
def get_rankings():
    """获取排行榜API"""
    try:
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        settings = Settings.get_current()
        if not settings.show_rankings:
            return jsonify({
                'success': False,
                'error': 'Rankings not available'
            }), 403
        
        rankings = PhotoService.get_photo_rankings(limit=limit)
        
        return jsonify({
            'success': True,
            'data': [photo.to_dict() for photo in rankings],
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"API获取排行榜失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/stats')
@rate_limit(max_requests=20, window=60)
@cached(timeout=300, key_prefix='api_stats')
def get_statistics():
    """获取统计信息API"""
    try:
        stats = PhotoService.get_photo_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"API获取统计失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# 需要登录的API
@api_bp.route('/vote', methods=['POST'])
@login_required
@rate_limit(max_requests=30, window=60)
def vote_api():
    """投票API"""
    try:
        data = request.get_json()
        if not data or 'photo_id' not in data:
            return jsonify({
                'success': False,
                'error': 'photo_id is required'
            }), 400
        
        photo_id = data['photo_id']
        ip_address = request.remote_addr
        
        success, message = VoteService.vote_for_photo(
            session['user_id'], photo_id, ip_address
        )
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        logger.error(f"API投票失败: {e}")
        return jsonify({'success': False, 'error': 'Vote failed'}), 500


@api_bp.route('/vote/<photo_id>', methods=['DELETE'])
@login_required
@rate_limit(max_requests=20, window=60)
def cancel_vote_api(photo_id):
    """取消投票API"""
    try:
        success, message = VoteService.cancel_vote(session['user_id'], photo_id)
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        logger.error(f"API取消投票失败: {e}")
        return jsonify({'success': False, 'error': 'Cancel vote failed'}), 500


@api_bp.route('/user/photos')
@login_required
@rate_limit(max_requests=20, window=60)
def get_user_photos():
    """获取用户照片API"""
    try:
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
        
        photos = PhotoService.get_user_photos(
            session['user_id'], 
            include_deleted=include_deleted
        )
        
        return jsonify({
            'success': True,
            'data': [photo.to_dict() for photo in photos]
        })
        
    except Exception as e:
        logger.error(f"API获取用户照片失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/user/votes')
@login_required
@rate_limit(max_requests=20, window=60)
def get_user_votes():
    """获取用户投票记录API"""
    try:
        limit = min(request.args.get('limit', 20, type=int), 100)
        
        votes = VoteService.get_user_votes(session['user_id'], limit=limit)
        
        return jsonify({
            'success': True,
            'data': [vote.to_dict() for vote in votes],
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"API获取用户投票失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/user/vote_summary')
@login_required
def get_user_vote_summary_api():
    """获取用户投票摘要API"""
    try:
        summary = VoteService.get_user_vote_summary(session['user_id'])
        
        return jsonify({
            'success': True,
            'data': summary
        })
        
    except Exception as e:
        logger.error(f"API获取投票摘要失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_bp.route('/settings')
@rate_limit(max_requests=10, window=60)
@cached(timeout=600, key_prefix='api_settings')
def get_settings():
    """获取系统设置API（公开部分）"""
    try:
        settings = Settings.get_current()
        
        # 只返回公开的设置信息
        public_settings = {
            'contest_title': settings.contest_title,
            'allow_upload': settings.allow_upload,
            'allow_vote': settings.allow_vote,
            'show_rankings': settings.show_rankings,
            'one_vote_per_user': settings.one_vote_per_user,
            'is_voting_allowed': settings.is_voting_allowed(),
            'is_upload_allowed': settings.is_upload_allowed()
        }
        
        return jsonify({
            'success': True,
            'data': public_settings
        })
        
    except Exception as e:
        logger.error(f"API获取设置失败: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# 错误处理
@api_bp.errorhandler(400)
def bad_request(error):
    return jsonify({'success': False, 'error': 'Bad request'}), 400


@api_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({'success': False, 'error': 'Unauthorized'}), 401


@api_bp.errorhandler(403)
def forbidden(error):
    return jsonify({'success': False, 'error': 'Forbidden'}), 403


@api_bp.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404


@api_bp.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429


@api_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# API 文档路由
@api_bp.route('/docs')
def api_docs():
    """API文档"""
    docs = {
        'version': '1.0',
        'endpoints': {
            'GET /api/photos': '获取照片列表',
            'GET /api/photos/search': '搜索照片',
            'GET /api/photos/rankings': '获取排行榜',
            'GET /api/stats': '获取统计信息',
            'POST /api/vote': '投票（需要登录）',
            'DELETE /api/vote/<photo_id>': '取消投票（需要登录）',
            'GET /api/user/photos': '获取用户照片（需要登录）',
            'GET /api/user/votes': '获取用户投票记录（需要登录）',
            'GET /api/user/vote_summary': '获取用户投票摘要（需要登录）',
            'GET /api/settings': '获取系统设置'
        },
        'rate_limits': {
            'default': '60 requests per minute',
            'search': '30 requests per minute',
            'vote': '30 requests per minute'
        }
    }
    
    return jsonify(docs)
"""
好友系统模块
提供关注、取关、好友请求处理等接口
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_

from .models import db, User, Friendship, Message

friends_bp = Blueprint('friends', __name__, url_prefix='/friends')


# ==================== 关注用户 ====================

@friends_bp.route('/<int:user_id>/follow', methods=['POST'])
@jwt_required()
def follow_user(user_id: int):
    """
    关注用户

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Follow request sent" / "Already following"}
        400: {"error": "Cannot follow yourself"}
        404: {"error": "User not found"}
    """
    current_user_id = int(get_jwt_identity())

    if current_user_id == user_id:
        return jsonify({'error': 'Cannot follow yourself'}), 400

    # 检查目标用户是否存在
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'error': 'User not found'}), 404

    # 检查是否已经关注且状态为 accepted
    existing = Friendship.query.filter_by(
        follower_id=current_user_id,
        followed_id=user_id,
        status='accepted'
    ).first()
    if existing:
        return jsonify({'message': 'Already following'}), 200

    # 如果有 pending 或 rejected 的记录，先删除（允许重新关注）
    stale = Friendship.query.filter_by(
        follower_id=current_user_id,
        followed_id=user_id
    ).first()
    if stale:
        db.session.delete(stale)

       # 创建关注请求
    friendship = Friendship(
        follower_id=current_user_id,
        followed_id=user_id,
        status='pending'
    )
    db.session.add(friendship)

    # 发送系统消息给被关注者（由 TODO 用户发送）
    current_user = User.query.get(current_user_id)
    from .messages import get_or_create_todo_user
    todo_user = get_or_create_todo_user()
    msg = Message(
        user_id=user_id,
        sender_id=todo_user.id,
        type='system',
        title='新的关注请求',
        content=f'{current_user.username if current_user else "某用户"} 关注了您，是否回关？',
        related_id=current_user_id
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'message': 'Follow request sent'}), 200


# ==================== 取关 ====================

@friends_bp.route('/<int:user_id>/unfollow', methods=['POST'])
@jwt_required()
def unfollow_user(user_id: int):
    """
    取关

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Unfollowed"}
        404: {"error": "Friendship not found"}
    """
    current_user_id = int(get_jwt_identity())

    friendship = Friendship.query.filter_by(
        follower_id=current_user_id,
        followed_id=user_id
    ).first()
    if not friendship:
        return jsonify({'error': 'Friendship not found'}), 404

    db.session.delete(friendship)
    db.session.commit()

    return jsonify({'message': 'Unfollowed'}), 200


# ==================== 获取待处理的好友请求 ====================

@friends_bp.route('/requests', methods=['GET'])
@jwt_required()
def list_follow_requests():
    """
    获取待处理的好友请求（别人关注当前用户且状态为 pending）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"requests": [...]}
    """
    current_user_id = int(get_jwt_identity())

    requests = Friendship.query.filter_by(
        followed_id=current_user_id,
        status='pending'
    ).all()

    result = []
    for f in requests:
        follower = User.query.get(f.follower_id)
        if follower:
            result.append({
                'friendship_id': f.id,
                'user': follower.to_dict(),
                'created_at': f.created_at.isoformat() if f.created_at else None
            })

    return jsonify({'requests': result}), 200


# ==================== 接受关注 ====================

@friends_bp.route('/<int:user_id>/accept', methods=['POST'])
@jwt_required()
def accept_follow(user_id: int):
    """
    接受关注（互相关注）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Follow request accepted", "is_friend": true/false}
        404: {"error": "Friendship not found"}
    """
    current_user_id = int(get_jwt_identity())

    friendship = Friendship.query.filter_by(
        follower_id=user_id,
        followed_id=current_user_id,
        status='pending'
    ).first()
    if not friendship:
        return jsonify({'error': 'Friendship not found'}), 404

    friendship.status = 'accepted'
    db.session.commit()

    # 检查是否互相关注（即对方也关注了当前用户）
    reverse = Friendship.query.filter_by(
        follower_id=current_user_id,
        followed_id=user_id,
        status='accepted'
    ).first()
    is_friend = reverse is not None

    return jsonify({
        'message': 'Follow request accepted',
        'is_friend': is_friend
    }), 200


# ==================== 拒绝关注 ====================

@friends_bp.route('/<int:user_id>/reject', methods=['POST'])
@jwt_required()
def reject_follow(user_id: int):
    """
    拒绝关注

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Follow request rejected"}
        404: {"error": "Friendship not found"}
    """
    current_user_id = int(get_jwt_identity())

    friendship = Friendship.query.filter_by(
        follower_id=user_id,
        followed_id=current_user_id,
        status='pending'
    ).first()
    if not friendship:
        return jsonify({'error': 'Friendship not found'}), 404

    db.session.delete(friendship)
    db.session.commit()

    return jsonify({'message': 'Follow request rejected'}), 200


# ==================== 获取好友列表（互相关注的） ====================

@friends_bp.route('/list', methods=['GET'])
@jwt_required()
def list_friends():
    """
    获取好友列表（双方都关注对方，即互相关注）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"friends": [...]}
    """
    current_user_id = int(get_jwt_identity())

    # 找到所有当前用户关注且对方也关注当前用户的记录
    following = Friendship.query.filter_by(
        follower_id=current_user_id,
        status='accepted'
    ).all()

    friends = []
    for f in following:
        # 检查反向关注是否存在且已接受
        reverse = Friendship.query.filter_by(
            follower_id=f.followed_id,
            followed_id=current_user_id,
            status='accepted'
        ).first()
        if reverse:
            user = User.query.get(f.followed_id)
            if user:
                friends.append(user.to_dict())

    return jsonify({'friends': friends}), 200


# ==================== 获取粉丝列表 ====================

@friends_bp.route('/followers', methods=['GET'])
@jwt_required()
def list_followers():
    """
    获取粉丝列表（关注当前用户的用户）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"followers": [...]}
    """
    current_user_id = int(get_jwt_identity())

    # 当前用户是被关注者（followed_id），且状态为 accepted
    followers = Friendship.query.filter_by(
        followed_id=current_user_id,
        status='accepted'
    ).all()

    result = []
    for f in followers:
        user = User.query.get(f.follower_id)
        if user:
            result.append(user.to_dict())

    return jsonify({'followers': result}), 200


# ==================== 获取关注列表 ====================

@friends_bp.route('/following', methods=['GET'])
@jwt_required()
def list_following():
    """
    获取关注列表（当前用户关注的用户）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"following": [...]}
    """
    current_user_id = int(get_jwt_identity())

    following = Friendship.query.filter_by(
        follower_id=current_user_id,
        status='accepted'
    ).all()

    result = []
    for f in following:
        user = User.query.get(f.followed_id)
        if user:
            result.append(user.to_dict())

    return jsonify({'following': result}), 200


# ==================== 搜索用户 ====================

@friends_bp.route('/search', methods=['GET'])
@jwt_required()
def search_users():
    """
    搜索用户（通过用户名）

    请求头:
        Authorization: Bearer <token>

    查询参数:
        q: 搜索关键词（用户名）

    返回:
        200: {"users": [...]}
    """
    current_user_id = int(get_jwt_identity())
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({'users': []}), 200

    # 模糊搜索用户名
    users = User.query.filter(
        User.username.like(f'%{query}%'),
        User.id != current_user_id
    ).limit(20).all()

    result = []
    for user in users:
        # 检查是否已经关注
        existing = Friendship.query.filter_by(
            follower_id=current_user_id,
            followed_id=user.id
        ).first()
        result.append({
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname or '',
            'status': existing.status if existing else 'none'
        })

    return jsonify({'users': result}), 200
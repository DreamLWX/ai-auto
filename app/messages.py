"""
消息系统模块
提供消息查看、标记已读等功能
"""
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from .models import db, Message

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')


def get_current_user_id():
    """从请求中获取当前用户ID（支持 JWT 或 session）"""
    from flask import session
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return int(identity)
    except Exception:
        pass

    if 'user_id' in session:
        return session['user_id']

    return None


@messages_bp.route('/page', methods=['GET'])
def view_messages_page():
    """消息页面（需登录）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    messages = Message.query.filter_by(user_id=user_id).order_by(Message.created_at.desc()).all()
    unread_count = Message.query.filter_by(user_id=user_id, is_read=False).count()

    return render_template('messages.html',
                           messages=messages,
                           unread_count=unread_count)


@messages_bp.route('', methods=['GET'])
@jwt_required()
def list_messages():
    """获取消息列表API"""
    user_id = int(get_jwt_identity())
    messages = Message.query.filter_by(user_id=user_id).order_by(Message.created_at.desc()).all()
    return jsonify({'messages': [m.to_dict() for m in messages]}), 200


@messages_bp.route('/unread_count', methods=['GET'])
@jwt_required()
def unread_count():
    """获取未读消息数"""
    user_id = int(get_jwt_identity())
    count = Message.query.filter_by(user_id=user_id, is_read=False).count()
    return jsonify({'unread_count': count}), 200


@messages_bp.route('/<int:msg_id>/read', methods=['GET'])
def mark_read(msg_id):
    """标记消息已读"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    msg = Message.query.get(msg_id)
    if msg and msg.user_id == user_id:
        msg.is_read = True
        db.session.commit()

    # 重定向回消息页面
    return redirect(url_for('messages.view_messages_page'))
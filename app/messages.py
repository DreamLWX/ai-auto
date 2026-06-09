"""
消息系统模块
提供消息查看、标记已读、IM会话等功能
"""
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from .models import db, Message, User, Friendship

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')


def get_or_create_todo_user():
    """获取或创建 TODO 系统用户"""
    todo_user = User.query.filter_by(username='TODO').first()
    if not todo_user:
        # 创建一个不带密码的系统用户（仅用于发送消息）
        todo_user = User(
            username='TODO',
            password_hash='',
            nickname='系统助手'
        )
        db.session.add(todo_user)
        db.session.commit()
    return todo_user


def send_system_message(user_id: int, content: str, msg_type: str = 'system', related_id: int = None):
    """发送系统消息（由 TODO 用户发送）"""
    todo_user = get_or_create_todo_user()
    msg = Message(
        user_id=user_id,
        sender_id=todo_user.id,
        type=msg_type,
        title='系统通知',
        content=content,
        related_id=related_id
    )
    db.session.add(msg)
    db.session.commit()
    return msg


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


def get_conversations(user_id: int):
    """
    获取与当前用户有消息往来的会话列表
    返回：[{user_id, username, nickname, avatar, last_message, unread_count}]
    """
    # 获取所有与当前用户相关的消息，提取对话方
    messages = Message.query.filter_by(user_id=user_id).order_by(Message.created_at.desc()).all()

    conversations = {}
    for msg in messages:
        # 确定对话方：消息发送者或接收者
        if msg.sender_id:
            other_id = msg.sender_id
        else:
            continue # 系统消息不计入对话

        if other_id not in conversations:
            other_user = User.query.get(other_id)
            if other_user:
                conversations[other_id] = {
                    'user_id': other_id,
                    'username': other_user.username,
                    'nickname': other_user.nickname or '',
                    'avatar': other_user.username[0].upper() if other_user.username else '?',
                    'last_message': msg.content[:50] if msg.content else '',
                    'last_time': msg.created_at.isoformat() if msg.created_at else None,
                    'unread_count': 0
                }

        # 更新未读数
        if not msg.is_read:
            conversations[other_id]['unread_count'] +=1

    return list(conversations.values())


def get_messages_with(user_id: int, other_id: int):
    """获取与指定用户的聊天记录"""
    # 当前用户发送给对方的消息
    sent = Message.query.filter_by(user_id=other_id, sender_id=user_id).all()
    # 对方发送给当前用户的消息
    received = Message.query.filter_by(user_id=user_id, sender_id=other_id).all()

    all_messages = sent + received
    all_messages.sort(key=lambda x: x.created_at if x.created_at else 0)

    return all_messages


@messages_bp.route('/page', methods=['GET'])
def view_messages_page():
    """消息页面（IM风格，需登录）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    conversations = get_conversations(user_id)
    unread_count = Message.query.filter_by(user_id=user_id, is_read=False).count()

    # 获取好友列表（用于新建对话）
    following = Friendship.query.filter_by(
        follower_id=user_id,
        status='accepted'
    ).all()
    friends = []
    # 添加 TODO 系统用户到好友列表首位
    todo_user = get_or_create_todo_user()
    friends.append({
        'user_id': todo_user.id,
        'username': todo_user.username,
        'nickname': todo_user.nickname or ''
    })
    for f in following:
        friend = User.query.get(f.followed_id)
        if friend and friend.id != todo_user.id:
            friends.append({
                'user_id': friend.id,
                'username': friend.username,
                'nickname': friend.nickname or ''
            })

    return render_template('messages.html',
                           conversations=conversations,
                           friends=friends,
                           unread_count=unread_count)


@messages_bp.route('/conversation/<int:other_id>', methods=['GET'])
def get_conversation(other_id: int):
    """获取与指定用户的聊天记录"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    messages = get_messages_with(user_id, other_id)
    other_user = User.query.get(other_id)

    # 标记已读
    for msg in messages:
        if msg.user_id == user_id and not msg.is_read:
            msg.is_read = True
    db.session.commit()

    # 获取好友列表
    following = Friendship.query.filter_by(
        follower_id=user_id,
        status='accepted'
    ).all()
    friends = []
    # 添加 TODO 系统用户到好友列表首位
    todo_user = get_or_create_todo_user()
    friends.append({
        'user_id': todo_user.id,
        'username': todo_user.username,
        'nickname': todo_user.nickname or ''
    })
    for f in following:
        friend = User.query.get(f.followed_id)
        if friend and friend.id != todo_user.id:
            friends.append({
                'user_id': friend.id,
                'username': friend.username,
                'nickname': friend.nickname or ''
            })

    return render_template('messages.html',
                           conversation_user=other_user,
                           messages=messages,
                           friends=friends,
                           unread_count=0)


@messages_bp.route('/api/conversations', methods=['GET'])
@jwt_required()
def list_conversations_api():
    """获取会话列表API"""
    user_id = int(get_jwt_identity())
    conversations = get_conversations(user_id)
    return jsonify({'conversations': conversations}), 200


@messages_bp.route('/api/with/<int:other_id>', methods=['GET'])
@jwt_required()
def list_messages_with_api(other_id: int):
    """获取与指定用户的聊天记录API"""
    user_id = int(get_jwt_identity())
    messages = get_messages_with(user_id, other_id)

    # 标记已读
    for msg in messages:
        if msg.user_id == user_id and not msg.is_read:
            msg.is_read = True
    db.session.commit()

    return jsonify({'messages': [m.to_dict() for m in messages]}), 200


@messages_bp.route('/api/send', methods=['POST'])
@jwt_required()
def send_message_api():
    """发送消息API"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}

    receiver_id = data.get('user_id')
    content = data.get('content', '').strip()

    if not receiver_id or not content:
        return jsonify({'error': 'user_id and content are required'}), 400

    msg = Message(
        user_id=receiver_id,
        sender_id=user_id,
        type='chat',
        title='新消息',
        content=content
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'message': 'Message sent', 'msg': msg.to_dict()}), 200


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


@messages_bp.route('/<int:msg_id>/handle/<action>', methods=['POST'])
@jwt_required()
def handle_message(msg_id: int, action: str):
    """处理申请/邀请消息（批准/拒绝）"""
    user_id = int(get_jwt_identity())

    msg = Message.query.get(msg_id)
    if not msg or msg.user_id != user_id:
        return jsonify({'error': 'Message not found'}), 404

    if msg.type not in ('application', 'invitation'):
        return jsonify({'error': 'Cannot handle this message type'}), 400

    if msg.action_status != 'pending':
        return jsonify({'error': 'Already processed'}), 400

    if action not in ('approve', 'reject'):
        return jsonify({'error': 'Invalid action'}), 400

    msg.action_status = 'approved' if action == 'approve' else 'rejected'

    # 确定要被添加为参与者的用户ID（不是当前审批人，而是申请人/被邀请人）
    target_user_id = msg.sender_id if msg.type == 'application' else msg.user_id

    # 如果是接受，处理相关操作
    if action == 'approve' and msg.related_id:
        from .trips import is_participant, Trip, TripParticipant
        trip = Trip.query.get(msg.related_id)
        if trip:
            current_count = TripParticipant.query.filter_by(trip_id=trip.id).count()
            if current_count < trip.max_participants:
                participant = TripParticipant(
                    trip_id=trip.id,
                    user_id=target_user_id
                )
                db.session.add(participant)
                if current_count + 1 >= trip.min_participants:
                    trip.status = 'confirmed'

    # 发送结果通知给申请人/被邀请人（由 TODO 系统用户发送）
    from .models import User
    trip = Trip.query.get(msg.related_id) if msg.related_id else None
    trip_title = trip.title if trip else '行程'
    actor = User.query.get(user_id)
    todo_user = get_or_create_todo_user()

    if action == 'approve':
        result_content = f'您{"申请" if msg.type == "application" else "被邀请"}的行程「{trip_title}」已被 {actor.username if actor else "某用户"} 批准'
    else:
        result_content = f'您{"申请" if msg.type == "application" else "被邀请"}的行程「{trip_title}」已被 {actor.username if actor else "某用户"} 拒绝'

    result_msg = Message(
        user_id=target_user_id,
        sender_id=todo_user.id,
        type='approval',
        title='申请结果' if msg.type == 'application' else '邀请结果',
        content=result_content,
        related_id=msg.related_id,
        action_status='approved' if action == 'approve' else 'rejected'
    )
    db.session.add(result_msg)

    db.session.commit()

    return jsonify({'message': f'Message {action}d'}), 200
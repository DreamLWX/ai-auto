"""
行程系统模块
提供行程的 CRUD、申请审批、我的行程等接口
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_

from .models import db, Trip, TripApplication, TripParticipant

trips_bp = Blueprint('trips', __name__, url_prefix='/trips')


def can_view_trip(trip, user_id):
    """检查用户是否有权限查看行程"""
    if not trip.is_private:
        if trip.visibility == 'public':
            return True
        if trip.visibility == 'friends':
            # TODO: 检查是否为好友关系
            return True
    # 私人行程：只有创建者或参与者可以查看
    if trip.creator_id == user_id:
        return True
    participant = TripParticipant.query.filter_by(trip_id=trip.id, user_id=user_id).first()
    return participant is not None


def is_participant(trip_id, user_id):
    """检查用户是否为行程参与者"""
    return TripParticipant.query.filter_by(trip_id=trip_id, user_id=user_id).first() is not None


def is_creator(trip_id, user_id):
    """检查用户是否为行程创建者"""
    trip = Trip.query.get(trip_id)
    return trip and trip.creator_id == user_id


# ==================== 行程列表（大厅） ====================

@trips_bp.route('', methods=['GET'])
def list_trips():
    """
    获取行程列表（大厅）

    查询参数:
        page: 页码，默认1
        per_page: 每页条数，默认10
        status: 可选，筛选状态

    返回:
        200: {"trips": [...], "total": N, "total_pages": N, "current_page": N}
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status_filter = request.args.get('status')

    # 限制每页最多100条
    per_page = min(per_page, 100)

    query = Trip.query.filter_by(is_private=False, visibility='public')

    if status_filter:
        query = query.filter_by(status=status_filter)

    query = query.order_by(Trip.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'trips': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'total_pages': pagination.pages,
        'current_page': pagination.page
    }), 200


# ==================== 创建行程 ====================

@trips_bp.route('', methods=['POST'])
@jwt_required()
def create_trip():
    """
    创建行程

    请求体:
        {
            "title": "北京之旅",           # 必填
            "description": "一起去北京玩",  # 可选
            "is_private": false,           # 可选，是否私人行程
            "visibility": "public",        # public / friends / private
            "min_participants": 3,        # 可选，最小参与人数
            "max_participants": 10,       # 可选，最大参与人数
            "deadline": "2025-06-01T00:00:00",  # 可选，报名截止时间
            "trigger_condition": "auto",   # auto / manual
            "public_content": "...",       # 可选，公开内容
            "hidden_content": "..."        # 可选，隐藏内容
        }

    请求头:
        Authorization: Bearer <token>

    返回:
        201: {"message": "Trip created", "trip": {...}}
        400: {"error": "Title is required"}
    """
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    title = data['title'].strip()
    if len(title) > 200:
        return jsonify({'error': 'Title too long (max 200 chars)'}), 400

    description = data.get('description', '').strip() or None

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid deadline format, use ISO format'}), 400

    trip = Trip(
        title=title,
        description=description,
        creator_id=user_id,
        is_private=data.get('is_private', False),
        visibility=data.get('visibility', 'public'),
        min_participants=data.get('min_participants', 1),
        max_participants=data.get('max_participants', 10),
        deadline=deadline,
        trigger_condition=data.get('trigger_condition', 'auto'),
        public_content=data.get('public_content', '').strip() or None,
        hidden_content=data.get('hidden_content', '').strip() or None
    )
    db.session.add(trip)
    db.session.commit()

    return jsonify({'message': 'Trip created', 'trip': trip.to_dict()}), 201


# ==================== 获取行程详情 ====================

@trips_bp.route('/<int:trip_id>', methods=['GET'])
@jwt_required()
def get_trip(trip_id: int):
    """
    获取行程详情

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"trip": {...}}
        403: {"error": "Access denied"}
        404: {"error": "Trip not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if not can_view_trip(trip, user_id):
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'trip': trip.to_dict()}), 200


# ==================== 更新行程 ====================

@trips_bp.route('/<int:trip_id>', methods=['PUT'])
@jwt_required()
def update_trip(trip_id: int):
    """
    更新行程（仅创建者可更新）

    请求体（可选）:
        {
            "title": "新标题",
            "description": "新描述",
            "status": "confirmed",
            "public_content": "...",
            "hidden_content": "..."
        }

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Trip updated", "trip": {...}}
        403: {"error": "Access denied"}
        404: {"error": "Trip not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.creator_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        if len(title) > 200:
            return jsonify({'error': 'Title too long'}), 400
        trip.title = title

    if 'description' in data:
        trip.description = data['description'].strip() or None

    if 'is_private' in data:
        trip.is_private = bool(data['is_private'])

    if 'visibility' in data:
        if data['visibility'] not in ('public', 'friends', 'private'):
            return jsonify({'error': 'Invalid visibility'}), 400
        trip.visibility = data['visibility']

    if 'min_participants' in data:
        trip.min_participants = int(data['min_participants'])

    if 'max_participants' in data:
        trip.max_participants = int(data['max_participants'])

    if 'deadline' in data:
        if data['deadline']:
            try:
                trip.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid deadline format'}), 400
        else:
            trip.deadline = None

    if 'trigger_condition' in data:
        if data['trigger_condition'] not in ('auto', 'manual'):
            return jsonify({'error': 'Invalid trigger_condition'}), 400
        trip.trigger_condition = data['trigger_condition']

    if 'status' in data:
        if data['status'] not in ('recruiting', 'confirmed', 'cancelled'):
            return jsonify({'error': 'Invalid status'}), 400
        trip.status = data['status']

    if 'public_content' in data:
        trip.public_content = data['public_content'].strip() or None

    if 'hidden_content' in data:
        trip.hidden_content = data['hidden_content'].strip() or None

    db.session.commit()

    return jsonify({'message': 'Trip updated', 'trip': trip.to_dict()}), 200


# ==================== 删除行程 ====================

@trips_bp.route('/<int:trip_id>', methods=['DELETE'])
@jwt_required()
def delete_trip(trip_id: int):
    """
    删除行程（仅创建者可删除）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Trip deleted"}
        403: {"error": "Access denied"}
        404: {"error": "Trip not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.creator_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    # 删除相关的申请和参与记录
    TripApplication.query.filter_by(trip_id=trip_id).delete()
    TripParticipant.query.filter_by(trip_id=trip_id).delete()
    db.session.delete(trip)
    db.session.commit()

    return jsonify({'message': 'Trip deleted'}), 200


# ==================== 申请加入行程 ====================

@trips_bp.route('/<int:trip_id>/apply', methods=['POST'])
@jwt_required()
def apply_trip(trip_id: int):
    """
    申请加入行程

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Application submitted"}
        400: {"error": "Already applied or already a participant"}
        404: {"error": "Trip not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.status != 'recruiting':
        return jsonify({'error': 'Trip is not recruiting'}), 400

    # 检查是否已经是参与者
    if is_participant(trip_id, user_id):
        return jsonify({'error': 'Already a participant'}), 400

    # 检查是否已有待处理申请
    existing = TripApplication.query.filter_by(
        trip_id=trip_id,
        applicant_id=user_id,
        status='pending'
    ).first()
    if existing:
        return jsonify({'error': 'Already applied'}), 400

    # 自动审批：如果不需要审批，直接成为参与者
    if trip.trigger_condition == 'auto':
        # 检查是否已达最大人数
        current_count = TripParticipant.query.filter_by(trip_id=trip_id).count()
        if current_count >= trip.max_participants:
            return jsonify({'error': 'Trip is full'}), 400

        participant = TripParticipant(
            trip_id=trip_id,
            user_id=user_id
        )
        db.session.add(participant)

        # 更新状态
        participant_count = TripParticipant.query.filter_by(trip_id=trip_id).count()
        if participant_count >= trip.min_participants:
            trip.status = 'confirmed'

        db.session.commit()
        return jsonify({'message': 'Joined trip successfully'}), 200

    # 需要手动审批
    application = TripApplication(
        trip_id=trip_id,
        applicant_id=user_id,
        status='pending'
    )
    db.session.add(application)
    db.session.commit()

    return jsonify({'message': 'Application submitted'}), 200


# ==================== 获取申请列表 ====================

@trips_bp.route('/<int:trip_id>/applications', methods=['GET'])
@jwt_required()
def list_applications(trip_id: int):
    """
    获取申请列表（发起人用）

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"applications": [...]}
        403: {"error": "Access denied"}
        404: {"error": "Trip not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.creator_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    applications = TripApplication.query.filter_by(
        trip_id=trip_id,
        status='pending'
    ).all()

    return jsonify({'applications': [a.to_dict() for a in applications]}), 200


# ==================== 审批通过 ====================

@trips_bp.route('/<int:trip_id>/applications/<int:app_id>/approve', methods=['POST'])
@jwt_required()
def approve_application(trip_id: int, app_id: int):
    """
    审批通过

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Application approved"}
        400: {"error": "Trip is full"}
        403: {"error": "Access denied"}
        404: {"error": "Trip or application not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.creator_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    application = TripApplication.query.get(app_id)
    if not application or application.trip_id != trip_id:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'pending':
        return jsonify({'error': 'Application already processed'}), 400

    # 检查是否已达最大人数
    current_count = TripParticipant.query.filter_by(trip_id=trip_id).count()
    if current_count >= trip.max_participants:
        return jsonify({'error': 'Trip is full'}), 400

    application.status = 'approved'

    participant = TripParticipant(
        trip_id=trip_id,
        user_id=application.applicant_id
    )
    db.session.add(participant)

    # 检查是否达到最小参与人数
    participant_count = TripParticipant.query.filter_by(trip_id=trip_id).count()
    if participant_count >= trip.min_participants:
        trip.status = 'confirmed'

    db.session.commit()

    return jsonify({'message': 'Application approved'}), 200


# ==================== 审批拒绝 ====================

@trips_bp.route('/<int:trip_id>/applications/<int:app_id>/reject', methods=['POST'])
@jwt_required()
def reject_application(trip_id: int, app_id: int):
    """
    审批拒绝

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Application rejected"}
        403: {"error": "Access denied"}
        404: {"error": "Trip or application not found"}
    """
    user_id = int(get_jwt_identity())
    trip = Trip.query.get(trip_id)

    if not trip:
        return jsonify({'error': 'Trip not found'}), 404

    if trip.creator_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    application = TripApplication.query.get(app_id)
    if not application or application.trip_id != trip_id:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'pending':
        return jsonify({'error': 'Application already processed'}), 400

    application.status = 'rejected'
    db.session.commit()

    return jsonify({'message': 'Application rejected'}), 200


# ==================== 获取我发布和参与的行程 ====================

@trips_bp.route('/mine', methods=['GET'])
@jwt_required()
def list_my_trips():
    """
    获取我发布和参与的行程

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"created_trips": [...], "joined_trips": [...]}
    """
    user_id = int(get_jwt_identity())

    # 我创建的行程
    created_trips = Trip.query.filter_by(creator_id=user_id).order_by(Trip.created_at.desc()).all()

    # 我参与的行程（通过参与者表）
    participations = TripParticipant.query.filter_by(user_id=user_id).all()
    joined_trip_ids = [p.trip_id for p in participations]
    joined_trips = Trip.query.filter(Trip.id.in_(joined_trip_ids)).order_by(Trip.created_at.desc()).all() if joined_trip_ids else []

    return jsonify({
        'created_trips': [t.to_dict() for t in created_trips],
        'joined_trips': [t.to_dict() for t in joined_trips]
    }), 200


# ==================== 页面路由 ====================

@trips_bp.route('/page', methods=['GET'])
def list_trips_page():
    """行程大厅页面（需登录）"""
    user_id = get_current_user_id_from_request()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter_type', 'all')

    query = Trip.query.filter_by(is_private=False)
    if filter_type == 'public':
        query = query.filter_by(visibility='public')
    elif filter_type == 'private':
        query = query.filter_by(visibility='friends')

    query = query.order_by(Trip.created_at.desc())
    per_page = 10
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('trips.html',
                           trips=pagination.items,
                           total_pages=pagination.pages,
                           current_page=pagination.page,
                           filter_type=filter_type)


@trips_bp.route('/new', methods=['GET', 'POST'])
def create_trip_page():
    """发布新行程页面"""
    user_id = get_current_user_id_from_request()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('标题不能为空', 'danger')
            return redirect(url_for('trips.create_trip_page'))

        description = request.form.get('description', '').strip() or None
        is_private = request.form.get('is_private') == 'on'
        visibility = request.form.get('visibility', 'public')
        min_participants = request.form.get('min_participants', 1, type=int)
        max_participants = request.form.get('max_participants', 10, type=int)
        deadline = request.form.get('deadline', '').strip() or None
        trigger_condition = request.form.get('trigger_condition', 'auto')
        public_content = request.form.get('public_content', '').strip() or None
        hidden_content = request.form.get('hidden_content', '').strip() or None

        trip = Trip(
            title=title,
            description=description,
            creator_id=user_id,
            is_private=is_private,
            visibility=visibility,
            min_participants=min_participants,
            max_participants=max_participants,
            deadline=deadline,
            trigger_condition=trigger_condition,
            public_content=public_content,
            hidden_content=hidden_content
        )
        db.session.add(trip)
        db.session.commit()

        flash('行程已发布', 'success')
        return redirect(url_for('trips.list_trips_page'))

    return render_template('trip_form.html', trip=None)


@trips_bp.route('/mine/page', methods=['GET'])
def my_trips_page():
    """我的行程页面（需登录）"""
    user_id = get_current_user_id_from_request()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    created_trips = Trip.query.filter_by(creator_id=user_id).order_by(Trip.created_at.desc()).all()
    participations = TripParticipant.query.filter_by(user_id=user_id).all()
    joined_trip_ids = [p.trip_id for p in participations]
    joined_trips = Trip.query.filter(Trip.id.in_(joined_trip_ids)).order_by(Trip.created_at.desc()).all() if joined_trip_ids else []

    return render_template('my_trips.html',
                           created_trips=created_trips,
                           joined_trips=joined_trips)


def get_current_user_id_from_request():
    """从请求中获取当前用户ID（支持 JWT 或 session）"""
    from flask import session
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    # 优先尝试 JWT
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return int(identity)
    except Exception:
        pass

    # 其次尝试 session
    if 'user_id' in session:
        return session['user_id']

    return None
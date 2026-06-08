"""
任务管理模块
提供任务的 CRUD 操作，包含 Redis 缓存逻辑
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

from .models import db, Task
from .redis_client import get_redis

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


# ==================== 任务列表（分页 + 缓存） ====================

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def list_tasks():
    """
    获取当前用户的任务列表（分页）
    优先从 Redis 缓存读取，缓存未命中则查库

    查询参数:
        page: 页码，默认1
        per_page: 每页条数，默认10
        completed: 可选，筛选完成状态

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {
            "tasks": [...],
            "total": 50,
            "total_pages": 5,
            "current_page": 1,
            "from_cache": true/false
        }
    """
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    completed_filter = request.args.get('completed')

    # 限制每页最多100条
    per_page = min(per_page, 100)

    # 尝试从缓存读取（仅在无筛选条件时缓存）
    redis_client = get_redis()
    from_cache = False

    if completed_filter is None:
        cached = redis_client.get_tasks_cache(user_id, page, per_page)
        if cached:
            cached['from_cache'] = True
            return jsonify(cached), 200
        from_cache = False

    # 缓存未命中，查询数据库
    query = Task.query.filter_by(user_id=user_id)

    if completed_filter is not None:
        # 按完成状态筛选（0/1, true/false）
        completed_val = completed_filter.lower() in ('1', 'true', 'yes')
        query = query.filter_by(completed=completed_val)

    # 按创建时间倒序
    query = query.order_by(desc(Task.created_at))

    # 生成分页对象
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = {
        'tasks': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'total_pages': pagination.pages,
        'current_page': pagination.page,
        'from_cache': from_cache
    }

    # 写入缓存（仅在无筛选条件时）
    if completed_filter is None:
        redis_client.set_tasks_cache(user_id, page, per_page, result, ttl=60)

    return jsonify(result), 200


# ==================== 创建任务 ====================

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """
    创建新任务

    请求体:
        {
            "title": "买牛奶",          # 必填
            "description": "低脂",    # 可选
            "due_date": "2025-06-01"  # 可选，格式 YYYY-MM-DD
        }

    请求头:
        Authorization: Bearer <token>

    返回:
        201: {"message": "Task created", "task": {...}}
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

    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid due_date format, use YYYY-MM-DD'}), 400

    # 创建任务
    task = Task(
        title=title,
        description=description,
        due_date=due_date,
        user_id=user_id
    )
    db.session.add(task)
    db.session.commit()

    # 清除该用户的所有缓存
    get_redis().invalidate_user_tasks_cache(user_id)

    return jsonify({'message': 'Task created', 'task': task.to_dict()}), 201


@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id: int):
    """获取单个任务"""
    user_id = int(get_jwt_identity())
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task.user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify(task.to_dict()), 200


# ==================== 更新任务 ====================

@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id: int):
    """
    修改任务（任意字段）

    请求体（可选）:
        {
            "title": "新标题",
            "description": "新描述",
            "due_date": "2025-06-02",
            "completed": true
        }

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Task updated", "task": {...}}
        403: {"error": "Access denied"}（非本人任务）
        404: {"error": "Task not found"}
    """
    user_id = int(get_jwt_identity())

    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    # 可更新字段
    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        if len(title) > 200:
            return jsonify({'error': 'Title too long'}), 400
        task.title = title

    if 'description' in data:
        task.description = data['description'].strip() or None

    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid due_date format'}), 400
        else:
            task.due_date = None

    if 'completed' in data:
        task.completed = bool(data['completed'])

    db.session.commit()

    # 清除缓存
    get_redis().invalidate_user_tasks_cache(user_id)

    return jsonify({'message': 'Task updated', 'task': task.to_dict()}), 200


# ==================== 删除任务 ====================

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id: int):
    """
    删除任务

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Task deleted"}
        403: {"error": "Access denied"}
        404: {"error": "Task not found"}
    """
    user_id = int(get_jwt_identity())

    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(task)
    db.session.commit()

    # 清除缓存
    get_redis().invalidate_user_tasks_cache(user_id)

    return jsonify({'message': 'Task deleted'}), 200


# ==================== 标记完成/未完成 ====================

@tasks_bp.route('/<int:task_id>/complete', methods=['PATCH'])
@jwt_required()
def toggle_complete(task_id: int):
    """
    切换任务完成状态

    请求头:
        Authorization: Bearer <token>

    返回:
        200: {"message": "Task updated", "task": {...}}
        403: {"error": "Access denied"}
        404: {"error": "Task not found"}
    """
    user_id = int(get_jwt_identity())

    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    task.completed = not task.completed
    db.session.commit()

    # 清除缓存
    get_redis().invalidate_user_tasks_cache(user_id)

    status_text = "completed" if task.completed else "incomplete"
    return jsonify({
        'message': f'Task marked as {status_text}',
        'task': task.to_dict()
    }), 200


# ==================== Web: 任务管理页面 ====================

from flask import render_template, redirect, url_for, flash, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity as _get_id


def get_current_user_id():
    """从 JWT 获取当前用户 ID（无 JWT 时返回 None）"""
    try:
        verify_jwt_in_request(optional=True)
        identity = _get_id()
        if identity is None:
            return None
        return int(identity)
    except Exception:
        return None


@tasks_bp.route('/page', methods=['GET'])
def list_tasks_page():
    """任务管理页面（需登录）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    # 读取查询参数
    page = request.args.get('page', 1, type=int)
    completed_filter = request.args.get('completed')
    per_page = 10

    # 构造查询
    query = Task.query.filter_by(user_id=user_id)
    if completed_filter is not None:
        completed_val = completed_filter.lower() in ('1', 'true', 'yes')
        query = query.filter_by(completed=completed_val)
    query = query.order_by(desc(Task.created_at))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('tasks.html',
                           tasks=pagination.items,
                           total_pages=pagination.pages,
                           current_page=pagination.page,
                           completed_filter=completed_filter)


@tasks_bp.route('/new', methods=['POST'])
def create_task_page():
    """创建任务（表单提交）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    title = request.form.get('title', '').strip()
    if not title:
        flash('标题不能为空', 'danger')
        return redirect(url_for('tasks.list_tasks_page'))

    description = request.form.get('description', '').strip() or None
    due_date = None
    due_date_str = request.form.get('due_date', '').strip()
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('日期格式错误（YYYY-MM-DD）', 'danger')
            return redirect(url_for('tasks.list_tasks_page'))

    task = Task(title=title, description=description, due_date=due_date, user_id=user_id)
    db.session.add(task)
    db.session.commit()
    get_redis().invalidate_user_tasks_cache(user_id)

    flash('任务已创建', 'success')
    return redirect(url_for('tasks.list_tasks_page'))


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
def delete_task_page(task_id: int):
    """删除任务（表单提交）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    task = Task.query.get(task_id)
    if not task or task.user_id != user_id:
        flash('任务不存在或无权删除', 'danger')
        return redirect(url_for('tasks.list_tasks_page'))

    db.session.delete(task)
    db.session.commit()
    get_redis().invalidate_user_tasks_cache(user_id)

    flash('任务已删除', 'info')
    return redirect(url_for('tasks.list_tasks_page'))


@tasks_bp.route('/<int:task_id>/toggle', methods=['POST'])
def toggle_task_page(task_id: int):
    """切换任务完成状态（表单提交）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    task = Task.query.get(task_id)
    if not task or task.user_id != user_id:
        flash('任务不存在', 'danger')
        return redirect(url_for('tasks.list_tasks_page'))

    task.completed = not task.completed
    db.session.commit()
    get_redis().invalidate_user_tasks_cache(user_id)

    status = '完成' if task.completed else '未完成'
    flash(f'任务已标记为{status}', 'success')
    return redirect(url_for('tasks.list_tasks_page'))
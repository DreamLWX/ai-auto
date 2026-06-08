"""
课程表视图模块
展示用户的任务和行程合并的时间网格视图
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from .models import db, Task, Trip, TripParticipant

schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule')


def get_current_user_id():
    """从 JWT 获取当前用户 ID（无 JWT 时返回 None）"""
    try:
        verify_jwt_in_request(optional=True)
        return int(get_jwt_identity())
    except Exception:
        return None


def get_schedule_items(user_id: int):
    """
    获取当前用户的日程项（任务 + 行程）
    返回格式：[{
        'type': 'task' | 'trip_public' | 'trip_private' | 'trip_full',
        'title': str,
        'day': int (0=周一, 6=周日),
        'hour': int (6-22),
        'id': int,
        'deadline': str,
        'participant_count': int,
        'max_participants': int,
        'status': str
    }]
    """
    items = []

    # 获取用户任务（截至日期在当周内的）
    tasks = Task.query.filter_by(user_id=user_id, completed=False).all()
    today = datetime.utcnow().date()
    for task in tasks:
        if task.due_date:
            # 计算周几 (weekday: 0=周一, 6=周日)
            day = task.due_date.weekday()
            # 计算小时（使用创建时间的小时或截止时间的小时）
            hour = task.due_date.hour if hasattr(task.due_date, 'hour') else 12
            items.append({
                'type': 'task',
                'title': task.title,
                'day': day,
                'hour': hour,
                'id': task.id,
                'deadline': task.due_date.isoformat() if task.due_date else None,
                'participant_count': None,
                'max_participants': None,
                'status': 'pending'
            })

    # 获取用户参与的行程
    participations = TripParticipant.query.filter_by(user_id=user_id).all()
    for p in participations:
        trip = p.trip
        if trip and trip.deadline:
            day = trip.deadline.weekday()
            hour = trip.deadline.hour if hasattr(trip.deadline, 'hour') else 12
            participant_count = TripParticipant.query.filter_by(trip_id=trip.id).count()

            if trip.is_private:
                item_type = 'trip_private'
            elif participant_count >= trip.max_participants:
                item_type = 'trip_full'
            else:
                item_type = 'trip_public'

            items.append({
                'type': item_type,
                'title': trip.title,
                'day': day,
                'hour': hour,
                'id': trip.id,
                'deadline': trip.deadline.isoformat() if trip.deadline else None,
                'participant_count': participant_count,
                'max_participants': trip.max_participants,
                'status': trip.status
            })

    return items


@schedule_bp.route('', methods=['GET'])
def view_schedule():
    """课程表页面（需登录）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    items = get_schedule_items(user_id)

    # 获取当前用户的任务列表（用于 Tab 切换）
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.created_at.desc()).all()

    return render_template('schedule.html',
                           schedule_items=items,
                           tasks=tasks)
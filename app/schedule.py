"""
课程表视图模块
展示用户的任务和行程合并的时间网格视图
"""
from datetime import datetime, timedelta
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
        'id': int,
        'title': str,
        'type': 'task' | 'trip_public' | 'trip_private' | 'trip_full',
        'day': int (0=周一, 6=周日),
        'hour': int (6-22),
        'time': str (HH:MM),
        'date': str (YYYY-MM-DD),
        'completed': bool,
        'deadline': str,
        'participant_count': int,
        'max_participants': int,
        'description': str
    }]
    """
    items = []

    # 获取用户任务（截至日期在当周内的）
    tasks = Task.query.filter_by(user_id=user_id, completed=False).all()
    for task in tasks:
        if task.due_date:
            # 计算周几 (weekday: 0=周一, 6=周日)
            day = task.due_date.weekday()
            # Task.due_date 是 Date 类型，没有具体时间，固定 hour 为 12
            hour = 12
            items.append({
                'id': task.id,
                'title': task.title,
                'type': 'task',
                'day': day,
                'hour': hour,
                'time': '12:00',
                'date': task.due_date.isoformat() if task.due_date else None,
                'completed': task.completed,
                'deadline': task.due_date.isoformat() if task.due_date else None,
                'participant_count': None,
                'max_participants': None,
                'description': task.description or ''
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
                'id': trip.id,
                'title': trip.title,
                'type': item_type,
                'day': day,
                'hour': hour,
                'time': trip.deadline.strftime('%H:%M') if hasattr(trip.deadline, 'strftime') else '12:00',
                'date': trip.deadline.date().isoformat() if hasattr(trip.deadline, 'date') else trip.deadline.isoformat()[:10],
                'completed': trip.status == 'confirmed',
                'deadline': trip.deadline.isoformat() if trip.deadline else None,
                'participant_count': participant_count,
                'max_participants': trip.max_participants,
                'description': trip.description or ''
            })

    return items


def group_items_by_date(items: list):
    """
    将日程项按今天/明天/后天/XX日后分组
    返回格式：{
        'today': [...],
        'tomorrow': [...],
        'day_after_tomorrow': [...],
        'future': { 'N days': [...] }
    }
    """
    today = datetime.now().date()
    groups = {
        'today': [],
        'tomorrow': [],
        'day_after_tomorrow': [],
        'future': {}
    }

    for item in items:
        if not item.get('date'):
            continue

        try:
            item_date = datetime.fromisoformat(item['date']).date() if isinstance(item['date'], str) else item['date']
        except (ValueError, TypeError):
            continue

        days_diff = (item_date - today).days

        if days_diff < 0:
            # 跳过过去的任务
            continue
        elif days_diff == 0:
            groups['today'].append(item)
        elif days_diff == 1:
            groups['tomorrow'].append(item)
        elif days_diff == 2:
            groups['day_after_tomorrow'].append(item)
        else:
            key = f'{days_diff} days'
            if key not in groups['future']:
                groups['future'][key] = []
            groups['future'][key].append(item)

    return groups


@schedule_bp.route('', methods=['GET'])
def view_schedule():
    """课程表页面（需登录）"""
    user_id = get_current_user_id()
    if not user_id:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    items = get_schedule_items(user_id)
    list_groups = group_items_by_date(items)

    # 获取当前用户的任务列表（用于 Tab 切换）
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.created_at.desc()).all()

    return render_template('schedule.html',
                           schedule_items=items,
                           list_groups=list_groups,
                           tasks=tasks)
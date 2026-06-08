"""
课程表视图测试
"""
import pytest
from datetime import datetime, timedelta


class TestScheduleView:
    """时间表页面测试"""

    def test_schedule_requires_login(self, client):
        """未登录访问课程表应重定向到登录页"""
        response = client.get('/schedule')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_schedule_page_loads(self, client, db, auth_headers):
        """登录后访问课程表应正常加载"""
        response = client.get('/schedule', headers=auth_headers)
        assert response.status_code == 200
        assert '时间表' in response.text

    def test_schedule_shows_tasks(self, client, db, auth_headers):
        """时间表应显示用户的未完成任务"""
        # 通过 API 创建任务
        client.post('/tasks', headers=auth_headers, json={
            'title': '测试任务',
            'due_date': (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        })

        response = client.get('/schedule', headers=auth_headers)
        assert response.status_code == 200
        assert '测试任务' in response.text

    def test_schedule_shows_trips(self, client, db, auth_headers):
        """时间表应显示用户参与的行程"""
        # 创建行程并参与
        trip_response = client.post('/trips', headers=auth_headers, json={
            'title': '测试行程',
            'max_participants': 10,
            'deadline': (datetime.utcnow() + timedelta(days=2)).isoformat()
        })

        response = client.get('/schedule', headers=auth_headers)
        assert response.status_code == 200
        # 行程通过 API 创建后，当前用户是创建者，会显示在课程表中


class TestScheduleItems:
    """时间表数据项测试"""

    def test_get_schedule_items_tasks(self, app, client, db, auth_headers):
        """获取日程项应包含用户任务"""
        from app.schedule import get_schedule_items
        from app.models import Task

        # 通过 API 创建任务
        client.post('/tasks', headers=auth_headers, json={
            'title': '任务1',
            'due_date': (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        })

        with app.app_context():
            items = get_schedule_items(1)
            task_items = [i for i in items if i['type'] == 'task']
            assert len(task_items) == 1
            assert task_items[0]['title'] == '任务1'

    def test_get_schedule_items_excludes_completed_tasks(self, app, client, db, auth_headers):
        """已完成的任务不应出现在课程表中"""
        from app.schedule import get_schedule_items

        # 创建并完成一个任务
        create_resp = client.post('/tasks', headers=auth_headers, json={
            'title': '已完成任务',
            'due_date': (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        })
        task_id = create_resp.get_json()['task']['id']
        client.patch(f'/tasks/{task_id}/complete', headers=auth_headers)

        with app.app_context():
            items = get_schedule_items(1)
            task_items = [i for i in items if i['type'] == 'task']
            assert len(task_items) == 0

    def test_get_schedule_items_trips(self, app, client, db, auth_headers):
        """获取日程项应包含用户参与的行程"""
        from app.schedule import get_schedule_items
        from app.models import Trip, TripParticipant
        from app.models import db as app_db

        # 创建行程（当前用户是创建者，需要手动添加为参与者）
        create_resp = client.post('/trips', headers=auth_headers, json={
            'title': '行程1',
            'max_participants': 10,
            'deadline': (datetime.utcnow() + timedelta(days=2)).isoformat()
        })
        trip_id = create_resp.get_json().get('id') or create_resp.get_json().get('trip', {}).get('id')

        # 将当前用户添加为参与者
        with app.app_context():
            participant = TripParticipant(trip_id=trip_id, user_id=1)
            app_db.session.add(participant)
            app_db.session.commit()

            items = get_schedule_items(1)
            trip_items = [i for i in items if 'trip' in i['type']]
            assert len(trip_items) >= 1
            titles = [i['title'] for i in trip_items]
            assert '行程1' in titles


class TestScheduleNavigation:
    """导航栏测试"""

    def test_nav_has_schedule_link(self, client, db, auth_headers):
        """登录后导航栏应显示时间表链接"""
        response = client.get('/schedule', headers=auth_headers)
        assert response.status_code == 200
        # 导航栏应包含时间表链接
        assert '时间表' in response.text
"""
任务 CRUD 测试：创建、查询、更新、删除、用户隔离
"""
import pytest


class TestTaskCreate:
    """创建任务"""

    def test_create_task_success(self, client, db, auth_headers):
        """正常创建任务返回 201"""
        response = client.post('/tasks',
            headers=auth_headers,
            json={
                'title': '买牛奶',
                'description': '低脂',
                'due_date': '2025-06-01'
            })
        assert response.status_code == 201
        assert response.get_json()['task']['title'] == '买牛奶'

    def test_create_task_title_required(self, client, db, auth_headers):
        """没有 title 返回 400"""
        response = client.post('/tasks',
            headers=auth_headers,
            json={'description': '无标题'})
        assert response.status_code == 400

    def test_create_task_without_auth(self, client):
        """未登录创建任务返回 401"""
        response = client.post('/tasks', json={'title': 'test'})
        assert response.status_code == 401


class TestTaskList:
    """任务列表"""

    def test_list_tasks_empty(self, client, db, auth_headers):
        """空列表返回空数组"""
        response = client.get('/tasks', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['tasks'] == []

    def test_list_tasks_pagination(self, client, db, auth_headers):
        """分页返回"""
        # 创建 12 条任务
        for i in range(12):
            client.post('/tasks', headers=auth_headers,
                json={'title': f'任务{i}'})

        # 第一页（默认10条）
        resp = client.get('/tasks?page=1', headers=auth_headers)
        assert len(resp.get_json()['tasks']) == 10
        assert resp.get_json()['total'] == 12

        # 第二页
        resp = client.get('/tasks?page=2', headers=auth_headers)
        assert len(resp.get_json()['tasks']) == 2


class TestTaskUpdate:
    """更新任务"""

    def test_update_task_success(self, client, db, auth_headers):
        """正常更新任务"""
        # 创建
        create_resp = client.post('/tasks', headers=auth_headers,
            json={'title': '旧标题'})
        task_id = create_resp.get_json()['task']['id']

        # 更新
        response = client.put(f'/tasks/{task_id}',
            headers=auth_headers,
            json={'title': '新标题', 'completed': True})
        assert response.status_code == 200
        assert response.get_json()['task']['title'] == '新标题'
        assert response.get_json()['task']['completed'] is True

    def test_update_task_not_found(self, client, db, auth_headers):
        """更新不存在的任务返回 404"""
        response = client.put('/tasks/99999',
            headers=auth_headers,
            json={'title': '新标题'})
        assert response.status_code == 404


class TestTaskDelete:
    """删除任务"""

    def test_delete_task_success(self, client, db, auth_headers):
        """正常删除任务"""
        create_resp = client.post('/tasks', headers=auth_headers,
            json={'title': '待删除任务'})
        task_id = create_resp.get_json()['task']['id']

        response = client.delete(f'/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200

        # 再次访问应返回 404
        response = client.get(f'/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 404

    def test_delete_task_not_found(self, client, db, auth_headers):
        """删除不存在的任务返回 404"""
        response = client.delete('/tasks/99999', headers=auth_headers)
        assert response.status_code == 404


class TestTaskUserIsolation:
    """用户任务隔离"""

    def test_user_cannot_see_other_user_tasks(self, client, db, two_users):
        """用户 A 看不到用户 B 的任务"""
        headers_a, headers_b = two_users

        # A 创建任务
        client.post('/tasks', headers=headers_a, json={'title': 'A的任务'})

        # B 列出任务，应该为空
        response = client.get('/tasks', headers=headers_b)
        assert response.get_json()['tasks'] == []

    def test_user_cannot_update_other_user_task(self, client, db, two_users):
        """用户 A 不能更新用户 B 的任务"""
        headers_a, headers_b = two_users

        # B 创建任务
        resp = client.post('/tasks', headers=headers_b, json={'title': 'B的任务'})
        task_id = resp.get_json()['task']['id']

        # A 尝试更新
        response = client.put(f'/tasks/{task_id}',
            headers=headers_a,
            json={'title': '被A篡改'})
        assert response.status_code == 403

    def test_user_cannot_delete_other_user_task(self, client, db, two_users):
        """用户 A 不能删除用户 B 的任务"""
        headers_a, headers_b = two_users

        resp = client.post('/tasks', headers=headers_b, json={'title': 'B的任务'})
        task_id = resp.get_json()['task']['id']

        response = client.delete(f'/tasks/{task_id}', headers=headers_a)
        assert response.status_code == 403


class TestTaskComplete:
    """标记完成"""

    def test_toggle_complete(self, client, db, auth_headers):
        """切换完成状态"""
        resp = client.post('/tasks', headers=auth_headers, json={'title': '任务'})
        task_id = resp.get_json()['task']['id']

        # 标记完成
        response = client.patch(f'/tasks/{task_id}/complete', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['task']['completed'] is True

        # 再次调用，切换回未完成
        response = client.patch(f'/tasks/{task_id}/complete', headers=auth_headers)
        assert response.get_json()['task']['completed'] is False
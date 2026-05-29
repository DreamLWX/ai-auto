"""
Redis 缓存测试：缓存命中、缓存失效、用户隔离缓存
"""
import pytest


class TestCacheHit:
    """缓存命中测试"""

    def test_first_request_not_from_cache(self, client, db, auth_headers):
        """第一次请求不走缓存"""
        client.post('/tasks', headers=auth_headers, json={'title': '任务1'})
        response = client.get('/tasks', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json().get('from_cache') is False

    def test_second_request_from_cache(self, client, db, auth_headers, redis_client):
        """第二次请求走缓存（同一用户、同页）"""
        client.post('/tasks', headers=auth_headers, json={'title': '任务1'})

        # 第一次
        client.get('/tasks', headers=auth_headers)
        # 第二次
        response = client.get('/tasks', headers=auth_headers)
        assert response.get_json().get('from_cache') is True


class TestCacheInvalidation:
    """缓存失效测试"""

    def test_create_task_invalidates_cache(self, client, db, auth_headers, redis_client):
        """创建新任务后，缓存被清除"""
        # 先触发一次缓存
        client.get('/tasks', headers=auth_headers)
        response = client.get('/tasks', headers=auth_headers)
        assert response.get_json().get('from_cache') is True

        # 创建任务
        client.post('/tasks', headers=auth_headers, json={'title': '新任务'})

        # 再次请求，应重新查库（from_cache=False）
        response = client.get('/tasks', headers=auth_headers)
        assert response.get_json().get('from_cache') is False

    def test_update_task_invalidates_cache(self, client, db, auth_headers, redis_client):
        """更新任务后，缓存被清除"""
        resp = client.post('/tasks', headers=auth_headers, json={'title': '任务'})
        task_id = resp.get_json()['task']['id']

        client.get('/tasks', headers=auth_headers)  # 触发缓存

        client.put(f'/tasks/{task_id}', headers=auth_headers, json={'title': '更新'})

        response = client.get('/tasks', headers=auth_headers)
        assert response.get_json().get('from_cache') is False

    def test_delete_task_invalidates_cache(self, client, db, auth_headers, redis_client):
        """删除任务后，缓存被清除"""
        resp = client.post('/tasks', headers=auth_headers, json={'title': '任务'})
        task_id = resp.get_json()['task']['id']

        client.get('/tasks', headers=auth_headers)  # 触发缓存

        client.delete(f'/tasks/{task_id}', headers=auth_headers)

        response = client.get('/tasks', headers=auth_headers)
        assert response.get_json().get('from_cache') is False


class TestCacheUserIsolation:
    """缓存用户隔离"""

    def test_users_have_separate_cache(self, client, db, two_users, redis_client):
        """用户 A 的缓存不会影响用户 B"""
        headers_a, headers_b = two_users

        # A 查任务（缓存）
        client.get('/tasks', headers=headers_a)
        resp_a = client.get('/tasks', headers=headers_a)
        assert resp_a.get_json().get('from_cache') is True

        # B 查任务（冷启动，应为 False）
        resp_b = client.get('/tasks', headers=headers_b)
        assert resp_b.get_json().get('from_cache') is False

        # B 有自己的缓存
        resp_b2 = client.get('/tasks', headers=headers_b)
        assert resp_b2.get_json().get('from_cache') is True


class TestBlacklist:
    """Token 黑名单测试（Redis）"""

    def test_blacklisted_token_rejected(self, client, db, auth_headers):
        """登出后的 token 无法访问受保护路由"""
        # 验证 token 有效
        response = client.get('/auth/api/profile', headers=auth_headers)
        assert response.status_code == 200

        # 登出
        client.post('/auth/api/logout', headers=auth_headers)

        # token 已被拉黑
        response = client.get('/auth/api/profile', headers=auth_headers)
        assert response.status_code == 401

    def test_other_tokens_still_work(self, client, db, two_users, auth_headers):
        """用户 A 登出不影响用户 B 的 token"""
        headers_a, headers_b = two_users

        # A 登出
        client.post('/auth/api/logout', headers=headers_a)

        # B 的 token 仍然有效
        response = client.get('/auth/api/profile', headers=headers_b)
        assert response.status_code == 200
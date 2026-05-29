"""
认证模块测试：注册、登录、登出、Token 黑名单、用户隔离
"""
import pytest


class TestRegister:
    """注册接口"""

    def test_register_success(self, client):
        """正常注册返回 201"""
        response = client.post('/auth/api/register', json={
            'username': 'alice',
            'password': 'password123'
        })
        assert response.status_code == 201
        assert response.get_json()['message'] == 'User created'

    def test_register_duplicate_username(self, client, db):
        """重复用户名返回 409"""
        client.post('/auth/api/register', json={
            'username': 'alice', 'password': 'password123'
        })
        response = client.post('/auth/api/register', json={
            'username': 'alice', 'password': 'password123'
        })
        assert response.status_code == 409
        assert 'already exists' in response.get_json()['error']

    def test_register_short_password(self, client):
        """密码太短返回 400"""
        response = client.post('/auth/api/register', json={
            'username': 'alice',
            'password': '123'
        })
        assert response.status_code == 400

    def test_register_missing_fields(self, client):
        """缺少字段返回 400"""
        response = client.post('/auth/api/register', json={'username': 'alice'})
        assert response.status_code == 400

        response = client.post('/auth/api/register', json={'password': 'password123'})
        assert response.status_code == 400


class TestLogin:
    """登录接口"""

    def test_login_success(self, client, db):
        """正确账号密码返回 token"""
        client.post('/auth/api/register', json={
            'username': 'alice', 'password': 'password123'
        })
        response = client.post('/auth/api/login', json={
            'username': 'alice',
            'password': 'password123'
        })
        assert response.status_code == 200
        assert 'access_token' in response.get_json()

    def test_login_wrong_password(self, client, db):
        """密码错误返回 401"""
        client.post('/auth/api/register', json={
            'username': 'alice', 'password': 'password123'
        })
        response = client.post('/auth/api/login', json={
            'username': 'alice',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """用户不存在返回 401"""
        response = client.post('/auth/api/login', json={
            'username': 'nobody',
            'password': 'password123'
        })
        assert response.status_code == 401


class TestLogout:
    """登出接口"""

    def test_logout_adds_to_blacklist(self, client, db, auth_headers):
        """登出后 token 被加入黑名单，无法再用"""
        # 先确认 token 可用
        response = client.get('/auth/api/profile', headers=auth_headers)
        assert response.status_code == 200

        # 登出
        client.post('/auth/api/logout', headers=auth_headers)

        # 再次使用同一个 token 访问受保护路由，应失败
        response = client.get('/auth/api/profile', headers=auth_headers)
        assert response.status_code == 401

    def test_logout_without_token(self, client):
        """没有 token 的 logout 返回 401"""
        response = client.post('/auth/api/logout')
        assert response.status_code == 401


class TestProfile:
    """受保护路由"""

    def test_profile_with_valid_token(self, client, db, auth_headers):
        """带有效 token 获取用户信息"""
        response = client.get('/auth/api/profile', headers=auth_headers)
        assert response.status_code == 200
        assert 'username' in response.get_json()

    def test_profile_without_token(self, client):
        """不带 token 返回 401"""
        response = client.get('/auth/api/profile')
        assert response.status_code == 401

    def test_profile_with_invalid_token(self, client):
        """无效 token 返回 401 或 422"""
        response = client.get('/auth/api/profile', headers={
            'Authorization': 'Bearer invalid.token.here'
        })
        assert response.status_code in (401, 422)
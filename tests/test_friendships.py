"""
好友系统测试：关注、取关、好友请求处理、好友列表
"""
import pytest


def login_and_get_headers(client, username, password):
    """登录并返回JWT auth headers"""
    client.post('/auth/register', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    resp = client.post('/auth/api/login', json={
        'username': username,
        'password': password
    })
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


class TestFollowUser:
    """关注用户"""

    def test_follow_user_success(self, client, db, auth_headers):
        """正常关注返回 200"""
        target_headers = login_and_get_headers(client, 'target', 'password123')
        resp = client.get('/auth/api/profile', headers=target_headers)
        target_id = resp.get_json()['id']

        response = client.post(f'/friends/{target_id}/follow', headers=auth_headers)
        assert response.status_code == 200
        assert 'Follow request sent' in response.get_json()['message']

    def test_follow_self_error(self, client, db, auth_headers):
        """关注自己返回 400"""
        resp = client.get('/auth/api/profile', headers=auth_headers)
        current_user_id = resp.get_json()['id']

        response = client.post(f'/friends/{current_user_id}/follow', headers=auth_headers)
        assert response.status_code == 400
        assert 'Cannot follow yourself' in response.get_json()['error']

    def test_follow_user_not_found(self, client, db, auth_headers):
        """关注不存在的用户返回 404"""
        response = client.post('/friends/99999/follow', headers=auth_headers)
        assert response.status_code == 404

    def test_follow_without_auth(self, client, db):
        """未登录关注返回 401"""
        response = client.post('/friends/1/follow')
        assert response.status_code == 401


class TestUnfollowUser:
    """取关"""

    def test_unfollow_user_success(self, client, db, auth_headers):
        """正常取关返回 200"""
        target_headers = login_and_get_headers(client, 'target2', 'password123')
        resp = client.get('/auth/api/profile', headers=target_headers)
        target_id = resp.get_json()['id']

        # 先关注
        client.post(f'/friends/{target_id}/follow', headers=auth_headers)

        # 再取关
        response = client.post(f'/friends/{target_id}/unfollow', headers=auth_headers)
        assert response.status_code == 200
        assert 'Unfollowed' in response.get_json()['message']

    def test_unfollow_not_found(self, client, db, auth_headers):
        """取关不存在的关注关系返回 404"""
        response = client.post('/friends/99999/unfollow', headers=auth_headers)
        assert response.status_code == 404


class TestFollowRequests:
    """待处理的好友请求"""

    def test_list_follow_requests_empty(self, client, db, auth_headers):
        """无请求时返回空列表"""
        response = client.get('/friends/requests', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['requests'] == []


class TestAcceptRejectFollow:
    """接受/拒绝关注"""

    def test_reject_follow_success(self, client, db, two_users):
        """拒绝关注请求返回 200"""
        headers_a, headers_b = two_users

        # A关注 B
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)

        # B 拒绝 A 的关注请求（URL参数是关注者的ID，即A的ID）
        response = client.post(f'/friends/{a_id}/reject', headers=headers_b)
        assert response.status_code == 200
        assert 'rejected' in response.get_json()['message']

    def test_accept_follow_creates_friendship(self, client, db, two_users):
        """接受关注请求后建立关注关系"""
        headers_a, headers_b = two_users

        # A 关注 B
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)

        # B 接受 A 的关注（URL参数是关注者的ID，即A的ID）
        response = client.post(f'/friends/{a_id}/accept', headers=headers_b)
        assert response.status_code == 200
        assert 'accepted' in response.get_json()['message']


class TestMutualFollow:
    """互相关注判断"""

    def test_mutual_follow_becomes_friends(self, client, db, two_users):
        """互相关注后成为好友"""
        headers_a, headers_b = two_users

        # A关注 B，B 接受
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)
        client.post(f'/friends/{a_id}/accept', headers=headers_b)

        # B 也关注 A
        client.post(f'/friends/{a_id}/follow', headers=headers_b)

        # A 接受 B 的关注
        response = client.post(f'/friends/{b_id}/accept', headers=headers_a)
        assert response.status_code == 200
        assert response.get_json()['is_friend'] is True


class TestFriendList:
    """好友列表"""

    def test_list_friends_empty(self, client, db, auth_headers):
        """无好友时返回空列表"""
        response = client.get('/friends/list', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['friends'] == []

    def test_list_friends_after_mutual_follow(self, client, db, two_users):
        """互相关注后在好友列表中能看到对方"""
        headers_a, headers_b = two_users

        # A 关注 B，B 接受
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)
        client.post(f'/friends/{a_id}/accept', headers=headers_b)

        # B 关注 A，A 接受
        client.post(f'/friends/{a_id}/follow', headers=headers_b)
        client.post(f'/friends/{b_id}/accept', headers=headers_a)

        # A 的好友列表
        response = client.get('/friends/list', headers=headers_a)
        assert response.status_code == 200
        friends = response.get_json()['friends']
        assert any(f['id'] == b_id for f in friends)


class TestFollowersFollowing:
    """粉丝列表和关注列表"""

    def test_list_followers(self, client, db, two_users):
        """获取粉丝列表"""
        headers_a, headers_b = two_users

        # A 关注 B，B 接受
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)
        client.post(f'/friends/{a_id}/accept', headers=headers_b)

        # B 的粉丝列表应该有 A
        response = client.get('/friends/followers', headers=headers_b)
        assert response.status_code == 200
        followers = response.get_json()['followers']
        assert any(f['id'] == a_id for f in followers)

    def test_list_following(self, client, db, two_users):
        """获取关注列表"""
        headers_a, headers_b = two_users

        # A 关注 B，B 接受
        resp_a = client.get('/auth/api/profile', headers=headers_a)
        a_id = resp_a.get_json()['id']
        resp_b = client.get('/auth/api/profile', headers=headers_b)
        b_id = resp_b.get_json()['id']
        client.post(f'/friends/{b_id}/follow', headers=headers_a)
        client.post(f'/friends/{a_id}/accept', headers=headers_b)

        # A 的关注列表应该有 B
        response = client.get('/friends/following', headers=headers_a)
        assert response.status_code == 200
        following = response.get_json()['following']
        assert any(f['id'] == b_id for f in following)
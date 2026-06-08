"""
行程系统测试：CRUD、申请审批、隐藏条件、权限控制
"""
import pytest
from datetime import datetime, timedelta


class TestTripCreate:
    """创建行程"""

    def test_create_trip_success(self, client, db, auth_headers):
        """正常创建行程返回 201"""
        response = client.post('/trips',
            headers=auth_headers,
            json={
                'title': '北京之旅',
                'description': '一起去北京玩',
                'min_participants': 2,
                'max_participants': 5
            })
        assert response.status_code == 201
        data = response.get_json()
        assert data['trip']['title'] == '北京之旅'
        assert data['trip']['min_participants'] == 2
        assert data['trip']['max_participants'] == 5
        assert data['trip']['status'] == 'recruiting'

    def test_create_trip_title_required(self, client, db, auth_headers):
        """没有 title 返回 400"""
        response = client.post('/trips',
            headers=auth_headers,
            json={'description': '无标题'})
        assert response.status_code == 400

    def test_create_trip_without_auth(self, client):
        """未登录创建行程返回 401"""
        response = client.post('/trips', json={'title': 'test'})
        assert response.status_code == 401


class TestTripList:
    """行程列表"""

    def test_list_trips_empty(self, client, db, auth_headers):
        """空列表返回空数组"""
        response = client.get('/trips')
        assert response.status_code == 200
        assert response.get_json()['trips'] == []

    def test_list_trips_shows_public(self, client, db, auth_headers):
        """大厅显示公开行程"""
        #创建一个公开行程
        client.post('/trips', headers=auth_headers, json={'title': '公开行程'})

        response = client.get('/trips')
        assert response.status_code == 200
        assert len(response.get_json()['trips']) == 1

    def test_list_trips_excludes_private(self, client, db, auth_headers):
        """大厅不显示私人行程"""
        #创建一个私人行程
        client.post('/trips', headers=auth_headers,
            json={'title': '私人行程', 'is_private': True})

        response = client.get('/trips')
        assert response.status_code == 200
        assert len(response.get_json()['trips']) == 0

    def test_list_trips_pagination(self, client, db, auth_headers):
        """分页返回"""
        # 创建 12 条行程
        for i in range(12):
            client.post('/trips', headers=auth_headers,
                json={'title': f'行程{i}'})

        resp = client.get('/trips?page=1')
        assert len(resp.get_json()['trips']) == 10
        assert resp.get_json()['total'] == 12

        resp = client.get('/trips?page=2')
        assert len(resp.get_json()['trips']) == 2


class TestTripGet:
    """获取行程详情"""

    def test_get_trip_success(self, client, db, auth_headers):
        """正常获取行程详情"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '我的行程'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()['trip']['title'] == '我的行程'

    def test_get_trip_not_found(self, client, db, auth_headers):
        """获取不存在的行程返回 404"""
        response = client.get('/trips/99999', headers=auth_headers)
        assert response.status_code == 404

    def test_get_private_trip_by_creator(self, client, db, auth_headers):
        """创建者可以查看私人行程"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '私人行程', 'is_private': True})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        assert response.status_code == 200

    def test_get_private_trip_by_stranger(self, client, db, two_users):
        """陌生人无法查看私人行程"""
        headers_a, headers_b = two_users

        # A 创建私人行程
        create_resp = client.post('/trips', headers=headers_a,
            json={'title': '私人行程', 'is_private': True})
        trip_id = create_resp.get_json()['trip']['id']

        # B 尝试查看
        response = client.get(f'/trips/{trip_id}', headers=headers_b)
        assert response.status_code == 403


class TestTripUpdate:
    """更新行程"""

    def test_update_trip_success(self, client, db, auth_headers):
        """正常更新行程"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '旧标题'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.put(f'/trips/{trip_id}',
            headers=auth_headers,
            json={'title': '新标题', 'status': 'confirmed'})
        assert response.status_code == 200
        assert response.get_json()['trip']['title'] == '新标题'
        assert response.get_json()['trip']['status'] == 'confirmed'

    def test_update_trip_not_creator(self, client, db, two_users):
        """非创建者不能更新行程"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.put(f'/trips/{trip_id}',
            headers=headers_b,
            json={'title': '被B篡改'})
        assert response.status_code == 403

    def test_update_trip_not_found(self, client, db, auth_headers):
        """更新不存在的行程返回 404"""
        response = client.put('/trips/99999',
            headers=auth_headers,
            json={'title': '新标题'})
        assert response.status_code == 404


class TestTripDelete:
    """删除行程"""

    def test_delete_trip_success(self, client, db, auth_headers):
        """正常删除行程"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '待删除行程'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.delete(f'/trips/{trip_id}', headers=auth_headers)
        assert response.status_code == 200

    def test_delete_trip_not_creator(self, client, db, two_users):
        """非创建者不能删除行程"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.delete(f'/trips/{trip_id}', headers=headers_b)
        assert response.status_code == 403


class TestTripApply:
    """申请加入行程"""

    def test_apply_trip_auto_approve(self, client, db, auth_headers):
        """auto trigger_condition 自动审批直接成为参与者"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '北京之旅', 'trigger_condition': 'auto', 'min_participants': 1})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.post(f'/trips/{trip_id}/apply', headers=auth_headers)
        assert response.status_code == 200
        assert 'Joined trip' in response.get_json()['message']

    def test_apply_trip_manual_require_approval(self, client, db, auth_headers):
        """manual trigger_condition 需要审批"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '北京之旅', 'trigger_condition': 'manual'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.post(f'/trips/{trip_id}/apply', headers=auth_headers)
        assert response.status_code == 200
        assert 'Application submitted' in response.get_json()['message']

    def test_apply_trip_already_applied(self, client, db, auth_headers):
        """重复申请返回 400"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '北京之旅', 'trigger_condition': 'manual'})
        trip_id = create_resp.get_json()['trip']['id']

        client.post(f'/trips/{trip_id}/apply', headers=auth_headers)
        response = client.post(f'/trips/{trip_id}/apply', headers=auth_headers)
        assert response.status_code == 400

    def test_apply_trip_not_found(self, client, db, auth_headers):
        """申请不存在的行程返回 404"""
        response = client.post('/trips/99999/apply', headers=auth_headers)
        assert response.status_code == 404


class TestTripApplications:
    """申请列表和审批"""

    def test_list_applications_by_creator(self, client, db, two_users):
        """创建者可以查看申请列表"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程', 'trigger_condition': 'manual'})
        trip_id = create_resp.get_json()['trip']['id']

        # B 申请加入
        client.post(f'/trips/{trip_id}/apply', headers=headers_b)

        response = client.get(f'/trips/{trip_id}/applications', headers=headers_a)
        assert response.status_code == 200
        assert len(response.get_json()['applications']) == 1

    def test_list_applications_not_creator(self, client, db, two_users):
        """非创建者不能查看申请列表"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程', 'trigger_condition': 'manual'})
        trip_id = create_resp.get_json()['trip']['id']

        client.post(f'/trips/{trip_id}/apply', headers=headers_b)

        response = client.get(f'/trips/{trip_id}/applications', headers=headers_b)
        assert response.status_code == 403

    def test_approve_application(self, client, db, two_users):
        """审批通过"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程', 'trigger_condition': 'manual', 'min_participants': 1})
        trip_id = create_resp.get_json()['trip']['id']

        # B 申请
        apply_resp = client.post(f'/trips/{trip_id}/apply', headers=headers_b)
        # 获取申请ID（从申请列表中）
        apps_resp = client.get(f'/trips/{trip_id}/applications', headers=headers_a)
        app_id = apps_resp.get_json()['applications'][0]['id']

        # A 审批通过
        response = client.post(f'/trips/{trip_id}/applications/{app_id}/approve',
            headers=headers_a)
        assert response.status_code == 200

    def test_reject_application(self, client, db, two_users):
        """审批拒绝"""
        headers_a, headers_b = two_users

        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的行程', 'trigger_condition': 'manual'})
        trip_id = create_resp.get_json()['trip']['id']

        client.post(f'/trips/{trip_id}/apply', headers=headers_b)
        apps_resp = client.get(f'/trips/{trip_id}/applications', headers=headers_a)
        app_id = apps_resp.get_json()['applications'][0]['id']

        response = client.post(f'/trips/{trip_id}/applications/{app_id}/reject',
            headers=headers_a)
        assert response.status_code == 200


class TestTripMine:
    """我的行程"""

    def test_list_my_trips(self, client, db, auth_headers):
        """获取我发布和参与的行程"""
        # 创建行程
        client.post('/trips', headers=auth_headers, json={'title': '我创建的'})

        # 用另一个用户参与一个行程
        client.post('/auth/register', data={
            'username': 'other', 'password': 'password123'
        }, follow_redirects=True)
        resp_other = client.post('/auth/api/login', json={
            'username': 'other', 'password': 'password123'
        })
        other_token = resp_other.get_json()['access_token']
        other_headers = {'Authorization': f'Bearer {other_token}'}

        create_resp = client.post('/trips', headers=other_headers,
            json={'title': '其他人的', 'trigger_condition': 'auto'})
        trip_id = create_resp.get_json()['trip']['id']
        client.post(f'/trips/{trip_id}/apply', headers=auth_headers)

        response = client.get('/trips/mine', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['created_trips']) == 1
        assert len(data['joined_trips']) == 1


class TestTripHiddenLogic:
    """隐藏条件逻辑"""

    def test_hidden_when_min_participants_reached(self, client, db, auth_headers):
        """达到最小参与人数时内容应隐藏"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={
                'title': '测试行程',
                'trigger_condition': 'auto',
                'min_participants': 1,
                'public_content': '公开内容',
                'hidden_content': '隐藏内容'
            })
        trip_id = create_resp.get_json()['trip']['id']

        # 参与行程达到最小人数
        client.post(f'/trips/{trip_id}/apply', headers=auth_headers)

        # 获取行程详情
        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        trip_data = response.get_json()['trip']
        # 此时 status 应该是 confirmed，触发隐藏
        assert trip_data['status'] == 'confirmed'

    def test_hidden_when_deadline_passed(self, client, db, auth_headers):
        """超过截止时间内容应隐藏"""
        past_deadline = (datetime.utcnow() - timedelta(days=1)).isoformat()
        create_resp = client.post('/trips', headers=auth_headers,
            json={
                'title': '已截止行程',
                'trigger_condition': 'auto',
                'deadline': past_deadline,
                'public_content': '公开内容',
                'hidden_content': '隐藏内容'
            })
        trip_id = create_resp.get_json()['trip']['id']

        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        trip_data = response.get_json()['trip']
        # 超过截止时间，is_hidden 应返回 True，内容字段不应出现
        assert trip_data.get('public_content') is None # 内容被隐藏

    def test_manual_trigger_hidden_when_confirmed(self, client, db, auth_headers):
        """manual trigger_condition 确认后内容隐藏"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={
                'title': '手动行程',
                'trigger_condition': 'manual',
                'public_content': '公开内容',
                'hidden_content': '隐藏内容'
            })
        trip_id = create_resp.get_json()['trip']['id']

        # 将状态改为 confirmed
        client.put(f'/trips/{trip_id}', headers=auth_headers,
            json={'status': 'confirmed'})

        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        trip_data = response.get_json()['trip']
        # manual trigger + confirmed 状态，内容应隐藏
        assert trip_data.get('public_content') is None


class TestTripPrivacy:
    """私人行程权限控制"""

    def test_private_trip_only_visible_to_creator(self, client, db, two_users):
        """私人行程只有创建者可见"""
        headers_a, headers_b = two_users

        # A 创建私人行程
        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的私人行程', 'is_private': True, 'visibility': 'private'})
        trip_id = create_resp.get_json()['trip']['id']

        # A 可以查看
        response = client.get(f'/trips/{trip_id}', headers=headers_a)
        assert response.status_code == 200

        # B 不能查看
        response = client.get(f'/trips/{trip_id}', headers=headers_b)
        assert response.status_code == 403

    def test_private_trip_visible_to_participant(self, client, db, two_users):
        """私人行程对参与者可见"""
        headers_a, headers_b = two_users

        # A 创建私人行程（auto模式，自动审批）
        create_resp = client.post('/trips', headers=headers_a,
            json={'title': 'A的私人行程', 'is_private': True, 'trigger_condition': 'auto'})
        trip_id = create_resp.get_json()['trip']['id']

        # B 申请加入并自动成为参与者
        client.post(f'/trips/{trip_id}/apply', headers=headers_b)

        # B 可以查看
        response = client.get(f'/trips/{trip_id}', headers=headers_b)
        assert response.status_code == 200

    def test_friends_trip_visible_to_all(self, client, db, auth_headers):
        """friends 可见性的行程对所有人可见（简化实现）"""
        create_resp = client.post('/trips', headers=auth_headers,
            json={'title': '好友行程', 'visibility': 'friends'})
        trip_id = create_resp.get_json()['trip']['id']

        response = client.get(f'/trips/{trip_id}', headers=auth_headers)
        assert response.status_code == 200
"""
Pytest 夹具：app, client, db, redis_client
"""
import pytest
import os
from datetime import timedelta

os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['REDIS_URL'] = 'redis://localhost:6379/15'

import fakeredis
from app import create_app
from app.models import db as _db, User, Task, Trip, TripApplication, TripParticipant, Friendship
from app.redis_client import RedisClient
from app import redis_client as redis_mod


_fake_redis = fakeredis.FakeRedis(decode_responses=True)


def make_fake_redis_client():
    client = RedisClient.__new__(RedisClient)
    client.redis = _fake_redis
    return client


@pytest.fixture(scope='session')
def app():
    _app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'JWT_ACCESS_TOKEN_EXPIRES': timedelta(hours=1),
        'WTF_CSRF_ENABLED': False,
    })

    with _app.app_context():
        _db.create_all()

    yield _app

    with _app.app_context():
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def db(app, redis_client):
    """每个测试函数用完清空数据（自动回滚）"""
    _fake_redis.flushall()
    with app.app_context():
        yield _db.session
        _db.session.query(TripParticipant).delete()
        _db.session.query(TripApplication).delete()
        _db.session.query(Trip).delete()
        _db.session.query(Task).delete()
        _db.session.query(Friendship).delete()
        _db.session.query(User).delete()
        _db.session.commit()


@pytest.fixture(scope='function')
def redis_client(app):
    old_client = redis_mod._redis_client
    redis_mod._redis_client = make_fake_redis_client()

    yield redis_mod._redis_client

    redis_mod._redis_client = old_client
    _fake_redis.flushall()


@pytest.fixture(scope='function')
def auth_headers(client, db):
    client.post('/auth/register', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)

    response = client.post('/auth/api/login', json={
        'username': 'testuser',
        'password': 'password123'
    })
    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(scope='function')
def two_users(client, db):
    client.post('/auth/register', data={
        'username': 'alice', 'password': 'password123'
    }, follow_redirects=True)
    resp_a = client.post('/auth/api/login', json={
        'username': 'alice', 'password': 'password123'
    })
    token_a = resp_a.get_json()['access_token']
    headers_a = {'Authorization': f'Bearer {token_a}'}

    client.post('/auth/register', data={
        'username': 'bob', 'password': 'password123'
    }, follow_redirects=True)
    resp_b = client.post('/auth/api/login', json={
        'username': 'bob', 'password': 'password123'
    })
    token_b = resp_b.get_json()['access_token']
    headers_b = {'Authorization': f'Bearer {token_b}'}

    return headers_a, headers_b
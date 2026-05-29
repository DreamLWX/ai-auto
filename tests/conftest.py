"""
Pytest 夹具：app, client, db, redis_client
"""
import pytest
import tempfile
import os
from datetime import timedelta

# 在 import app 之前设置测试环境变量
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['REDIS_URL'] = 'redis://localhost:6379/15'  # 用 db 15 避免污染生产数据

from app import create_app
from app.models import db as _db, User, Task
from app.redis_client import init_redis, _redis_client, RedisClient
import fakeredis


@pytest.fixture(scope='session')
def app():
    """创建测试用 Flask app（内存 SQLite）"""
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
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """每个测试函数用独立的数据库 session（自动回滚）"""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        # 让 db.session 使用这个连接
        session_options = dict(bind=connection, binds={})
        session = _db.create_scoped_session(options=session_options)
        _db.session = session

        yield session

        # 回滚并关闭
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture(scope='function')
def redis_client(app):
    """使用 fakeredis 模拟 Redis（每个测试独立）"""
    with app.app_context():
        # 替换全局单例为 fakeredis
        fake = fakeredis.FakeRedis(decode_responses=True)
        fake_redis = RedisClient.__new__(RedisClient)
        fake_redis.redis = fake

        global _redis_client
        old_client = _redis_client
        _redis_client = fake_redis

        yield fake_redis

        _redis_client = old_client
        fake.close()


@pytest.fixture(scope='function')
def auth_headers(client, db):
    """注册+登录，返回含 token 的请求头"""
    client.post('/auth/register', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)

    # 用 API 登录获取 token
    response = client.post('/auth/api/login', json={
        'username': 'testuser',
        'password': 'password123'
    })
    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(scope='function')
def two_users(client, db):
    """创建两个测试用户，各返回 token header"""
    # 用户 A
    client.post('/auth/register', data={
        'username': 'alice', 'password': 'password123'
    }, follow_redirects=True)
    resp_a = client.post('/auth/api/login', json={
        'username': 'alice', 'password': 'password123'
    })
    token_a = resp_a.get_json()['access_token']
    headers_a = {'Authorization': f'Bearer {token_a}'}

    # 用户 B
    client.post('/auth/register', data={
        'username': 'bob', 'password': 'password123'
    }, follow_redirects=True)
    resp_b = client.post('/auth/api/login', json={
        'username': 'bob', 'password': 'password123'
    })
    token_b = resp_b.get_json()['access_token']
    headers_b = {'Authorization': f'Bearer {token_b}'}

    return headers_a, headers_b
"""
Flask 应用工厂
初始化 SQLAlchemy、JWT、Redis 等扩展
"""
import os
from flask import Flask, request, jsonify, make_response
from flask_jwt_extended import JWTManager
from datetime import timedelta

from .models import db
from .redis_client import init_redis, get_redis


def create_app(config: dict = None) -> Flask:
    """
    Flask 应用工厂函数

    Args:
        config: 可选的配置字典，默认从环境变量读取

    Returns:
        Flask 实例
    """
    app = Flask(__name__)

    # ==================== 基础配置 ====================
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///ai_todo_pro.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ==================== JWT 配置 ====================
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(
        seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    )
    # 允许从 Cookie 或 Authorization 头读取 JWT
    app.config['JWT_TOKEN_LOCATION'] = ('headers', 'cookies')
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
    app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
    # 关闭 CSRF（Cookie 认证天然防 CSRF，SameSite 保护）
    app.config['JWT_CSRF_ENABLED'] = False
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False

    # ==================== 初始化扩展 ====================
    db.init_app(app)
    jwt = JWTManager(app)

    # ==================== 注册蓝图 ====================
    from .auth import auth_bp
    from .tasks import tasks_bp
    from .friendships import friends_bp
    from .trips import trips_bp
    from .schedule import schedule_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(friends_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(schedule_bp)

    from .auth import inject_current_user
    app.context_processor(inject_current_user)

    # 自定义 JWT 验证回调：检查 token 是否在黑名单（在蓝图注册后定义）
    from flask_jwt_extended import verify_jwt_in_request, get_jwt

    @app.before_request
    def check_token_not_blacklisted():
        """在每个请求前检查 JWT 是否已被登出"""
        if 'Authorization' in request.headers:
            try:
                verify_jwt_in_request()
                jti = get_jwt()['jti']
                try:
                    redis_client = get_redis()
                    if redis_client.is_blacklisted(jti):
                        return make_response(jsonify({'error': 'Token has been revoked'}), 401)
                except Exception:
                    pass
            except Exception:
                pass

    # ==================== 初始化 Redis ====================
    redis_url = app.config.get('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    init_redis(redis_url)

    # ==================== 创建数据库表 ====================
    with app.app_context():
        db.create_all()

    # ==================== 路由：首页 ====================
    @app.route('/')
    def index():
        return {
            'message': 'AI-Todo Pro API',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/auth/register, /auth/login, /auth/logout, /auth/profile',
                'tasks': '/tasks (GET, POST), /tasks/<id> (PUT, DELETE), /tasks/<id>/complete (PATCH)'
            }
        }

    return app
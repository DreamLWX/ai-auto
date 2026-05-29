"""
Flask 应用工厂
初始化 SQLAlchemy、JWT、Redis 等扩展
"""
import os
from flask import Flask, request
from flask_jwt_extended import JWTManager
from datetime import timedelta

from .models import db
from .redis_client import init_redis


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
    # JWT 过期时间（与 auth.py 里的 ACCESS_TOKEN_EXPIRES 保持一致）
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(
        seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    )

    # 自定义 JWT 验证回调：检查 token 是否在黑名单
    from .models import User
    from flask_jwt_extended import get_jwt, verify_jwt_in_request

    @app.before_request
    def check_token_not_blacklisted():
        """在每个请求前检查 JWT 是否已被登出"""
        # 只在有 Authorization 头时检查
        if 'Authorization' in request.headers:
            try:
                verify_jwt_in_request()
                jti = get_jwt()['jti']
                # 使用 get_redis() 复用已初始化的单例，避免重复创建连接
                redis_client = get_redis()
                if redis_client.is_blacklisted(jti):
                    return jsonify({'error': 'Token has been revoked'}), 401
            except Exception:
                # 没有 token 或格式错误，不阻挡（让路由自己的 @jwt_required() 处理）
                pass

    # ==================== 初始化扩展 ====================
    db.init_app(app)
    jwt = JWTManager(app)

    # 初始化 Redis
    redis_url = app.config.get('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    init_redis(redis_url)

    # ==================== 注册蓝图 ====================
    from .auth import auth_bp
    from .tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)

    # 注册 context_processor（让所有模板能访问 current_user）
    from .auth import inject_current_user
    app.context_processor(inject_current_user)

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
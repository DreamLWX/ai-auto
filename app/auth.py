"""
认证模块（Web 页面 + API）
"""
from datetime import timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, g, current_app
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    set_access_cookies,
    verify_jwt_in_request
)
import bcrypt

from .models import db, User
from .redis_client import get_redis

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ==================== Token 过期时间配置 ====================
ACCESS_TOKEN_EXPIRES = timedelta(hours=1)  # JWT 默认1小时过期


# ==================== API: JSON 接口 ====================

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """API: 用户注册（JSON）"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400

    username = data['username'].strip()
    password = data['password']

    if len(username) < 3 or len(username) > 80:
        return jsonify({'error': 'Username must be 3-80 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(username=username, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User created'}), 201


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """API: 用户登录（JSON）"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400

    username = data['username']
    password = data['password']
    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user.id), expires_delta=ACCESS_TOKEN_EXPIRES)
    return jsonify({'access_token': access_token}), 200


@auth_bp.route('/api/logout', methods=['POST'])
@jwt_required()
def api_logout():
    """API: 登出（JSON）"""
    jti = get_jwt()['jti']
    expires_in = get_jwt()['exp'] - get_jwt()['iat']
    try:
        get_redis().add_to_blacklist(jti, expires_in)
    except Exception:
        pass
    return jsonify({'message': 'Successfully logged out'}), 200


@auth_bp.route('/api/profile', methods=['GET'])
@jwt_required()
def api_profile():
    """API: 获取当前用户信息"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


# ==================== Web: 页面路由 ====================

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面（GET）+ 表单提交处理（POST）"""
    if request.method == 'GET':
        return render_template('register.html')

    # POST: 处理表单提交
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if len(username) < 3 or len(username) > 80:
        flash('用户名需要3-80个字符', 'danger')
        return redirect(url_for('auth.register'))

    if len(password) < 6:
        flash('密码至少6个字符', 'danger')
        return redirect(url_for('auth.register'))

    if User.query.filter_by(username=username).first():
        flash('用户名已存在', 'danger')
        return redirect(url_for('auth.register'))

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(username=username, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    flash('注册成功，请登录', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面（GET）+ 表单提交处理（POST）"""
    if request.method == 'GET':
        return render_template('login.html')

    # POST: 处理表单提交
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash('请输入用户名和密码', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        flash('用户名或密码错误', 'danger')
        return redirect(url_for('auth.login'))

    access_token = create_access_token(identity=str(user.id), expires_delta=ACCESS_TOKEN_EXPIRES)
    resp = redirect(url_for('tasks.list_tasks_page'))
    set_access_cookies(resp, access_token)
    return resp


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """登出（GET/POST 均可）"""
    jti = None
    expires_in = 3600
    try:
        verify_jwt_in_request()
        jti = get_jwt()['jti']
        expires_in = get_jwt()['exp'] - get_jwt()['iat']
    except Exception:
        pass

    if jti:
        try:
            get_redis().add_to_blacklist(jti, expires_in)
        except Exception:
            pass

    resp = redirect(url_for('auth.login'))
    flash('已退出登录', 'info')
    return resp


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """忘记密码页面"""
    if request.method == 'GET':
        return render_template('forgot_password.html')
    # POST just shows the same page with a message
    flash('请联系管理员找回密码', 'info')
    return render_template('forgot_password.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """个人信息页面（需登录）"""
    user = g.get('current_user')
    if not user:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template('profile.html', user=user)

    # POST: 更新个人信息
    nickname = request.form.get('nickname', '').strip()
    gender = request.form.get('gender', '').strip()
    contact = request.form.get('contact', '').strip()

    user.nickname = nickname if nickname else None
    user.gender = gender if gender else None
    user.contact = contact if contact else None
    db.session.commit()

    flash('个人信息已更新', 'success')
    return redirect(url_for('auth.profile'))


# ==================== 模板上下文：current_user ====================

@auth_bp.before_app_request
def load_logged_in_user():
    """每个请求前加载当前用户到 g.current_user"""
    g.current_user = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user = User.query.get(int(user_id))
            if user:
                g.current_user = user
    except Exception:
        pass


def inject_current_user():
    """在所有模板中注入 current_user 全局变量"""
    return dict(current_user=g.get('current_user'))
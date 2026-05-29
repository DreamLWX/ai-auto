# AI-Todo Pro

一个支持用户认证的待办任务管理系统，基于 Flask + SQLAlchemy + Redis + Bootstrap。

## 功能特性

- **用户认证**：注册、登录、JWT token、登出（token 黑名单）
- **任务管理**：创建、查看（分页）、更新、删除、标记完成/未完成
- **Redis 缓存**：任务列表分页缓存（60秒），增/删/改时自动失效
- **用户隔离**：每个用户只能访问自己的任务
- **Web 界面**：Bootstrap 5 响应式页面，登录/注册/任务管理
- **测试**：pytest 单元/集成测试，覆盖核心逻辑
- **容器化**：Docker Compose 一键启动

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | Python 3.10+ / Flask 2.3+ |
| ORM | Flask-SQLAlchemy 3.0+ |
| 认证 | Flask-JWT-Extended 4.5+ / bcrypt |
| 缓存/黑名单 | Redis 7.0+ / redis-py |
| 前端 | Bootstrap 5 / Jinja2 |
| 测试 | pytest / fakeredis |
| CI | GitHub Actions |
| 容器 | Docker / Docker Compose |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/DreamLWX/ai-auto.git
cd ai-auto
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动 Redis（本地或 Docker）

```bash
# Docker 方式（推荐）
docker run -d -p 6379:6379 redis

# 或本地已安装 redis 服务端
redis-server
```

### 4. 启动应用

```bash
cp .env.example .env   # 可直接使用默认配置
python run.py
```

访问 http://localhost:5000

## API 接口

基础路径 `/auth`（认证）和 `/tasks`（任务），所有任务接口需要 `Authorization: Bearer <token>` 头。

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/api/register` | 注册（JSON body） |
| POST | `/auth/api/login` | 登录（返回 JWT） |
| POST | `/auth/api/logout` | 登出（token 加入黑名单） |
| GET | `/auth/api/profile` | 获取当前用户信息 |

### 任务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 分页获取任务列表（?page=1） |
| POST | `/tasks` | 创建任务 |
| PUT | `/tasks/<id>` | 更新任务 |
| DELETE | `/tasks/<id>` | 删除任务 |
| PATCH | `/tasks/<id>/complete` | 切换完成状态 |

## Docker 部署

```bash
# 构建并启动所有服务
docker-compose up --build

# 后台运行
docker-compose up -d
```

访问 http://localhost:5000

## 运行测试

```bash
# 需要 Redis 运行中
pytest tests/ -v --cov=app --cov-report=term-missing

# 或用 fakeredis 模拟（无需 Redis）
pytest tests/ -v
```

## 项目结构

```
ai-auto/
├── app/
│   ├── __init__.py      # Flask 应用工厂
│   ├── models.py         # User / Task 模型
│   ├── auth.py           # 认证路由（API + Web）
│   ├── tasks.py          # 任务路由（API + Web）
│   ├── redis_client.py   # Redis 客户端封装
│   └── templates/        # Jinja2 模板
│       ├── base.html
│       ├── login.html
│       ├── register.html
│       └── tasks.html
├── tests/
│   ├── conftest.py       # pytest fixtures
│   ├── test_auth.py
│   ├── test_tasks.py
│   └── test_cache.py
├── .github/workflows/test.yml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── run.py
```

## 环境变量

复制 `.env.example` 为 `.env`，主要变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | `dev-secret-...` | Flask 密钥（生产必须改） |
| `JWT_SECRET_KEY` | `jwt-secret-...` | JWT 签名密钥（生产必须改） |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |
| `DATABASE_URL` | `sqlite:///ai_todo_pro.db` | SQLAlchemy 数据库 URI |
| `JWT_ACCESS_TOKEN_EXPIRES` | `3600` | Token 有效期（秒） |
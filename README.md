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

### 好友系统接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/friends/<user_id>/follow` | 关注用户 |
| POST | `/friends/<user_id>/unfollow` | 取关 |
| GET | `/friends/requests` | 获取待处理的好友请求 |
| POST | `/friends/<user_id>/accept` | 接受关注（互相关注则成为好友） |
| POST | `/friends/<user_id>/reject` | 拒绝关注 |
| GET | `/friends/list` | 获取好友列表（互相关注的） |
| GET | `/friends/followers` | 获取粉丝列表 |
| GET | `/friends/following` | 获取关注列表 |

### 行程系统接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/trips` | 获取行程列表（大厅，仅公开行程） |
| POST | `/trips` | 创建行程 |
| GET | `/trips/<id>` | 获取行程详情 |
| PUT | `/trips/<id>` | 更新行程（仅创建者） |
| DELETE | `/trips/<id>` | 删除行程（仅创建者） |
| POST | `/trips/<id>/apply` | 申请加入行程 |
| GET | `/trips/<id>/applications` | 获取申请列表（仅创建者） |
| POST | `/trips/<id>/applications/<app_id>/approve` | 审批通过 |
| POST | `/trips/<id>/applications/<app_id>/reject` | 审批拒绝 |
| GET | `/trips/mine` | 获取我发布和参与的行程 |

行程支持以下字段：
- `title`（必填）：行程标题
- `description`：行程描述
- `is_private`：是否私人行程
- `visibility`：可见性（public/friends/private）
- `min_participants`/`max_participants`：最小/最大参与人数
- `deadline`：报名截止时间（ISO 格式）
- `trigger_condition`：触发条件（auto 自动审批/manual手动审批）
- `public_content`/`hidden_content`：公开/隐藏内容

### 课程表视图接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/schedule` | 获取课程表视图（合并任务和行程） |
| GET | `/schedule/items` | 获取日程项目列表（未完成的任务 + 即将开始的行程） |

课程表视图会自动合并用户的待办任务和行程，展示统一的时间线视图。

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
│   ├── models.py         # User / Task / Friendship / Trip 模型
│   ├── auth.py           # 认证路由（API + Web）
│   ├── tasks.py          # 任务路由（API + Web）
│   ├── friendships.py    # 好友系统路由（API）
│   ├── trips.py          # 行程系统路由（API）
│   ├── schedule.py       # 课程表视图路由
│   ├── redis_client.py   # Redis 客户端封装
│   └── templates/        # Jinja2 模板
│       ├── base.html
│       ├── login.html
│       ├── register.html
│       ├── tasks.html
│       ├── schedule.html # 课程表视图
│       ├── trips.html      # 行程大厅
│       ├── trip_detail.html # 行程详情
│       ├── trip_form.html  # 发布/编辑行程表单
│       ├── my_trips.html   # 我的行程
│       └── applications.html # 行程申请列表
├── tests/
│   ├── conftest.py       # pytest fixtures
│   ├── test_auth.py
│   ├── test_tasks.py
│   ├── test_friendships.py
│   ├── test_trips.py
│   ├── test_schedule.py
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
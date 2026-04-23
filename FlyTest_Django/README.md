# FlyTest Django Backend

FlyTest 后端基于 `Django + Django REST Framework`，负责项目管理、测试用例管理、知识库、AI 对话、API 自动化等核心能力。

## 主要能力

- 用户注册、登录、权限与项目成员管理
- 测试用例、用例模块、执行记录管理
- API 自动化导入、解析、执行与报告
- 基于 LangChain / LangGraph 的 AI 对话与生成能力
- 知识库文档上传、切分、向量化与检索
- MCP 工具集成与远程配置

## 技术栈

- Python 3.10+
- Django 5
- Django REST Framework
- SimpleJWT
- LangChain / LangGraph
- Qdrant
- OpenAPI / drf-spectacular

## 目录说明

```text
FlyTest_Django/
├── accounts/                # 用户与认证
├── projects/                # 项目与成员
├── testcases/               # 测试用例与模块
├── api_automation/          # API 自动化
├── knowledge/               # 知识库
├── langgraph_integration/   # AI 对话与生成
├── mcp_tools/               # MCP 工具
├── flytest_django/          # Django 配置
└── manage.py
```

## 快速开始

### 1. 安装依赖

```bash
cd FlyTest_Django
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 3. 启动开发服务

```bash
python manage.py runserver 0.0.0.0:8000
```

## 常用环境变量

建议从仓库根目录的 `.env.example` 开始配置。常见变量包括：

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `QDRANT_URL`
- `FLYTEST_API_KEY`

## 常用接口

- `POST /api/token/`：登录获取 JWT
- `POST /api/token/refresh/`：刷新 JWT
- `GET /api/projects/`：项目列表
- `GET /api/projects/{project_id}/testcases/`：测试用例列表
- `POST /api/lg/chat/`：AI 对话
- `POST /api/lg/chat/stream/`：AI 流式对话
- `GET /api/schema/swagger-ui/`：Swagger UI

## 生产部署

推荐使用以下方式之一：

- `uvicorn flytest_django.asgi:application --host 0.0.0.0 --port 8000`
- `gunicorn` + `uvicorn workers`
- Docker / Docker Compose

如需反向代理，建议配合 Nginx 并正确配置静态文件、媒体文件和超时时间。

## 补充说明

- AI 与知识库能力依赖大模型和向量服务配置是否完整。
- API 自动化的 AI 解析能力会检查当前模型配置与提示词是否可用。
- 如果你在本地开发，建议同时关注仓库根目录的 `README.md` 与 `docs/` 文档。

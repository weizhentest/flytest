# Copilot Instructions — FlyTest

## 项目概述

FlyTest 是 AI 驱动的智能测试用例生成平台，采用前后端分离的 Monorepo 架构。

| 子项目 | 技术栈 | 说明 |
|---|---|---|
| `FlyTest_Django` | Django 5.2 + DRF + Celery + LangChain/LangGraph | 后端 API 服务 |
| `FlyTest_Vue` | Vue 3 + TypeScript + Vite + Arco Design Vue | 前端 SPA |
| `FlyTest_Actuator` | Python + Playwright + WebSocket | UI 自动化执行器 |
| `FlyTest_MCP` | Python + FastMCP | MCP 工具服务 |

## 运行环境

- Python 3.12+，使用 `uv` 管理依赖，运行命令统一使用 `uv run python` / `uv run celery`
- Node.js 18+，使用 npm 管理前端依赖
- PostgreSQL（生产端口 8919）、Redis（Broker 端口 8911）、Qdrant（向量存储）、Daphne（ASGI）
- 时区：`Asia/Shanghai`

## 后端规范（FlyTest_Django）

### 视图与路由
- 所有 ViewSet 继承 `flytest_django.viewsets.BaseModelViewSet`（封装 `IsAuthenticated` + `HasModelPermission`）
- 顶级资源通过 `DefaultRouter` 注册（如 `projects`），项目下嵌套资源通过 `drf-nested-routers` 的 `NestedDefaultRouter`（如 `projects/{pk}/testcases`）
- 认证支持 JWT（`Authorization: Bearer <token>`）和 API Key（`Authorization: Api-Key <key>`）

### 统一响应格式
所有 API 通过 `UnifiedResponseRenderer` 返回统一结构：
```json
{
  "status": "success | error",
  "code": 200,
  "message": "操作成功",
  "data": {},
  "errors": null
}
```
视图中**不要**手动构造此结构，直接返回数据即可，Renderer 会自动包装。

### 应用模块
| App | 职责 |
|---|---|
| `accounts` | 用户注册/登录/JWT |
| `projects` | 项目与成员管理、RBAC（Owner/Admin/Member） |
| `testcases` | 测试用例/模块/步骤/套件/执行记录 |
| `knowledge` | 知识库、文档上传与分块、向量化、图片提取与多模态嵌入 |
| `langgraph_integration` | LLM 配置、AI 对话、LangGraph 流式响应 |
| `mcp_tools` | MCP 服务器配置与工具管理 |
| `api_keys` | API Key 管理 |
| `prompts` | 提示词管理 |
| `requirements` | 需求评审 |
| `skills` | Skill 管理 |
| `task_center` | 定时/周期任务调度（django-celery-beat） |
| `ui_automation` | UI 自动化管理 |
| `orchestrator_integration` | 智能编排 |

### Celery 配置
- Broker/Backend：Redis
- Beat 调度器：`django_celery_beat.schedulers:DatabaseScheduler`
- 任务路由：`task_center.tasks.*` → 队列 `task_center`；其他 → 默认队列 `celery`
- Worker 启动：`uv run celery -A flytest_django worker --loglevel=info -Q celery,task_center -B`

### 知识库核心服务（`knowledge/services.py`）
- `CustomAPIEmbeddings`：OpenAI 兼容嵌入 API 封装，支持 `embed_image()` 多模态嵌入
- `DocumentProcessor`：文档加载、分块（`RecursiveCharacterTextSplitter`）、图片提取（PDF 用 PyMuPDF，DOCX 用 python-docx）
- `VectorStoreManager`：Qdrant 向量管理，支持 Dense + BM25 Sparse 混合检索 + RRF 融合 + Reranker 精排
- 集合命名：`kb_{knowledge_base_id}`

### 数据库模型规范
- 常用基础字段：`created_at`、`updated_at`（`auto_now_add` / `auto_now`）
- 项目隔离：模型通常关联 `project` 外键，ViewSet 的 `get_queryset()` 按 `project_id` 过滤
- Migration 文件需明确命名，如 `0014_add_document_image.py`

## 前端规范（FlyTest_Vue）

### 技术栈
- Vue 3 + Composition API（`<script setup lang="ts">`）
- UI：Arco Design Vue（`@arco-design/web-vue`）
- 样式：TailwindCSS + Scoped CSS
- 状态：Pinia
- HTTP：Axios（封装在 `utils/request.ts`，含 JWT 自动刷新拦截器）

### 目录结构
```
src/
├── features/        # 按功能模块划分（knowledge、langgraph、prompts、requirements 等）
│   └── <module>/
│       ├── api/         # API 调用
│       ├── components/  # 模块组件
│       ├── types/       # TypeScript 类型定义
│       └── views/       # 页面组件
├── services/        # 通用 API 服务（跨模块）
├── components/      # 全局公共组件
├── views/           # 页面级组件
├── store/           # Pinia Store（authStore、projectStore）
├── router/          # 路由配置（含 requiresAuth 守卫）
├── layouts/         # 布局组件
└── utils/           # 工具函数
```

### 编码规范
- 组件使用 PascalCase，composable 使用 camelCase
- 类型定义优先使用 `interface`
- 组件超过 500 行时拆分为更小单元
- API 响应中直接使用 `response.data`（Axios 拦截器已处理统一格式解包）
- 路由：公开页面（login/register）无需 auth，其他页面设 `meta: { requiresAuth: true }`

## 通用开发规范

- 代码简洁，避免冗余和重复
- 单文件不超过 500 行，超过则合理拆分
- 遵循 PEP 8（Python）和 ESLint（前端）
- 注释仅描述代码意义，不保留废弃代码注释
- 新增功能需在对应 app 的 `urls.py` 注册路由

## 常用命令

```bash
# 后端
cd FlyTest_Django
uv run python manage.py runserver           # 启动开发服务器
uv run python manage.py makemigrations      # 生成迁移
uv run python manage.py migrate             # 执行迁移
uv run celery -A flytest_django worker --loglevel=info -Q celery,task_center -B  # Celery Worker + Beat

# 前端
cd FlyTest_Vue
npm install                                  # 安装依赖
npm run dev                                  # 启动开发服务器
npm run build                                # 生产构建
```

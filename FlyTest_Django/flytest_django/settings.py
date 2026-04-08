"""
FlyTest Django 项目的设置文件。

更多说明见：
https://docs.djangoproject.com/en/5.2/topics/settings/
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 加载环境变量
load_dotenv(BASE_DIR / ".env")


def setup_huggingface_env():
    """设置HuggingFace环境变量，处理相对路径"""
    hf_vars = [
        "HF_HOME",
        "HF_HUB_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
    ]

    for var in hf_vars:
        value = os.environ.get(var)
        if value and not os.path.isabs(value):
            abs_path = str(BASE_DIR / value)
            os.environ[var] = abs_path


setup_huggingface_env()


# 核心设置
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-jsto-5oth_9(a_xfy#zg@$i$0w47h9a$rw0s&(v#1o5t+s-!*7",  # 仅用于本地开发
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# ALLOWED_HOSTS
ALLOWED_HOSTS_ENV = os.environ.get("DJANGO_ALLOWED_HOSTS")
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(",")]
elif DEBUG:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "testserver",
    ]
else:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
    ]


# 应用定义
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "channels",
    "accounts",
    "projects",
    "testcases",
    "drf_spectacular",
    "corsheaders",
    "langgraph_integration",
    "mcp_tools",
    "api_keys",
    "knowledge",
    "prompts",
    "requirements",
    "orchestrator_integration",
    "skills",
    "testcase_templates",
    "ui_automation",
    "api_automation",
    "data_factory",
    "app_automation_permissions.apps.AppAutomationPermissionsConfig",
]

# ASGI / Channels
ASGI_APPLICATION = "flytest_django.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "flytest_django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "flytest_django.wsgi.application"


# 数据库配置
# DATABASE_TYPE: sqlite 或 postgres
# DATABASE_PATH: SQLite 文件路径
# POSTGRES_*: PostgreSQL 连接参数
DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "postgres")

if DATABASE_TYPE == "postgres":
    # PostgreSQL
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "flytest"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("POSTGRES_PORT", "8919"),
            "OPTIONS": {
                "connect_timeout": 5,
            },
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    # SQLite
    DATABASE_PATH = os.environ.get("DATABASE_PATH")
    if DATABASE_PATH:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": DATABASE_PATH,
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }


# 密码校验
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# 国际化
LANGUAGE_CODE = "zh-Hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = True


# 静态文件
STATIC_URL = "static/"

# 媒体文件
MEDIA_URL = "/media/"
_media_root_env = os.environ.get("MEDIA_ROOT", "")
if _media_root_env:
    _media_path = Path(_media_root_env)
    if not _media_path.is_absolute():
        MEDIA_ROOT = str((BASE_DIR / _media_root_env).resolve())
    else:
        MEDIA_ROOT = str(_media_path)
else:
    MEDIA_ROOT = str(BASE_DIR / "media")


# 默认主键类型
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "api_keys.authentication.APIKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "flytest_django.permissions.DjangoModelPermissions",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "flytest_django.renderers.UnifiedResponseRenderer",
    ),
    # 'DEFAULT_PARSER_CLASSES': [  # 如需显式声明，可保留 JSONParser
    # ],
    # 'EXCEPTION_HANDLER': 'your_project_name.utils.custom_exception_handler',
}

# CORS 配置
# 生产环境建议通过 DJANGO_CORS_ALLOWED_ORIGINS 配置允许来源
CORS_ALLOWED_ORIGINS_ENV = os.environ.get("DJANGO_CORS_ALLOWED_ORIGINS")
if CORS_ALLOWED_ORIGINS_ENV:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(",")
    ]
elif DEBUG:
    # 开发环境默认允许常见前端端口跨域访问
    CORS_ALLOWED_ORIGINS = [
        # Nginx 默认端口
        "http://localhost",
        "http://127.0.0.1",
        # React 默认端口
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Vite 默认端口
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Vue / Angular 常用端口
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        # Django 开发端口
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
else:
    # 生产环境通过 DJANGO_CORS_ALLOWED_ORIGINS 显式配置
    CORS_ALLOWED_ORIGINS = []

# 生产环境默认不允许任意来源
CORS_ALLOW_ALL_ORIGINS = False

# 允许发送凭证信息，如 Cookie 和 Authorization
CORS_ALLOW_CREDENTIALS = True

# 允许的 HTTP 方法
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# 允许的请求头
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# CSRF 信任来源，前后端分离场景下建议显式配置
CSRF_TRUSTED_ORIGINS_ENV = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS")
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip() for origin in CSRF_TRUSTED_ORIGINS_ENV.split(",")
    ]
elif DEBUG:
    # 开发环境默认可信来源
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
else:
    CSRF_TRUSTED_ORIGINS = []


# CORS 配置已在上方声明

# Simple JWT 配置
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# 日志输出目录
LOGS_DIR = BASE_DIR / "data" / "logs"
# 自动创建日志目录
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}:{lineno} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "detailed": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        # 控制台输出
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # 应用主日志文件
        "app_file": {
            "level": "INFO",
            "class": "flytest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "when": "midnight",
            "interval": 1,
            # 保留 30 天
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        # 错误日志文件
        "error_file": {
            "level": "ERROR",
            "class": "flytest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "error.log"),
            "when": "midnight",
            "interval": 1,
            # 保留 60 天
            "backupCount": 60,
            "formatter": "detailed",
            "encoding": "utf-8",
        },
        # Requirements 模块日志
        "requirements_file": {
            "level": "DEBUG",
            "class": "flytest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "requirements.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        # Celery 任务日志
        "celery_file": {
            "level": "INFO",
            "class": "flytest_django.safe_log_handler.SafeTimedRotatingFileHandler",
            "filename": str(LOGS_DIR / "celery.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        # Django 核心日志
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Requirements 模块日志
        "requirements": {
            "handlers": ["console", "requirements_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "requirements.services": {
            "handlers": ["console", "requirements_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "requirements.tasks": {
            "handlers": ["console", "celery_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Celery 日志
        "celery": {
            "handlers": ["console", "celery_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # MCP 工具日志
        "mcp_tools": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Knowledge 模块日志
        "knowledge": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "knowledge.services": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Testcases 模块日志
        "testcases": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "testcases.views": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "testcases.serializers": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Orchestrator 集成日志
        "orchestrator_integration": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # LangGraph 集成日志
        "langgraph_integration": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 第三方 AI SDK 日志
        "langchain": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langchain_core": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langchain_openai": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "langgraph": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "openai": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "httpx": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Celery 配置
# 使用 Redis 作为 broker 和 result backend
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "redis://localhost:6379/0"
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

# Celery 6.0+ 启动时自动重试 broker 连接
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery 时区设置
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery 结果配置
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 3600

# Celery 序列化配置
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# Celery 任务控制
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60

# Celery Worker 配置
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Celery 日志格式
CELERY_WORKER_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
CELERY_WORKER_TASK_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# 内部服务调用基准地址
# Docker 环境下可设置为 http://backend:8000
BASE_URL = os.environ.get("DJANGO_BASE_URL", "http://localhost:8000")



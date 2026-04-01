"""确保 Celery 应用在 Django 启动时被加载。"""

# 导入 Celery 应用实例，保证 shared_task 可以绑定到正确 app。
from .celery import app as celery_app

# 显式导出模块公开符号。
__all__ = ("celery_app",)

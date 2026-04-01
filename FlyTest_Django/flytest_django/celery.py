"""Celery 配置文件。"""

# 导入 os 模块，用于读取/设置运行时环境变量。
import os

# 导入 platform 模块，用于识别操作系统并做兼容处理。
import platform

# 导入 Celery 应用类。
from celery import Celery

# 设置 umask，确保新建文件权限便于同组协作写入。
os.umask(0o002)

# 设置默认 Django settings 模块（外部未设置时生效）。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

# 创建 Celery 应用实例。
app = Celery("flytest_django")

# 从 Django settings 读取 Celery 配置，要求配置键使用 CELERY_ 前缀。
app.config_from_object("django.conf:settings", namespace="CELERY")

# 自动从已注册 Django app 中发现并加载 tasks.py。
app.autodiscover_tasks()

# Windows 平台兼容配置。
if platform.system() == "Windows":
    app.conf.update(
        # 使用单进程池，避免 Windows 多进程兼容问题。
        CELERY_WORKER_POOL="solo",
        # 设置 broker 可见性超时，避免长任务被过早重投。
        CELERY_BROKER_TRANSPORT_OPTIONS={"visibility_timeout": 3600},
        # 设置结果后端可见性超时。
        CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS={"visibility_timeout": 3600},
    )


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """调试任务"""
    # 打印当前任务请求上下文，便于本地排查任务调度行为。
    print(f"Request: {self.request!r}")

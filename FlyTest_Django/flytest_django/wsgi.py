"""
flytest_django 项目的 WSGI 配置。

对外暴露模块级变量 ``application`` 作为 WSGI 可调用入口。

更多说明见：
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

# 导入 os 模块，用于设置 Django 配置环境变量。
import os

# 导入 WSGI 应用工厂函数。
from django.core.wsgi import get_wsgi_application

# 若未设置则指定默认 settings 模块。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

# 构建并导出 WSGI application 供 Gunicorn/uWSGI 加载。
application = get_wsgi_application()

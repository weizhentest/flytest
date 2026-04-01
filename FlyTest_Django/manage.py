#!/usr/bin/env python
"""Django 管理命令行入口。"""

import os
import sys

# 设置 umask 确保新建文件有正确的权限（664 文件，775 目录）
# 这样 Django 和 Celery 进程可以互相读写文件
os.umask(0o002)


def main():
    """执行管理命令。"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

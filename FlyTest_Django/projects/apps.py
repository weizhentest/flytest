# 导入 Django 应用配置基类。
from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    # 默认主键类型。
    default_auto_field = "django.db.models.BigAutoField"
    # 应用注册名。
    name = "projects"

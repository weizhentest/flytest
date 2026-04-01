# 导入 Django 应用配置基类。
from django.apps import AppConfig


class ApiKeysConfig(AppConfig):
    # 默认主键类型，减少模型重复声明。
    default_auto_field = 'django.db.models.BigAutoField'
    # 应用注册名。
    name = 'api_keys'

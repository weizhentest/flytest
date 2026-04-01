# 导入 Django 应用配置基类。
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    # 指定默认主键字段类型，避免各模型重复声明。
    default_auto_field = 'django.db.models.BigAutoField'
    # 声明应用标签名称，供 Django 应用注册使用。
    name = 'accounts'

    def ready(self):
        """
        当应用准备好时导入信号处理器
        """
        # 应用启动时导入 signals，确保用户保存钩子能被注册。
        import accounts.signals

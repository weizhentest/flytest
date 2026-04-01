from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .permissions import HasModelPermission



class BaseModelViewSet(viewsets.ModelViewSet):
    """
    基础视图集，提供统一的权限控制。

    所有视图集都应继承该类，默认要求用户已认证并具备模型权限。
    子类可重写 get_permissions 在基础权限上增加额外限制。
    """

    # 重写 DRF 的权限获取钩子。
    def get_permissions(self):
        # 返回基础权限列表：登录认证 + 模型权限。
        return [IsAuthenticated(), HasModelPermission()]

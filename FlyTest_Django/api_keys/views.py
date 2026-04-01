# 导入 DRF 视图集与权限基类。
from rest_framework import viewsets, permissions

# 导入 API Key 模型。
from .models import APIKey

# 导入 API Key 序列化器。
from .serializers import APIKeySerializer

# 导入对象级权限（所有者或管理员）。
from .permissions import IsOwnerOrAdmin

# 导入项目统一模型权限控制。
from flytest_django.permissions import HasModelPermission


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    API Key 管理接口，支持查看与编辑。
    普通用户仅可管理自己的 API Key。
    管理员可管理所有 API Key。
    访问受 api_keys 模型权限控制。
    """

    serializer_class = APIKeySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasModelPermission,
        IsOwnerOrAdmin,
    ]

    def get_queryset(self):
        """
        返回当前认证用户可见的 API Key 列表。
        """
        user = self.request.user


        # 条件：任意登录用户（含 staff）；动作：仅返回本人 Key；结果：列表接口不暴露他人密钥元数据。
        return APIKey.objects.filter(user=user).order_by("-created_at")

    def perform_create(self, serializer):
        """
        创建时自动绑定当前用户。
        """
        # 创建时强制绑定当前用户，避免通过伪造请求体写入他人账号名下。
        serializer.save(user=self.request.user)

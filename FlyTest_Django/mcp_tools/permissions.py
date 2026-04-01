from rest_framework import permissions
from asgiref.sync import sync_to_async


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    自定义权限：仅对象所有者可编辑，
    管理员可查看/编辑所有对象。
    同时支持 'user' 与 'owner' 字段。
    """

    def has_permission(self, request, view):
        # 已认证用户可以执行列表/创建；对象级权限会在列表与详情阶段继续过滤。
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # 读取权限对任意请求开放，因此始终允许 GET/HEAD/OPTIONS。
        if request.method in permissions.SAFE_METHODS:
            return True

        # 写权限仅允许对象所有者；管理员可修改/删除任意对象。
        if request.user.is_staff:  # Django 管理员可访问全部对象
            return True


        # 同时兼容 'user' 与 'owner' 字段
        if hasattr(obj, "user"):
            return obj.user == request.user
        elif hasattr(obj, "owner"):
            return obj.owner == request.user
        else:
            # 若两者都不存在，则拒绝访问（更安全的默认行为）
            return False


class IsOwnerOrAdminOriginal(permissions.BasePermission):
    """
    兼容旧逻辑的原始版本：仅支持 'user' 字段。
    """

    def has_permission(self, request, view):
        # 已认证用户可以执行 API Key 列表/创建；对象级权限会在列表与详情阶段继续过滤。
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # 读取权限对任意请求开放，因此始终允许 GET/HEAD/OPTIONS。
        if request.method in permissions.SAFE_METHODS:
            return True

        # 写权限仅允许对象所有者；对 APIKey 而言仅所有者可改/删，管理员除外。
        if request.user.is_staff:  # Django 管理员可访问全部对象
            return True

        return obj.user == request.user

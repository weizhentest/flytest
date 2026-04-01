# 导入 DRF 权限基类。
from rest_framework import permissions




class IsOwnerOrAdmin(permissions.BasePermission):
    """
    自定义权限：仅对象所有者可编辑；
    管理员可查看和编辑所有对象。
    """

    def has_permission(self, request, view):
        # 条件：用户已登录；动作：允许进入视图；结果：再由对象级权限控制是否可操作目标 Key。
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # 安全方法统一放行，由 queryset 限制可见范围即可。
        if request.method in permissions.SAFE_METHODS:
            return True

        # 条件：管理员写操作；动作：放行；结果：支持运维排障与统一托管管理。
        if request.user.is_staff:
            return True

        # 非管理员仅允许操作自己名下的 Key，防止跨用户篡改。
        return obj.user == request.user

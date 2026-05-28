from rest_framework import permissions

from flytest_django.permissions import HasModelPermission

from .models import ProjectMember


def _is_system_admin(user):
    return bool(user and (user.is_superuser or user.is_staff))


def _has_any_permission(user, permissions_to_check):
    return bool(user and any(user.has_perm(permission) for permission in permissions_to_check))


def _is_project_member(user, project_id):
    return bool(user and project_id and ProjectMember.objects.filter(project_id=project_id, user=user).exists())


class IsProjectMember(permissions.BasePermission):
    """
    检查用户是否是项目成员，或平台管理员。
    """

    def has_permission(self, request, view):
        if _is_system_admin(request.user):
            return True

        project_id = view.kwargs.get("pk") or view.kwargs.get("project_pk")
        return _is_project_member(request.user, project_id)

    def has_object_permission(self, request, view, obj):
        if _is_system_admin(request.user):
            return True

        return ProjectMember.objects.filter(project=obj, user=request.user).exists()


class IsProjectAdmin(permissions.BasePermission):
    """
    检查用户是否是项目管理员/拥有者，或平台管理员。
    """

    def has_permission(self, request, view):
        if _is_system_admin(request.user):
            return True

        project_id = view.kwargs.get("pk") or view.kwargs.get("project_pk")
        if not _is_project_member(request.user, project_id):
            return False

        action = getattr(view, "action", None)
        action_permissions = {
            "add_member": [
                "projects.add_projectmember",
                "projects.change_projectmember",
                "projects.change_project",
            ],
            "remove_member": [
                "projects.delete_projectmember",
                "projects.change_projectmember",
                "projects.change_project",
                "projects.delete_project",
            ],
            "update_member_role": [
                "projects.change_projectmember",
                "projects.change_project",
            ],
            "update": ["projects.change_project"],
            "partial_update": ["projects.change_project"],
            "destroy": ["projects.delete_project"],
        }
        if _has_any_permission(request.user, action_permissions.get(action, [])):
            return True

        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=["admin", "owner"],
        ).exists()

    def has_object_permission(self, request, view, obj):
        if _is_system_admin(request.user):
            return True

        if not ProjectMember.objects.filter(project=obj, user=request.user).exists():
            return False

        action = getattr(view, "action", None)
        action_permissions = {
            "add_member": [
                "projects.add_projectmember",
                "projects.change_projectmember",
                "projects.change_project",
            ],
            "remove_member": [
                "projects.delete_projectmember",
                "projects.change_projectmember",
                "projects.change_project",
                "projects.delete_project",
            ],
            "update_member_role": [
                "projects.change_projectmember",
                "projects.change_project",
            ],
            "update": ["projects.change_project"],
            "partial_update": ["projects.change_project"],
            "destroy": ["projects.delete_project"],
        }
        if _has_any_permission(request.user, action_permissions.get(action, [])):
            return True

        return ProjectMember.objects.filter(
            project=obj,
            user=request.user,
            role__in=["admin", "owner"],
        ).exists()


class IsProjectOwner(permissions.BasePermission):
    """
    检查用户是否是项目拥有者，或平台管理员。
    """

    def has_permission(self, request, view):
        if _is_system_admin(request.user):
            return True

        project_id = view.kwargs.get("pk") or view.kwargs.get("project_pk")
        if not project_id:
            return False

        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role="owner",
        ).exists()

    def has_object_permission(self, request, view, obj):
        if _is_system_admin(request.user):
            return True

        return ProjectMember.objects.filter(project=obj, user=request.user, role="owner").exists()


class HasProjectMemberPermission(HasModelPermission):
    """
    专门检查 ProjectMember 模型权限的权限类。
    """

    def _get_model_info(self, view):
        return ProjectMember, "projects", "projectmember"

# 导入 DRF 权限基类。
from rest_framework import permissions

# 导入项目成员模型用于成员关系判定。
from .models import ProjectMember

# 导入统一模型权限基类。
from flytest_django.permissions import HasModelPermission


class IsProjectMember(permissions.BasePermission):
    """
    检查用户是否是项目成员
    """
    def has_permission(self, request, view):
        # 条件：超级用户；动作：直接放行；结果：统一平台级运维权限。
        if request.user.is_superuser:
            return True
            
        # 从详情路由或嵌套路由中提取项目 ID。
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
        
        # 条件：成员关系存在；动作：放行；结果：仅项目成员可访问项目资源。
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目成员（对象级权限）
        """
        # 对象级判定同样允许超级用户短路放行。
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user
        ).exists()


class IsProjectAdmin(permissions.BasePermission):
    """
    检查用户是否是项目管理员或拥有者
    """
    def has_permission(self, request, view):
        # 条件：超级用户；动作：直接放行；结果：允许跨项目管理操作。
        if request.user.is_superuser:
            return True
            
        # 从路由参数提取项目 ID，兼容 pk/project_pk 两种写法。
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
        
        # 仅 admin/owner 角色可执行管理员级操作。
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目管理员或拥有者（对象级权限）
        """
        # 对象级权限同样支持超级用户短路。
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()


class IsProjectOwner(permissions.BasePermission):
    """
    检查用户是否是项目拥有者
    """
    def has_permission(self, request, view):
        # 条件：超级用户；动作：直接放行；结果：支持平台级删除/关键操作兜底。
        if request.user.is_superuser:
            return True
            
        # 获取目标项目 ID。
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
            
        # 仅 owner 角色可通过此权限。
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role='owner'
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目拥有者（对象级权限）
        """
        # 对象级权限同样支持超级用户短路。
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user,
            role='owner'
        ).exists()


class HasProjectMemberPermission(HasModelPermission):
    """
    专门检查 ProjectMember 模型权限的权限类
    用于成员管理相关操作
    """
    def _get_model_info(self, view):
        """
        强制返回 ProjectMember 模型信息
        """
        # 将成员管理动作固定映射到 projects.projectmember 模型权限编码。
        return ProjectMember, 'projects', 'projectmember'

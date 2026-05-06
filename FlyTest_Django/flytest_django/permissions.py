import logging
from rest_framework import permissions
from accounts.models import is_user_approved
from projects.models import ProjectMember

logger = logging.getLogger(__name__)

PROJECT_MEMBER_PERMISSION_APPS = {
    "projects",
    "requirements",
    "testcases",
    "api_automation",
    "ui_automation",
    "app_automation",
    "knowledge",
    "data_factory",
    "langgraph_integration",
    "skills",
    "mcp_tools",
}


class HasModelPermission(permissions.BasePermission):
    """
    自定义权限类，检查用户是否有特定的模型权限

    可以通过两种方式使用：
    1. 提供特定权限：HasModelPermission('app_label.permission_codename')
    2. 自动根据视图和操作类型检查权限

    对于自定义操作，默认需要查看权限，除非在视图中明确指定了所需权限。
    """
    def __init__(self, perm=None):
        self.perm = perm

    def has_permission(self, request, view):
        """
        检查用户是否有权限执行当前操作
        """
        # 匿名用户没有任何权限
        if not request.user or request.user.is_anonymous:
            return False

        # 超级用户拥有所有权限
        if request.user.is_superuser:
            return True

        if not request.user.is_staff and not is_user_approved(request.user):
            logger.debug("用户 %s 尚未通过审核，拒绝访问", request.user.username)
            return False

        # 如果提供了特定权限，则检查该权限
        if self.perm:
            has_perm = request.user.has_perm(self.perm)
            if not has_perm:
                logger.debug(f"用户 {request.user.username} 没有权限 {self.perm}")
            return has_perm

        # 尝试从视图获取模型信息
        model_cls, app_label, model_name = self._get_model_info(view)

        # 如果无法确定模型，默认拒绝访问，避免权限旁路。
        if model_cls is None:
            logger.warning(f"无法确定视图 {view.__class__.__name__} 的模型，拒绝访问")
            return False

        # 获取视图的操作类型
        action = getattr(view, 'action', None)

        # 获取所需权限
        required_perm = self._get_required_permission(request, view, action, app_label, model_name)
        if self._should_allow_project_member_access(request, view, app_label, model_name, required_perm):
            return True
        logger.debug(f"检查用户 {request.user.username} 是否有权限 {required_perm} (操作: {action})")

        # 检查用户是否有所需权限
        has_perm = request.user.has_perm(required_perm)
        if not has_perm:
            logger.debug(f"用户 {request.user.username} 没有权限 {required_perm} 执行操作 {action}")
        else:
            logger.debug(f"用户 {request.user.username} 有权限 {required_perm}")

        return has_perm

    def has_object_permission(self, request, view, obj):
        """
        检查用户是否有权限操作特定对象
        
        注意: 此方法只检查模型级权限，不检查Django的对象级权限。
        对象级权限检查应该由其他专门的权限类处理（如IsProjectMember等）。
        """
        # 匿名用户没有任何权限
        if not request.user or request.user.is_anonymous:
            return False

        # 超级用户拥有所有权限
        if request.user.is_superuser:
            return True

        if not request.user.is_staff and not is_user_approved(request.user):
            logger.debug("用户 %s 尚未通过审核，拒绝对象访问", request.user.username)
            return False

        # 如果提供了特定权限，则检查该权限（仅模型级别）
        if self.perm:
            # 只检查模型级权限，不检查对象级权限
            has_perm = request.user.has_perm(self.perm)
            if not has_perm:
                logger.debug(f"用户 {request.user.username} 没有权限 {self.perm}")
            return has_perm

        # 获取模型信息
        model_cls = obj.__class__
        app_label = model_cls._meta.app_label
        model_name = model_cls._meta.model_name

        # 获取视图的操作类型
        action = getattr(view, 'action', None)

        # 获取所需权限
        required_perm = self._get_required_permission(request, view, action, app_label, model_name)
        if self._should_allow_project_member_access(request, view, app_label, model_name, required_perm, obj=obj):
            return True

        # 只检查模型级权限，不检查对象级权限
        # 对象级权限检查由其他权限类负责（如IsProjectMember等）
        has_perm = request.user.has_perm(required_perm)
        if not has_perm:
            logger.debug(f"用户 {request.user.username} 没有权限 {required_perm}")

        return has_perm

    def _get_model_info(self, view):
        """
        从视图获取模型信息
        """
        model_cls = None

        # 方法1：从 queryset 属性获取
        if hasattr(view, 'queryset') and view.queryset is not None:
            if hasattr(view.queryset, 'model'):
                model_cls = view.queryset.model

        # 方法2：从 get_queryset 方法获取
        if model_cls is None and hasattr(view, 'get_queryset'):
            try:
                queryset = view.get_queryset()
                if hasattr(queryset, 'model'):
                    model_cls = queryset.model
            except Exception as e:
                logger.warning(f"获取 queryset 时出错: {str(e)}")

        # 方法3：从 serializer_class 获取
        if model_cls is None and hasattr(view, 'serializer_class'):
            serializer_class = view.serializer_class
            if hasattr(serializer_class, 'Meta') and hasattr(serializer_class.Meta, 'model'):
                model_cls = serializer_class.Meta.model

        # 如果无法确定模型，返回 None
        if model_cls is None:
            return None, None, None

        app_label = model_cls._meta.app_label
        model_name = model_cls._meta.model_name

        return model_cls, app_label, model_name

    def _get_required_permission(self, request, view, action, app_label, model_name):
        """
        根据操作类型和请求方法确定所需权限
        """
        # 标准 CRUD 操作的权限映射
        if action == 'list' or action == 'retrieve' or request.method == 'GET':
            required_perm = f'{app_label}.view_{model_name}'
        elif action == 'create' or request.method == 'POST':
            required_perm = f'{app_label}.add_{model_name}'
        elif action in ['update', 'partial_update'] or request.method in ['PUT', 'PATCH']:
            required_perm = f'{app_label}.change_{model_name}'
        elif action == 'destroy' or request.method == 'DELETE':
            required_perm = f'{app_label}.delete_{model_name}'
        else:
            # 对于自定义操作，默认需要查看权限
            required_perm = f'{app_label}.view_{model_name}'

        # 尝试从操作方法的 permission_required 属性获取所需权限
        if action and hasattr(getattr(view, action, None), 'permission_required'):
            method_perm = getattr(getattr(view, action), 'permission_required')
            logger.debug(f"找到方法 {action} 的 permission_required: {method_perm}")
            required_perm = method_perm
        else:
            logger.debug(f"方法 {action} 没有 permission_required 属性，使用默认权限: {required_perm}")

        logger.debug(f"最终所需权限: {required_perm}")
        return required_perm

    def _should_allow_project_member_access(self, request, view, app_label, model_name, required_perm, obj=None):
        if request.method != "GET":
            return False

        if not required_perm or not required_perm.startswith(f"{app_label}.view_"):
            return False

        if app_label not in PROJECT_MEMBER_PERMISSION_APPS:
            return False

        if app_label == "projects" and model_name == "projectdeletionrequest":
            return False

        project_id = self._resolve_project_id(view, app_label, model_name, obj=obj)
        member_queryset = ProjectMember.objects.filter(user=request.user)
        if project_id is not None:
            member_queryset = member_queryset.filter(project_id=project_id)

        return member_queryset.exists()

    def _resolve_project_id(self, view, app_label, model_name, obj=None):
        for key in ("project_pk", "project_id"):
            raw_value = view.kwargs.get(key)
            if raw_value not in (None, ""):
                try:
                    return int(raw_value)
                except (TypeError, ValueError):
                    return None

        if obj is not None:
            if getattr(obj, "project_id", None):
                return obj.project_id
            project = getattr(obj, "project", None)
            if project is not None:
                return getattr(project, "id", None)
            if app_label == "projects" and model_name == "project":
                return getattr(obj, "id", None)

        if app_label == "projects" and model_name == "project":
            raw_value = view.kwargs.get("pk")
            if raw_value not in (None, ""):
                try:
                    return int(raw_value)
                except (TypeError, ValueError):
                    return None

        return None


def permission_required(perm):
    """
    装饰器，用于为视图方法指定所需权限

    用法示例：

    @action(detail=True, methods=['get'])
    @permission_required('app_label.permission_codename')
    def my_custom_action(self, request, pk=None):
        # 方法实现
        pass
    """
    def decorator(func):
        func.permission_required = perm
        return func
    return decorator


class DjangoModelPermissions(permissions.DjangoModelPermissions):
    """
    扩展 DjangoModelPermissions，添加对 GET 请求的权限检查
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

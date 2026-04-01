from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from flytest_django.viewsets import BaseModelViewSet
from flytest_django.permissions import HasModelPermission
from .models import UserPrompt, PromptType
from .serializers import (
    UserPromptSerializer,
    UserPromptListSerializer
)
from .services import initialize_user_prompts


class UserPromptViewSet(BaseModelViewSet):
    """
    用户提示词管理视图集
    提供用户级别的提示词CRUD操作
    """
    serializer_class = UserPromptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_default', 'is_active', 'prompt_type']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-updated_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        return [
            HasModelPermission(),
        ]

    def get_queryset(self):
        """只返回当前用户的提示词"""
        return UserPrompt.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'list':
            return UserPromptListSerializer
        return UserPromptSerializer

    def perform_create(self, serializer):
        """创建时自动设置用户"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def default(self, request):
        """获取用户的默认提示词"""
        default_prompt = UserPrompt.get_user_default_prompt(request.user)

        if default_prompt:
            serializer = self.get_serializer(default_prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "用户暂无默认提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """根据类型获取提示词"""
        prompt_type = request.query_params.get('type')
        if not prompt_type:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "缺少type参数",
                "data": None,
                "errors": {"type": ["此字段是必需的"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        prompt = UserPrompt.get_user_prompt_by_type(request.user, prompt_type)
        if prompt:
            serializer = self.get_serializer(prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": f"用户暂无{prompt_type}类型的提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def types(self, request):
        """获取所有提示词类型"""
        types = [
            {
                'value': choice[0],
                'label': choice[1],
                'is_program_call': choice[0] in UserPrompt.PROGRAM_CALL_TYPES
            }
            for choice in PromptType.choices
        ]
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "获取成功",
            "data": types,
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设置指定提示词为默认提示词"""
        prompt = self.get_object()

        # 检查提示词是否属于当前用户且处于激活状态
        if not prompt.is_active:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "无法设置未激活的提示词为默认",
                "data": {},
                "errors": {"prompt": ["提示词未激活"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否为程序调用类型（程序调用类型不允许设为默认）
        if prompt.prompt_type in UserPrompt.PROGRAM_CALL_TYPES:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "程序调用类型的提示词不能设为默认",
                "data": {},
                "errors": {"prompt_type": ["程序调用类型的提示词不能设为默认，会影响对话功能"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 取消其他默认提示词
        UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).exclude(pk=prompt.pk).update(is_default=False)

        # 设置当前提示词为默认
        prompt.is_default = True
        prompt.save()

        serializer = self.get_serializer(prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "默认提示词设置成功",
            "data": serializer.data,
            "errors": {}
        })

    @action(detail=False, methods=['post'])
    def clear_default(self, request):
        """清除用户的默认提示词设置"""
        updated_count = UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": f"已清除默认提示词设置，影响{updated_count}条记录",
            "data": {"updated_count": updated_count},
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """复制提示词"""
        original_prompt = self.get_object()

        # 创建副本
        new_prompt = UserPrompt.objects.create(
            user=request.user,
            name=f"{original_prompt.name} (副本)",
            content=original_prompt.content,
            description=f"复制自: {original_prompt.description}" if original_prompt.description else "复制的提示词",
            is_default=False,  # 副本不设为默认
            is_active=True
        )

        serializer = self.get_serializer(new_prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_201_CREATED,
            "message": "提示词复制成功",
            "data": serializer.data,
            "errors": {}
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def initialize(self, request):
        """初始化用户的默认提示词
        
        支持参数:
        - force_update: bool, 是否强制更新已存在的提示词（默认False）
        
        使用 services.initialize_user_prompts 实现，提示词模板统一在 services.get_default_prompts 中维护
        """
        force_update = request.data.get('force_update', False)
        
        # 使用服务层函数初始化提示词
        result = initialize_user_prompts(request.user, force_update=force_update)
        
        # 获取创建的提示词详细信息（用于前端展示）
        created_prompts = []
        for item in result['created']:
            prompt = UserPrompt.objects.filter(
                user=request.user,
                name=item['name']
            ).first()
            if prompt:
                serializer = self.get_serializer(prompt)
                created_prompts.append(serializer.data)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": f"初始化完成！创建了 {result['summary']['created_count']} 个提示词，跳过 {result['summary']['skipped_count']} 个",
            "data": {
                "created": created_prompts,
                "skipped": result['skipped'],
                "summary": result['summary']
            },
            "errors": {}
        })

    @action(detail=False, methods=['get'])
    def init_status(self, request):
        """获取用户提示词初始化状态"""
        from prompts.services import get_default_prompts
        
        # 获取用户现有的提示词数量
        existing_prompts = UserPrompt.objects.filter(user=request.user)
        existing_count = existing_prompts.count()
        existing_types = set(existing_prompts.values_list('prompt_type', flat=True))
        
        # 获取默认提示词模板列表
        default_prompts = get_default_prompts()
        total_default_prompts = len(default_prompts)
        
        # 所有可用的提示词类型（用于展示）
        all_types = dict(PromptType.choices)
        
        status_info = []
        for prompt_type, display_name in all_types.items():
            status_info.append({
                'type': prompt_type,
                'name': display_name,
                'exists': prompt_type in existing_types,
                'is_program_call': prompt_type in UserPrompt.PROGRAM_CALL_TYPES
            })

        missing_types = [
            info for info in status_info
            if not info['exists']
        ]
        
        # 计算缺失的提示词数量（默认模板数 - 已存在数）
        missing_count = max(0, total_default_prompts - existing_count)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "获取初始化状态成功",
            "data": {
                "all_types": status_info,
                "missing_types": missing_types,
                "summary": {
                    "total_default_prompts": total_default_prompts,
                    "existing_count": existing_count,
                    "missing_count": missing_count,
                    "can_initialize": missing_count > 0 or existing_count < total_default_prompts
                }
            },
            "errors": {}
        })

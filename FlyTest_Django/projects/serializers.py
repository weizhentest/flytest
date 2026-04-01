# 导入 DRF 序列化器基类。
from rest_framework import serializers

# 导入用户模型用于成员创建校验。
from django.contrib.auth.models import User

# 导入项目相关模型。
from .models import Project, ProjectMember, ProjectCredential

# 导入用户详情序列化器用于嵌套回显。
from accounts.serializers import UserDetailSerializer


class ProjectCredentialSerializer(serializers.ModelSerializer):
    """项目凭据序列化器"""
    password = serializers.CharField(write_only=True, allow_blank=True, required=False, help_text='登录密码')

    class Meta:
        model = ProjectCredential
        fields = ['id', 'system_url', 'username', 'password', 'user_role', 'created_at']
        read_only_fields = ['created_at']
        extra_kwargs = {
            'system_url': {'help_text': '系统访问地址（如 https://test.example.com）'},
            'username': {'help_text': '登录账号'},
            'user_role': {'help_text': '如"管理员"、"普通用户"、"审核员"等'}
        }


class ProjectMemberSerializer(serializers.ModelSerializer):
    """项目成员序列化器"""
    user_detail = UserDetailSerializer(source='user', read_only=True)

    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'user_detail', 'role', 'joined_at']
        read_only_fields = ['joined_at']


class ProjectSerializer(serializers.ModelSerializer):
    """项目基本信息序列化器"""
    creator_detail = UserDetailSerializer(source='creator', read_only=True)
    credentials = ProjectCredentialSerializer(many=True, required=False)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'creator', 'creator_detail', 'created_at', 'updated_at', 'credentials']
        read_only_fields = ['created_at', 'updated_at', 'creator']

    def validate_name(self, value):
        """验证项目名称唯一性"""
        # 条件：创建时名称已存在，或更新时改成了已存在名称；动作：拒绝；结果：保证项目名唯一约束前置可读报错。
        if self.instance is None and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("项目名称已存在")
        elif self.instance and self.instance.name != value and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("项目名称已存在")
        return value

    def create(self, validated_data):
        # 拆出嵌套凭据数据，先创建项目主记录，再逐条创建凭据。
        credentials_data = validated_data.pop('credentials', [])
        project = Project.objects.create(**validated_data)
        for credential_data in credentials_data:
            ProjectCredential.objects.create(project=project, **credential_data)
        return project

    def update(self, instance, validated_data):
        # 允许局部更新；若传入 credentials，则按“全量替换”策略更新凭据。
        credentials_data = validated_data.pop('credentials', None)
        
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()

        if credentials_data is not None:
            # 条件：前端显式提交凭据数组；动作：清空后重建；结果：数据库状态与提交内容完全一致。
            instance.credentials.all().delete()
            for credential_data in credentials_data:
                ProjectCredential.objects.create(project=instance, **credential_data)

        return instance


class ProjectDetailSerializer(ProjectSerializer):
    """项目详细信息序列化器，包含成员信息"""
    members = ProjectMemberSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['members']


class ProjectMemberCreateSerializer(serializers.ModelSerializer):
    """创建项目成员的序列化器"""
    user_id = serializers.IntegerField(write_only=True, help_text="用户ID")

    class Meta:
        model = ProjectMember
        fields = ['user_id', 'role']

    def validate_user_id(self, value):
        """验证用户ID是否存在"""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("用户不存在")
        return value

    def validate(self, attrs):
        """验证用户是否已经是项目成员"""
        project = self.context['project']
        user_id = attrs['user_id']

        # 条件：用户已是成员；动作：拒绝重复添加；结果：避免违反 unique_together 并返回可读错误。
        if ProjectMember.objects.filter(project=project, user_id=user_id).exists():
            raise serializers.ValidationError({"user_id": "该用户已经是项目成员"})

        return attrs

    def create(self, validated_data):
        # 创建成员时通过上下文绑定项目，避免请求体伪造 project 归属。
        project = self.context['project']
        user_id = validated_data.pop('user_id')
        user = User.objects.get(id=user_id)
        return ProjectMember.objects.create(project=project, user=user, **validated_data)

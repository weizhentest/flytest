from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.serializers import UserDetailSerializer

from .models import Project, ProjectMember


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

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'creator', 'creator_detail', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'creator']

    def validate_name(self, value):
        """验证项目名称唯一性"""
        if self.instance is None and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("项目名称已存在")
        if self.instance and self.instance.name != value and Project.objects.filter(name=value).exists():
            raise serializers.ValidationError("项目名称已存在")
        return value

    def create(self, validated_data):
        return Project.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()
        return instance


class ProjectDetailSerializer(ProjectSerializer):
    """项目详情序列化器，包含成员信息"""

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
        try:
            User.objects.get(id=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("用户不存在") from exc
        return value

    def validate(self, attrs):
        project = self.context['project']
        user_id = attrs['user_id']

        if ProjectMember.objects.filter(project=project, user_id=user_id).exists():
            raise serializers.ValidationError({"user_id": "该用户已经是项目成员"})

        return attrs

    def create(self, validated_data):
        project = self.context['project']
        user_id = validated_data.pop('user_id')
        user = User.objects.get(id=user_id)
        return ProjectMember.objects.create(project=project, user=user, **validated_data)

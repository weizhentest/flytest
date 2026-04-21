from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.serializers import UserDetailSerializer

from .models import Project, ProjectDeletionRequest, ProjectMember


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_detail = UserDetailSerializer(source='user', read_only=True)

    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'user_detail', 'role', 'joined_at']
        read_only_fields = ['joined_at']


class ProjectSerializer(serializers.ModelSerializer):
    creator_detail = UserDetailSerializer(source='creator', read_only=True)
    deleted_by_detail = UserDetailSerializer(source='deleted_by', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'description',
            'creator',
            'creator_detail',
            'is_deleted',
            'deleted_at',
            'deleted_by',
            'deleted_by_detail',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'creator',
            'is_deleted',
            'deleted_at',
            'deleted_by',
        ]

    def validate_name(self, value):
        queryset = Project.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('项目名称已存在')
        return value


class ProjectDetailSerializer(ProjectSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['members']


class ProjectMemberCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True, help_text='用户ID')

    class Meta:
        model = ProjectMember
        fields = ['user_id', 'role']

    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError('用户不存在') from exc
        return value

    def validate(self, attrs):
        project = self.context['project']
        user_id = attrs['user_id']

        if ProjectMember.objects.filter(project=project, user_id=user_id).exists():
            raise serializers.ValidationError({'user_id': '该用户已经是项目成员'})

        return attrs

    def create(self, validated_data):
        project = self.context['project']
        user_id = validated_data.pop('user_id')
        user = User.objects.get(id=user_id)
        return ProjectMember.objects.create(project=project, user=user, **validated_data)


class ProjectDeletionRequestSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    requested_by_detail = UserDetailSerializer(source='requested_by', read_only=True)
    reviewed_by_detail = UserDetailSerializer(source='reviewed_by', read_only=True)
    restored_by_detail = UserDetailSerializer(source='restored_by', read_only=True)
    can_restore = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDeletionRequest
        fields = [
            'id',
            'project',
            'project_name',
            'project_display_id',
            'requested_by',
            'requested_by_name',
            'requested_by_detail',
            'request_note',
            'status',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_by_detail',
            'review_note',
            'requested_at',
            'reviewed_at',
            'deleted_at',
            'restored_at',
            'restored_by',
            'restored_by_name',
            'restored_by_detail',
            'can_restore',
        ]
        read_only_fields = fields

    def get_can_restore(self, obj):
        return bool(
            obj.project_id
            and obj.status == ProjectDeletionRequest.STATUS_APPROVED
            and obj.project
            and obj.project.is_deleted
        )

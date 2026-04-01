# 导入 DRF 序列化器基类。
from rest_framework import serializers

# 导入 API Key 模型。
from .models import APIKey


class APIKeySerializer(serializers.ModelSerializer):
    # 仅回显用户名，避免暴露并要求前端传递 user 主键。
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = APIKey
        fields = ['id', 'name', 'key', 'user', 'created_at', 'expires_at', 'is_active']
        # key/created_at 由后端生成，前端不可覆盖。
        read_only_fields = ['key', 'created_at']

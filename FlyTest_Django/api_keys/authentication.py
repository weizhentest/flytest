# 导入 DRF 认证基类。
from rest_framework.authentication import BaseAuthentication

# 导入认证失败异常。
from rest_framework.exceptions import AuthenticationFailed



# 导入 API Key 模型。
from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    """
    基于 API Key 的自定义认证类。
    优先读取 Authorization: Bearer <token>，无可用值时回退到 X-API-Key 请求头。
    """

    def authenticate(self, request):
        api_key_value = None

        # 优先兼容 Authorization: Bearer <token> 头，方便统一接入网关/SDK。
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            try:
                token_type, token = auth_header.split(" ", 1)
                if token_type.lower() == "bearer":
                    api_key_value = token
            except ValueError:
                # 格式非法时回退到 X-API-Key 头，不直接失败。
                pass

        # 条件：Authorization 未携带可用 token；动作：回退 X-API-Key；结果：兼容旧客户端调用方式。
        if not api_key_value:
            api_key_value = request.META.get("HTTP_X_API_KEY")

        if not api_key_value:
            # 未提供 API Key 时返回 None，交由后续认证类（如 JWT）继续尝试。
            return None

        try:
            api_key_obj = APIKey.objects.select_related("user").get(key=api_key_value)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API Key.")

        # 条件：Key 不可用（禁用或过期）；动作：拒绝认证；结果：阻断无效密钥访问。
        if not api_key_obj.is_valid():
            raise AuthenticationFailed("API Key is inactive or expired.")

        # 认证成功后返回 (user, token_obj)，让权限系统按关联用户继续判定。
        return (api_key_obj.user, api_key_obj)

    def authenticate_header(self, request):
        """
        返回 401 未授权响应中 WWW-Authenticate 请求头应使用的值。
        """
        return "API-Key"

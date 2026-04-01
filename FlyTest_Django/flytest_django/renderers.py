# 导入标准库 json。
import json

# 导入 DRF 的 JSON 渲染器基类。
from rest_framework.renderers import JSONRenderer

# 导入 DRF 编码器工具。
from rest_framework.utils import encoders


# 定义统一响应渲染器。
class UnifiedResponseRenderer(JSONRenderer):
    """
    自定义 Renderer，用于将 API 响应统一格式化。
    确保所有 API 端点在成功和错误时都返回遵循以下统一结构的 JSON 响应：
    {
      "status": "success" / "error",
      "code": 200 / 400 / 500,
      "message": "操作成功" / "具体的错误信息",
      "data": { ... } / null,
      "errors": { ... } / null / []
    }
    """

    # 指定字符集。
    charset = "utf-8"

    # 执行统一响应渲染。
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # 断言渲染上下文存在。
        assert renderer_context is not None

        # 断言 response 存在于上下文中。
        assert "response" in renderer_context

        # 取出 response 对象。
        response = renderer_context["response"]

        # 读取当前状态码。
        status_code = response.status_code

        # 兼容 204 无响应体场景。
        if status_code == 204:
            # 保存原始状态码。
            response._original_status = 204

            # 将状态码调整为 200 以返回统一 JSON 结构。
            response.status_code = 200

            # 同步本地状态码。
            status_code = 200

        # 初始化统一响应结构。
        unified_response = {
            "status": "success",
            "code": status_code,
            "message": "",
            "data": None,
            "errors": None,
        }

        # 针对 dict 类型数据做特判。
        if isinstance(data, dict):
            # 命中 simplejwt 成功返回结构。
            if "access" in data and "refresh" in data and status_code == 200:
                unified_response["status"] = "success"
                unified_response["message"] = "Token 获取成功"
                unified_response["data"] = data



            # 命中 simplejwt 错误返回结构。
            elif (
                "detail" in data
                and "code" in data
                and "messages" not in data
                and status_code >= 400
            ):
                unified_response["status"] = "error"
                unified_response["message"] = data.get("detail", "认证失败")
                unified_response["errors"] = {
                    "token_error": data.get("detail"),
                    "error_code": data.get("code"),
                }

                # 防止重复进入通用分支。
                data = None

        # 通用包装分支。
        if data is not None:
            # 错误响应分支。
            if status_code >= 400:
                unified_response["status"] = "error"
                unified_response["data"] = None

                # 标准 detail 错误。
                if isinstance(data, dict) and "detail" in data:
                    unified_response["message"] = data.get("detail", "请求处理失败")
                    unified_response["errors"] = {"detail": data.get("detail")}

                # 字段校验错误或列表错误。
                elif isinstance(data, (dict, list)):
                    unified_response["message"] = "请求参数有误或处理失败"
                    unified_response["errors"] = data

                # 未知错误类型。
                else:
                    unified_response["message"] = str(data)
                    unified_response["errors"] = {"detail": str(data)}

            # 成功响应分支。
            else:
                unified_response["status"] = "success"


                # 已是统一结构时做合并。
                if isinstance(data, dict) and all(
                    k in data for k in ["status", "code", "message"]
                ):
                    original_code = unified_response["code"]
                    unified_response.update(data)
                    unified_response["code"] = original_code

                # 普通成功数据包装。
                else:
                    unified_response["data"] = data
                    unified_response["message"] = "操作成功"

        # 兜底填充 message。
        if not unified_response.get("message"):
            if unified_response["status"] == "success":
                unified_response["message"] = "操作成功完成"
            else:
                if unified_response.get("errors"):
                    unified_response["message"] = "请求处理失败，请查看错误详情"
                else:
                    unified_response["message"] = "发生未知错误"

        # 成功时确保 errors 为空。
        if unified_response["status"] == "success":
            if unified_response.get("errors") is not None:
                unified_response["errors"] = None

        # 错误时确保 data 为空并补全 errors。
        elif unified_response["status"] == "error":
            if unified_response.get("data") is not None:
                unified_response["data"] = None

            if unified_response.get("errors") is None:
                unified_response["errors"] = {
                    "detail": unified_response.get(
                        "message", "请求处理时发生错误，具体原因未知。"
                    )
                }

        # 删除操作语义化提示。
        if (
            status_code == 200
            and data is None
            and getattr(response, "_original_status", None) == 204
        ):
            unified_response["message"] = "删除操作成功完成"

        # 调用父类完成最终 JSON 序列化。
        return super().render(unified_response, accepted_media_type, renderer_context)

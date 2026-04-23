from typing import Any


def success_response(data: Any = None, message: str = "操作成功", code: int = 200) -> dict[str, Any]:
    return {
        "status": "success",
        "code": code,
        "message": message,
        "data": data,
        "errors": None,
    }


def error_response(message: str = "操作失败", code: int = 400, errors: Any = None) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "data": None,
        "errors": errors,
    }

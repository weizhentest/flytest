from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.router import router as api_router
from app.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.lifespan import app_lifespan


def generate_unique_operation_id(route: APIRoute) -> str:
    methods = sorted(method for method in (route.methods or set()) if method not in {"HEAD", "OPTIONS"})
    method_part = "_".join(methods).lower() or "any"
    path_part = route.path_format.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
    return f"{method_part}_{path_part}"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        debug=settings.debug,
        lifespan=app_lifespan,
        generate_unique_id_function=generate_unique_operation_id,
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router)
    return app


app = create_app()

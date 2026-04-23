from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html


router = APIRouter(prefix="/api", tags=["schema"])


@router.get("/schema/")
def openapi_schema(request: Request):
    return JSONResponse(request.app.openapi())


@router.get("/schema/swagger-ui/")
def swagger_ui():
    return get_swagger_ui_html(openapi_url="/api/schema/", title="Swagger UI")


@router.get("/schema/redoc/")
def redoc_ui():
    return get_redoc_html(openapi_url="/api/schema/", title="ReDoc")

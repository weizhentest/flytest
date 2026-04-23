from __future__ import annotations

import os
import threading
from types import SimpleNamespace

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def _request_context(user):
    return {"request": SimpleNamespace(user=user)}


def _accessible_knowledge_bases(user_id: int):
    ensure_django_setup()
    from knowledge.models import KnowledgeBase

    user = get_django_user(user_id)
    if not user:
        return KnowledgeBase.objects.none()
    if user.is_superuser:
        return KnowledgeBase.objects.all()
    return KnowledgeBase.objects.filter(project__members__user=user).distinct()


def _accessible_documents(user_id: int):
    ensure_django_setup()
    from knowledge.models import Document

    user = get_django_user(user_id)
    if not user:
        return Document.objects.none()
    if user.is_superuser:
        return Document.objects.all()
    return Document.objects.filter(knowledge_base__project__members__user=user).distinct()


def get_global_config(*, user_id: int) -> dict:
    ensure_django_setup()
    from knowledge.models import KnowledgeGlobalConfig
    from knowledge.serializers import KnowledgeGlobalConfigSerializer

    config = KnowledgeGlobalConfig.get_config()
    data = KnowledgeGlobalConfigSerializer(config).data
    if data.get("api_key"):
        api_key = data["api_key"]
        data["api_key"] = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "*" * len(api_key)
    return data


def update_global_config(*, user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.models import KnowledgeGlobalConfig
    from knowledge.serializers import KnowledgeGlobalConfigSerializer
    from knowledge.services import VectorStoreManager

    user = get_django_user(user_id)
    if not user or not user.is_superuser:
        raise AppError("只有管理员可以修改全局配置", status_code=403)
    config = KnowledgeGlobalConfig.get_config()
    serializer = KnowledgeGlobalConfigSerializer(config, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("全局配置更新失败", status_code=400, errors=serializer.errors)
    instance = serializer.save(updated_by=user)
    VectorStoreManager.clear_global_config_cache()
    VectorStoreManager._embeddings_cache.clear()
    return KnowledgeGlobalConfigSerializer(instance).data


def embedding_services() -> dict:
    ensure_django_setup()
    from knowledge.models import KnowledgeGlobalConfig

    return {
        "services": [{"value": value, "label": label} for value, label in KnowledgeGlobalConfig.EMBEDDING_SERVICE_CHOICES]
    }


def list_knowledge_bases(*, user_id: int, project=None, search: str | None = None, is_active: bool | None = None):
    ensure_django_setup()
    from knowledge.serializers import KnowledgeBaseSerializer

    queryset = _accessible_knowledge_bases(user_id)
    if project:
        queryset = queryset.filter(project=project)
    if search:
        queryset = queryset.filter(name__icontains=search) | queryset.filter(description__icontains=search)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return KnowledgeBaseSerializer(queryset.order_by("-created_at"), many=True, context=_request_context(get_django_user(user_id))).data


def create_knowledge_base(*, user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.serializers import KnowledgeBaseSerializer

    user = get_django_user(user_id)
    serializer = KnowledgeBaseSerializer(data=payload, context=_request_context(user))
    if not serializer.is_valid():
        raise AppError("知识库创建失败", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=user)
    return KnowledgeBaseSerializer(instance, context=_request_context(user)).data


def get_knowledge_base(*, user_id: int, kb_id: str) -> dict:
    ensure_django_setup()
    from knowledge.models import KnowledgeBase
    from knowledge.serializers import KnowledgeBaseSerializer

    item = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not item:
        raise AppError("知识库不存在", status_code=404)
    return KnowledgeBaseSerializer(item, context=_request_context(get_django_user(user_id))).data


def update_knowledge_base(*, user_id: int, kb_id: str, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.serializers import KnowledgeBaseSerializer

    user = get_django_user(user_id)
    item = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not item:
        raise AppError("知识库不存在", status_code=404)
    serializer = KnowledgeBaseSerializer(item, data=payload, partial=True, context=_request_context(user))
    if not serializer.is_valid():
        raise AppError("知识库更新失败", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return KnowledgeBaseSerializer(instance, context=_request_context(user)).data


def delete_knowledge_base(*, user_id: int, kb_id: str) -> None:
    item = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not item:
        raise AppError("知识库不存在", status_code=404)
    item.delete()


def get_knowledge_base_statistics(*, user_id: int, kb_id: str) -> dict:
    ensure_django_setup()
    from knowledge.views import KnowledgeBaseViewSet

    item = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not item:
        raise AppError("知识库不存在", status_code=404)
    view = KnowledgeBaseViewSet()
    view.request = SimpleNamespace(user=get_django_user(user_id))
    view.kwargs = {}
    view.get_object = lambda: item
    response = view.statistics(view.request)
    data = dict(response.data)
    if "recent_queries" in data:
        data["recent_queries"] = list(data["recent_queries"])
    return data


def query_knowledge_base(*, user_id: int, kb_id: str, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.models import KnowledgeBase
    from knowledge.serializers import KnowledgeQueryResponseSerializer, KnowledgeQuerySerializer
    from knowledge.services import KnowledgeBaseService

    user = get_django_user(user_id)
    knowledge_base = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not knowledge_base:
        raise AppError("知识库不存在", status_code=404)

    data = dict(payload)
    data["knowledge_base_id"] = kb_id
    serializer = KnowledgeQuerySerializer(data=data, context=_request_context(user))
    if not serializer.is_valid():
        raise AppError("知识库查询失败", status_code=400, errors=serializer.errors)
    service = KnowledgeBaseService(knowledge_base)
    result = service.query(
        query_text=serializer.validated_data["query"],
        top_k=serializer.validated_data.get("top_k", 5),
        similarity_threshold=serializer.validated_data.get("similarity_threshold", 0.1),
        user=user,
    )
    return KnowledgeQueryResponseSerializer(result).data


def system_status(*, user_id: int) -> dict:
    ensure_django_setup()
    from knowledge.views import KnowledgeBaseViewSet

    user = get_django_user(user_id)
    view = KnowledgeBaseViewSet()
    request = SimpleNamespace(user=user)
    response = view.system_status(request)
    return response.data


def list_documents(*, user_id: int, knowledge_base=None, document_type: str | None = None, status: str | None = None, search: str | None = None):
    ensure_django_setup()
    from knowledge.models import Document
    from knowledge.serializers import DocumentSerializer

    queryset = _accessible_documents(user_id)
    if knowledge_base:
        queryset = queryset.filter(knowledge_base=knowledge_base)
    if document_type:
        queryset = queryset.filter(document_type=document_type)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(title__icontains=search) | queryset.filter(content__icontains=search)
    return DocumentSerializer(queryset.order_by("-uploaded_at"), many=True).data


def upload_document(*, user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.serializers import DocumentSerializer, DocumentUploadSerializer
    from knowledge.services import KnowledgeBaseService

    user = get_django_user(user_id)
    serializer = DocumentUploadSerializer(data=payload, context=_request_context(user))
    if not serializer.is_valid():
        raise AppError("文档上传失败", status_code=400, errors=serializer.errors)
    document = serializer.save(uploader=user)

    def process_document_async():
        try:
            service = KnowledgeBaseService(document.knowledge_base)
            service.process_document(document)
        except Exception as exc:  # noqa: BLE001
            document.status = "failed"
            document.error_message = str(exc)
            document.save()

    thread = threading.Thread(target=process_document_async, daemon=True)
    thread.start()
    return DocumentSerializer(document).data


def get_document(*, user_id: int, document_id: str) -> dict:
    ensure_django_setup()
    from knowledge.serializers import DocumentSerializer

    item = _accessible_documents(user_id).filter(id=document_id).first()
    if not item:
        raise AppError("文档不存在", status_code=404)
    return DocumentSerializer(item).data


def get_document_content(*, user_id: int, document_id: str, include_chunks: bool = False, chunk_page: int = 1, chunk_page_size: int = 10) -> dict:
    ensure_django_setup()
    from knowledge.views import DocumentViewSet

    item = _accessible_documents(user_id).filter(id=document_id).first()
    if not item:
        raise AppError("文档不存在", status_code=404)
    view = DocumentViewSet()
    request = SimpleNamespace(
        user=get_django_user(user_id),
        query_params={
            "include_chunks": str(include_chunks).lower(),
            "chunk_page": str(chunk_page),
            "chunk_page_size": str(chunk_page_size),
        },
    )
    view.request = request
    view.kwargs = {}
    view.get_object = lambda: item
    response = view.content(request)
    return response.data


def reprocess_document(*, user_id: int, document_id: str) -> dict:
    ensure_django_setup()
    from knowledge.views import DocumentViewSet

    item = _accessible_documents(user_id).filter(id=document_id).first()
    if not item:
        raise AppError("文档不存在", status_code=404)
    view = DocumentViewSet()
    request = SimpleNamespace(user=get_django_user(user_id))
    view.request = request
    view.kwargs = {}
    view.get_object = lambda: item
    response = view.reprocess(request)
    return response.data


def delete_document(*, user_id: int, document_id: str) -> None:
    ensure_django_setup()
    from knowledge.services import KnowledgeBaseService, VectorStoreManager

    item = _accessible_documents(user_id).filter(id=document_id).first()
    if not item:
        raise AppError("文档不存在", status_code=404)
    knowledge_base_id = item.knowledge_base.id

    try:
        service = KnowledgeBaseService(item.knowledge_base)
        service.delete_document(item)
        return
    except Exception:  # noqa: BLE001
        # Fall back to local record cleanup when vector store dependencies are unavailable.
        pass

    try:
        item.chunks.all().delete()
    except Exception:  # noqa: BLE001
        pass

    try:
        if item.file and os.path.exists(item.file.path):
            os.remove(item.file.path)
    except Exception:  # noqa: BLE001
        pass

    item.delete()
    try:
        VectorStoreManager.clear_cache(knowledge_base_id)
    except Exception:  # noqa: BLE001
        pass


def _accessible_chunks(user_id: int):
    ensure_django_setup()
    from knowledge.models import DocumentChunk

    user = get_django_user(user_id)
    if not user:
        return DocumentChunk.objects.none()
    if user.is_superuser:
        return DocumentChunk.objects.all()
    return DocumentChunk.objects.filter(document__knowledge_base__project__members__user=user).distinct()


def _accessible_query_logs(user_id: int):
    ensure_django_setup()
    from knowledge.models import QueryLog

    user = get_django_user(user_id)
    if not user:
        return QueryLog.objects.none()
    if user.is_superuser:
        return QueryLog.objects.all()
    return QueryLog.objects.filter(knowledge_base__project__members__user=user).distinct()


def get_knowledge_base_content(
    *,
    user_id: int,
    kb_id: str,
    search: str = "",
    document_type: str = "",
    status: str = "completed",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    ensure_django_setup()
    from knowledge.views import KnowledgeBaseViewSet

    item = _accessible_knowledge_bases(user_id).filter(id=kb_id).first()
    if not item:
        raise AppError("Knowledge base not found", status_code=404)
    view = KnowledgeBaseViewSet()
    request = SimpleNamespace(
        user=get_django_user(user_id),
        query_params={
            "search": search,
            "document_type": document_type,
            "status": status,
            "page": str(page),
            "page_size": str(page_size),
        },
    )
    view.request = request
    view.kwargs = {}
    view.get_object = lambda: item
    response = view.content(request)
    return response.data


def get_document_status(*, user_id: int, document_id: str) -> dict:
    ensure_django_setup()
    from knowledge.views import DocumentViewSet

    item = _accessible_documents(user_id).filter(id=document_id).first()
    if not item:
        raise AppError("Document not found", status_code=404)
    view = DocumentViewSet()
    request = SimpleNamespace(user=get_django_user(user_id))
    view.request = request
    view.kwargs = {}
    view.get_object = lambda: item
    response = view.status(request)
    return response.data


def list_chunks(
    *,
    user_id: int,
    document: str | None = None,
    knowledge_base: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from knowledge.serializers import DocumentChunkSerializer

    queryset = _accessible_chunks(user_id)
    if document:
        queryset = queryset.filter(document_id=document)
    if knowledge_base:
        queryset = queryset.filter(document__knowledge_base_id=knowledge_base)
    if search:
        queryset = queryset.filter(content__icontains=search)
    return DocumentChunkSerializer(queryset.order_by("document", "chunk_index"), many=True).data


def get_chunk(*, user_id: int, chunk_id: str) -> dict:
    ensure_django_setup()
    from knowledge.serializers import DocumentChunkSerializer

    item = _accessible_chunks(user_id).filter(id=chunk_id).first()
    if not item:
        raise AppError("Document chunk not found", status_code=404)
    return DocumentChunkSerializer(item).data


def list_query_logs(
    *,
    user_id: int,
    knowledge_base: str | None = None,
    user: int | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from django.db.models import Q
    from knowledge.serializers import QueryLogSerializer

    queryset = _accessible_query_logs(user_id)
    if knowledge_base:
        queryset = queryset.filter(knowledge_base_id=knowledge_base)
    if user:
        queryset = queryset.filter(user_id=user)
    if search:
        queryset = queryset.filter(Q(query__icontains=search) | Q(response__icontains=search))
    return QueryLogSerializer(queryset.order_by("-created_at"), many=True).data


def get_query_log(*, user_id: int, log_id: str) -> dict:
    ensure_django_setup()
    from knowledge.serializers import QueryLogSerializer

    item = _accessible_query_logs(user_id).filter(id=log_id).first()
    if not item:
        raise AppError("Query log not found", status_code=404)
    return QueryLogSerializer(item).data


def test_embedding_connection(payload: dict) -> dict:
    import requests as http_requests

    embedding_service = payload.get("embedding_service")
    api_base_url = str(payload.get("api_base_url") or "").rstrip("/")
    api_key = str(payload.get("api_key") or "")
    model_name = str(payload.get("model_name") or "")

    if not embedding_service:
        raise AppError("请选择嵌入服务", status_code=400)
    if not api_base_url:
        raise AppError("请输入API基础URL", status_code=400)
    if not model_name:
        raise AppError("请输入模型名称", status_code=400)
    if embedding_service in ["openai", "azure_openai"] and not api_key:
        service_name = "OpenAI" if embedding_service == "openai" else "Azure OpenAI"
        raise AppError(f"{service_name} 服务需要API密钥", status_code=400)

    test_text = "This is a test embedding request."

    if embedding_service == "openai":
        test_url = f"{api_base_url}/embeddings"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        request_body = {"input": test_text, "model": model_name}
    elif embedding_service == "azure_openai":
        test_url = f"{api_base_url}/openai/deployments/{model_name}/embeddings?api-version=2024-02-15-preview"
        headers = {"Content-Type": "application/json", "api-key": api_key}
        request_body = {"input": test_text}
    elif embedding_service == "ollama":
        test_url = f"{api_base_url}/api/embeddings"
        headers = {"Content-Type": "application/json"}
        request_body = {"model": model_name, "prompt": test_text}
    elif embedding_service == "xinference":
        test_url = f"{api_base_url}/v1/embeddings"
        headers = {"Content-Type": "application/json"}
        request_body = {"input": test_text, "model": model_name}
    elif embedding_service == "custom":
        test_url = api_base_url
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request_body = {"input": test_text, "model": model_name}
    else:
        raise AppError(f"不支持的嵌入服务类型: {embedding_service}", status_code=400)

    try:
        response = http_requests.post(test_url, json=request_body, headers=headers, timeout=30)
        if response.ok:
            data = response.json()
            if embedding_service == "ollama":
                has_embedding = bool(data.get("embedding")) and isinstance(data["embedding"], list)
            else:
                has_embedding = (
                    data.get("data")
                    and isinstance(data["data"], list)
                    and len(data["data"]) > 0
                    and data["data"][0].get("embedding")
                )
            if has_embedding:
                return {"success": True, "message": "嵌入模型测试成功！服务运行正常"}
            return {"success": False, "message": "服务响应成功但数据格式异常，请检查配置"}
        return {
            "success": False,
            "message": f"嵌入模型测试失败: HTTP {response.status_code} - {response.text[:500]}",
        }
    except http_requests.Timeout:
        return {"success": False, "message": "请求超时，请检查服务是否正常运行"}
    except http_requests.ConnectionError as exc:
        return {"success": False, "message": f"无法连接到服务，请检查URL和网络: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": f"嵌入模型测试失败: {exc}"}


def test_reranker_connection(payload: dict) -> dict:
    import requests as http_requests

    reranker_service = payload.get("reranker_service")
    reranker_api_url = str(payload.get("reranker_api_url") or "").rstrip("/")
    reranker_api_key = str(payload.get("reranker_api_key") or "")
    reranker_model_name = str(payload.get("reranker_model_name") or "")

    if not reranker_service or reranker_service == "none":
        raise AppError("请选择 Reranker 服务", status_code=400)
    if not reranker_api_url:
        raise AppError("请输入 Reranker API 地址", status_code=400)
    if not reranker_model_name:
        raise AppError("请输入 Reranker 模型名称", status_code=400)

    test_query = "What is machine learning?"
    test_documents = ["Machine learning is a subset of AI.", "The weather is nice today."]

    if reranker_service == "xinference":
        test_url = f"{reranker_api_url}/v1/rerank"
        headers = {"Content-Type": "application/json"}
        request_body = {"model": reranker_model_name, "query": test_query, "documents": test_documents}
    elif reranker_service == "custom":
        test_url = reranker_api_url
        headers = {"Content-Type": "application/json"}
        if reranker_api_key:
            headers["Authorization"] = f"Bearer {reranker_api_key}"
        request_body = {"model": reranker_model_name, "query": test_query, "documents": test_documents}
    else:
        raise AppError(f"不支持的 Reranker 服务类型: {reranker_service}", status_code=400)

    try:
        response = http_requests.post(test_url, json=request_body, headers=headers, timeout=30)
        if response.ok:
            data = response.json()
            has_results = bool(data.get("results")) and isinstance(data["results"], list) and len(data["results"]) > 0
            if has_results:
                return {"success": True, "message": "Reranker 服务测试成功！服务运行正常"}
            return {"success": False, "message": "服务响应成功但数据格式异常，请检查配置"}
        return {
            "success": False,
            "message": f"Reranker 测试失败: HTTP {response.status_code} - {response.text[:500]}",
        }
    except http_requests.Timeout:
        return {"success": False, "message": "请求超时，请检查服务是否正常运行"}
    except http_requests.ConnectionError as exc:
        return {"success": False, "message": f"无法连接到服务，请检查URL和网络: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": f"Reranker 测试失败: {exc}"}

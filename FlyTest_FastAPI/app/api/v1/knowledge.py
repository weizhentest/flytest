from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.knowledge.service import (
    create_knowledge_base,
    delete_document,
    delete_knowledge_base,
    embedding_services,
    get_document,
    get_document_content,
    get_document_status,
    get_global_config,
    get_knowledge_base,
    get_knowledge_base_content,
    get_knowledge_base_statistics,
    get_chunk,
    get_query_log,
    list_documents,
    list_chunks,
    list_query_logs,
    list_knowledge_bases,
    query_knowledge_base,
    reprocess_document,
    system_status,
    test_embedding_connection,
    test_reranker_connection,
    update_global_config,
    update_knowledge_base,
    upload_document,
)


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/global-config/")
def knowledge_global_config(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_global_config(db=db, user=user))


@router.put("/global-config/")
def knowledge_update_global_config(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_global_config(db=db, user=user, payload=payload))


@router.get("/embedding-services/")
def knowledge_embedding_services(user=Depends(get_current_user)) -> dict:
    return success_response(embedding_services())


@router.get("/knowledge-bases/")
def knowledge_base_list(
    project: int | str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        list_knowledge_bases(
            db=db,
            user=user,
            project=project,
            search=search,
            is_active=is_active,
        )
    )


@router.post("/knowledge-bases/", status_code=201)
def knowledge_base_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_knowledge_base(db=db, user=user, payload=payload), code=201)


@router.get("/knowledge-bases/system_status/")
def knowledge_system_status(user=Depends(get_current_user)) -> dict:
    return success_response(system_status(user_id=user.id))


@router.get("/knowledge-bases/{kb_id}/")
def knowledge_base_detail(kb_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_knowledge_base(db=db, user=user, kb_id=kb_id))


@router.put("/knowledge-bases/{kb_id}/")
def knowledge_base_put(kb_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_knowledge_base(db=db, user=user, kb_id=kb_id, payload=payload))


@router.patch("/knowledge-bases/{kb_id}/")
def knowledge_base_patch(kb_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_knowledge_base(db=db, user=user, kb_id=kb_id, payload=payload))


@router.delete("/knowledge-bases/{kb_id}/")
def knowledge_base_delete(kb_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_knowledge_base(db=db, user=user, kb_id=kb_id)
    return success_response(None)


@router.get("/knowledge-bases/{kb_id}/statistics/")
def knowledge_base_statistics(kb_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(get_knowledge_base_statistics(user_id=user.id, kb_id=kb_id))


@router.get("/knowledge-bases/{kb_id}/content/")
def knowledge_base_content(
    kb_id: str,
    search: str = "",
    document_type: str = "",
    status: str = "completed",
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        get_knowledge_base_content(
            user_id=user.id,
            kb_id=kb_id,
            search=search,
            document_type=document_type,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/knowledge-bases/{kb_id}/query/")
def knowledge_base_query(kb_id: str, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(query_knowledge_base(user_id=user.id, kb_id=kb_id, payload=payload))


@router.get("/documents/")
def knowledge_documents(
    knowledge_base: str | None = None,
    document_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        list_documents(
            db=db,
            user=user,
            knowledge_base=knowledge_base,
            document_type=document_type,
            status=status,
            search=search,
        )
    )


@router.post("/documents/", status_code=201)
async def knowledge_upload_document(
    knowledge_base: str = Form(...),
    title: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    content: str | None = Form(default=None),
    url: str | None = Form(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = {
        "knowledge_base": knowledge_base,
        "title": title,
        "document_type": document_type,
        "content": content,
        "url": url,
    }
    if file is not None:
        payload["file"] = file.file
        if not getattr(file.file, "name", None):
            file.file.name = file.filename or "upload.bin"
    return success_response(await run_in_threadpool(upload_document, db=db, user=user, payload=payload), code=201)


@router.get("/documents/{document_id}/")
def knowledge_document_detail(document_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_document(db=db, user=user, document_id=document_id))


@router.get("/documents/{document_id}/status/")
def knowledge_document_status(document_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_document_status(db=db, user=user, document_id=document_id))


@router.get("/documents/{document_id}/content/")
def knowledge_document_content(
    document_id: str,
    include_chunks: bool = False,
    chunk_page: int = 1,
    chunk_page_size: int = 10,
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        get_document_content(
            user_id=user.id,
            document_id=document_id,
            include_chunks=include_chunks,
            chunk_page=chunk_page,
            chunk_page_size=chunk_page_size,
        )
    )


@router.post("/documents/{document_id}/reprocess/")
def knowledge_document_reprocess(document_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(reprocess_document(user_id=user.id, document_id=document_id))


@router.delete("/documents/{document_id}/")
def knowledge_document_delete(document_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_document(db=db, user=user, document_id=document_id)
    return success_response(None)


@router.get("/chunks/")
def knowledge_chunks(
    document: str | None = None,
    knowledge_base: str | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        list_chunks(
            user_id=user.id,
            document=document,
            knowledge_base=knowledge_base,
            search=search,
        )
    )


@router.get("/chunks/{chunk_id}/")
def knowledge_chunk_detail(chunk_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(get_chunk(user_id=user.id, chunk_id=chunk_id))


@router.get("/query-logs/")
def knowledge_query_logs(
    knowledge_base: str | None = None,
    user_id: int | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        list_query_logs(
            user_id=user.id,
            knowledge_base=knowledge_base,
            user=user_id,
            search=search,
        )
    )


@router.get("/query-logs/{log_id}/")
def knowledge_query_log_detail(log_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(get_query_log(user_id=user.id, log_id=log_id))


@router.post("/test-embedding-connection/")
async def knowledge_test_embedding_connection(payload: dict, user=Depends(get_current_user)):
    return await run_in_threadpool(test_embedding_connection, payload)


@router.post("/test-reranker-connection/")
async def knowledge_test_reranker_connection(payload: dict, user=Depends(get_current_user)):
    return await run_in_threadpool(test_reranker_connection, payload)

from datetime import datetime

from sqlalchemy.orm import Session

from app.compat.django_bridge import get_default_prompts_from_django
from app.core.errors import AppError
from app.db.models.auth import User
from app.db.models.prompts import UserPrompt
from app.repositories.prompts import PromptRepository


PROMPT_TYPE_LABELS = {
    "general": "通用对话",
    "completeness_analysis": "完整性分析",
    "consistency_analysis": "一致性分析",
    "testability_analysis": "可测性分析",
    "feasibility_analysis": "可行性分析",
    "clarity_analysis": "清晰度分析",
    "logic_analysis": "逻辑分析",
    "test_case_execution": "测试用例执行",
    "api_automation_parsing": "API自动化解析",
    "api_automation_report_summary": "API测试报告摘要",
    "diagram_generation": "图表生成",
}

PROGRAM_CALL_TYPES = {
    "completeness_analysis",
    "consistency_analysis",
    "testability_analysis",
    "feasibility_analysis",
    "clarity_analysis",
    "logic_analysis",
    "test_case_execution",
    "api_automation_parsing",
    "api_automation_report_summary",
    "diagram_generation",
}


def serialize_prompt(prompt: UserPrompt) -> dict:
    return {
        "id": prompt.id,
        "name": prompt.name,
        "content": prompt.content,
        "description": prompt.description,
        "prompt_type": prompt.prompt_type,
        "prompt_type_display": PROMPT_TYPE_LABELS.get(prompt.prompt_type, prompt.prompt_type),
        "is_default": bool(prompt.is_default),
        "is_active": bool(prompt.is_active),
        "created_at": prompt.created_at.isoformat() if prompt.created_at else "",
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else "",
        "is_requirement_type": prompt.prompt_type != "general",
    }


def validate_prompt_payload(
    *,
    repo: PromptRepository,
    user_id: int,
    name: str,
    content: str,
    prompt_type: str,
    is_default: bool,
    current_prompt_id: int | None = None,
) -> None:
    if not name.strip():
        raise AppError("提示词名称不能为空", status_code=400, errors={"name": ["提示词名称不能为空"]})
    if not content.strip():
        raise AppError("提示词内容不能为空", status_code=400, errors={"content": ["提示词内容不能为空"]})
    existing_by_name = repo.find_by_name(user_id=user_id, name=name.strip())
    if existing_by_name and existing_by_name.id != current_prompt_id:
        raise AppError("该名称的提示词已存在", status_code=400, errors={"name": ["该名称的提示词已存在"]})

    if is_default and prompt_type in PROGRAM_CALL_TYPES:
        raise AppError(
            "程序调用类型的提示词不能设为默认",
            status_code=400,
            errors={"is_default": ["程序调用类型的提示词不能设为默认"]},
        )

    if prompt_type in PROGRAM_CALL_TYPES:
        existing_by_type = repo.get_by_type(user_id=user_id, prompt_type=prompt_type)
        if existing_by_type and existing_by_type.id != current_prompt_id:
            raise AppError(
                "每个用户每种程序调用类型只能存在一个提示词",
                status_code=400,
                errors={"prompt_type": ["每个用户每种程序调用类型只能存在一个提示词"]},
            )


def list_prompts(
    db: Session,
    *,
    user: User,
    search: str | None = None,
    is_default: bool | None = None,
    is_active: bool | None = None,
    prompt_type: str | None = None,
    ordering: str | None = None,
) -> dict:
    repo = PromptRepository(db)
    results = repo.list_user_prompts(
        user_id=user.id,
        search=search,
        is_default=is_default,
        is_active=is_active,
        prompt_type=prompt_type,
        ordering=ordering,
    )
    return {
        "count": len(results),
        "next": None,
        "previous": None,
        "results": [
            {key: value for key, value in serialize_prompt(item).items() if key != "content" and key != "is_requirement_type"}
            for item in results
        ],
    }


def get_prompt(db: Session, *, user: User, prompt_id: int) -> UserPrompt:
    repo = PromptRepository(db)
    prompt = repo.get_by_id(user_id=user.id, prompt_id=prompt_id)
    if not prompt:
        raise AppError("提示词不存在", status_code=404)
    return prompt


def create_prompt(db: Session, *, user: User, payload: dict) -> UserPrompt:
    repo = PromptRepository(db)
    name = str(payload.get("name") or "").strip()
    content = str(payload.get("content") or "").strip()
    prompt_type = str(payload.get("prompt_type") or "general").strip()
    is_default = bool(payload.get("is_default", False))
    validate_prompt_payload(
        repo=repo,
        user_id=user.id,
        name=name,
        content=content,
        prompt_type=prompt_type,
        is_default=is_default,
    )
    if is_default and prompt_type == "general":
        _clear_general_default(db, user)
    prompt = UserPrompt(
        user_id=user.id,
        name=name,
        content=content,
        description=(str(payload.get("description")) if payload.get("description") is not None else None),
        prompt_type=prompt_type,
        is_default=is_default,
        is_active=bool(payload.get("is_active", True)),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    repo.create(prompt)
    db.commit()
    return prompt


def update_prompt(db: Session, *, user: User, prompt_id: int, payload: dict) -> UserPrompt:
    repo = PromptRepository(db)
    prompt = get_prompt(db, user=user, prompt_id=prompt_id)
    name = str(payload.get("name", prompt.name) or "").strip()
    content = str(payload.get("content", prompt.content) or "").strip()
    prompt_type = str(payload.get("prompt_type", prompt.prompt_type) or "general").strip()
    is_default = bool(payload.get("is_default", prompt.is_default))
    validate_prompt_payload(
        repo=repo,
        user_id=user.id,
        name=name,
        content=content,
        prompt_type=prompt_type,
        is_default=is_default,
        current_prompt_id=prompt.id,
    )
    if is_default and prompt_type == "general":
        _clear_general_default(db, user, exclude_prompt_id=prompt.id)
    prompt.name = name
    prompt.content = content
    prompt.description = str(payload.get("description")) if payload.get("description") is not None else prompt.description
    prompt.prompt_type = prompt_type
    prompt.is_default = is_default
    if "is_active" in payload:
        prompt.is_active = bool(payload.get("is_active"))
    prompt.updated_at = datetime.now()
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def delete_prompt(db: Session, *, user: User, prompt_id: int) -> None:
    repo = PromptRepository(db)
    prompt = get_prompt(db, user=user, prompt_id=prompt_id)
    repo.delete(prompt)
    db.commit()


def _clear_general_default(db: Session, user: User, exclude_prompt_id: int | None = None) -> int:
    repo = PromptRepository(db)
    prompts = repo.list_user_prompts(user_id=user.id, prompt_type="general")
    count = 0
    for prompt in prompts:
        if exclude_prompt_id and prompt.id == exclude_prompt_id:
            continue
        if prompt.is_default:
            prompt.is_default = False
            prompt.updated_at = datetime.now()
            db.add(prompt)
            count += 1
    return count


def set_default_prompt(db: Session, *, user: User, prompt_id: int) -> UserPrompt:
    prompt = get_prompt(db, user=user, prompt_id=prompt_id)
    if prompt.prompt_type in PROGRAM_CALL_TYPES:
        raise AppError("程序调用类型的提示词不能设为默认", status_code=400)
    _clear_general_default(db, user, exclude_prompt_id=prompt.id)
    prompt.is_default = True
    prompt.updated_at = datetime.now()
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def clear_default_prompt(db: Session, *, user: User) -> dict:
    updated_count = _clear_general_default(db, user)
    db.commit()
    return {"updated_count": updated_count}


def duplicate_prompt(db: Session, *, user: User, prompt_id: int) -> UserPrompt:
    repo = PromptRepository(db)
    prompt = get_prompt(db, user=user, prompt_id=prompt_id)
    base_name = f"{prompt.name} (副本)"
    name = base_name
    suffix = 2
    while repo.find_by_name(user_id=user.id, name=name):
        name = f"{base_name}-{suffix}"
        suffix += 1
    duplicated = UserPrompt(
        user_id=user.id,
        name=name,
        content=prompt.content,
        description=f"复制自: {prompt.description}" if prompt.description else "复制的提示词",
        prompt_type=prompt.prompt_type,
        is_default=False,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    repo.create(duplicated)
    db.commit()
    return duplicated


def get_prompt_types() -> list[dict]:
    return [
        {
            "value": key,
            "label": value,
            "is_program_call": key in PROGRAM_CALL_TYPES,
        }
        for key, value in PROMPT_TYPE_LABELS.items()
    ]


def initialize_prompts(db: Session, *, user: User, force_update: bool = False) -> dict:
    repo = PromptRepository(db)
    created: list[dict] = []
    skipped: list[dict] = []

    for prompt_data in get_default_prompts_from_django():
        prompt_type = str(prompt_data.get("prompt_type") or "general")
        existing = (
            repo.get_by_type(user_id=user.id, prompt_type=prompt_type)
            if prompt_type in PROGRAM_CALL_TYPES
            else repo.find_by_name(user_id=user.id, name=str(prompt_data.get("name") or ""))
        )
        if existing and not force_update:
            skipped.append({"name": prompt_data.get("name"), "prompt_type": prompt_type, "reason": "已存在"})
            continue

        if existing and force_update:
            existing.name = str(prompt_data.get("name") or existing.name)
            existing.content = str(prompt_data.get("content") or existing.content)
            existing.description = prompt_data.get("description")
            existing.is_default = bool(prompt_data.get("is_default", False))
            existing.is_active = True
            existing.updated_at = datetime.now()
            db.add(existing)
            created.append({"name": existing.name, "prompt_type": prompt_type, "action": "updated"})
            continue

        new_prompt = UserPrompt(
            user_id=user.id,
            name=str(prompt_data.get("name") or ""),
            content=str(prompt_data.get("content") or ""),
            description=prompt_data.get("description"),
            prompt_type=prompt_type,
            is_default=bool(prompt_data.get("is_default", False)),
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        repo.create(new_prompt)
        created.append({"name": new_prompt.name, "prompt_type": prompt_type, "action": "created"})

    db.commit()
    return {
        "created": created,
        "skipped": skipped,
        "summary": {
            "created_count": len(created),
            "skipped_count": len(skipped),
        },
    }


def get_init_status(db: Session, *, user: User) -> dict:
    prompts = PromptRepository(db).list_user_prompts(user_id=user.id)
    existing_types = {item.prompt_type for item in prompts}
    status_info = [
        {
            "type": key,
            "name": value,
            "exists": key in existing_types,
            "is_program_call": key in PROGRAM_CALL_TYPES,
        }
        for key, value in PROMPT_TYPE_LABELS.items()
    ]
    return {
        "existing_count": len(prompts),
        "status": status_info,
    }

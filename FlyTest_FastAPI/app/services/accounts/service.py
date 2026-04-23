from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.compat.django_bridge import make_password_with_django
from app.core.errors import AppError
from app.db.models.auth import ContentType, Group, Permission, User


APP_LABEL_LABELS = {
    "projects": "项目管理",
    "requirements": "需求管理",
    "orchestrator_integration": "智能图表",
    "ui_automation": "UI自动化",
    "testcases": "测试管理",
    "testcase_templates": "测试管理",
    "knowledge": "知识库管理",
    "langgraph_integration": "LLM对话",
    "prompts": "LLM对话",
    "auth": "系统管理",
    "accounts": "系统管理",
    "api_keys": "系统管理",
    "mcp_tools": "系统管理",
    "skills": "系统管理",
}

APP_LABEL_SORT = {
    "projects": 1,
    "requirements": 2,
    "orchestrator_integration": 3,
    "ui_automation": 4,
    "testcases": 5,
    "knowledge": 6,
}

MODEL_LABELS = {
    "user": "用户",
    "group": "用户组",
    "permission": "权限",
    "contenttype": "内容类型",
}

ACTION_LABELS = {
    "add": "添加",
    "change": "修改",
    "delete": "删除",
    "view": "查看",
}


def _user_query(db: Session):
    return select(User).options(
        selectinload(User.groups).selectinload(Group.permissions).selectinload(Permission.content_type),
        selectinload(User.direct_permissions).selectinload(Permission.content_type),
    )


def _group_query(db: Session):
    return select(Group).options(
        selectinload(Group.users),
        selectinload(Group.permissions).selectinload(Permission.content_type),
    )


def _permission_query():
    return (
        select(Permission)
        .options(selectinload(Permission.content_type))
        .join(ContentType, Permission.content_type_id == ContentType.id)
        .where(ContentType.app_label.not_in(["admin", "contenttypes", "sessions"]))
        .order_by(ContentType.app_label.asc(), Permission.codename.asc(), Permission.id.asc())
    )


def _content_type_query():
    return (
        select(ContentType)
        .where(ContentType.app_label.not_in(["admin", "contenttypes", "sessions"]))
        .order_by(ContentType.app_label.asc(), ContentType.model.asc(), ContentType.id.asc())
    )


def _has_permission(user: User, perm: str) -> bool:
    if user.is_superuser:
        return True
    app_label, codename = perm.split(".", 1)
    if any(p.content_type and p.content_type.app_label == app_label and p.codename == codename for p in user.direct_permissions):
        return True
    return any(
        p.content_type and p.content_type.app_label == app_label and p.codename == codename
        for group in user.groups
        for p in group.permissions
    )


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_staff": bool(user.is_staff),
        "is_active": bool(user.is_active),
        "groups": [group.name for group in user.groups],
    }


def _serialize_group(group: Group) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "users": [user.username for user in group.users],
    }


def _serialize_content_type(item: ContentType) -> dict:
    app_label = item.app_label
    model = item.model
    app_label_cn = APP_LABEL_LABELS.get(app_label, app_label)
    return {
        "id": item.id,
        "app_label": app_label,
        "app_label_cn": app_label_cn,
        "app_label_sort": APP_LABEL_SORT.get(app_label, 99),
        "app_label_subcategory": app_label_cn,
        "app_label_subcategory_sort": 0,
        "model": model,
        "model_cn": MODEL_LABELS.get(model.lower(), model),
        "model_verbose": MODEL_LABELS.get(model.lower(), model),
    }


def _permission_name_cn(permission: Permission) -> str:
    codename = permission.codename or ""
    if "_" in codename:
        action, model = codename.split("_", 1)
        if action in ACTION_LABELS:
            return f"{ACTION_LABELS[action]}{MODEL_LABELS.get(model.lower(), model)}"
    return permission.name


def _serialize_permission(permission: Permission) -> dict:
    return {
        "id": permission.id,
        "name": permission.name,
        "name_cn": _permission_name_cn(permission),
        "codename": permission.codename,
        "content_type": _serialize_content_type(permission.content_type),
    }


def _get_user(db: Session, user_id: int) -> User:
    user = db.scalar(_user_query(db).where(User.id == user_id))
    if not user:
        raise AppError("User not found", status_code=404)
    return user


def _get_group(db: Session, group_id: int) -> Group:
    group = db.scalar(_group_query(db).where(Group.id == group_id))
    if not group:
        raise AppError("Group not found", status_code=404)
    return group


def _get_permission(db: Session, permission_id: int) -> Permission:
    permission = db.scalar(_permission_query().where(Permission.id == permission_id))
    if not permission:
        raise AppError("Permission not found", status_code=404)
    return permission


def _get_content_type(db: Session, content_type_id: int) -> ContentType:
    item = db.scalar(_content_type_query().where(ContentType.id == content_type_id))
    if not item:
        raise AppError("Content type not found", status_code=404)
    return item


def _ensure_can_view_user(actor: User, target: User) -> None:
    if actor.id == target.id or actor.is_superuser or _has_permission(actor, "auth.view_user"):
        return
    raise AppError("You can only view your own user information", status_code=403)


def _ensure_can_change_user(actor: User, target: User, payload: dict | None = None) -> None:
    payload = payload or {}
    if actor.id == target.id:
        sensitive_fields = {"is_staff", "is_superuser", "is_active", "groups", "user_permissions"}
        if any(field in payload for field in sensitive_fields):
            raise AppError("You do not have permission to update this user", status_code=403)
        return
    if actor.is_superuser or _has_permission(actor, "auth.change_user"):
        return
    raise AppError("You do not have permission to update this user", status_code=403)


def _ensure_can_delete_user(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise AppError("You do not have permission to delete this user", status_code=403)
    if actor.is_superuser or _has_permission(actor, "auth.delete_user"):
        return
    raise AppError("You do not have permission to delete this user", status_code=403)


def register_user(db: Session, payload: dict) -> dict:
    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    if not username:
        raise AppError("Username is required", status_code=400, errors={"username": ["This field is required."]})
    if not email:
        raise AppError("Email is required", status_code=400, errors={"email": ["This field is required."]})
    if not password:
        raise AppError("Password is required", status_code=400, errors={"password": ["This field is required."]})
    if db.scalar(select(User).where(User.username == username)):
        raise AppError("A user with that username already exists.", status_code=400, errors={"username": ["A user with that username already exists."]})

    user = User(
        username=username,
        email=email,
        password=make_password_with_django(password),
        first_name=str(payload.get("first_name") or ""),
        last_name=str(payload.get("last_name") or ""),
        is_staff=bool(payload.get("is_staff", False)),
        is_active=bool(payload.get("is_active", True)),
        is_superuser=False,
        date_joined=datetime.now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user = _get_user(db, user.id)
    return _serialize_user(user)


def get_current_user_detail(*, db: Session, user: User) -> dict:
    return _serialize_user(_get_user(db, user.id))


def list_users(*, db: Session, search: str | None = None) -> list[dict]:
    stmt = _user_query(db).order_by(User.id.asc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(like),
                User.email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
            )
        )
    return [_serialize_user(item) for item in db.scalars(stmt).all()]


def get_user_detail(*, db: Session, actor: User, target_user_id: int) -> dict:
    target = _get_user(db, target_user_id)
    _ensure_can_view_user(actor, target)
    return _serialize_user(target)


def create_user_admin(*, db: Session, payload: dict) -> dict:
    return register_user(db, payload)


def update_user_detail(*, db: Session, actor: User, target_user_id: int, payload: dict) -> dict:
    target = _get_user(db, target_user_id)
    _ensure_can_change_user(actor, target, payload)

    for field in ("username", "email", "first_name", "last_name"):
        if field in payload and payload.get(field) is not None:
            setattr(target, field, str(payload.get(field) or ""))
    if "password" in payload and payload.get("password"):
        target.password = make_password_with_django(str(payload["password"]))
    if "is_staff" in payload and payload.get("is_staff") is not None and actor.id != target.id:
        target.is_staff = bool(payload["is_staff"])
    if "is_active" in payload and payload.get("is_active") is not None and actor.id != target.id:
        target.is_active = bool(payload["is_active"])
    if "groups" in payload and payload.get("groups") is not None and actor.id != target.id:
        group_ids = list(payload.get("groups") or [])
        target.groups = list(db.scalars(select(Group).where(Group.id.in_(group_ids))).all()) if group_ids else []
    db.add(target)
    db.commit()
    return _serialize_user(_get_user(db, target.id))


def delete_user_detail(*, db: Session, actor: User, target_user_id: int) -> None:
    target = _get_user(db, target_user_id)
    _ensure_can_delete_user(actor, target)
    target.groups = []
    target.direct_permissions = []
    db.delete(target)
    db.commit()


def list_groups(*, db: Session, search: str | None = None) -> list[dict]:
    stmt = _group_query(db).order_by(Group.name.asc())
    if search:
        stmt = stmt.where(Group.name.ilike(f"%{search}%"))
    return [_serialize_group(item) for item in db.scalars(stmt).all()]


def get_group_detail(*, db: Session, group_id: int) -> dict:
    return _serialize_group(_get_group(db, group_id))


def create_group(*, db: Session, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("Group name is required", status_code=400)
    if db.scalar(select(Group).where(Group.name == name)):
        raise AppError("Group already exists", status_code=400)
    group = Group(name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _serialize_group(_get_group(db, group.id))


def update_group(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise AppError("Group name is required", status_code=400)
        existing = db.scalar(select(Group).where(Group.name == name, Group.id != group_id))
        if existing:
            raise AppError("Group name already exists", status_code=400)
        group.name = name
    db.add(group)
    db.commit()
    return _serialize_group(_get_group(db, group.id))


def delete_group(*, db: Session, group_id: int) -> None:
    group = _get_group(db, group_id)
    group.users = []
    group.permissions = []
    db.delete(group)
    db.commit()


def list_group_users(*, db: Session, group_id: int) -> list[dict]:
    return [_serialize_user(user) for user in _get_group(db, group_id).users]


def group_add_users(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    user_ids = list(payload.get("user_ids") or [])
    users = list(db.scalars(_user_query(db).where(User.id.in_(user_ids))).all()) if user_ids else []
    for user in users:
        if user not in group.users:
            group.users.append(user)
    db.add(group)
    db.commit()
    return {"status": "success", "message": f"{len(users)} users added to group {group.name}."}


def group_remove_users(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    user_ids = set(payload.get("user_ids") or [])
    group.users = [user for user in group.users if user.id not in user_ids]
    db.add(group)
    db.commit()
    return {"status": "success", "message": f"{len(user_ids)} users removed from group {group.name}."}


def group_permissions(*, db: Session, group_id: int) -> list[dict]:
    return [_serialize_permission(permission) for permission in _get_group(db, group_id).permissions]


def batch_assign_group_permissions(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    permission_ids = list(payload.get("permission_ids") or [])
    permissions = list(db.scalars(_permission_query().where(Permission.id.in_(permission_ids))).all()) if permission_ids else []
    for permission in permissions:
        if permission not in group.permissions:
            group.permissions.append(permission)
    db.add(group)
    db.commit()
    return {
        "status": "success",
        "message": f"Assigned {len(permissions)} permissions to group {group.name}.",
        "assigned_permissions": [{"id": p.id, "name": p.name, "codename": p.codename} for p in permissions],
    }


def batch_remove_group_permissions(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    permission_ids = set(payload.get("permission_ids") or [])
    removed = [p for p in group.permissions if p.id in permission_ids]
    group.permissions = [p for p in group.permissions if p.id not in permission_ids]
    db.add(group)
    db.commit()
    return {
        "status": "success",
        "message": f"Removed {len(removed)} permissions from group {group.name}.",
        "removed_permissions": [{"id": p.id, "name": p.name, "codename": p.codename} for p in removed],
    }


def update_group_permissions(*, db: Session, group_id: int, payload: dict) -> dict:
    group = _get_group(db, group_id)
    old_permissions = list(group.permissions)
    permission_ids = list(payload.get("permission_ids") or [])
    new_permissions = list(db.scalars(_permission_query().where(Permission.id.in_(permission_ids))).all()) if permission_ids else []
    group.permissions = new_permissions
    db.add(group)
    db.commit()
    old_ids = {p.id for p in old_permissions}
    new_ids = {p.id for p in new_permissions}
    return {
        "status": "success",
        "message": f"Updated permissions for group {group.name}.",
        "group_id": group.id,
        "group_name": group.name,
        "changes": {
            "added_count": len(new_ids - old_ids),
            "removed_count": len(old_ids - new_ids),
            "total_permissions": len(new_ids),
        },
        "permissions": {
            "before": [{"id": p.id, "name": p.name, "codename": p.codename} for p in old_permissions],
            "after": [{"id": p.id, "name": p.name, "codename": p.codename} for p in new_permissions],
        },
    }


def assign_permission_to_user(*, db: Session, actor: User, permission_id: int, payload: dict) -> dict:
    target = _get_user(db, int(payload.get("user_id") or 0))
    permission = _get_permission(db, permission_id)
    if actor.id == target.id:
        raise AppError("You cannot modify your own permissions.", status_code=403)
    if not (actor.is_superuser or _has_permission(actor, "auth.change_permission")):
        raise AppError("You do not have permission to modify user permissions.", status_code=403)
    if permission not in target.direct_permissions:
        target.direct_permissions.append(permission)
    db.add(target)
    db.commit()
    return {"status": "success", "message": f"Permission {permission.codename} assigned to user {target.username}."}


def remove_permission_from_user(*, db: Session, actor: User, permission_id: int, payload: dict) -> dict:
    target = _get_user(db, int(payload.get("user_id") or 0))
    permission = _get_permission(db, permission_id)
    if actor.id == target.id:
        raise AppError("You cannot modify your own permissions.", status_code=403)
    if not (actor.is_superuser or _has_permission(actor, "auth.change_permission")):
        raise AppError("You do not have permission to modify user permissions.", status_code=403)
    target.direct_permissions = [p for p in target.direct_permissions if p.id != permission.id]
    db.add(target)
    db.commit()
    return {"status": "success", "message": f"Permission {permission.codename} removed from user {target.username}."}


def assign_permission_to_group(*, db: Session, permission_id: int, payload: dict) -> dict:
    group = _get_group(db, int(payload.get("group_id") or 0))
    permission = _get_permission(db, permission_id)
    if permission not in group.permissions:
        group.permissions.append(permission)
    db.add(group)
    db.commit()
    return {"status": "success", "message": f"Permission {permission.codename} assigned to group {group.name}."}


def remove_permission_from_group(*, db: Session, permission_id: int, payload: dict) -> dict:
    group = _get_group(db, int(payload.get("group_id") or 0))
    permission = _get_permission(db, permission_id)
    group.permissions = [p for p in group.permissions if p.id != permission.id]
    db.add(group)
    db.commit()
    return {"status": "success", "message": f"Permission {permission.codename} removed from group {group.name}."}


def list_content_types(*, db: Session, app_label: str | None = None, search: str | None = None) -> list[dict]:
    stmt = _content_type_query()
    if app_label:
        stmt = stmt.where(ContentType.app_label == app_label)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(ContentType.app_label.ilike(like), ContentType.model.ilike(like)))
    return [_serialize_content_type(item) for item in db.scalars(stmt).all()]


def get_content_type_detail(*, db: Session, content_type_id: int) -> dict:
    return _serialize_content_type(_get_content_type(db, content_type_id))


def list_permissions(*, db: Session, content_type: int | None = None, app_label: str | None = None, search: str | None = None) -> list[dict]:
    stmt = _permission_query()
    if content_type:
        stmt = stmt.where(Permission.content_type_id == content_type)
    if app_label:
        stmt = stmt.where(ContentType.app_label == app_label)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Permission.name.ilike(like), Permission.codename.ilike(like)))
    return [_serialize_permission(item) for item in db.scalars(stmt).all()]


def get_permission_detail(*, db: Session, permission_id: int) -> dict:
    return _serialize_permission(_get_permission(db, permission_id))


def user_permissions(*, db: Session, actor: User, target_user_id: int) -> list[dict]:
    target = _get_user(db, target_user_id)
    _ensure_can_view_user(actor, target)
    permissions = {p.id: p for p in target.direct_permissions}
    for group in target.groups:
        for permission in group.permissions:
            permissions[permission.id] = permission
    return [_serialize_permission(permission) for permission in permissions.values()]


def batch_assign_user_permissions(*, db: Session, actor: User, target_user_id: int, payload: dict) -> dict:
    target = _get_user(db, target_user_id)
    if actor.id == target.id:
        raise AppError("You cannot modify your own permissions.", status_code=403)
    if not (actor.is_superuser or _has_permission(actor, "auth.change_permission")):
        raise AppError("You do not have permission to modify user permissions.", status_code=403)
    permission_ids = list(payload.get("permission_ids") or [])
    permissions = list(db.scalars(_permission_query().where(Permission.id.in_(permission_ids))).all()) if permission_ids else []
    for permission in permissions:
        if permission not in target.direct_permissions:
            target.direct_permissions.append(permission)
    db.add(target)
    db.commit()
    return {
        "status": "success",
        "message": f"Assigned {len(permissions)} permissions to user {target.username}.",
        "assigned_permissions": [{"id": p.id, "name": p.name, "codename": p.codename} for p in permissions],
    }


def batch_remove_user_permissions(*, db: Session, actor: User, target_user_id: int, payload: dict) -> dict:
    target = _get_user(db, target_user_id)
    if actor.id == target.id:
        raise AppError("You cannot modify your own permissions.", status_code=403)
    if not (actor.is_superuser or _has_permission(actor, "auth.change_permission")):
        raise AppError("You do not have permission to modify user permissions.", status_code=403)
    permission_ids = set(payload.get("permission_ids") or [])
    removed = [p for p in target.direct_permissions if p.id in permission_ids]
    target.direct_permissions = [p for p in target.direct_permissions if p.id not in permission_ids]
    db.add(target)
    db.commit()
    return {
        "status": "success",
        "message": f"Removed {len(removed)} permissions from user {target.username}.",
        "removed_permissions": [{"id": p.id, "name": p.name, "codename": p.codename} for p in removed],
    }


def update_user_permissions(*, db: Session, actor: User, target_user_id: int, payload: dict) -> dict:
    target = _get_user(db, target_user_id)
    if actor.id == target.id:
        raise AppError("You cannot modify your own permissions.", status_code=403)
    if not (actor.is_superuser or _has_permission(actor, "auth.change_permission")):
        raise AppError("You do not have permission to modify user permissions.", status_code=403)
    old_permissions = list(target.direct_permissions)
    permission_ids = list(payload.get("permission_ids") or [])
    new_permissions = list(db.scalars(_permission_query().where(Permission.id.in_(permission_ids))).all()) if permission_ids else []
    target.direct_permissions = new_permissions
    db.add(target)
    db.commit()
    old_ids = {p.id for p in old_permissions}
    new_ids = {p.id for p in new_permissions}
    return {
        "status": "success",
        "message": f"Updated permissions for user {target.username}.",
        "user_id": target.id,
        "username": target.username,
        "changes": {
            "added_count": len(new_ids - old_ids),
            "removed_count": len(old_ids - new_ids),
            "total_permissions": len(new_ids),
        },
        "permissions": {
            "before": [{"id": p.id, "name": p.name, "codename": p.codename} for p in old_permissions],
            "after": [{"id": p.id, "name": p.name, "codename": p.codename} for p in new_permissions],
        },
    }

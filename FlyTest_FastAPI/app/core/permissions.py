def has_project_access(*, user_id: int | None, project_id: int | None) -> bool:
    if user_id is None or project_id is None:
        return False
    return True

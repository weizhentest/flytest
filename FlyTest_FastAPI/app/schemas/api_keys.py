from pydantic import BaseModel


class APIKeyPublic(BaseModel):
    id: int
    name: str
    key: str
    user: str
    created_at: str
    expires_at: str | None = None
    is_active: bool


class APIKeyCreatePayload(BaseModel):
    name: str
    expires_at: str | None = None
    is_active: bool = True


class APIKeyUpdatePayload(BaseModel):
    name: str | None = None
    expires_at: str | None = None
    is_active: bool | None = None

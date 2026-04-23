from pydantic import BaseModel, Field


class TokenObtainRequest(BaseModel):
    username: str
    password: str


class TokenRefreshRequest(BaseModel):
    refresh: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""
    is_staff: bool
    is_active: bool
    groups: list[str] = Field(default_factory=list)


class TokenPairPayload(BaseModel):
    refresh: str
    access: str
    user: UserPublic

from pydantic import BaseModel, Field


class UserDetailSchema(BaseModel):
    id: int
    username: str
    email: str = ""


class ProjectCredentialSchema(BaseModel):
    id: int | None = None
    system_url: str = ""
    username: str = ""
    password: str | None = None
    user_role: str = ""
    created_at: str | None = None


class ProjectMemberSchema(BaseModel):
    id: int
    user: int
    user_detail: UserDetailSchema
    role: str
    joined_at: str


class ProjectSchema(BaseModel):
    id: int
    name: str
    description: str
    creator: int | None = None
    creator_detail: UserDetailSchema | None = None
    created_at: str
    updated_at: str
    credentials: list[ProjectCredentialSchema] = Field(default_factory=list)
    members: list[ProjectMemberSchema] = Field(default_factory=list)


class ProjectCreatePayload(BaseModel):
    name: str
    description: str = ""
    credentials: list[ProjectCredentialSchema] = Field(default_factory=list)


class ProjectUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    credentials: list[ProjectCredentialSchema] | None = None


class ProjectMemberCreatePayload(BaseModel):
    user_id: int
    role: str = "member"


class ProjectMemberRolePayload(BaseModel):
    user_id: int
    role: str


class ProjectMemberRemovePayload(BaseModel):
    user_id: int

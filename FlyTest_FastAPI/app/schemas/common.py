from pydantic import BaseModel


class HealthPayload(BaseModel):
    ok: bool
    app_name: str
    environment: str
    version: str

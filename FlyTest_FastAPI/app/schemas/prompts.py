from typing import Literal

from pydantic import BaseModel, Field


PromptTypeValue = Literal[
    "general",
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
]


class PromptTypeItem(BaseModel):
    value: str
    label: str
    is_program_call: bool


class PromptListItem(BaseModel):
    id: int
    name: str
    description: str | None = None
    prompt_type: str
    prompt_type_display: str
    is_default: bool
    is_active: bool
    created_at: str
    updated_at: str


class PromptDetail(PromptListItem):
    content: str
    is_requirement_type: bool


class PromptListPayload(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: list[PromptListItem]


class PromptCreatePayload(BaseModel):
    name: str
    content: str
    description: str | None = None
    prompt_type: str = "general"
    is_default: bool = False
    is_active: bool = True


class PromptUpdatePayload(BaseModel):
    name: str | None = None
    content: str | None = None
    description: str | None = None
    prompt_type: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class PromptInitPayload(BaseModel):
    force_update: bool = False

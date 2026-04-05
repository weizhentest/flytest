from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeviceConnectPayload(BaseModel):
    ip_address: str = Field(..., min_length=1)
    port: int = Field(default=5555, ge=1, le=65535)


class DeviceUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    location: str | None = None
    status: str | None = None


class PackagePayload(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=100)
    package_name: str = Field(..., min_length=1, max_length=255)
    activity_name: str = Field(default="", max_length=255)
    platform: str = Field(default="android", max_length=32)
    description: str = Field(default="", max_length=2000)


class ElementPayload(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=120)
    element_type: str = Field(..., min_length=1, max_length=32)
    selector_type: str = Field(default="", max_length=40)
    selector_value: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    image_path: str = Field(default="", max_length=500)
    is_active: bool = True


class ImageCategoryPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class TestCasePayload(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    package_id: int | None = None
    ui_flow: dict[str, Any] = Field(default_factory=dict)
    variables: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    timeout: int = Field(default=300, ge=1, le=7200)
    retry_count: int = Field(default=0, ge=0, le=10)


class ExecuteTestCasePayload(BaseModel):
    device_id: int
    trigger_mode: str = Field(default="manual", max_length=32)
    triggered_by: str = Field(default="FlyTest", max_length=64)


class SettingsPayload(BaseModel):
    adb_path: str = Field(default="adb", min_length=1, max_length=500)
    default_timeout: int = Field(default=300, ge=1, le=7200)
    workspace_root: str = Field(default="", max_length=500)
    auto_discover_on_open: bool = True
    notes: str = Field(default="", max_length=2000)


class ComponentPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    category: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=2000)
    schema_definition: dict[str, Any] = Field(default_factory=dict, alias="schema")
    default_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    sort_order: int = 0


class CustomComponentPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=2000)
    schema_definition: dict[str, Any] = Field(default_factory=dict, alias="schema")
    default_config: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    sort_order: int = 0


class ComponentPackagePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    version: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=2000)
    author: str = Field(default="", max_length=100)
    source: str = Field(default="upload", max_length=20)
    manifest: dict[str, Any] = Field(default_factory=dict)


class TestSuitePayload(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    test_case_ids: list[int] = Field(default_factory=list)


class TestSuiteRunPayload(BaseModel):
    device_id: int
    package_name: str = Field(default="", max_length=255)
    triggered_by: str = Field(default="FlyTest", max_length=64)


class ScheduledTaskPayload(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    task_type: str = Field(..., min_length=1, max_length=20)
    trigger_type: str = Field(..., min_length=1, max_length=20)
    cron_expression: str = Field(default="", max_length=100)
    interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    execute_at: str | None = None
    device_id: int | None = None
    package_id: int | None = None
    test_suite_id: int | None = None
    test_case_id: int | None = None
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notification_type: str = Field(default="", max_length=20)
    notify_emails: list[str] = Field(default_factory=list)
    status: str = Field(default="ACTIVE", max_length=20)
    created_by: str = Field(default="FlyTest", max_length=64)

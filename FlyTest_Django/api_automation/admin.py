from django.contrib import admin

from .models import (
    ApiCollection,
    ApiEnvironment,
    ApiExecutionRecord,
    ApiRequest,
    ApiTestCase,
)


@admin.register(ApiCollection)
class ApiCollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "parent", "order", "creator", "created_at")
    list_filter = ("project",)
    search_fields = ("name",)


@admin.register(ApiRequest)
class ApiRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "collection", "method", "url", "timeout_ms", "created_by", "updated_at")
    list_filter = ("method", "body_type", "collection__project")
    search_fields = ("name", "url")


@admin.register(ApiEnvironment)
class ApiEnvironmentAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "base_url", "is_default", "timeout_ms", "creator", "updated_at")
    list_filter = ("project", "is_default")
    search_fields = ("name", "base_url")


@admin.register(ApiExecutionRecord)
class ApiExecutionRecordAdmin(admin.ModelAdmin):
    list_display = ("request_name", "project", "status", "status_code", "passed", "executor", "created_at")
    list_filter = ("project", "status", "passed")
    search_fields = ("request_name", "url", "error_message")


@admin.register(ApiTestCase)
class ApiTestCaseAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "request", "status", "creator", "updated_at")
    list_filter = ("project", "status")
    search_fields = ("name", "description")

from django.contrib import admin

from .models import DataFactoryRecord, DataFactoryTag


@admin.register(DataFactoryTag)
class DataFactoryTagAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "project", "creator", "created_at")
    search_fields = ("name", "code", "description")
    list_filter = ("project",)


@admin.register(DataFactoryRecord)
class DataFactoryRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tool_name",
        "tool_category",
        "tool_scenario",
        "project",
        "creator",
        "is_saved",
        "created_at",
    )
    search_fields = ("tool_name",)
    list_filter = ("project", "tool_category", "tool_scenario", "is_saved")
    filter_horizontal = ("tags",)

# Register your models here.

from django.contrib import admin

from .models import Project, ProjectDeletionRequest, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'creator', 'is_deleted', 'deleted_at', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'creator__username')
    list_filter = ('is_deleted', 'created_at', 'updated_at')
    inlines = [ProjectMemberInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'role', 'joined_at')
    list_filter = ('role', 'joined_at', 'project')
    search_fields = ('user__username', 'project__name')


@admin.register(ProjectDeletionRequest)
class ProjectDeletionRequestAdmin(admin.ModelAdmin):
    list_display = (
        'project_display_id',
        'project_name',
        'status',
        'requested_by_name',
        'reviewed_by_name',
        'deleted_at',
        'restored_at',
    )
    list_filter = ('status', 'requested_at', 'deleted_at', 'restored_at')
    search_fields = ('project_name', 'requested_by_name', 'reviewed_by_name', 'restored_by_name')

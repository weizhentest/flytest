# 导入 Django Admin 注册入口。
from django.contrib import admin

# 导入项目模型与项目成员模型。
from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    # 在项目后台页内联维护成员关系。
    model = ProjectMember
    # 默认展示 1 行空白输入，便于快速新增成员。
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',  # 项目名称。
        'creator',  # 创建人。
        'created_at',  # 创建时间。
        'updated_at',  # 更新时间。
    )
    search_fields = (
        'name',  # 按项目名称搜索。
        'description',  # 按描述搜索。
        'creator__username',  # 按创建人用户名搜索。
    )
    list_filter = (
        'created_at',  # 按创建时间筛选。
        'updated_at',  # 按更新时间筛选。
    )
    inlines = [ProjectMemberInline]  # 在项目页联动展示成员。


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = (
        'user',  # 成员用户。
        'project',  # 所属项目。
        'role',  # 项目角色。
        'joined_at',  # 加入时间。
    )
    list_filter = (
        'role',  # 按角色筛选。
        'joined_at',  # 按加入时间筛选。
        'project',  # 按项目筛选。
    )
    search_fields = (
        'user__username',  # 按用户名搜索。
        'project__name',  # 按项目名搜索。
    )

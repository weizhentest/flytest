# 导入 Django 管理命令基类。
from django.core.management.base import BaseCommand

# 导入权限模型。
from django.contrib.auth.models import Permission

# 导入项目成员模型。
from projects.models import ProjectMember


class Command(BaseCommand):
    help = '为所有项目成员分配必要的Django模型权限'

    def add_arguments(self, parser):
        # 预览模式仅输出变更，不真正写入数据库。
        parser.add_argument('--dry-run', action='store_true', help='只显示将要执行的操作，不实际执行')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # 预先加载项目模块四类模型权限，缺失则直接终止修复。
        try:
            view_perm = Permission.objects.get(codename='view_project', content_type__app_label='projects')
            add_perm = Permission.objects.get(codename='add_project', content_type__app_label='projects')
            change_perm = Permission.objects.get(codename='change_project', content_type__app_label='projects')
            delete_perm = Permission.objects.get(codename='delete_project', content_type__app_label='projects')
        except Permission.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'权限不存在: {e}'))
            return

        # 扫描全部项目成员，按其角色补齐应有权限。
        members = ProjectMember.objects.select_related('user').all()
        
        self.stdout.write(f"找到 {members.count()} 个项目成员")
        
        updated_count = 0
        
        for member in members:
            user = member.user
            
            # 跳过超级用户（他们已经有所有权限）
            if user.is_superuser:
                continue
                
            permissions_to_add = []
            
            # 所有项目成员至少应具备项目查看权限。
            if not user.has_perm('projects.view_project'):
                permissions_to_add.append(view_perm)
            
            # admin/owner 补齐新增和修改权限。
            if member.role in ['owner', 'admin']:
                if not user.has_perm('projects.add_project'):
                    permissions_to_add.append(add_perm)
                if not user.has_perm('projects.change_project'):
                    permissions_to_add.append(change_perm)
                    
            # owner 额外补齐删除权限。
            if member.role == 'owner':
                if not user.has_perm('projects.delete_project'):
                    permissions_to_add.append(delete_perm)
            
            if permissions_to_add:
                if dry_run:
                    # 预览模式仅打印将变更的权限，不执行写入。
                    perm_names = [p.codename for p in permissions_to_add]
                    self.stdout.write(f"将为用户 {user.username} ({member.role}) 添加权限: {perm_names}")
                else:
                    # 正式模式执行权限写入。
                    user.user_permissions.add(*permissions_to_add)
                    perm_names = [p.codename for p in permissions_to_add]
                    self.stdout.write(f"已为用户 {user.username} ({member.role}) 添加权限: {perm_names}")
                updated_count += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"预览模式：将更新 {updated_count} 个用户的权限"))
            self.stdout.write("使用 --dry-run=False 来实际执行操作")
        else:
            self.stdout.write(self.style.SUCCESS(f"成功更新了 {updated_count} 个用户的权限"))

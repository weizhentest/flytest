# 导入 Django 管理命令基类。
from django.core.management.base import BaseCommand

# 导入用户与权限模型。
from django.contrib.auth.models import User, Permission

# 导入项目与成员模型。
from projects.models import Project, ProjectMember


class Command(BaseCommand):
    help = '检查项目权限配置'

    def add_arguments(self, parser):
        # 可选按项目过滤检查范围。
        parser.add_argument('--project-id', type=int, help='项目ID')
        # 可选按用户过滤检查范围。
        parser.add_argument('--user-id', type=int, help='用户ID')

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        user_id = options.get('user_id')

        self.stdout.write("=== 项目权限检查 ===")

        # 条件：传入 project_id；动作：输出项目与成员信息；结果：快速确认成员关系是否正确。
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                self.stdout.write(f"项目 {project_id}: {project.name}")
                
                # 检查项目成员
                members = ProjectMember.objects.filter(project=project)
                self.stdout.write(f"项目成员数量: {members.count()}")
                for member in members:
                    self.stdout.write(f"  - {member.user.username} ({member.role})")
                    
            except Project.DoesNotExist:
                self.stdout.write(f"项目 {project_id} 不存在")
                return

        # 条件：传入 user_id；动作：输出用户权限与成员关系；结果：定位单用户权限异常。
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f"用户 {user_id}: {user.username}")
                self.stdout.write(f"是否为超级用户: {user.is_superuser}")
                
                # 检查核心模型权限是否存在且用户是否具备。
                try:
                    view_perm = Permission.objects.get(codename='view_project', content_type__app_label='projects')
                    has_view_perm = user.has_perm('projects.view_project')
                    self.stdout.write(f"是否有view_project权限: {has_view_perm}")
                except Permission.DoesNotExist:
                    self.stdout.write("view_project权限不存在")
                
                # 若同时传入项目 ID，则补充检查该用户在该项目中的成员角色。
                if project_id:
                    try:
                        project = Project.objects.get(id=project_id)
                        is_member = ProjectMember.objects.filter(project=project, user=user).exists()
                        self.stdout.write(f"是否为项目成员: {is_member}")
                        if is_member:
                            member = ProjectMember.objects.get(project=project, user=user)
                            self.stdout.write(f"项目角色: {member.role}")
                    except Project.DoesNotExist:
                        pass
                        
            except User.DoesNotExist:
                self.stdout.write(f"用户 {user_id} 不存在")
                return

        # 输出全量用户权限概览，便于批量排查配置偏差。
        self.stdout.write("\n=== 所有用户权限概览 ===")
        users = User.objects.all()
        for user in users:
            has_view_perm = user.has_perm('projects.view_project')
            self.stdout.write(f"{user.username}: 超级用户={user.is_superuser}, view_project权限={has_view_perm}")

        # 检查权限对象本身是否存在，并列出直接授权用户。
        self.stdout.write("\n=== 权限对象检查 ===")
        try:
            view_perm = Permission.objects.get(codename='view_project', content_type__app_label='projects')
            self.stdout.write(f"view_project权限存在: {view_perm}")
            
            # 检查哪些用户直接拥有这个权限
            users_with_perm = User.objects.filter(user_permissions=view_perm)
            self.stdout.write(f"直接拥有view_project权限的用户: {[u.username for u in users_with_perm]}")
            
        except Permission.DoesNotExist:
            self.stdout.write("view_project权限不存在")

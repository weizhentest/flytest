"""
预置 Skills 自动初始化命令

每次部署时自动将 bundled_skills 目录中的 Skill 同步到系统。
- 新 Skill：创建数据库记录并复制文件
- 已有 Skill：更新内容和文件（保留用户的 is_active 设置）
"""

import os
import shutil
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

EXCLUDE_PATTERNS = {
    '.venv', 'venv', '__pycache__', 'node_modules', '.git',
    '.mypy_cache', '.pytest_cache', '.DS_Store', 'Thumbs.db',
}


def _sync_files(src_dir: str, dst_dir: str):
    """将源目录文件同步到目标目录（覆盖更新，不删除目标中的运行时产物）"""
    os.makedirs(dst_dir, exist_ok=True)

    for item in os.listdir(src_dir):
        # 跳过虚拟环境、缓存和依赖目录，避免把运行时垃圾同步进媒体目录。
        if item in EXCLUDE_PATTERNS:
            continue
        src = os.path.join(src_dir, item)
        dst = os.path.join(dst_dir, item)
        if os.path.isdir(src):
            shutil.copytree(
                src, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS),
            )
        else:
            shutil.copy2(src, dst)


class Command(BaseCommand):
    help = '从 bundled_skills 目录同步预置 Skills（新增或更新）'

    def add_arguments(self, parser):
        # 支持通过参数或环境变量指定预置 Skills 目录。
        parser.add_argument(
            '--skills-dir',
            default=os.environ.get('BUNDLED_SKILLS_DIR', '/app/bundled_skills'),
            help='预置 Skills 目录路径（默认 /app/bundled_skills）',
        )

    def handle(self, *args, **options):
        skills_dir = options['skills_dir']

        # 条件：目录不存在；动作：告警并退出；结果：部署环境可无 bundled_skills 也不中断启动流程。
        if not os.path.isdir(skills_dir):
            self.stdout.write(self.style.WARNING(
                f'预置 Skills 目录不存在: {skills_dir}，跳过初始化'
            ))
            return

        from skills.models import Skill
        from projects.models import Project

        admin_user = User.objects.filter(is_superuser=True).order_by('id').first()
        # 条件：无管理员用户；动作：跳过导入；结果：避免创建“无归属”Skill 记录。
        if not admin_user:
            self.stdout.write(self.style.WARNING('未找到管理员用户，跳过 Skills 初始化'))
            return

        project = Project.objects.order_by('id').first()
        # 条件：系统尚无项目；动作：创建默认项目；结果：预置 Skill 有合法项目归属。
        if not project:
            project = Project.objects.create(
                name='默认项目',
                description='系统自动创建的默认项目',
                owner=admin_user,
            )
            self.stdout.write(self.style.SUCCESS(f'创建默认项目: {project.name}'))

        created_count = 0
        updated_count = 0

        for entry in sorted(os.listdir(skills_dir)):
            entry_path = os.path.join(skills_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            skill_md_path = os.path.join(entry_path, 'SKILL.md')
            if not os.path.exists(skill_md_path):
                self.stdout.write(self.style.WARNING(f'  跳过 {entry}（无 SKILL.md）'))
                continue

            try:
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    skill_content = f.read()

                parsed = Skill.parse_skill_md(skill_content)
                skill_name = parsed['name']

                existing = Skill.objects.filter(name=skill_name).first()

                if existing:
                    # 条件：Skill 已存在；动作：更新内容和文件；结果：保留 is_active 等用户运行态配置。
                    existing.description = parsed['description']
                    existing.skill_content = skill_content
                    existing.save(update_fields=['description', 'skill_content', 'updated_at'])

                    full_path = existing.get_full_path()
                    if full_path:
                        _sync_files(entry_path, full_path)

                    self.stdout.write(f'  更新 {skill_name}')
                    updated_count += 1
                else:
                    # 条件：Skill 不存在；动作：创建记录并同步文件；结果：新增预置 Skill 生效。
                    skill = Skill.objects.create(
                        project=project,
                        creator=admin_user,
                        name=skill_name,
                        description=parsed['description'],
                        skill_content=skill_content,
                        is_active=True,
                    )

                    storage_path = f'skills/{project.id}/{skill.id}'
                    full_path = os.path.join(settings.MEDIA_ROOT, storage_path)
                    _sync_files(entry_path, full_path)

                    skill.skill_path = storage_path
                    skill.save(update_fields=['skill_path'])

                    self.stdout.write(self.style.SUCCESS(f'  导入 {skill_name}'))
                    created_count += 1

            except Exception as e:
                # 单个 Skill 导入失败不影响后续条目，记录异常后继续处理。
                self.stdout.write(self.style.ERROR(f'  {entry} 失败: {e}'))
                logger.exception('同步 Skill %s 失败', entry)

        self.stdout.write(self.style.SUCCESS(
            f'Skills 同步完成: 新增 {created_count}，更新 {updated_count}'
        ))

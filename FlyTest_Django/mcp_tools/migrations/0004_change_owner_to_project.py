from django.db import migrations, models
import django.db.models.deletion


def migrate_owner_to_project(apps, schema_editor):
    """
    将现有 MCP 配置的 owner 迁移到 project。
    如果 owner 有所属项目，则使用第一个项目；否则删除该配置。
    """
    RemoteMCPConfig = apps.get_model('mcp_tools', 'RemoteMCPConfig')
    ProjectMember = apps.get_model('projects', 'ProjectMember')

    for config in RemoteMCPConfig.objects.all():
        # 查找 owner 所属的第一个项目
        membership = ProjectMember.objects.filter(user=config.owner).first()
        if membership:
            config.project = membership.project
            config.save()
        else:
            # 没有所属项目，删除该配置
            config.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mcp_tools', '0003_alter_remotemcpconfig_url'),
        ('projects', '0001_initial'),
    ]

    operations = [
        # 1. 添加 project 字段（暂时可空）
        migrations.AddField(
            model_name='remotemcpconfig',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='remote_mcp_configs',
                to='projects.project',
                help_text='此远程 MCP 配置所属的项目'
            ),
        ),
        # 2. 数据迁移：将 owner 映射到 project
        migrations.RunPython(migrate_owner_to_project, migrations.RunPython.noop),
        # 3. 移除 owner 字段
        migrations.RemoveField(
            model_name='remotemcpconfig',
            name='owner',
        ),
        # 4. 将 project 字段改为非空
        migrations.AlterField(
            model_name='remotemcpconfig',
            name='project',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='remote_mcp_configs',
                to='projects.project',
                help_text='此远程 MCP 配置所属的项目'
            ),
        ),
        # 5. 移除 name 的全局唯一约束
        migrations.AlterField(
            model_name='remotemcpconfig',
            name='name',
            field=models.CharField(max_length=255, help_text='远程 MCP 服务器的名称'),
        ),
        # 6. 添加 (project, name) 的联合唯一约束
        migrations.AlterUniqueTogether(
            name='remotemcpconfig',
            unique_together={('project', 'name')},
        ),
    ]

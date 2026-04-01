from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mcp_tools', '0004_change_owner_to_project'),
    ]

    operations = [
        # 1. 移除 (project, name) 的联合唯一约束
        migrations.AlterUniqueTogether(
            name='remotemcpconfig',
            unique_together=set(),
        ),
        # 2. 移除 project 字段
        migrations.RemoveField(
            model_name='remotemcpconfig',
            name='project',
        ),
        # 3. 恢复 name 的全局唯一约束
        migrations.AlterField(
            model_name='remotemcpconfig',
            name='name',
            field=models.CharField(max_length=255, unique=True, help_text='远程 MCP 服务器的名称'),
        ),
    ]

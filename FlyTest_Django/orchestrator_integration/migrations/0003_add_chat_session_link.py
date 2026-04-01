# Generated manually for chat session integration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('langgraph_integration', '0008_llmconfig_supports_vision'),
        ('orchestrator_integration', '0002_add_interactive_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='orchestratortask',
            name='chat_session',
            field=models.ForeignKey(
                blank=True,
                help_text='任务源自的对话会话',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='langgraph_integration.chatsession',
                verbose_name='关联对话会话'
            ),
        ),
    ]
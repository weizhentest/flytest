"""删除 brain_orchestrator 类型的提示词"""
from django.db import migrations


def remove_brain_orchestrator_prompts(apps, schema_editor):
    """删除所有 brain_orchestrator 类型的提示词"""
    UserPrompt = apps.get_model('prompts', 'UserPrompt')
    deleted_count, _ = UserPrompt.objects.filter(prompt_type='brain_orchestrator').delete()
    if deleted_count > 0:
        print(f"Deleted {deleted_count} brain_orchestrator prompts")


def reverse_func(apps, schema_editor):
    """反向迁移不做任何操作"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('prompts', '0008_remove_userprompt_unique_user_program_prompt_type_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_brain_orchestrator_prompts, reverse_func),
    ]

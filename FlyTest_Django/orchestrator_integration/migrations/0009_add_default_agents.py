# Generated data migration for default Agent configs
from django.db import migrations


def create_default_agents(apps, schema_editor):
    """创建默认的 Agent 配置"""
    AgentConfig = apps.get_model('orchestrator_integration', 'AgentConfig')

    default_agents = [
        {
            'name': 'Chat 助手',
            'tool_name': 'chat_assistant',
            'description': '处理用户的一般对话、闲聊、问候和简单问答。当用户进行非测试相关的对话时调用此 Agent。',
            'system_prompt': '''你是一个友好的测试助手。

你的职责是：
1. 回答用户的一般性问题
2. 提供测试相关的指导和建议
3. 与用户进行友好的对话

回复要求：
- 简洁、专业、友好
- 如果涉及项目具体信息，可以使用知识库工具搜索''',
            'include_knowledge_base': True,
            'is_active': True,
            'order': 0,
        },
        {
            'name': '需求分析专家',
            'tool_name': 'requirement_analyst',
            'description': '分析测试需求，提取测试点、业务规则和边界条件。当用户提供需求文档或描述需求时调用此 Agent。',
            'system_prompt': '''你是一名专业的测试需求分析专家。

你的职责是：
1. 分析用户提供的需求描述
2. 提取关键测试点和业务规则
3. 识别边界条件和异常场景
4. 输出结构化的需求分析结果

分析要求：
- 全面覆盖功能点
- 考虑正向和逆向测试场景
- 输出 JSON 格式的分析结果''',
            'include_knowledge_base': True,
            'is_active': True,
            'order': 1,
        },
        {
            'name': '测试用例生成器',
            'tool_name': 'testcase_generator',
            'description': '基于需求分析结果生成测试用例。当需要生成具体的测试用例时调用此 Agent。',
            'system_prompt': '''你是一名专业的测试用例编写专家。

你的职责是：
1. 基于需求分析结果生成测试用例
2. 覆盖正常流程、异常流程和边界条件
3. 确保用例的可执行性和可验证性

用例格式要求：
- 包含用例标题、前置条件、测试步骤、预期结果
- 按优先级和模块分类
- 输出 JSON 格式的用例列表''',
            'include_knowledge_base': True,
            'is_active': True,
            'order': 2,
        },
    ]

    for agent_data in default_agents:
        AgentConfig.objects.get_or_create(
            tool_name=agent_data['tool_name'],
            defaults=agent_data
        )


def remove_default_agents(apps, schema_editor):
    """删除默认的 Agent 配置"""
    AgentConfig = apps.get_model('orchestrator_integration', 'AgentConfig')
    AgentConfig.objects.filter(
        tool_name__in=['chat_assistant', 'requirement_analyst', 'testcase_generator']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('orchestrator_integration', '0008_add_agent_config'),
    ]

    operations = [
        migrations.RunPython(create_default_agents, remove_default_agents),
    ]

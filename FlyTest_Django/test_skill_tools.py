"""测试 Skill 工具"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

import django

django.setup()

from orchestrator_integration.builtin_tools.skill_tools import get_skill_tools
from skills.models import Skill


def test_skill_tools():
    # 查找有 Skill 的项目
    skills = list(Skill.objects.filter(is_active=True)[:5])
    print("=== Skills ===")
    for s in skills:
        print(f"  project_id={s.project_id}, name={s.name}")

    if not skills:
        print("No skills found")
        return

    project_id = skills[0].project_id
    skill_name = skills[0].name
    print(f"\n=== Testing project_id={project_id}, skill_name={skill_name} ===")

    tools = get_skill_tools(user_id=1, project_id=project_id)
    print(f"Loaded {len(tools)} tools: {[t.name for t in tools]}")

    # 测试 read_skill_content
    read_tool = tools[0]
    print(f"\n--- Test {read_tool.name} ---")
    result = read_tool.invoke({"skill_name": skill_name})
    print(f"Length: {len(result)} chars")
    print(f"First 400 chars:\n{result[:400]}")

    # 测试 execute_skill_script
    exec_tool = tools[1]
    print(f"\n--- Test {exec_tool.name} ---")
    result = exec_tool.invoke(
        {"skill_name": skill_name, "command": "python whart_tools.py --help"}
    )
    print(f"Result:\n{result[:600]}")


async def test_prompt_injection():
    """测试系统提示词注入只包含元数据"""
    from asgiref.sync import sync_to_async
    from langgraph_integration.views import _format_project_skills
    from projects.models import Project

    # 获取有 Skill 的项目 (project_id=1)
    project = await sync_to_async(Project.objects.filter(id=1).first)()
    if not project:
        print("No project with id=1 found")
        return

    print(
        f"\n=== Test prompt injection for project id={project.id}: {project.name} ==="
    )

    skills_text = await _format_project_skills(project)
    print(f"Skills prompt length: {len(skills_text)} chars")
    print(f"Content:\n{skills_text}")

    # 验证不包含完整的 SKILL.md 内容
    if "```bash" in skills_text or "## Quick Start" in skills_text:
        print("\n[FAIL] Prompt contains full SKILL.md content!")
    else:
        print("\n[PASS] Prompt only contains metadata (name + description)")


if __name__ == "__main__":
    test_skill_tools()

    import asyncio

    asyncio.run(test_prompt_injection())

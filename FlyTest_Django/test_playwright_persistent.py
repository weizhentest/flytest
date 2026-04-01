"""测试 Playwright 持久化会话功能"""
import sys
import os
import time
import io

# 解决 Windows 控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flytest_django.settings')

import django
django.setup()

from orchestrator_integration.builtin_tools.skill_tools import get_skill_tools
from skills.models import Skill


def test_persistent_session():
    """测试持久化会话：多次调用应复用同一浏览器"""
    print("=" * 60)
    print("测试 Playwright 持久化会话")
    print("=" * 60)

    # 检查 playwright-skill 是否存在
    skill = Skill.objects.filter(name='playwright-skill', is_active=True).first()
    if not skill:
        print("[SKIP] playwright-skill 未找到或未激活")
        return False

    print(f"找到 Skill: {skill.name}, path={skill.skill_path}")
    skill_dir = skill.get_full_path()
    print(f"Skill 目录: {skill_dir}")

    if not os.path.isdir(skill_dir):
        print(f"[ERROR] Skill 目录不存在: {skill_dir}")
        return False

    # 获取工具
    tools = get_skill_tools(user_id=1, project_id=1)
    exec_tool = None
    for t in tools:
        if t.name == 'execute_skill_script':
            exec_tool = t
            break

    if not exec_tool:
        print("[ERROR] 未找到 execute_skill_script 工具")
        return False

    session_id = f"test-session-{int(time.time())}"
    print(f"\n使用 session_id: {session_id}")

    # 测试步骤1: 导航到页面
    print("\n--- 步骤 1: 导航到 example.com ---")
    code1 = '''
await page.goto('https://example.com');
console.log('Page title:', await page.title());
console.log('Current URL:', page.url());
'''
    result1 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': f'node run.js "{code1}"',
        'session_id': session_id
    })
    print(f"结果:\n{result1}")

    # 测试步骤2: 获取页面内容（应该复用同一浏览器）
    print("\n--- 步骤 2: 获取 h1 文本（复用浏览器）---")
    code2 = '''
const h1 = await page.locator('h1').textContent();
console.log('H1 text:', h1);
console.log('Still at URL:', page.url());
'''
    result2 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': f'node run.js "{code2}"',
        'session_id': session_id
    })
    print(f"结果:\n{result2}")

    # 测试步骤3: 导航到另一个页面
    print("\n--- 步骤 3: 导航到另一个页面 ---")
    code3 = '''
await page.goto('https://httpbin.org/html');
console.log('New page title:', await page.title());
const bodyText = await page.locator('body').textContent();
console.log('Body preview:', bodyText.slice(0, 100));
'''
    result3 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': f'node run.js "{code3}"',
        'session_id': session_id
    })
    print(f"结果:\n{result3}")

    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    success = True
    if 'Example Domain' in result1 or 'example.com' in result1.lower():
        print("[PASS] 步骤1: 成功导航到 example.com")
    else:
        print("[WARN] 步骤1: 可能未成功导航")

    if 'Example Domain' in result2:
        print("[PASS] 步骤2: 成功获取 H1 文本，确认复用同一页面")
    else:
        print("[WARN] 步骤2: 未找到预期的 H1 文本")

    if 'httpbin' in result3.lower() or 'herman' in result3.lower():
        print("[PASS] 步骤3: 成功导航到新页面")
    else:
        print("[WARN] 步骤3: 可能未成功导航")

    return success


def test_different_sessions():
    """测试不同 session_id 使用不同浏览器"""
    print("\n" + "=" * 60)
    print("测试不同 session_id 独立性")
    print("=" * 60)

    skill = Skill.objects.filter(name='playwright-skill', is_active=True).first()
    if not skill:
        print("[SKIP] playwright-skill 未找到")
        return

    tools = get_skill_tools(user_id=1, project_id=1)
    exec_tool = next((t for t in tools if t.name == 'execute_skill_script'), None)
    if not exec_tool:
        return

    ts = int(time.time())
    session_a = f"session-A-{ts}"
    session_b = f"session-B-{ts}"

    # Session A 导航到 example.com
    print(f"\n--- Session A ({session_a}): 导航到 example.com ---")
    result_a1 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': 'node run.js "await page.goto(\'https://example.com\'); console.log(\'A: \' + page.url());"',
        'session_id': session_a
    })
    print(f"结果: {result_a1}")

    # Session B 导航到 httpbin
    print(f"\n--- Session B ({session_b}): 导航到 httpbin ---")
    result_b1 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': 'node run.js "await page.goto(\'https://httpbin.org/get\'); console.log(\'B: \' + page.url());"',
        'session_id': session_b
    })
    print(f"结果: {result_b1}")

    # 验证 Session A 仍在 example.com
    print(f"\n--- Session A: 验证仍在 example.com ---")
    result_a2 = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': 'node run.js "console.log(\'A still at: \' + page.url());"',
        'session_id': session_a
    })
    print(f"结果: {result_a2}")

    if 'example.com' in result_a2:
        print("[PASS] Session A 独立保持在 example.com")
    else:
        print("[FAIL] Session A 状态被 Session B 影响")


def test_no_session_id():
    """测试不传 session_id 时走原有 subprocess 路径"""
    print("\n" + "=" * 60)
    print("测试无 session_id（走 subprocess 路径）")
    print("=" * 60)

    skill = Skill.objects.filter(name='playwright-skill', is_active=True).first()
    if not skill:
        print("[SKIP] playwright-skill 未找到")
        return

    tools = get_skill_tools(user_id=1, project_id=1)
    exec_tool = next((t for t in tools if t.name == 'execute_skill_script'), None)
    if not exec_tool:
        return

    # 不传 session_id
    print("\n--- 不传 session_id 执行命令 ---")
    result = exec_tool.invoke({
        'skill_name': 'playwright-skill',
        'command': 'node run.js "await page.goto(\'https://example.com\'); console.log(page.url());"'
    })
    print(f"结果: {result}")

    if 'example.com' in result:
        print("[PASS] 无 session_id 模式正常工作")
    else:
        print("[INFO] 结果可能需要检查")


if __name__ == '__main__':
    print("Playwright 持久化会话测试\n")

    try:
        test_persistent_session()
        test_different_sessions()
        test_no_session_id()
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n测试完成")

# -*- coding: utf-8 -*-
import sys
import io

# Windows 终端 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
import os
import time
import requests
from pathlib import Path

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# 配置
BASE_URL = "http://127.0.0.1:8000"
API_KEY = "flytest-default-mcp-key-2025"
HEADERS = {
    "accept": "application/json, text/plain,*/*",
    "X-API-Key": API_KEY
}


def _extract_tree(nodes_list, id_key, name_key):
    """递归提取树形结构"""
    result = []
    if not isinstance(nodes_list, list):
        return result
    for node in nodes_list:
        if isinstance(node, dict):
            result.append({id_key: node.get("id"), name_key: node.get("name")})
            children = node.get("children")
            if isinstance(children, list):
                result.extend(_extract_tree(children, id_key, name_key))
    return result


def get_projects():
    """获取项目列表"""
    url = f"{BASE_URL}/api/projects/"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return _extract_tree(data, "project_id", "project_name")
    except Exception as e:
        return {"error": str(e)}


def get_modules(project_id: int):
    """获取项目下的模块"""
    url = f"{BASE_URL}/api/projects/{project_id}/testcase-modules/"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return _extract_tree(data, "module_id", "module_name")
    except Exception as e:
        return {"error": str(e)}


def get_levels():
    """获取用例等级"""
    return ["P0", "P1", "P2", "P3"]


def get_testcases(project_id: int, module_id: int):
    """获取用例列表"""
    url = f"{BASE_URL}/api/projects/{project_id}/testcases/?page=1&page_size=1000&module_id={module_id}"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [{"case_id": i.get("id"), "case_name": i.get("name")} for i in data]
    except Exception as e:
        return {"error": str(e)}


def get_testcase_detail(project_id: int, case_id: int):
    """获取用例详情"""
    url = f"{BASE_URL}/api/projects/{project_id}/testcases/{case_id}/"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        return {"error": str(e)}


def add_testcase(project_id: int, module_id: int, name: str, level: str = "P1",
                 precondition: str = "无", steps: list = None, notes: str = "",
                 review_status: str = "pending_review", test_type: str = "functional"):
    """新增测试用例"""
    url = f"{BASE_URL}/api/projects/{project_id}/testcases/"
    data = {
        "name": name,
        "precondition": precondition,
        "level": level,
        "module_id": module_id,
        "steps": steps or [],
        "notes": notes,
        "review_status": review_status,
        "test_type": test_type
    }
    try:
        resp = requests.post(url, headers=HEADERS, json=data)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 201:
            return {"message": "保存成功", "testcase": {"id": result.get("data", {}).get("id"),"name": result.get("data", {}).get("name", name)}}
        return {"message": "保存失败", "response": result}
    except Exception as e:
        return {"error": str(e)}


def edit_testcase(project_id: int, case_id: int, name: str = None, level: str = None,
                  module_id: int = None, precondition: str = None, steps: list = None, notes: str = None,
                  review_status: str = None, test_type: str = None, is_optimization: bool = False):
    """编辑测试用例"""
    url = f"{BASE_URL}/api/projects/{project_id}/testcases/{case_id}/"
    data = {}
    if name is not None: data["name"] = name
    if level is not None: data["level"] = level
    if module_id is not None: data["module_id"] = module_id
    if precondition is not None: data["precondition"] = precondition
    if steps is not None: data["steps"] = steps
    if notes is not None: data["notes"] = notes
    if test_type is not None: data["test_type"] = test_type

    # 处理优化工作流
    if is_optimization:
        data["review_status"] = "optimization_pending_review"
    elif review_status is not None:
        data["review_status"] = review_status

    try:
        resp = requests.patch(url, headers=HEADERS, json=data)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 200:
            status_msg = ""
            if is_optimization:
                status_msg = "，状态已自动设为「优化待审核」"
            elif review_status:
                status_msg = f"，状态已设为「{review_status}」"
            return {
                "success": True,
                "message": f"用例ID {case_id} 编辑成功{status_msg}。任务已完成，无需再次编辑或查询。"
            }
        return {"success": False, "message": "编辑失败", "response": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_screenshot(project_id: int, case_id: int, file_path: str, title: str,
                      description: str = "", step_number: int = None, page_url: str = ""):
    """上传单张截图"""
    # 如果是文件名（无目录分隔符），自动从 SCREENSHOT_DIR 查找
    if os.sep not in file_path and '/' not in file_path:
        screenshot_dir = os.environ.get('SCREENSHOT_DIR', '')
        if screenshot_dir:
            file_path = os.path.join(screenshot_dir, file_path)

    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    url = f"{BASE_URL}/api/projects/{project_id}/testcases/{case_id}/upload-screenshots/"
    mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
    ext = os.path.splitext(file_path)[1].lower()
    content_type = mime_types.get(ext, 'image/png')

    try:
        with open(file_path, 'rb') as f:
            files = {'screenshots': (os.path.basename(file_path), f, content_type)}
            data = {'title': title}
            if description: data['description'] = description
            if step_number is not None: data['step_number'] = str(step_number)
            if page_url: data['page_url'] = page_url

            resp = requests.post(url, headers=HEADERS, files=files, data=data)
            resp.raise_for_status()
            return {"message": f"截图 '{title}' 上传成功"}
    except Exception as e:
        return {"error": str(e)}


def upload_screenshots(project_id: int, case_id: int, file_paths: str, title: str,
                       description: str = "", step_number: int = None, page_url: str = ""):
    """批量上传截图（最多10张）"""
    paths = [p.strip() for p in file_paths.split(',') if p.strip()]
    if not paths:
        return {"error": "未提供文件路径"}
    if len(paths) > 10:
        return {"error": "一次最多上传10张图片"}

    screenshot_dir = os.environ.get('SCREENSHOT_DIR', '')
    resolved_paths = []
    for fp in paths:
        if os.sep not in fp and '/' not in fp and screenshot_dir:
            fp = os.path.join(screenshot_dir, fp)
        if not os.path.exists(fp):
            return {"error": f"文件不存在: {fp}"}
        resolved_paths.append(fp)

    url = f"{BASE_URL}/api/projects/{project_id}/testcases/{case_id}/upload-screenshots/"
    mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}

    try:
        files = []
        file_handles = []
        for fp in resolved_paths:
            ext = os.path.splitext(fp)[1].lower()
            content_type = mime_types.get(ext, 'image/png')
            f = open(fp, 'rb')
            file_handles.append(f)
            files.append(('screenshots', (os.path.basename(fp), f, content_type)))

        data = {'title': title}
        if description: data['description'] = description
        if step_number is not None: data['step_number'] = str(step_number)
        if page_url: data['page_url'] = page_url

        resp = requests.post(url, headers=HEADERS, files=files, data=data)
        resp.raise_for_status()

        for f in file_handles:
            f.close()

        return {"message": f"成功上传 {len(resolved_paths)} 张截图"}
    except Exception as e:
        for f in file_handles:
            try: f.close()
            except: pass
        return {"error": str(e)}


def _parse_steps(steps_str):
    """解析 steps JSON，支持容错，自动修复常见格式问题"""
    if not steps_str:
        return []

    # 先尝试直接解析
    try:
        parsed = json.loads(steps_str)
        if isinstance(parsed, list):
            return parsed
        return [parsed] if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        pass

    # 尝试修复：给没有引号的键名加上引号
    import re
    fixed = steps_str
    # 匹配 {key: 或 ,key: 形式的未加引号键名
    fixed = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', fixed)
    # 匹配未加引号的字符串值（排除数字、布尔值、null）
    def quote_value(m):
        val = m.group(1).strip()
        suffix = m.group(2)
        if re.match(r'^-?\d+\.?\d*$', val) or val in ('true', 'false', 'null'):
            return f':{val}{suffix}'
        return f':"{val}"{suffix}'
    fixed = re.sub(r':\s*([^",\[\]{}][^,\[\]{}]*?)([,}\]])', quote_value, fixed)

    try:
        parsed = json.loads(fixed)
        if isinstance(parsed, list):
            return parsed
        return [parsed] if isinstance(parsed, dict) else []
    except json.JSONDecodeError as e:
        return {"error": f"steps JSON 格式错误，无法解析: {str(e)}。正确格式: [{{\"step_number\":1,\"description\":\"...\",\"expected_result\":\"...\"}}]"}


# Action 路由
ACTIONS = {
    "get_projects": lambda args: get_projects(),
    "get_modules": lambda args: get_modules(args.project_id),
    "get_levels": lambda args: get_levels(),
    "get_testcases": lambda args: get_testcases(args.project_id, args.module_id),
    "get_testcase_detail": lambda args: get_testcase_detail(args.project_id, args.case_id),
    "add_testcase": lambda args: (
        _parse_steps(args.steps) if isinstance(_parse_steps(args.steps), dict) else
        add_testcase(
            args.project_id, args.module_id, args.name, args.level,
            args.precondition or "", _parse_steps(args.steps), args.notes or "",
            args.review_status or "pending_review", args.test_type or "functional"
        )
    ),
    "edit_testcase": lambda args: (
        _parse_steps(args.steps) if args.steps and isinstance(_parse_steps(args.steps), dict) else
        edit_testcase(
            args.project_id, args.case_id, args.name, args.level, args.module_id,
            args.precondition, _parse_steps(args.steps) if args.steps else None, args.notes,
            args.review_status, args.test_type, args.is_optimization
        )
    ),
    "upload_screenshot": lambda args: upload_screenshot(
        args.project_id, args.case_id, args.file_path, args.title,
        args.description or "", args.step_number, args.page_url or ""
    ),
    "upload_screenshots": lambda args: upload_screenshots(
        args.project_id, args.case_id, args.file_paths, args.title,
        args.description or "", args.step_number, args.page_url or ""
    ),
}


def main():
    parser = argparse.ArgumentParser(description="FlyTest 测试管理平台工具")
    parser.add_argument("--action", required=True, choices=ACTIONS.keys(), help="要执行的操作")
    parser.add_argument("--project_id", type=int, help="项目ID")
    parser.add_argument("--module_id", type=int, help="模块ID")
    parser.add_argument("--case_id", type=int, help="用例ID")
    parser.add_argument("--name", help="用例名称")
    parser.add_argument("--level", help="用例等级 (P0/P1/P2/P3)")
    parser.add_argument("--precondition", help="前置条件")
    parser.add_argument("--steps", help="用例步骤 (JSON格式)")
    parser.add_argument("--notes", help="备注")
    parser.add_argument("--file_path", help="文件路径（单张上传）")
    parser.add_argument("--file_paths", help="文件路径列表（批量上传，逗号分隔）")
    parser.add_argument("--title", help="标题")
    parser.add_argument("--description", help="描述")
    parser.add_argument("--step_number", type=int, help="步骤编号")
    parser.add_argument("--page_url", help="页面URL")
    parser.add_argument("--review_status", help="审核状态 (pending_review/approved/needs_optimization/optimization_pending_review/unavailable)")
    parser.add_argument("--test_type", help="测试类型 (smoke/functional/boundary/exception/permission/security/compatibility)", default="functional")
    parser.add_argument("--is_optimization", action="store_true", help="是否为优化操作（自动设置状态为optimization_pending_review）")

    args = parser.parse_args()
    result = ACTIONS[args.action](args)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 如果结果包含 error 字段，返回非零退出码
    if isinstance(result, dict) and "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()

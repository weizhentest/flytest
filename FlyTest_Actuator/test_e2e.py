#!/usr/bin/env python
"""
UI自动化端到端测试
测试完整流程：创建数据 -> 前端发送执行请求 -> 执行器执行 -> 返回结果

需要两个终端：
1. Django后端: uv run uvicorn flytest_django.asgi:application --reload
2. 执行本测试: uv run python test_e2e.py
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from models import SocketDataModel, QueueModel, UiSocketEnum, ResponseCode, NoticeType

try:
    import websockets
except ImportError:
    print("请安装websockets: pip install websockets")
    sys.exit(1)


API_BASE = "http://127.0.0.1:8000/api/ui-automation"
AUTH_URL = "http://127.0.0.1:8000/api/token/"
WS_URL = "ws://127.0.0.1:8000/ws/ui/web/"

# 测试用户凭据
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"
TEST_PROJECT_ID = 4  # UI自动化测试项目


async def get_auth_token() -> str | None:
    """获取JWT认证token"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(AUTH_URL, json={
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD
            })
            if resp.status_code == 200:
                data = resp.json()
                # 响应格式: {"status": "success", "data": {"access": "...", "refresh": "..."}}
                if data.get('status') == 'success' and data.get('data'):
                    return data['data'].get('access')
                # 备用格式: {"access": "...", "refresh": "..."}
                return data.get('access')
            else:
                print(f"   ❌ 登录失败: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            print(f"   ❌ 登录请求失败: {e}")
            return None


def extract_data(resp_json: dict) -> dict:
    """从API响应中提取data字段"""
    # 响应格式: {"status": "success", "data": {...}}
    if resp_json.get('status') == 'success' and 'data' in resp_json:
        return resp_json['data']
    # 直接返回响应
    return resp_json


async def create_test_data(token: str):
    """创建测试数据"""
    print("\n📝 步骤2: 创建测试数据...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(headers=headers) as client:
        # 创建模块
        module_resp = await client.post(f"{API_BASE}/modules/", json={
            "name": "E2E测试模块",
            "type": "module",
            "project": TEST_PROJECT_ID
        })
        if module_resp.status_code != 201:
            print(f"❌ 创建模块失败: {module_resp.text}")
            return None
        module = extract_data(module_resp.json())
        print(f"   ✅ 创建模块: {module['name']} (ID: {module['id']})")
        
        # 创建页面
        page_resp = await client.post(f"{API_BASE}/pages/", json={
            "name": "百度首页",
            "url": "https://www.baidu.com",
            "module": module['id'],
            "project": TEST_PROJECT_ID
        })
        if page_resp.status_code != 201:
            print(f"❌ 创建页面失败: {page_resp.text}")
            return None
        page = extract_data(page_resp.json())
        print(f"   ✅ 创建页面: {page['name']} (ID: {page['id']})")
        
        # 创建元素
        element_resp = await client.post(f"{API_BASE}/elements/", json={
            "name": "搜索框",
            "locator_type": "id",
            "locator_value": "kw",
            "page": page['id']
        })
        if element_resp.status_code != 201:
            print(f"❌ 创建元素失败: {element_resp.text}")
            return None
        element = extract_data(element_resp.json())
        print(f"   ✅ 创建元素: {element['name']} (ID: {element['id']})")
        
        # 创建页面步骤
        page_step_resp = await client.post(f"{API_BASE}/page-steps/", json={
            "name": "百度搜索步骤",
            "page": page['id'],
            "module": module['id'],
            "project": TEST_PROJECT_ID
        })
        if page_step_resp.status_code != 201:
            print(f"❌ 创建页面步骤失败: {page_step_resp.text}")
            return None
        page_step = extract_data(page_step_resp.json())
        print(f"   ✅ 创建页面步骤: {page_step['name']} (ID: {page_step['id']})")
        
        # 创建步骤详情
        step_detail_resp = await client.post(f"{API_BASE}/page-steps-detailed/", json={
            "page_step": page_step['id'],
            "ope_type": "fill",
            "ope_key": "id",
            "ope_value": "kw",
            "key_list": "输入搜索关键词",
            "sort": 1
        })
        if step_detail_resp.status_code != 201:
            print(f"❌ 创建步骤详情失败: {step_detail_resp.text}")
            return None
        step_detail = extract_data(step_detail_resp.json())
        print(f"   ✅ 创建步骤详情 (ID: {step_detail['id']})")
        
        # 创建测试用例
        test_case_resp = await client.post(f"{API_BASE}/testcases/", json={
            "name": "百度搜索测试",
            "module": module['id'],
            "project": TEST_PROJECT_ID
        })
        if test_case_resp.status_code != 201:
            print(f"❌ 创建测试用例失败: {test_case_resp.text}")
            return None
        test_case = extract_data(test_case_resp.json())
        print(f"   ✅ 创建测试用例: {test_case['name']} (ID: {test_case['id']})")
        
        # 创建用例步骤详情
        case_step_resp = await client.post(f"{API_BASE}/case-steps/", json={
            "test_case": test_case['id'],
            "page_step": page_step['id'],
            "sort": 1
        })
        if case_step_resp.status_code != 201:
            print(f"❌ 创建用例步骤详情失败: {case_step_resp.text}")
            return None
        case_step = extract_data(case_step_resp.json())
        print(f"   ✅ 创建用例步骤详情 (ID: {case_step['id']})")
        
        return {
            'module': module,
            'page': page,
            'element': element,
            'page_step': page_step,
            'test_case': test_case
        }


async def test_websocket_execution(test_data: dict):
    """测试WebSocket执行流程"""
    print("\n🔌 步骤2: 测试WebSocket执行流程...")
    
    try:
        async with websockets.connect(WS_URL) as ws:
            # 接收连接成功消息
            welcome = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(welcome)
            print(f"   ✅ WebSocket连接成功: {data['msg']}")
            
            # 发送执行用例请求
            execute_msg = SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="execute",
                user="test_user",
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args={"case_id": test_data['test_case']['id']}
                )
            )
            
            print(f"   📤 发送执行请求: case_id={test_data['test_case']['id']}")
            await ws.send(execute_msg.model_dump_json())
            
            # 等待响应
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            resp_data = json.loads(response)
            print(f"   📥 收到响应: {resp_data['msg']}")
            
            if resp_data['code'] == ResponseCode.SUCCESS:
                print("   ✅ 执行请求已发送给执行器")
            else:
                print(f"   ❌ 执行请求失败: {resp_data['msg']}")
            
            # 继续监听结果
            print("   ⏳ 等待执行结果 (10秒超时)...")
            try:
                while True:
                    result = await asyncio.wait_for(ws.recv(), timeout=10)
                    result_data = json.loads(result)
                    
                    if result_data.get('data', {}).get('func_name') == UiSocketEnum.STEP_RESULT:
                        step_result = result_data['data']['func_args']
                        status = "✅" if step_result['status'] == 'success' else "❌"
                        print(f"   {status} 步骤结果: {step_result}")
                    elif result_data.get('data', {}).get('func_name') == UiSocketEnum.CASE_RESULT:
                        case_result = result_data['data']['func_args']
                        status = "✅" if case_result['status'] == 'success' else "❌"
                        print(f"   {status} 用例结果: {case_result['status']}")
                        break
                    else:
                        print(f"   📨 其他消息: {result_data['msg']}")
            except asyncio.TimeoutError:
                print("   ⚠️ 等待结果超时 (需要执行器运行中)")
                
    except ConnectionRefusedError:
        print("   ❌ WebSocket连接被拒绝 - 请确保Django服务器正在运行")
    except Exception as e:
        print(f"   ❌ WebSocket错误: {e}")


async def cleanup_test_data(test_data: dict, token: str):
    """清理测试数据"""
    print("\n🧹 步骤4: 清理测试数据...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(headers=headers) as client:
        # 按依赖关系逆序删除
        endpoints = [
            ('testcases', test_data['test_case']['id']),
            ('page-steps', test_data['page_step']['id']),
            ('elements', test_data['element']['id']),
            ('pages', test_data['page']['id']),
            ('modules', test_data['module']['id']),
        ]
        
        for endpoint, id in endpoints:
            if id:
                resp = await client.delete(f"{API_BASE}/{endpoint}/{id}/")
                if resp.status_code in (200, 204):
                    print(f"   ✅ 删除 {endpoint}/{id}")
                else:
                    print(f"   ⚠️ 删除 {endpoint}/{id} 失败: {resp.status_code}")


async def main():
    print("=" * 60)
    print("UI自动化端到端测试")
    print("=" * 60)
    
    # 获取认证token
    print("\n🔐 步骤1: 获取认证Token...")
    token = await get_auth_token()
    if not token:
        print("   ❌ 获取Token失败，终止测试")
        print(f"   请确保用户 {TEST_USERNAME} 存在且密码正确")
        return
    print("   ✅ 获取Token成功")
    
    # 创建测试数据
    test_data = await create_test_data(token)
    if not test_data:
        print("\n❌ 创建测试数据失败，终止测试")
        return
    
    # 测试WebSocket执行
    await test_websocket_execution(test_data)
    
    # 清理测试数据
    await cleanup_test_data(test_data, token)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    print("\n提示: 如果要测试完整执行流程，需要同时运行执行器:")
    print("cd FlyTest_Actuator && uv run python main.py")


if __name__ == '__main__':
    asyncio.run(main())

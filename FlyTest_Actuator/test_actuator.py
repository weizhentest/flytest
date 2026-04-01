#!/usr/bin/env python
"""
简化的执行器测试 - 直接发送消息给执行器测试
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import SocketDataModel, QueueModel, UiSocketEnum, ResponseCode, NoticeType

try:
    import websockets
except ImportError:
    print("请安装websockets: pip install websockets")
    sys.exit(1)


async def test_actuator_directly():
    """直接连接执行器路由发送测试消息"""
    print("测试1: 检查执行器是否连接...")
    
    # 连接到前端WebSocket
    web_ws_url = "ws://127.0.0.1:8000/ws/ui/web/"
    
    try:
        async with websockets.connect(web_ws_url) as ws:
            # 接收欢迎消息
            welcome = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"✅ 前端WebSocket连接成功")
            
            # 发送一个简单的测试任务
            test_msg = SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="test_execute",
                user="test_user",
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args={"case_id": 999}  # 不存在的ID，测试执行器响应
                )
            )
            
            print("📤 发送测试执行请求...")
            await ws.send(test_msg.model_dump_json())
            
            # 等待响应
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            resp_data = json.loads(response)
            print(f"📥 收到响应: {resp_data}")
            
            if "执行器" in resp_data.get('msg', ''):
                if "没有可用" in resp_data.get('msg', ''):
                    print("❌ 没有执行器连接！请确保执行器正在运行")
                else:
                    print("✅ 任务已发送给执行器")
            
            # 监听更多消息
            print("\n等待执行器响应 (5秒)...")
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    print(f"📨 收到: {data}")
            except asyncio.TimeoutError:
                print("⏰ 5秒内无更多消息")
                
    except Exception as e:
        print(f"❌ 错误: {e}")


async def check_actuator_connection():
    """检查执行器是否已连接"""
    print("\n测试2: 直接连接执行器WebSocket...")
    actuator_ws_url = "ws://127.0.0.1:8000/ws/ui/actuator/"
    
    try:
        async with websockets.connect(actuator_ws_url) as ws:
            welcome = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(welcome)
            print(f"✅ 执行器WebSocket端点可用: {data.get('msg', '')}")
            
            # 发送一个模拟的任务
            task_msg = SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="execute",
                user="test_user",
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args={"case_id": 999}
                )
            )
            
            print("📤 发送模拟任务...")
            await ws.send(task_msg.model_dump_json())
            
            # 等待处理
            await asyncio.sleep(2)
            print("✅ 消息已发送")
            
    except Exception as e:
        print(f"❌ 连接执行器端点失败: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("执行器连接测试")
    print("=" * 50)
    
    asyncio.run(test_actuator_directly())
    asyncio.run(check_actuator_connection())

#!/usr/bin/env python
"""
测试WebSocket连接和执行器通信
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


async def test_connection():
    """测试WebSocket连接"""
    server_url = "ws://localhost:8000/ws/ui/actuator/"
    
    print(f"正在连接: {server_url}")
    
    try:
        async with websockets.connect(server_url) as ws:
            print("✅ 连接成功!")
            
            # 接收欢迎消息
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            print(f"收到消息: {data}")
            
            # 发送测试消息
            test_msg = SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="test",
                user="test_user",
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.STEP_RESULT,
                    func_args={"step_id": 1, "status": "success", "message": "test"}
                )
            )
            
            print(f"发送测试消息...")
            await ws.send(test_msg.model_dump_json())
            print("✅ 发送成功!")
            
            # 等待响应
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3)
                data = json.loads(response)
                print(f"收到响应: {data}")
            except asyncio.TimeoutError:
                print("(无响应 - 这是预期的，因为没有前端客户端)")
            
            print("\n✅ WebSocket连接测试通过!")
            
    except ConnectionRefusedError:
        print("❌ 连接被拒绝 - 请确保Django服务器正在运行")
        print("   启动方式: cd FlyTest_Django && python manage.py runserver")
    except Exception as e:
        print(f"❌ 连接错误: {e}")


async def test_executor_flow():
    """测试执行器工作流程"""
    from websocket_client import WebSocketClient
    from consumer import TaskConsumer
    
    print("\n测试执行器工作流程...")
    
    ws_client = WebSocketClient(
        "ws://localhost:8000/ws/ui/actuator/",
        "test-actuator"
    )
    
    # 只测试连接
    connected = await ws_client.connect()
    if connected:
        print("✅ 执行器连接成功!")
        await ws_client.disconnect()
    else:
        print("❌ 执行器连接失败")


if __name__ == '__main__':
    print("=" * 50)
    print("UI自动化执行器 - WebSocket连接测试")
    print("=" * 50)
    
    asyncio.run(test_connection())

"""
UI自动化 WebSocket Consumer


提供两个WebSocket端点：
- /ws/ui/web/ - 前端连接，用于接收执行结果和状态更新
- /ws/ui/actuator/ - 执行器连接，用于接收执行任务和返回结果
"""

import json
import logging
from typing import Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .socket_models import (
    SocketDataModel, QueueModel, NoticeType, ResponseCode,
    UiSocketEnum, ExecutionTaskModel, StepResultModel, CaseResultModel
)

logger = logging.getLogger('ui_automation')


class SocketUserManager:
    """WebSocket用户管理器"""
    
    _web_users: dict[str, 'UiAutomationConsumer'] = {}      # 前端用户连接
    _actuator_users: dict[str, 'UiAutomationConsumer'] = {} # 执行器连接
    
    @classmethod
    def add_web_user(cls, user_id: str, consumer: 'UiAutomationConsumer'):
        cls._web_users[user_id] = consumer
        logger.info(f"Web用户连接: {user_id}, 当前连接数: {len(cls._web_users)}")
    
    @classmethod
    def remove_web_user(cls, user_id: str):
        if user_id in cls._web_users:
            del cls._web_users[user_id]
            logger.info(f"Web用户断开: {user_id}, 当前连接数: {len(cls._web_users)}")
    
    @classmethod
    def add_actuator(cls, actuator_id: str, consumer: 'UiAutomationConsumer'):
        cls._actuator_users[actuator_id] = consumer
        logger.info(f"执行器连接: {actuator_id}, 当前执行器数: {len(cls._actuator_users)}")
    
    @classmethod
    def remove_actuator(cls, actuator_id: str):
        if actuator_id in cls._actuator_users:
            del cls._actuator_users[actuator_id]
            logger.info(f"执行器断开: {actuator_id}, 当前执行器数: {len(cls._actuator_users)}")
    
    @classmethod
    def get_actuator(cls, actuator_id: Optional[str] = None) -> Optional['UiAutomationConsumer']:
        """获取执行器，如果不指定则返回第一个可用的"""
        if actuator_id and actuator_id in cls._actuator_users:
            return cls._actuator_users[actuator_id]
        if cls._actuator_users:
            return list(cls._actuator_users.values())[0]
        return None
    
    @classmethod
    def get_actuator_by_id(cls, actuator_id: str) -> Optional['UiAutomationConsumer']:
        """根据ID获取指定执行器"""
        return cls._actuator_users.get(actuator_id)
    
    @classmethod
    def get_web_user(cls, user_id: str) -> Optional['UiAutomationConsumer']:
        return cls._web_users.get(user_id)
    
    @classmethod
    def has_actuator(cls) -> bool:
        return bool(cls._actuator_users)
    
    @classmethod
    def get_actuator_count(cls) -> int:
        return len(cls._actuator_users)
    
    @classmethod
    def get_all_actuators(cls) -> list['UiAutomationConsumer']:
        return list(cls._actuator_users.values())
    
    @classmethod
    def get_actuator_info(cls, actuator_id: str) -> dict:
        """获取执行器详细信息"""
        if actuator_id in cls._actuator_users:
            consumer = cls._actuator_users[actuator_id]
            return getattr(consumer, 'actuator_info', {})
        return {}


class UiAutomationConsumer(AsyncWebsocketConsumer):
    """UI自动化WebSocket消费者"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: Optional[str] = None
        self.is_actuator: bool = False
        self.group_name: str = 'ui_automation'
        self.actuator_info: dict = {}  # 执行器信息
    
    async def connect(self):
        """建立连接"""
        import datetime
        path = self.scope.get('path', '')
        
        # 获取客户端IP
        client = self.scope.get('client', ['unknown', 0])
        client_ip = client[0] if client else 'unknown'
        
        # 根据路径判断是前端还是执行器
        if '/actuator/' in path:
            self.is_actuator = True
            self.user_id = self.scope.get('query_string', b'').decode('utf-8')
            if not self.user_id:
                self.user_id = f"actuator_{id(self)}"
            
            # 初始化执行器信息
            self.actuator_info = {
                'id': self.user_id,
                'name': self.user_id,
                'ip': client_ip,
                'type': 'web_ui',
                'is_open': True,
                'debug': False,
                'browser_type': 'chromium',
                'headless': False,
                'connected_at': datetime.datetime.now().isoformat(),
            }
            SocketUserManager.add_actuator(self.user_id, self)
        else:
            self.is_actuator = False
            # 从用户认证获取ID
            user = self.scope.get('user')
            if user and hasattr(user, 'username'):
                self.user_id = user.username
            else:
                self.user_id = f"web_{id(self)}"
            SocketUserManager.add_web_user(self.user_id, self)
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # 发送连接成功消息
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=f"{'执行器' if self.is_actuator else 'Web客户端'}连接成功",
            user=self.user_id
        ))
        
        logger.info(f"{'执行器' if self.is_actuator else 'Web'}连接: {self.user_id}")
    
    async def disconnect(self, close_code):
        """断开连接"""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        
        if self.is_actuator:
            SocketUserManager.remove_actuator(self.user_id)
        else:
            SocketUserManager.remove_web_user(self.user_id)
        
        logger.info(f"{'执行器' if self.is_actuator else 'Web'}断开: {self.user_id}, code: {close_code}")
    
    async def receive(self, text_data=None, bytes_data=None):
        """接收消息"""
        if not text_data:
            return
        
        try:
            data = json.loads(text_data)
            socket_data = SocketDataModel(**data)
            
            # 如果有func_name，进行路由处理
            if socket_data.data and socket_data.data.func_name:
                await self.route_message(socket_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=f"消息格式错误: {str(e)}"
            ))
        except Exception as e:
            logger.error(f"处理消息错误: {e}", exc_info=True)
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=f"处理错误: {str(e)}"
            ))
    
    async def route_message(self, socket_data: SocketDataModel):
        """路由消息到对应处理器"""
        func_name = socket_data.data.func_name
        func_args = socket_data.data.func_args
        
        # 前端发送的执行请求 -> 转发给执行器
        if self.is_actuator:
            # 执行器返回的结果 -> 转发给前端
            handler_map = {
                UiSocketEnum.STEP_RESULT: self.handle_step_result,
                UiSocketEnum.PAGE_STEP_RESULT: self.handle_page_step_result,
                UiSocketEnum.CASE_RESULT: self.handle_case_result,
                UiSocketEnum.SET_ACTUATOR_INFO: self.handle_set_actuator_info,
            }
        else:
            # 前端发送执行请求 -> 转发给执行器
            handler_map = {
                UiSocketEnum.PAGE_STEPS: self.handle_execute_page_steps,
                UiSocketEnum.TEST_CASE: self.handle_execute_test_case,
                UiSocketEnum.TEST_CASE_BATCH: self.handle_execute_batch,
                UiSocketEnum.STOP_EXECUTION: self.handle_stop_execution,
            }
        
        handler = handler_map.get(func_name)
        if handler:
            await handler(func_args, socket_data.user)
        else:
            logger.warning(f"未知的func_name: {func_name}")
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=f"未知的操作: {func_name}"
            ))
    
    async def handle_execute_page_steps(self, args: dict, user: str):
        """处理执行页面步骤请求"""
        actuator_id = args.get('actuator_id')
        if actuator_id:
            actuator = SocketUserManager.get_actuator_by_id(actuator_id)
        else:
            actuator = SocketUserManager.get_actuator()
        
        if not actuator:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg="没有可用的执行器，请先启动执行器服务" if not actuator_id else f"执行器 {actuator_id} 不在线"
            ))
            return
        
        # 转发给执行器，使用服务端分配的user_id而非客户端传入的user
        await actuator.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="execute",
            user=self.user_id,
            is_notice=NoticeType.ACTUATOR,
            data=QueueModel(
                func_name=UiSocketEnum.PAGE_STEPS,
                func_args=args
            )
        ))
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="任务已发送给执行器"
        ))
    
    async def handle_execute_test_case(self, args: dict, user: str):
        """处理执行测试用例请求"""
        actuator_id = args.get('actuator_id')
        if actuator_id:
            actuator = SocketUserManager.get_actuator_by_id(actuator_id)
        else:
            actuator = SocketUserManager.get_actuator()
        if not actuator:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg="没有可用的执行器，请先启动执行器服务" if not actuator_id else f"执行器 {actuator_id} 不在线"
            ))
            return
        
        # 更新用例状态为执行中
        case_id = args.get('case_id')
        if case_id:
            await self.update_testcase_status(case_id, 1)  # 1 = 执行中
        
        # 转发给执行器，使用服务端分配的user_id而非客户端传入的user
        await actuator.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="execute",
            user=self.user_id,
            is_notice=NoticeType.ACTUATOR,
            data=QueueModel(
                func_name=UiSocketEnum.TEST_CASE,
                func_args=args
            )
        ))
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="任务已发送给执行器"
        ))
    
    async def handle_execute_batch(self, args: dict, user: str):
        """处理批量执行请求"""
        actuator_id = args.get('actuator_id')
        if actuator_id:
            actuator = SocketUserManager.get_actuator_by_id(actuator_id)
        else:
            actuator = SocketUserManager.get_actuator()
        if not actuator:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg="没有可用的执行器，请先启动执行器服务" if not actuator_id else f"执行器 {actuator_id} 不在线"
            ))
            return

        case_ids = args.get('case_ids', [])
        if not case_ids:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg="没有选择要执行的用例"
            ))
            return

        # 创建批量执行记录
        batch_id = await self.create_batch_record(case_ids)
        if not batch_id:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg="创建批量执行记录失败"
            ))
            return

        # 将 batch_id 加入参数传递给执行器
        args['batch_id'] = batch_id

        # 转发给执行器，使用服务端分配的user_id而非客户端传入的user
        await actuator.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="execute_batch",
            user=self.user_id,
            is_notice=NoticeType.ACTUATOR,
            data=QueueModel(
                func_name=UiSocketEnum.TEST_CASE_BATCH,
                func_args=args
            )
        ))

        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="批量任务已发送给执行器",
            data=QueueModel(
                func_name='batch_created',
                func_args={'batch_id': batch_id, 'total_cases': len(case_ids)}
            )
        ))
    
    async def handle_stop_execution(self, args: dict, user: str):
        """处理停止执行请求"""
        # 广播给所有执行器
        for actuator in SocketUserManager.get_all_actuators():
            await actuator.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="stop",
                user=self.user_id,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.STOP_EXECUTION,
                    func_args=args
                )
            ))
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="停止信号已发送"
        ))
    
    async def handle_step_result(self, args: dict, user: str):
        """处理步骤执行结果（来自执行器）"""
        logger.info(f"收到步骤结果, 目标用户: {user}, 当前Web用户: {list(SocketUserManager._web_users.keys())}")
        
        # 转发给对应的前端用户
        web_user = SocketUserManager.get_web_user(user)
        if web_user:
            await web_user.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="step_result",
                user=user,
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.STEP_RESULT,
                    func_args=args
                )
            ))
            logger.info(f"步骤结果已发送给用户: {user}")
        else:
            logger.warning(f"找不到Web用户: {user}")
        
        # 同时广播给所有前端（用于多人协作）
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.STEP_RESULT,
                    'args': args
                }
            }
        )
    
    async def handle_page_step_result(self, args: dict, user: str):
        """处理页面步骤执行结果（来自执行器）"""
        logger.info(f"收到页面步骤结果, 执行用户: {user}")

        # 更新页面步骤状态到数据库
        page_step_id = args.get('page_step_id')
        if page_step_id:
            status_str = args.get('status', 'unknown')
            status = 2 if status_str == 'success' else 3  # 2=成功, 3=失败
            await self.update_page_step_status(page_step_id, status, args)

        # 广播给所有前端
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.PAGE_STEP_RESULT,
                    'args': args,
                    'user': user
                }
            }
        )
    
    async def handle_case_result(self, args: dict, user: str):
        """处理用例执行结果（来自执行器）"""
        logger.info(f"收到用例结果, 执行用户: {user}")
        
        # 保存执行结果到数据库
        await self.save_execution_result(args)
        
        # 广播给所有前端（避免重复发送）
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.CASE_RESULT,
                    'args': args,
                    'user': user  # 携带执行用户信息
                }
            }
        )
    
    async def broadcast_result(self, event):
        """广播结果给所有前端"""
        if not self.is_actuator:
            await self.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="broadcast",
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=event['data']['func_name'],
                    func_args=event['data']['args']
                )
            ))
    
    @sync_to_async
    def update_testcase_status(self, case_id: int, status: int):
        """更新测试用例状态"""
        from .models import UiTestCase
        try:
            UiTestCase.objects.filter(id=case_id).update(status=status)
            logger.info(f"测试用例状态更新: case_id={case_id}, status={status}")
        except Exception as e:
            logger.error(f"更新测试用例状态失败: {e}")

    @sync_to_async
    def update_page_step_status(self, page_step_id: int, status: int, result_data: dict):
        """更新页面步骤状态"""
        from .models import UiPageSteps
        try:
            UiPageSteps.objects.filter(id=page_step_id).update(
                status=status,
                result_data=result_data
            )
            logger.info(f"页面步骤状态更新: page_step_id={page_step_id}, status={status}")
        except Exception as e:
            logger.error(f"更新页面步骤状态失败: {e}")
    
    @sync_to_async
    def save_execution_result(self, args: dict):
        """保存执行结果到数据库"""
        from .models import UiExecutionRecord, UiTestCase, UiBatchExecutionRecord
        from django.contrib.auth.models import User
        from datetime import datetime, timedelta

        logger.info(f">>> save_execution_result 被调用, args: {args}")

        # 状态映射: string -> int
        status_map = {'success': 2, 'failed': 3, 'skipped': 4}
        status_str = args.get('status', 'unknown')
        status = status_map.get(status_str, 3)  # 默认失败

        duration = args.get('duration', 0)
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=duration) if duration else end_time

        # 提取步骤结果
        steps = args.get('steps', [])
        screenshots = []
        for step in steps:
            if step.get('screenshot'):
                screenshots.append(step['screenshot'])

        # 提取 trace 路径
        trace_path = args.get('trace_path')

        # 提取 batch_id
        batch_id = args.get('batch_id')
        
        # 提取执行人信息
        executor_id = args.get('executor_id')
        executor = None
        if executor_id:
            try:
                executor = User.objects.get(id=executor_id)
                logger.info(f"找到执行人: id={executor_id}, username={executor.username}")
            except User.DoesNotExist:
                logger.warning(f"执行人不存在: id={executor_id}")

        case_id = args.get('case_id')
        try:
            record = UiExecutionRecord.objects.create(
                test_case_id=case_id,
                batch_id=batch_id,
                executor=executor,
                status=status,
                trigger_type='manual',
                step_results=steps,
                screenshots=screenshots,
                trace_path=trace_path,
                log=args.get('message', ''),
                error_message=args.get('message') if status == 3 else None,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )
            logger.info(f"执行记录已保存: id={record.id}, case_id={case_id}, batch_id={batch_id}, status={status}")

            # 同时更新测试用例的状态
            if case_id:
                UiTestCase.objects.filter(id=case_id).update(
                    status=status,
                    result_data={'last_execution': record.id, 'steps': steps},
                    error_message=args.get('message') if status == 3 else None
                )
                logger.info(f"测试用例状态已更新: case_id={case_id}, status={status}")

            # 更新批量执行记录统计
            if batch_id:
                try:
                    batch = UiBatchExecutionRecord.objects.get(id=batch_id)
                    batch.update_statistics()
                    logger.info(f"批量执行记录统计已更新: batch_id={batch_id}")
                except UiBatchExecutionRecord.DoesNotExist:
                    logger.warning(f"批量执行记录不存在: batch_id={batch_id}")
        except Exception as e:
            logger.error(f"保存执行结果失败: {e}", exc_info=True)

    @sync_to_async
    def create_batch_record(self, case_ids: list) -> int:
        """创建批量执行记录"""
        from .models import UiBatchExecutionRecord, UiTestCase
        from django.utils import timezone

        try:
            # 获取用例名称用于批次命名
            case_names = list(UiTestCase.objects.filter(id__in=case_ids).values_list('name', flat=True)[:3])
            batch_name = f"批量执行: {', '.join(case_names)}"
            if len(case_ids) > 3:
                batch_name += f" 等{len(case_ids)}个用例"

            batch = UiBatchExecutionRecord.objects.create(
                name=batch_name,
                total_cases=len(case_ids),
                status=1,  # 执行中
                start_time=timezone.now()
            )
            logger.info(f"批量执行记录已创建: id={batch.id}, total={len(case_ids)}")
            return batch.id
        except Exception as e:
            logger.error(f"创建批量执行记录失败: {e}", exc_info=True)
            return None
    
    async def handle_set_actuator_info(self, args: dict, user: str):
        """处理执行器信息更新（仅执行器可调用）"""
        if not self.is_actuator:
            return
        
        # 更新执行器信息
        if 'name' in args:
            self.actuator_info['name'] = args['name']
        if 'type' in args:
            self.actuator_info['type'] = args['type']
        if 'is_open' in args:
            self.actuator_info['is_open'] = args['is_open']
        if 'debug' in args:
            self.actuator_info['debug'] = args['debug']
        if 'browser_type' in args:
            self.actuator_info['browser_type'] = args['browser_type']
        if 'headless' in args:
            self.actuator_info['headless'] = args['headless']
        if 'version' in args:
            self.actuator_info['version'] = args['version']
        
        logger.info(f"执行器 {self.user_id} 信息已更新: {self.actuator_info}")
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="执行器信息已更新"
        ))
    
    async def send_json(self, data: SocketDataModel):
        """发送JSON消息"""
        await self.send(text_data=data.model_dump_json())
    
    @classmethod
    async def send_to_actuator(cls, task: ExecutionTaskModel, user: str) -> bool:
        """发送任务给执行器（供视图调用）"""
        actuator = SocketUserManager.get_actuator()
        if not actuator:
            return False
        
        func_name = UiSocketEnum.TEST_CASE
        if task.task_type == 'page_steps':
            func_name = UiSocketEnum.PAGE_STEPS
        elif task.task_type == 'batch':
            func_name = UiSocketEnum.TEST_CASE_BATCH
        
        await actuator.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="execute",
            user=user,
            is_notice=NoticeType.ACTUATOR,
            data=QueueModel(
                func_name=func_name,
                func_args=task.model_dump()
            )
        ))
        return True

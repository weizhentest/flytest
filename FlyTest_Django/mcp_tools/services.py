"""
MCP 工具同步服务

提供从远程 MCP 服务器同步工具列表到数据库的功能。
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

from asgiref.sync import sync_to_async
from langchain_mcp_adapters.client import MultiServerMCPClient

from .models import RemoteMCPConfig, MCPTool

logger = logging.getLogger(__name__)


async def sync_mcp_tools(mcp_config: RemoteMCPConfig) -> Dict[str, Any]:
    """
    从远程 MCP 服务器同步工具列表到数据库

    Args:
        mcp_config: MCP 配置对象

    Returns:
        同步结果: {
            'success': bool,
            'tools_count': int,
            'added': int,
            'updated': int,
            'removed': int,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'tools_count': 0,
        'added': 0,
        'updated': 0,
        'removed': 0,
    }

    try:
        # 构建服务器配置
        server_config = {
            mcp_config.name: {
                "transport": mcp_config.transport,
                "url": mcp_config.url,
            }
        }
        if mcp_config.headers:
            server_config[mcp_config.name]["headers"] = mcp_config.headers

        # 连接 MCP 服务器获取工具列表
        client = MultiServerMCPClient(server_config)

        async with client.session(mcp_config.name) as session:
            # 获取工具列表
            tools_response = await session.list_tools()
            remote_tools = tools_response.tools if hasattr(tools_response, 'tools') else []

            logger.info(f"从 MCP 服务器 {mcp_config.name} 获取到 {len(remote_tools)} 个工具")

            # 获取当前数据库中的工具（包装为 async）
            @sync_to_async
            def get_existing_tools():
                return {t.name: t for t in mcp_config.tools.all()}

            existing_tools = await get_existing_tools()
            existing_names = set(existing_tools.keys())
            remote_names = set()

            # 同步远程工具到数据库
            for tool in remote_tools:
                tool_name = tool.name
                remote_names.add(tool_name)

                tool_data = {
                    'description': getattr(tool, 'description', '') or '',
                    'input_schema': getattr(tool, 'inputSchema', {}) or {},
                }

                if tool_name in existing_tools:
                    # 更新现有工具
                    existing_tool = existing_tools[tool_name]
                    updated = False
                    if existing_tool.description != tool_data['description']:
                        existing_tool.description = tool_data['description']
                        updated = True
                    if existing_tool.input_schema != tool_data['input_schema']:
                        existing_tool.input_schema = tool_data['input_schema']
                        updated = True
                    if updated:
                        await sync_to_async(existing_tool.save)()
                        result['updated'] += 1
                else:
                    # 添加新工具
                    await sync_to_async(MCPTool.objects.create)(
                        mcp_config=mcp_config,
                        name=tool_name,
                        **tool_data
                    )
                    result['added'] += 1

            # 删除远程不存在的工具
            removed_names = existing_names - remote_names
            if removed_names:
                @sync_to_async
                def delete_removed_tools():
                    return MCPTool.objects.filter(
                        mcp_config=mcp_config,
                        name__in=removed_names
                    ).delete()
                await delete_removed_tools()
                result['removed'] = len(removed_names)

            result['success'] = True
            result['tools_count'] = len(remote_tools)

            logger.info(
                f"MCP {mcp_config.name} 工具同步完成: "
                f"总计 {result['tools_count']} 个, "
                f"新增 {result['added']}, 更新 {result['updated']}, 删除 {result['removed']}"
            )

    except Exception as e:
        logger.error(f"同步 MCP {mcp_config.name} 工具失败: {e}", exc_info=True)
        result['error'] = str(e)

    return result


def sync_mcp_tools_sync(mcp_config: RemoteMCPConfig) -> Dict[str, Any]:
    """同步版本的工具同步函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果在异步上下文中，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, sync_mcp_tools(mcp_config))
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(sync_mcp_tools(mcp_config))
    except Exception as e:
        logger.error(f"同步执行 MCP 工具同步失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'tools_count': 0,
            'added': 0,
            'updated': 0,
            'removed': 0,
        }


async def sync_all_active_mcp_tools() -> Dict[str, Dict[str, Any]]:
    """
    同步所有激活的 MCP 服务器的工具

    Returns:
        Dict[mcp_name, sync_result]
    """
    results = {}

    @sync_to_async
    def get_active_configs():
        return list(RemoteMCPConfig.objects.filter(is_active=True))

    active_configs = await get_active_configs()

    for config in active_configs:
        results[config.name] = await sync_mcp_tools(config)

    return results


def get_all_mcp_tools_for_approval() -> List[Dict[str, Any]]:
    """
    获取所有 MCP 工具的审批配置信息

    返回按 MCP 分组的工具列表，用于前端显示
    """
    from django.db.models import Prefetch

    tools_data = []

    # 获取所有激活的 MCP 配置及其工具
    mcp_configs = RemoteMCPConfig.objects.filter(
        is_active=True
    ).prefetch_related('tools')

    for mcp_config in mcp_configs:
        mcp_tools = mcp_config.tools.all()

        for tool in mcp_tools:
            tools_data.append({
                'tool_name': tool.name,
                'description': tool.description or f"[{mcp_config.name}] {tool.name}",
                'mcp_name': mcp_config.name,
                'mcp_id': mcp_config.id,
                'require_hitl': tool.effective_require_hitl,
                'allowed_decisions': ['approve', 'reject'],
            })

    return tools_data

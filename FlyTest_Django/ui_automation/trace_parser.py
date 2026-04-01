# -*- coding: utf-8 -*-
"""
Playwright Trace 解析器

解析 trace.zip 文件，提取关键信息用于前端展示：
- 操作时间线
- 网络请求
- 页面快照
- 控制台日志
"""

import json
import logging
import zipfile
import base64
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger('ui_automation')


@dataclass
class TraceAction:
    """操作记录"""
    action_id: str
    type: str                    # 操作类型：click, fill, goto 等
    selector: Optional[str]      # 选择器
    value: Optional[str]         # 输入值
    url: Optional[str]           # 目标URL
    start_time: float            # 开始时间 (ms)
    end_time: float              # 结束时间 (ms)
    duration: float              # 耗时 (ms)
    page_id: str                 # 页面ID
    error: Optional[str] = None  # 错误信息
    snapshot_before: Optional[str] = None  # 操作前快照
    snapshot_after: Optional[str] = None   # 操作后快照


@dataclass
class TraceNetworkRequest:
    """网络请求记录"""
    request_id: str
    url: str
    method: str
    resource_type: str           # document, xhr, fetch, script, stylesheet 等
    status: int
    status_text: str
    start_time: float
    end_time: float
    duration: float
    request_headers: dict
    response_headers: dict
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    response_size: int = 0


@dataclass
class TraceConsoleMessage:
    """控制台消息"""
    type: str                    # log, error, warning, info
    text: str
    timestamp: float
    location: Optional[str] = None


@dataclass
class TraceSnapshot:
    """页面快照"""
    snapshot_id: str
    timestamp: float
    html: Optional[str] = None   # DOM 快照
    screenshot: Optional[str] = None  # Base64 截图


@dataclass
class TraceData:
    """完整的 Trace 解析结果"""
    title: str
    start_time: float
    end_time: float
    duration: float
    page_url: str
    actions: list[TraceAction]
    network_requests: list[TraceNetworkRequest]
    console_messages: list[TraceConsoleMessage]
    snapshots: list[TraceSnapshot]
    summary: dict


class TraceParser:
    """Playwright Trace 解析器"""
    
    def __init__(self, trace_path: str):
        self.trace_path = Path(trace_path)
        self.trace_data: Optional[TraceData] = None
    
    def parse(self) -> Optional[dict]:
        """解析 trace.zip 文件，返回解析后的数据字典"""
        if not self.trace_path.exists():
            logger.error(f"Trace 文件不存在: {self.trace_path}")
            return None
        
        try:
            with zipfile.ZipFile(self.trace_path, 'r') as zf:
                return self._parse_zip(zf)
        except zipfile.BadZipFile:
            logger.error(f"无效的 zip 文件: {self.trace_path}")
            return None
        except Exception as e:
            logger.error(f"解析 Trace 失败: {e}")
            return None
    
    def _parse_zip(self, zf: zipfile.ZipFile) -> dict:
        """解析 zip 内容"""
        actions = []
        network_requests = []
        console_messages = []
        snapshots = []
        metadata = {}

        file_list = zf.namelist()

        # 查找并解析 trace 事件文件
        for name in file_list:
            if name.endswith('.trace'):
                content = zf.read(name).decode('utf-8')
                events = self._parse_trace_events(content)
                actions.extend(events.get('actions', []))
                console_messages.extend(events.get('console', []))
                metadata.update(events.get('metadata', {}))

        # 解析网络请求文件
        for name in file_list:
            if name.endswith('.network'):
                content = zf.read(name).decode('utf-8')
                network_requests.extend(self._parse_network_events(content, zf))

        # 解析截图（仅提取 page@ 截图帧，排除网站资源图片）
        # 截图命名格式: resources/page@<hash>-<timestamp>.jpeg
        # 网站资源命名格式: resources/<sha1_hash>.png (纯 hash，无 page@ 前缀)
        for name in file_list:
            if not (name.endswith('.png') or name.endswith('.jpeg')):
                continue
            basename = name.split('/')[-1]
            # 只提取 page@ 开头的截图帧，排除纯 sha1 hash 命名的资源图片
            if not basename.startswith('page@'):
                continue
            try:
                img_data = zf.read(name)
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                ext = 'png' if name.endswith('.png') else 'jpeg'
                # 从文件名提取时间戳 (格式: page@<hash>-<timestamp>.jpeg)
                timestamp = 0
                try:
                    # 提取最后一个 - 后面的数字
                    ts_part = basename.rsplit('-', 1)[-1].replace('.jpeg', '').replace('.png', '')
                    timestamp = float(ts_part)
                except (ValueError, IndexError):
                    pass
                snapshots.append({
                    'snapshot_id': name,
                    'timestamp': timestamp,
                    'screenshot': f"data:image/{ext};base64,{img_base64}"
                })
            except Exception as e:
                logger.warning(f"读取截图失败 {name}: {e}")

        # 按时间戳排序截图
        snapshots.sort(key=lambda x: x.get('timestamp', 0))

        # 将 snapshot 的绝对时间戳转换为与 action 相同的相对时间
        # 通过对齐第一个 action 的 start_time 和第一个 snapshot 的 timestamp
        if actions and snapshots:
            action_times = [a.get('start_time', 0) for a in actions if a.get('start_time', 0) > 0]
            snap_times = [s.get('timestamp', 0) for s in snapshots if s.get('timestamp', 0) > 0]
            if action_times and snap_times:
                # 计算时间偏移量：snapshot 绝对时间 - action 相对时间
                first_action_time = min(action_times)
                first_snap_time = min(snap_times)
                time_offset = first_snap_time - first_action_time
                # 将所有 snapshot 时间戳转换为相对时间
                for snap in snapshots:
                    if snap.get('timestamp', 0) > 0:
                        snap['timestamp'] = snap['timestamp'] - time_offset

        # 计算汇总信息
        start_time = min([a.get('start_time', 0) for a in actions], default=0)
        end_time = max([a.get('end_time', 0) for a in actions], default=0)
        duration = end_time - start_time
        
        # 网络请求统计
        network_summary = {
            'total': len(network_requests),
            'by_type': {},
            'by_status': {},
            'total_size': 0
        }
        for req in network_requests:
            rtype = req.get('resource_type', 'other')
            network_summary['by_type'][rtype] = network_summary['by_type'].get(rtype, 0) + 1
            status = req.get('status', 0)
            status_group = f"{status // 100}xx"
            network_summary['by_status'][status_group] = network_summary['by_status'].get(status_group, 0) + 1
            network_summary['total_size'] += req.get('response_size', 0)
        
        return {
            'title': metadata.get('title', 'Trace'),
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'page_url': metadata.get('url', ''),
            'actions': actions[:200],  # 限制返回数量
            'network_requests': network_requests[:500],
            'console_messages': console_messages[:200],
            'snapshots': snapshots,  # 返回全部截图
            'summary': {
                'total_actions': len(actions),
                'total_requests': len(network_requests),
                'total_console': len(console_messages),
                'total_snapshots': len(snapshots),
                'duration_ms': duration,
                'network': network_summary,
                'metadata': metadata
            }
        }
    
    def _parse_trace_events(self, content: str) -> dict:
        """解析 trace.trace 事件内容"""
        actions = []
        console = []
        metadata = {}
        pending_actions = {}  # callId -> before event data

        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                event_type = event.get('type', '')

                if event_type == 'context-options':
                    metadata['viewport'] = event.get('options', {}).get('viewport')
                    metadata['userAgent'] = event.get('options', {}).get('userAgent')

                elif event_type == 'before':
                    call_id = event.get('callId', '')
                    method = event.get('method', '')
                    params = event.get('params', {})

                    # 提取页面 URL
                    if method == 'goto' and params.get('url'):
                        metadata['url'] = params.get('url')

                    # 存储待匹配的 before 事件
                    pending_actions[call_id] = {
                        'action_id': call_id,
                        'type': method,
                        'selector': params.get('selector'),
                        'value': params.get('text'),
                        'url': params.get('url'),
                        'start_time': event.get('startTime', 0),
                        'page_id': event.get('pageId', ''),
                        'class': event.get('class', ''),
                    }

                elif event_type == 'after':
                    call_id = event.get('callId', '')
                    if call_id in pending_actions:
                        action = pending_actions.pop(call_id)
                        action['end_time'] = event.get('endTime', 0)
                        action['duration'] = action['end_time'] - action['start_time']
                        # 检查错误
                        if event.get('error'):
                            action['error'] = event['error'].get('message', str(event['error']))
                        # 只保留有意义的操作（过滤掉 screenshot 等）
                        if action['type'] in ('goto', 'click', 'fill', 'type', 'press', 'check', 'uncheck', 'selectOption', 'hover', 'waitForSelector'):
                            actions.append(action)

                elif event_type == 'console':
                    console.append({
                        'type': event.get('messageType', 'log'),
                        'text': event.get('text', ''),
                        'timestamp': event.get('timestamp', 0),
                        'location': event.get('location'),
                    })

            except json.JSONDecodeError:
                continue

        return {
            'actions': actions,
            'console': console,
            'metadata': metadata
        }

    def _parse_network_events(self, content: str, zf: zipfile.ZipFile) -> list:
        """解析 trace.network 文件"""
        network = []

        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get('type') == 'resource-snapshot':
                    snapshot = event.get('snapshot', {})
                    request = snapshot.get('request', {})
                    response = snapshot.get('response', {})

                    # headers 是数组格式 [{name, value}, ...]
                    req_headers = {h.get('name', ''): h.get('value', '') for h in request.get('headers', []) if isinstance(h, dict)}
                    resp_headers = {h.get('name', ''): h.get('value', '') for h in response.get('headers', []) if isinstance(h, dict)}

                    # 计算响应大小
                    resp_content = response.get('content', {})
                    body_size = resp_content.get('size', 0) or response.get('bodySize', 0) or 0

                    # 计算耗时
                    duration = snapshot.get('time', 0)

                    # 提取请求体
                    request_body = None
                    post_data = request.get('postData', {})
                    if post_data:
                        # postData 可能是字符串或对象
                        if isinstance(post_data, str):
                            request_body = post_data
                        elif isinstance(post_data, dict):
                            # 可能有 text 或 _sha1 引用
                            if post_data.get('text'):
                                request_body = post_data.get('text')
                            elif post_data.get('_sha1'):
                                try:
                                    resource_path = f"resources/{post_data.get('_sha1')}"
                                    if resource_path in zf.namelist():
                                        body_bytes = zf.read(resource_path)
                                        if len(body_bytes) <= 100 * 1024:
                                            request_body = body_bytes.decode('utf-8', errors='replace')
                                except Exception:
                                    pass

                    # 提取响应体（从 resources 目录读取）
                    response_body = None
                    sha1_ref = resp_content.get('_sha1', '')
                    mime_type = resp_content.get('mimeType', '')
                    if sha1_ref and self._is_text_content(mime_type):
                        try:
                            resource_path = f"resources/{sha1_ref}"
                            if resource_path in zf.namelist():
                                body_bytes = zf.read(resource_path)
                                # 限制响应体大小，避免过大
                                if len(body_bytes) <= 100 * 1024:  # 100KB 限制
                                    response_body = body_bytes.decode('utf-8', errors='replace')
                        except Exception:
                            pass

                    network.append({
                        'request_id': snapshot.get('pageref', '') + '_' + request.get('url', '')[:50],
                        'url': request.get('url', ''),
                        'method': request.get('method', 'GET'),
                        'resource_type': resp_content.get('mimeType', 'other').split('/')[0] if resp_content.get('mimeType') else 'other',
                        'mime_type': mime_type,
                        'status': response.get('status', 0),
                        'status_text': response.get('statusText', ''),
                        'start_time': 0,
                        'end_time': 0,
                        'duration': duration * 1000 if duration else 0,  # 转为毫秒
                        'request_headers': req_headers,
                        'response_headers': resp_headers,
                        'response_size': body_size,
                        'request_body': request_body,
                        'response_body': response_body,
                    })
            except json.JSONDecodeError:
                continue

        return network

    def _is_text_content(self, mime_type: str) -> bool:
        """判断是否为文本类型内容"""
        if not mime_type:
            return False
        text_types = [
            'text/', 'application/json', 'application/javascript',
            'application/xml', 'application/xhtml', 'application/x-www-form-urlencoded'
        ]
        return any(t in mime_type for t in text_types)


def parse_trace_file(trace_path: str) -> Optional[dict]:
    """解析 trace 文件的便捷函数"""
    parser = TraceParser(trace_path)
    return parser.parse()

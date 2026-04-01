"""
Agent Loop 停止信号管理

提供线程安全的停止信号存储，用于中断正在执行的 Agent Loop。

使用场景：
- 用户点击"停止"按钮时，调用 set_stop_signal(session_id)
- Agent Loop 在每步检查 should_stop(session_id)
- 任务结束后调用 clear_stop_signal(session_id) 清理
"""
import threading
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class StopSignalManager:
    """停止信号管理器（线程安全的内存存储）"""

    def __init__(self, signal_ttl: int = 300):
        """
        初始化停止信号管理器

        Args:
            signal_ttl: 信号过期时间（秒），防止信号永不清理
        """
        self._signals: Dict[str, float] = {}  # session_id -> timestamp
        self._lock = threading.Lock()
        self._signal_ttl = signal_ttl

    def set_stop_signal(self, session_id: str) -> bool:
        """
        设置停止信号

        Args:
            session_id: 会话 ID

        Returns:
            是否设置成功
        """
        with self._lock:
            self._signals[session_id] = time.time()
            logger.info(f"[StopSignal] Set stop signal for session: {session_id}")
            return True

    def should_stop(self, session_id: str) -> bool:
        """
        检查是否应该停止

        Args:
            session_id: 会话 ID

        Returns:
            是否应该停止
        """
        with self._lock:
            if session_id not in self._signals:
                return False

            # 检查信号是否过期
            signal_time = self._signals[session_id]
            if time.time() - signal_time > self._signal_ttl:
                # 信号已过期，清理
                del self._signals[session_id]
                logger.debug(f"[StopSignal] Signal expired for session: {session_id}")
                return False

            return True

    def clear_stop_signal(self, session_id: str) -> bool:
        """
        清除停止信号

        Args:
            session_id: 会话 ID

        Returns:
            是否清除成功（信号是否存在）
        """
        with self._lock:
            if session_id in self._signals:
                del self._signals[session_id]
                logger.info(f"[StopSignal] Cleared stop signal for session: {session_id}")
                return True
            return False

    def cleanup_expired(self) -> int:
        """
        清理所有过期的信号

        Returns:
            清理的信号数量
        """
        with self._lock:
            current_time = time.time()
            expired = [
                sid for sid, t in self._signals.items()
                if current_time - t > self._signal_ttl
            ]
            for sid in expired:
                del self._signals[sid]

            if expired:
                logger.info(f"[StopSignal] Cleaned up {len(expired)} expired signals")
            return len(expired)

    def get_active_signals(self) -> Dict[str, float]:
        """获取所有活跃的停止信号（调试用）"""
        with self._lock:
            return dict(self._signals)


# 全局单例
_stop_signal_manager: Optional[StopSignalManager] = None
_manager_lock = threading.Lock()


def get_stop_signal_manager() -> StopSignalManager:
    """获取全局停止信号管理器单例"""
    global _stop_signal_manager
    if _stop_signal_manager is None:
        with _manager_lock:
            if _stop_signal_manager is None:
                _stop_signal_manager = StopSignalManager()
    return _stop_signal_manager


# 便捷函数
def set_stop_signal(session_id: str) -> bool:
    """设置停止信号"""
    return get_stop_signal_manager().set_stop_signal(session_id)


def should_stop(session_id: str) -> bool:
    """检查是否应该停止"""
    return get_stop_signal_manager().should_stop(session_id)


def clear_stop_signal(session_id: str) -> bool:
    """清除停止信号"""
    return get_stop_signal_manager().clear_stop_signal(session_id)

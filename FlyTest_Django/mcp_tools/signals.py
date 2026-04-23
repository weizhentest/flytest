"""
Cleanup MCP sessions when Django exits.
"""

import atexit
import asyncio
import logging


logger = logging.getLogger(__name__)


def cleanup_mcp_sessions_on_exit():
    """Best-effort MCP cleanup during process shutdown."""
    previous_raise_exceptions = logging.raiseExceptions
    logging.raiseExceptions = False
    try:
        from mcp_tools.persistent_client import mcp_session_manager

        try:
            asyncio.run(mcp_session_manager.cleanup_all())
            logger.info("MCP sessions cleaned up on application exit")
        except RuntimeError as exc:
            logger.debug("MCP cleanup skipped during exit: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error cleaning up MCP sessions on exit: %s", exc, exc_info=True)
    finally:
        logging.raiseExceptions = previous_raise_exceptions


atexit.register(cleanup_mcp_sessions_on_exit)

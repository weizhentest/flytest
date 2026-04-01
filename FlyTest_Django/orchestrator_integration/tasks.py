"""智能编排 - 通过流式对话集成Brain和子Agent

旧的任务模式代码已移除,Brain现在通过流式对话接口工作:
1. 用户在对话框中与Brain交流
2. Brain生成计划并等待确认  
3. Brain调用子Agent并实时报告进度
4. 所有交互都在对话框中完成

TODO: 实现流式对话接口
- 集成到现有的ChatSession
- Brain可以调用子Agent(requirement/knowledge/testcase)
- 实时流式输出Brain的思考和Agent的结果
"""

import logging

logger = logging.getLogger(__name__)

# Celery任务已移除,改为流式对话模式
# 参考: orchestrator_integration/test_api/quick_test.py 中的对话示例

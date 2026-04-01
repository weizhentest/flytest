<template>
  <div class="diagram-container">
    <!-- 全屏图表区域 -->
    <div class="diagram-panel">
      <div class="diagram-header">
        <h3>AI 图表编辑器</h3>
        <a-space>
          <a-button type="text" @click="exportDiagram" :disabled="!currentXml">
            <template #icon><icon-download /></template>
            导出
          </a-button>
          <a-button type="text" @click="openInDrawio" :disabled="!currentXml">
            <template #icon><icon-launch /></template>
            在 Draw.io 中打开
          </a-button>
        </a-space>
      </div>
      <div class="diagram-content">
        <iframe
          ref="drawioIframeRef"
          class="drawio-iframe"
          :src="drawioUrl"
          @load="onIframeLoad"
        ></iframe>
      </div>
    </div>

    <!-- 悬浮按钮 - 打开 AI 对话 -->
    <a-tooltip content="AI 图表助手" position="left">
      <a-button
        type="primary"
        shape="circle"
        size="large"
        class="chat-fab"
        @click="showChatPanel = !showChatPanel"
      >
        <template #icon>
          <icon-close v-if="showChatPanel" />
          <icon-robot v-else />
        </template>
      </a-button>
    </a-tooltip>

    <!-- AI 对话弹窗面板 -->
    <transition name="slide-up">
      <div v-if="showChatPanel" class="chat-popup">
        <div class="chat-popup-header">
          <h4>AI 图表助手</h4>
          <a-space>
            <a-tooltip content="新对话" mini>
              <a-button type="text" size="small" @click="newChat" :disabled="isLoading || messages.length === 0">
                <template #icon><icon-plus /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip content="清空全部" mini>
              <a-button type="text" size="small" @click="clearChat" :disabled="isLoading">
                <template #icon><icon-delete /></template>
              </a-button>
            </a-tooltip>
            <a-button type="text" size="small" @click="showChatPanel = false">
              <template #icon><icon-close /></template>
            </a-button>
          </a-space>
        </div>

        <!-- 消息列表 -->
        <div class="chat-messages" ref="messagesContainerRef">
          <div v-if="messages.length === 0" class="empty-state">
            <icon-robot :size="36" />
            <p>向 AI 描述你想要创建的图表</p>
            <p class="hint">例如：创建一个用户登录的流程图</p>
          </div>
          
          <template v-for="(msg, index) in messages" :key="index">
            <!-- 步骤分隔符 -->
            <div v-if="msg.messageType === 'step'" class="step-separator">
              <div class="step-line"></div>
              <span class="step-label">步骤 {{ msg.stepNumber }}</span>
              <div class="step-line"></div>
            </div>
            
            <!-- 工具调用消息 -->
            <div v-else-if="msg.messageType === 'tool'" class="message tool-message">
              <div class="message-avatar tool-avatar">
                <icon-tool />
              </div>
              <div class="message-content tool-content">
                <div class="tool-name">🔧 {{ msg.toolName }}</div>
                <div v-html="formatMessage(msg.content)"></div>
              </div>
            </div>
            
            <!-- 普通消息 -->
            <div
              v-else
              :class="['message', msg.isUser ? 'user-message' : 'ai-message']"
            >
              <div class="message-avatar">
                <icon-user v-if="msg.isUser" />
                <icon-robot v-else />
              </div>
              <div class="message-content">
                <div v-if="msg.isLoading" class="loading-dots">
                  <span></span><span></span><span></span>
                </div>
                <template v-else>
                  <div v-html="formatMessage(msg.content)"></div>
                  <span v-if="msg.isStreaming" class="typing-cursor"></span>
                </template>
              </div>
            </div>
          </template>
          
          <!-- 工具审批卡片（紧凑版，适配小对话窗口） -->
          <div v-if="toolApprovalDialogVisible" class="compact-approval-wrapper">
            <ToolApprovalCard
              :visible="toolApprovalDialogVisible"
              :interrupt="currentInterrupt"
              :session-id="sessionId"
              @update:visible="toolApprovalDialogVisible = $event"
              @decision="handleToolDecision"
            />
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="chat-input">
          <!-- 上下文 Token 使用指示器 -->
          <TokenUsageIndicator
            v-if="contextTokenCount > 0 || contextLimit > 0"
            :current-tokens="contextTokenCount"
            :max-tokens="contextLimit"
          />
          <a-textarea
            v-model="inputMessage"
            placeholder="描述你想要的图表..."
            :auto-size="{ minRows: 1, maxRows: 3 }"
            @keydown.enter.prevent="handleEnterKey"
            :disabled="isLoading"
          />
          <a-button
            type="primary"
            :loading="isLoading"
            :disabled="!inputMessage.trim() || toolApprovalDialogVisible"
            @click="sendMessage"
          >
            <template #icon><icon-send /></template>
          </a-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { marked } from 'marked';
import { useProjectStore } from '@/store/projectStore';
import { useThemeStore } from '@/store/themeStore';
import { getPromptByType, initializeUserPrompts } from '@/features/prompts/services/promptService';
import { DiagramEditor, type EditOperation } from '../services/diagramEditor';
import TokenUsageIndicator from '@/features/langgraph/components/TokenUsageIndicator.vue';
import ToolApprovalCard from '@/features/langgraph/components/ToolApprovalCard.vue';
import type { InterruptEvent } from '@/features/langgraph/components/ToolApprovalCard.vue';

interface ChatMessage {
  content: string;
  isUser: boolean;
  isLoading?: boolean;
  isStreaming?: boolean;  // 标识消息正在流式输出
  messageType?: 'user' | 'ai' | 'tool' | 'step';  // 消息类型
  toolName?: string;  // 工具名称
  stepNumber?: number;  // 步骤编号
  maxSteps?: number;  // 最大步骤数
}

const projectStore = useProjectStore();
const themeStore = useThemeStore();
const messages = ref<ChatMessage[]>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const currentXml = ref<string>('');
const diagramEditor = new DiagramEditor();
const messagesContainerRef = ref<HTMLElement | null>(null);
const drawioIframeRef = ref<HTMLIFrameElement | null>(null);
const drawioReady = ref(false);
const pendingXml = ref<string>('');
const promptInitialized = ref(false);  // 标记提示词是否已初始化
const iframeLoading = ref(true);  // iframe 加载状态
const showChatPanel = ref(false);  // 控制聊天面板显示
const pendingMessageResolve = ref<((xml: string) => void) | null>(null);  // 等待 XML 导出的回调
const sessionId = ref<string>('');  // 会话ID，用于保持对话上下文
const contextTokenCount = ref<number>(0);  // 上下文 Token 使用量
const contextLimit = ref<number>(200000);  // 上下文 Token 限制

// ⭐ HITL 工具审批相关
const toolApprovalDialogVisible = ref(false);
const currentInterrupt = ref<InterruptEvent | null>(null);
const threadId = ref<string>('');  // 线程ID，用于恢复执行

// localStorage 键名
const STORAGE_KEY = 'ai-diagram-data';

// 保存数据到 localStorage
const saveToStorage = () => {
  const data = {
    currentXml: currentXml.value,
    messages: messages.value.filter(m => !m.isLoading),  // 不保存加载状态的消息
    sessionId: sessionId.value  // 保存会话ID
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

// 从 localStorage 恢复数据
const loadFromStorage = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const data = JSON.parse(saved);
      if (data.currentXml) {
        currentXml.value = data.currentXml;
        pendingXml.value = data.currentXml;  // 标记需要在 Draw.io 就绪后加载
      }
      if (data.messages?.length) {
        messages.value = data.messages;
      }
      if (data.sessionId) {
        sessionId.value = data.sessionId;  // 恢复会话ID
      }
    }
  } catch (e) {
    console.warn('加载保存的图表数据失败:', e);
  }
};

// Draw.io URL 配置
// 支持自托管：设置环境变量 VITE_DRAWIO_URL 为自托管地址，如 http://localhost:8920
// 生产环境可使用相对路径如 /drawio，通过 Nginx 反向代理
// 默认使用官方 embed 服务
const DRAWIO_ENV_URL = import.meta.env.VITE_DRAWIO_URL || 'https://embed.diagrams.net';
const DRAWIO_PUBLIC_URL = 'https://app.diagrams.net';  // 公共托底服务

// 处理相对路径：转换为完整 URL
const getFullUrl = (url: string) => {
  return url.startsWith('/') ? `${window.location.origin}${url}` : url;
};

// 当前使用的 Draw.io 服务 URL（支持托底切换）
const currentDrawioBaseUrl = ref(getFullUrl(DRAWIO_ENV_URL));
const DRAWIO_ORIGIN = computed(() => new URL(currentDrawioBaseUrl.value).origin);
const isFallbackMode = ref(false);  // 是否已切换到托底服务
const loadAttempts = ref(0);  // 加载尝试次数
let loadTimeoutId: ReturnType<typeof setTimeout> | null = null;

// Draw.io URL (使用 embed 模式，启用自动保存)
const drawioUi = ref(themeStore.isBlack ? 'dark' : 'kennedy');

const drawioUrl = computed(() => {
  const params = new URLSearchParams({
    embed: '1',
    spin: '1',
    proto: 'json',
    ui: drawioUi.value,
    noExitBtn: '1',  // 隐藏退出按钮
    autosave: '1',   // 启用自动保存
    math: '0'        // 禁用数学公式插件（避免 404 错误）
  });
  return `${currentDrawioBaseUrl.value}/?${params.toString()}`;
});

watch(
  () => themeStore.isBlack,
  async (isBlack) => {
    const nextUi = isBlack ? 'dark' : 'kennedy';
    if (drawioUi.value === nextUi) {
      return;
    }

    const latestXml = await getCurrentXmlFromDrawio();
    currentXml.value = latestXml;
    pendingXml.value = latestXml;
    drawioReady.value = false;
    iframeLoading.value = true;

    drawioUi.value = nextUi;
  }
);

// 从 Draw.io 获取最新的 XML（异步）
const getCurrentXmlFromDrawio = (): Promise<string> => {
  return new Promise((resolve) => {
    if (!drawioReady.value || !drawioIframeRef.value) {
      resolve(currentXml.value);
      return;
    }
    
    pendingMessageResolve.value = resolve;
    
    // 请求导出 XML
    sendDrawioMessage({
      action: 'export',
      format: 'xml'
    });
    
    // 设置超时，防止永久等待
    setTimeout(() => {
      if (pendingMessageResolve.value) {
        pendingMessageResolve.value = null;
        resolve(currentXml.value);
      }
    }, 3000);
  });
};

// 检查并初始化提示词
const checkAndInitializePrompt = async () => {
  try {
    const promptResponse = await getPromptByType('diagram_generation');
    if (promptResponse.data?.id) {
      promptInitialized.value = true;
      return true;
    }
    
    // 提示词不存在，询问用户是否初始化
    return new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: '提示词未初始化',
        content: '图表生成功能需要先初始化系统提示词。是否立即初始化？',
        okText: '初始化',
        cancelText: '取消',
        onOk: async () => {
          try {
            Message.loading({ content: '正在初始化提示词...', id: 'init-prompt' });
            const initResult = await initializeUserPrompts(false);
            if (initResult.status === 'success') {
              Message.success({ content: '提示词初始化成功！', id: 'init-prompt' });
              promptInitialized.value = true;
              resolve(true);
            } else {
              Message.error({ content: '初始化失败：' + initResult.message, id: 'init-prompt' });
              resolve(false);
            }
          } catch (error: any) {
            Message.error({ content: '初始化失败：' + error.message, id: 'init-prompt' });
            resolve(false);
          }
        },
        onCancel: () => {
          resolve(false);
        }
      });
    });
  } catch (error) {
    console.error('检查提示词失败:', error);
    return false;
  }
};

// 格式化消息内容 (支持 Markdown)
const formatMessage = (content: string): string => {
  return marked.parse(content) as string;
};

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
    }
  });
};

// 处理 Enter 键
const handleEnterKey = (e: KeyboardEvent) => {
  if (e.shiftKey) {
    return; // Shift+Enter 换行
  }
  sendMessage();
};

// 发送消息
const sendMessage = async () => {
  const message = inputMessage.value.trim();
  if (!message || isLoading.value) return;

  // 检查提示词是否初始化
  if (!promptInitialized.value) {
    const initialized = await checkAndInitializePrompt();
    if (!initialized) {
      Message.warning('请先初始化图表生成提示词');
      return;
    }
  }

  // 添加用户消息
  messages.value.push({ content: message, isUser: true });
  inputMessage.value = '';
  scrollToBottom();

  // 添加 AI 加载状态
  messages.value.push({ content: '', isUser: false, isLoading: true });
  isLoading.value = true;

  try {
    // 先从 Draw.io 获取最新的 XML（包含用户手动创建的页面和修改）
    const latestXml = await getCurrentXmlFromDrawio();
    
    // 获取图表生成提示词的 ID
    const promptResponse = await getPromptByType('diagram_generation');
    const promptId = promptResponse?.data?.id || null;

    // 构建消息 - 如果有当前图表，在消息中附加
    let fullMessage = message;
    if (latestXml) {
      fullMessage = `${message}\n\n【当前图表 XML】:\n${latestXml}`;
    }

    // 构建请求体（包含 session_id 以保持对话上下文）
    const requestBody: Record<string, unknown> = {
      message: fullMessage,
      project_id: projectStore.currentProjectId,
      prompt_id: promptId,
      use_knowledge_base: false  // 图表生成不需要知识库
    };
    
    // 如果有会话ID，传递给后端以继续同一对话
    if (sessionId.value) {
      requestBody.session_id = sessionId.value;
    }

    // 调用后端 API (使用 orchestrator 端点)
    const token = localStorage.getItem('auth-accessToken');
    const response = await fetch('/api/orchestrator/agent-loop/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // 处理流式响应
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    let aiContent = '';
    let buffer = '';
    let streamingMsgIndex = -1;  // 记录正在流式输出的消息索引
    let currentStep = 0;  // 当前步骤

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;

        const jsonData = line.slice(6);
        if (jsonData === '[DONE]') {
          // 流结束，移除光标
          if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
            messages.value[streamingMsgIndex].isStreaming = false;
          }
          continue;
        }

        try {
          const parsed = JSON.parse(jsonData);
          
          console.log('[Diagram] Event type:', parsed.type);
          
          // 处理开始事件，获取 session_id 和 thread_id
          if (parsed.type === 'start') {
            console.log('[Diagram] Start event received:', parsed);
            if (parsed.session_id) {
              sessionId.value = parsed.session_id;
            }
            if (parsed.thread_id) {
              threadId.value = parsed.thread_id;
            }
            saveToStorage();  // 保存会话ID
            continue;
          }
          
          // 处理上下文更新事件
          if (parsed.type === 'context_update') {
            contextTokenCount.value = parsed.context_token_count || 0;
            if (parsed.context_limit) {
              contextLimit.value = parsed.context_limit;
            }
            continue;
          }
          
          // ⭐ 处理 HITL 中断事件（工具审批）
          if (parsed.type === 'interrupt') {
            console.log('[Diagram] Interrupt event received:', parsed);
            // 保存 thread_id（可能与 session_id 不同）
            if (parsed.thread_id) {
              threadId.value = parsed.thread_id;
            }

            // 检查是否所有工具都需要自动拒绝
            const actionRequests = parsed.action_requests || [];
            const allAutoReject = actionRequests.length > 0 &&
              actionRequests.every((ar: { auto_reject?: boolean }) => ar.auto_reject === true);

            // 构造 InterruptEvent 对象
            currentInterrupt.value = {
              id: parsed.interrupt_id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || []
            };

            if (allAutoReject) {
              // 所有工具都设为"始终拒绝"，自动发送拒绝响应
              console.log('[Diagram] All tools marked as auto_reject, sending auto-reject');
              const toolNames = actionRequests.map((ar: { name?: string }) => ar.name || 'unknown').join(', ');
              Message.warning(`工具 ${toolNames} 已被设为始终拒绝，自动拒绝执行`);

              // 延迟自动拒绝，等待当前 SSE 流完全结束
              setTimeout(() => {
                handleToolDecision({
                  interruptId: parsed.interrupt_id,
                  type: 'reject',
                });
              }, 100);
              isLoading.value = false;
              continue;
            }

            // 显示审批对话框
            toolApprovalDialogVisible.value = true;
            // 停止当前加载状态，等待用户审批
            isLoading.value = false;
            continue;
          }
          
          // 步骤开始事件
          if (parsed.type === 'step_start') {
            currentStep = parsed.step || (currentStep + 1);
            // 如果有正在流式输出的消息，停止它
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
            }
            // 移除当前存在的空加载消息（sendMessage 添加的初始加载消息）
            const lastMsgIdx = messages.value.length - 1;
            if (lastMsgIdx >= 0 && messages.value[lastMsgIdx].isLoading && !messages.value[lastMsgIdx].content) {
              messages.value.pop();
            }
            // 添加步骤分隔符
            messages.value.push({
              content: '',
              isUser: false,
              messageType: 'step',
              stepNumber: currentStep,
              maxSteps: parsed.max_steps
            });
            // 添加新的加载消息
            messages.value.push({
              content: '',
              isUser: false,
              isLoading: true,
              messageType: 'ai'
            });
            // 重置 AI 内容，准备接收新步骤的消息
            aiContent = '';
            streamingMsgIndex = messages.value.length - 1;
            scrollToBottom();
          }
          
          // ⭐ 处理真正的流式输出 (type === 'stream')
          if (parsed.type === 'stream' && parsed.data) {
            aiContent += parsed.data;
            // 找到最后一条非步骤的 AI 消息
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && !lastMsg.isUser && lastMsg.messageType !== 'step' && lastMsg.messageType !== 'tool') {
              // 直接追加内容，取消加载状态，标记为流式输出
              lastMsg.content = aiContent;
              lastMsg.isLoading = false;
              lastMsg.isStreaming = true;
              streamingMsgIndex = messages.value.length - 1;
            } else {
              // 没有合适的 AI 消息，添加新的
              messages.value.push({ content: aiContent, isUser: false, isStreaming: true, messageType: 'ai' });
              streamingMsgIndex = messages.value.length - 1;
            }
            scrollToBottom();
          }
          
          // ⭐ 流式结束事件
          if (parsed.type === 'stream_end') {
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
              messages.value[streamingMsgIndex].isLoading = false;
            }
          }
          
          // 兼容旧的 message 类型（非流式模式下的完整消息）
          if (parsed.type === 'message' && parsed.data) {
            aiContent += parsed.data;
            // 找到最后一条非步骤的 AI 消息
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && !lastMsg.isUser && lastMsg.messageType !== 'step' && lastMsg.messageType !== 'tool') {
              // 直接追加内容，取消加载状态，标记为流式输出
              lastMsg.content = aiContent;
              lastMsg.isLoading = false;
              lastMsg.isStreaming = true;
              streamingMsgIndex = messages.value.length - 1;
            } else {
              // 没有合适的 AI 消息，添加新的
              messages.value.push({ content: aiContent, isUser: false, isStreaming: true, messageType: 'ai' });
              streamingMsgIndex = messages.value.length - 1;
            }
            scrollToBottom();
          }
          
          // 完成事件，移除光标和加载状态
          if (parsed.type === 'complete' || parsed.type === 'step_complete') {
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
              messages.value[streamingMsgIndex].isLoading = false;
            }
            // 移除所有空的加载消息
            messages.value = messages.value.filter(m => !(m.isLoading && !m.content));
          }

          // 处理工具调用 (tool_call 事件)
          if (parsed.type === 'tool_call') {
            // 工具调用时，停止当前消息的流式输出和加载状态
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
              // 如果消息为空且是加载状态，移除它
              if (messages.value[streamingMsgIndex].isLoading && !messages.value[streamingMsgIndex].content) {
                messages.value.splice(streamingMsgIndex, 1);
                streamingMsgIndex = -1;
              }
            }
            handleToolCall(parsed);
          }

          // 处理工具结束事件 (tool_end 或 tool_result)
          if (parsed.type === 'tool_end' || parsed.type === 'tool_result') {
            handleToolEnd(parsed);
          }
        } catch (parseError) {
          console.warn('解析响应失败:', parseError);
        }
      }
    }

    // 移除所有剩余的加载消息
    messages.value = messages.value.filter(m => !(m.isLoading && !m.content));
    
    // 确保所有消息的 isStreaming 都设置为 false（停止光标闪烁）
    messages.value.forEach(m => {
      if (m.isStreaming) {
        m.isStreaming = false;
      }
    });
    
    // 如果没有 AI 内容，添加默认消息
    if (!aiContent && messages.value[messages.value.length - 1]?.isUser) {
      messages.value.push({ content: '图表已更新，请查看右侧预览。', isUser: false });
    }

  } catch (error: any) {
    console.error('发送消息失败:', error);
    // 移除加载状态
    const lastMsg = messages.value[messages.value.length - 1];
    if (lastMsg?.isLoading) {
      messages.value.pop();
    }
    messages.value.push({ 
      content: `❌ 发送失败: ${error.message || '未知错误'}`, 
      isUser: false 
    });
  } finally {
    isLoading.value = false;
    scrollToBottom();
    saveToStorage();  // 保存对话消息到 localStorage
  }
};

// ⭐ 处理工具审批决策
const handleToolDecision = async (decision: {
  interruptId: string;
  type: 'approve' | 'reject';
  rememberChoice?: boolean;
  rememberScope?: string;
  toolName?: string;
}) => {
  console.log('[Diagram] handleToolDecision:', decision);
  
  // 关闭审批对话框
  toolApprovalDialogVisible.value = false;
  currentInterrupt.value = null;
  
  // 如果是拒绝，添加拒绝消息
  if (decision.type === 'reject') {
    messages.value.push({
      content: '❌ 工具调用已被拒绝',
      isUser: false,
      messageType: 'ai'
    });
    scrollToBottom();
    return;
  }
  
  // 批准后恢复执行
  try {
    isLoading.value = true;
    // 添加已批准的提示消息
    messages.value.push({
      content: '✅ 工具调用已批准，正在继续执行...',
      isUser: false,
      isLoading: true,
      messageType: 'ai'
    });
    scrollToBottom();
    
    // 调用 resume API 恢复执行 - 使用后端期望的格式
    // 后端期望: { resume: { [interrupt_id]: { decisions: [{type: 'approve'}], action_count: n } } }
    const actionCount = currentInterrupt.value?.action_requests?.length || 1;
    const resumePayload: Record<string, any> = {
      session_id: sessionId.value,
      project_id: projectStore.currentProjectId,
      resume: {
        [decision.interruptId]: {
          decisions: [{ type: decision.type }],
          action_count: actionCount
        }
      }
    };
    
    const response = await fetch('/api/orchestrator/agent-loop/resume/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth-accessToken')}`
      },
      body: JSON.stringify(resumePayload)
    });
    
    if (!response.ok) {
      throw new Error(`Resume failed: ${response.status}`);
    }
    
    // 处理流式响应（与 sendMessage 类似的逻辑）
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiContent = '';
    let currentStep = 0;
    let streamingMsgIndex = -1;
    
    // 移除"已批准"消息的加载状态
    const lastMsg = messages.value[messages.value.length - 1];
    if (lastMsg && lastMsg.isLoading) {
      lastMsg.isLoading = false;
      lastMsg.content = '✅ 工具调用已批准，继续执行...';
    }
    
    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonData = line.slice(6).trim();
        if (!jsonData || jsonData === '[DONE]') continue;
        
        try {
          const parsed = JSON.parse(jsonData);
          console.log('[Diagram Resume] Event type:', parsed.type);
          
          // 处理上下文更新事件
          if (parsed.type === 'context_update') {
            contextTokenCount.value = parsed.context_token_count || 0;
            continue;
          }
          
          // 再次遇到 interrupt 事件（嵌套工具审批）
          if (parsed.type === 'interrupt') {
            console.log('[Diagram Resume] Interrupt event received:', parsed);
            if (parsed.thread_id) {
              threadId.value = parsed.thread_id;
            }
            currentInterrupt.value = {
              id: parsed.interrupt_id,
              action_requests: parsed.action_requests || []
            };
            toolApprovalDialogVisible.value = true;
            isLoading.value = false;
            return;  // 中断当前流处理，等待下一次审批
          }
          
          // 步骤开始事件
          if (parsed.type === 'step_start') {
            currentStep = parsed.step || (currentStep + 1);
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
            }
            messages.value.push({
              content: '',
              isUser: false,
              messageType: 'step',
              stepNumber: currentStep,
              maxSteps: parsed.max_steps
            });
            messages.value.push({
              content: '',
              isUser: false,
              isLoading: true,
              messageType: 'ai'
            });
            aiContent = '';
            streamingMsgIndex = messages.value.length - 1;
            scrollToBottom();
          }
          
          // 处理流式输出
          if (parsed.type === 'stream' && parsed.data) {
            aiContent += parsed.data;
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && !lastMsg.isUser && lastMsg.messageType !== 'step' && lastMsg.messageType !== 'tool') {
              lastMsg.content = aiContent;
              lastMsg.isLoading = false;
              lastMsg.isStreaming = true;
              streamingMsgIndex = messages.value.length - 1;
            } else {
              messages.value.push({ content: aiContent, isUser: false, isStreaming: true, messageType: 'ai' });
              streamingMsgIndex = messages.value.length - 1;
            }
            scrollToBottom();
          }
          
          // 流式结束
          if (parsed.type === 'stream_end' || parsed.type === 'complete') {
            if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
              messages.value[streamingMsgIndex].isStreaming = false;
              messages.value[streamingMsgIndex].isLoading = false;
            }
          }
          
          // 处理工具结果
          if (parsed.type === 'tool_end' || parsed.type === 'tool_result') {
            handleToolEnd(parsed);
          }
        } catch (parseError) {
          console.warn('[Diagram Resume] Parse error:', parseError);
        }
      }
    }
    
    // 清理加载状态
    messages.value = messages.value.filter(m => !(m.isLoading && !m.content));
    
    // 确保所有消息的 isStreaming 都设置为 false（停止光标闪烁）
    messages.value.forEach(m => {
      if (m.isStreaming) {
        m.isStreaming = false;
      }
    });
    
  } catch (error: any) {
    console.error('[Diagram] Resume failed:', error);
    messages.value.push({
      content: `❌ 恢复执行失败: ${error.message || '未知错误'}`,
      isUser: false,
      messageType: 'ai'
    });
  } finally {
    isLoading.value = false;
    scrollToBottom();
  }
};

// 处理工具调用（注意：当前后端不发送 tool_call 事件，此函数仅为兼容保留）
const handleToolCall = (data: any) => {
  console.log('[Diagram] Tool call started:', data.tool_name);
};

// 处理工具结束事件
const handleToolEnd = (data: any) => {
  console.log('[Diagram] handleToolEnd called with:', JSON.stringify(data).substring(0, 300));
  
  // 移除正在加载的空消息（如果有）
  const lastIdx = messages.value.length - 1;
  if (lastIdx >= 0 && messages.value[lastIdx].isLoading && !messages.value[lastIdx].content) {
    messages.value.pop();
  }
  
  // 兼容 tool_end 和 tool_result 两种格式
  // tool_end 结构：{ tool_name, tool_output }
  // tool_result 结构：{ tool_name, tool_output } 或 { summary: "tool_name:\n{json}\n\nother_tool: 失败 - xxx" }
  let tool_name = '';
  let tool_output = '';

  if (data.tool_name) {
    // 新格式：直接包含 tool_name
    tool_name = data.tool_name;
    tool_output = data.tool_output || data.summary || '';
  } else if (data.summary) {
    // 旧格式：summary 可能包含多个工具结果，用 \n\n 分隔
    // 尝试直接解析为 JSON（如果是纯 JSON 字符串）
    try {
      const parsed = JSON.parse(data.summary);
      if (parsed.action === 'display' || parsed.action === 'edit') {
        tool_name = parsed.action === 'display' ? 'display_diagram' : 'edit_diagram';
        tool_output = data.summary;
      }
    } catch {
      // 不是纯 JSON，尝试匹配 "tool_name:\n{json}" 格式
      const tools = data.summary.split(/\n\n+/);
      for (const toolStr of tools) {
        const match = toolStr.match(/^(\w+):\s*\n?(.*)$/s);
        if (match && (match[1] === 'display_diagram' || match[1] === 'edit_diagram')) {
          tool_name = match[1];
          tool_output = match[2].trim();
          tool_output = tool_output.replace(/\\\\"/g, '\\"').replace(/\\\\n/g, '\\n');
          break;
        }
      }
    }
  }

  console.log('[Diagram] Tool end:', tool_name);
  console.log('[Diagram] Tool output (first 200 chars):', typeof tool_output === 'string' ? tool_output.substring(0, 200) : JSON.stringify(tool_output).substring(0, 200));

  if (!tool_name) return;
  
  try {
    // 处理 MCP 工具返回的数组格式: [{"type": "text", "text": "{...}"}]
    let resultStr = tool_output;
    if (Array.isArray(tool_output)) {
      // 从数组中提取第一个 text 类型的内容
      const textItem = tool_output.find((item: any) => item.type === 'text' && item.text);
      resultStr = textItem?.text || JSON.stringify(tool_output[0]);
    }
    
    let result = typeof resultStr === 'string' ? JSON.parse(resultStr) : resultStr;
    
    // 处理转义字符的辅助函数
    const unescapeXml = (xml: string): string => {
      if (typeof xml === 'string' && xml.includes('\\')) {
        return xml.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
      }
      return xml;
    };
    
    // 如果 xml 仍然有转义字符，尝试再次解析
    if (result.xml && typeof result.xml === 'string') {
      result.xml = unescapeXml(result.xml);
    }
    
    // 处理 operations 中的 pageXml 转义字符（用于 edit_diagram）
    if (result.operations && Array.isArray(result.operations)) {
      result.operations = result.operations.map((op: any) => {
        if (op.pageXml && typeof op.pageXml === 'string') {
          op.pageXml = unescapeXml(op.pageXml);
        }
        return op;
      });
    }
    
    console.log('[Diagram] Parsed result:', result.success, 'xml length:', result.xml?.length);
    
    // 查找对应的工具调用消息并更新它
    const toolMsgIndex = messages.value.findIndex(
      m => m.messageType === 'tool' && m.toolName === tool_name && m.isLoading
    );
    
    if (tool_name === 'display_diagram') {
      if (result.success && result.xml) {
        // 如果指定了页面名称，添加为新页面；否则替换现有图表
        if (result.page_name) {
          addNewPage(result.xml, result.page_name);
        } else {
          updateDiagram(result.xml);
        }
        // 更新工具调用消息的内容
        const msg = result.page_name 
          ? `已在新页面 "${result.page_name}" 生成图表，请查看预览` 
          : '已生成图表，请查看预览';
        
        if (toolMsgIndex >= 0) {
          // 更新现有的工具消息
          messages.value[toolMsgIndex].content = msg;
          messages.value[toolMsgIndex].isLoading = false;
        } else {
          // 没找到对应的工具消息，添加新的
          messages.value.push({
            content: msg,
            isUser: false,
            messageType: 'tool',
            toolName: 'display_diagram'
          });
        }
        scrollToBottom();
        Message.success('图表创建成功');
      } else if (result.error) {
        const errorMsg = `图表创建失败: ${result.error}`;
        if (toolMsgIndex >= 0) {
          messages.value[toolMsgIndex].content = errorMsg;
          messages.value[toolMsgIndex].isLoading = false;
        } else {
          messages.value.push({
            content: errorMsg,
            isUser: false,
            messageType: 'tool',
            toolName: 'display_diagram'
          });
        }
        scrollToBottom();
        Message.error(`图表创建失败: ${result.error}`);
      }
    } else if (tool_name === 'edit_diagram') {
      console.log('[Diagram] Processing edit_diagram, operations:', result.operations?.length, 'edits:', result.edits?.length);
      // 支持新的 operations 格式和旧的 edits 格式
      if (result.success && (result.operations || result.edits)) {
        const editResult = result.operations 
          ? applyOperations(result.operations)
          : applyEdits(result.edits);
        
        console.log('[Diagram] Edit result:', editResult);
        
        if (editResult.success) {
          if (toolMsgIndex >= 0) {
            messages.value[toolMsgIndex].content = editResult.message;
            messages.value[toolMsgIndex].isLoading = false;
          } else {
            messages.value.push({
              content: editResult.message,
              isUser: false,
              messageType: 'tool',
              toolName: 'edit_diagram'
            });
          }
          scrollToBottom();
          Message.success('图表编辑成功');
        } else {
          const errorMsg = `图表编辑失败: ${editResult.message}`;
          if (toolMsgIndex >= 0) {
            messages.value[toolMsgIndex].content = errorMsg;
            messages.value[toolMsgIndex].isLoading = false;
          } else {
            messages.value.push({
              content: errorMsg,
              isUser: false,
              messageType: 'tool',
              toolName: 'edit_diagram'
            });
          }
          scrollToBottom();
          Message.warning(editResult.message);
        }
      } else if (result.error) {
        messages.value.push({
          content: `图表编辑失败: ${result.error}`,
          isUser: false,
          messageType: 'tool',
          toolName: 'edit_diagram'
        });
        scrollToBottom();
        Message.error(`图表编辑失败: ${result.error}`);
      }
    }
  } catch (e) {
    console.warn('解析工具输出失败:', e, typeof tool_output === 'string' ? tool_output.substring(0, 500) : tool_output);
  }
};

// 应用新的操作格式（企业级 DOM 操作）
const applyOperations = (operations: EditOperation[]): { success: boolean; message: string } => {
  if (!currentXml.value) {
    return { success: false, message: '没有可编辑的图表' };
  }

  console.log('[Diagram] Applying operations:', operations.length);

  // 加载当前 XML 到编辑器
  if (!diagramEditor.load(currentXml.value)) {
    return { success: false, message: 'XML 解析失败' };
  }

  // 应用操作
  const result = diagramEditor.applyOperations(operations);
  
  console.log('[Diagram] Operations result:', result);

  if (result.success && result.xml) {
    updateDiagram(result.xml);
  }

  return {
    success: result.success,
    message: result.message
  };
};

// 添加新页面到现有图表
const addNewPage = (newPageXml: string, pageName: string) => {
  // 生成唯一 ID
  const pageId = `page-${Date.now()}`;
  
  // 将 mxGraphModel 包装成 diagram 元素
  const diagramElement = `<diagram name="${pageName}" id="${pageId}">${newPageXml}</diagram>`;
  
  let finalXml = '';
  
  if (!currentXml.value) {
    // 没有现有图表，创建新的 mxfile
    finalXml = `<mxfile>${diagramElement}</mxfile>`;
  } else if (currentXml.value.includes('<mxfile')) {
    // 已有 mxfile 结构，在 </mxfile> 前插入新页面
    finalXml = currentXml.value.replace('</mxfile>', `${diagramElement}</mxfile>`);
  } else if (currentXml.value.includes('<mxGraphModel')) {
    // 只有单个 mxGraphModel，转换为多页面结构
    const firstPageId = `page-${Date.now() - 1}`;
    finalXml = `<mxfile><diagram name="Page-1" id="${firstPageId}">${currentXml.value}</diagram>${diagramElement}</mxfile>`;
  } else {
    // 未知格式，直接替换
    finalXml = `<mxfile>${diagramElement}</mxfile>`;
  }
  
  updateDiagram(finalXml);
  Message.success(`已添加新页面: ${pageName}`);
};

// 更新图表
const updateDiagram = (xml: string) => {
  currentXml.value = xml;
  
  if (drawioReady.value && drawioIframeRef.value) {
    sendDrawioMessage({
      action: 'load',
      xml: xml
    });
  } else {
    pendingXml.value = xml;
  }
  
  // 保存到 localStorage
  nextTick(() => saveToStorage());
};

// 应用编辑操作（旧格式兼容）
const applyEdits = (edits: Array<{ search: string; replace: string }>): { success: boolean; message: string } => {
  if (!currentXml.value) {
    return { success: false, message: '没有可编辑的图表' };
  }

  console.log('[Diagram] Applying edits:', edits.length, 'operations');
  console.log('[Diagram] Current XML length:', currentXml.value.length);

  let newXml = currentXml.value;
  let appliedCount = 0;
  
  for (const edit of edits) {
    // 处理可能的转义字符
    let searchStr = edit.search.replace(/\\n/g, '\n').replace(/\\"/g, '"');
    let replaceStr = edit.replace.replace(/\\n/g, '\n').replace(/\\"/g, '"');
    
    // 尝试多种匹配策略
    let matched = false;
    
    // 策略1：精确匹配
    if (newXml.includes(searchStr)) {
      newXml = newXml.replace(searchStr, replaceStr);
      matched = true;
    }
    
    // 策略2：忽略空白差异的匹配
    if (!matched) {
      const normalizedSearch = searchStr.replace(/\s+/g, ' ').trim();
      const normalizedXml = newXml.replace(/\s+/g, ' ');
      if (normalizedXml.includes(normalizedSearch)) {
        // 使用正则表达式进行更宽松的匹配
        const escapeRegex = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regexPattern = searchStr.split(/\s+/).map(escapeRegex).join('\\s*');
        const regex = new RegExp(regexPattern, 's');
        if (regex.test(newXml)) {
          newXml = newXml.replace(regex, replaceStr);
          matched = true;
        }
      }
    }
    
    // 策略3：如果搜索包含元素 ID，尝试替换该元素
    if (!matched) {
      const idMatch = searchStr.match(/id="([^"]+)"/);
      if (idMatch) {
        const elementId = idMatch[1];
        // 尝试查找并替换整个元素
        const elementRegex = new RegExp(`<mxCell[^>]*id="${elementId}"[^>]*>(?:[^<]*<[^>]+>[^<]*)*</mxCell>|<mxCell[^>]*id="${elementId}"[^/]*/>`);
        if (elementRegex.test(newXml)) {
          console.log('[Diagram] Using ID-based replacement for:', elementId);
          // 只替换匹配的元素，需要从 replace 中提取对应的新元素
          const replaceIdMatch = replaceStr.match(new RegExp(`<mxCell[^>]*id="[^"]*"[^>]*>(?:[^<]*<[^>]+>[^<]*)*</mxCell>|<mxCell[^>]*id="[^"]*"[^/]*/>`));
          if (replaceIdMatch) {
            newXml = newXml.replace(elementRegex, replaceIdMatch[0]);
            matched = true;
          }
        }
      }
    }
    
    if (matched) {
      appliedCount++;
      console.log('[Diagram] Edit applied successfully');
    } else {
      console.warn('[Diagram] Search string not found in XML');
      console.log('[Diagram] Search (first 200 chars):', searchStr.substring(0, 200));
    }
  }
  
  console.log('[Diagram] Applied', appliedCount, 'of', edits.length, 'edits');
  
  if (appliedCount > 0) {
    updateDiagram(newXml);
    return { success: true, message: `图表已更新，应用了 ${appliedCount}/${edits.length} 个编辑` };
  } else {
    return { success: false, message: '编辑操作未能匹配到图表内容，建议使用 replace_page 操作重新生成页面' };
  }
};

// 发送消息到 Draw.io iframe
const sendDrawioMessage = (msg: any) => {
  if (drawioIframeRef.value?.contentWindow) {
    drawioIframeRef.value.contentWindow.postMessage(JSON.stringify(msg), '*');
  }
};

// 切换到公共托底服务
const fallbackToPublicService = () => {
  if (isFallbackMode.value) return;  // 已经是托底模式，不再切换
  
  console.warn('[Draw.io] 自托管服务不可用，切换到公共服务');
  isFallbackMode.value = true;
  currentDrawioBaseUrl.value = DRAWIO_PUBLIC_URL;
  drawioReady.value = false;
  iframeLoading.value = true;
  loadAttempts.value = 0;
  
  Message.warning({
    content: 'Draw.io 自托管服务不可用，已自动切换到公共服务',
    duration: 3000
  });
};

// 启动加载超时检测
const startLoadTimeout = () => {
  // 清除之前的超时
  if (loadTimeoutId) {
    clearTimeout(loadTimeoutId);
  }
  
  // 设置 10 秒超时
  loadTimeoutId = setTimeout(() => {
    if (!drawioReady.value && !isFallbackMode.value) {
      console.warn('[Draw.io] 加载超时，尝试切换到公共服务');
      loadAttempts.value++;
      if (loadAttempts.value >= 2) {
        fallbackToPublicService();
      }
    }
  }, 10000);
};

// iframe 加载完成
const onIframeLoad = () => {
  console.log('Draw.io iframe loaded');
  iframeLoading.value = false;
  
  // 启动超时检测（等待 Draw.io init 消息）
  startLoadTimeout();
};

// 处理来自 Draw.io 的消息
const handleDrawioMessage = (event: MessageEvent) => {
  // 验证消息来源是配置的 Draw.io 服务
  if (event.origin !== DRAWIO_ORIGIN.value) return;

  try {
    const msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
    
    if (msg.event === 'init') {
      // 清除超时检测
      if (loadTimeoutId) {
        clearTimeout(loadTimeoutId);
        loadTimeoutId = null;
      }
      drawioReady.value = true;
      // Draw.io embed 初始化后必须发送 load 消息才能显示编辑器
      const xmlToLoad = pendingXml.value || '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>';
      sendDrawioMessage({
        action: 'load',
        xml: xmlToLoad
      });
      if (pendingXml.value) {
        currentXml.value = pendingXml.value;
        pendingXml.value = '';
      }
    } else if (msg.event === 'save') {
      // 用户在 Draw.io 中保存了图表
      currentXml.value = msg.xml;
      saveToStorage();
    } else if (msg.event === 'autosave') {
      // 自动保存事件 - Draw.io 在内容变化时自动发送
      if (msg.xml) {
        currentXml.value = msg.xml;
        saveToStorage();
        console.log('[Diagram] Autosave: XML updated');
      }
    } else if (msg.event === 'export') {
      // 导出完成
      if (msg.format === 'xml') {
        // XML 导出 - 更新内容
        if (msg.data) {
          currentXml.value = msg.data;
          saveToStorage();
        }
        // 如果有等待的回调，调用它
        if (pendingMessageResolve.value) {
          pendingMessageResolve.value(msg.data || currentXml.value);
          pendingMessageResolve.value = null;
        }
      }
      // 注意：不再自动下载 PNG，用户需要手动点击导出按钮
    }
  } catch (e) {
    // 忽略非 JSON 消息
  }
};

// 导出图表
const exportDiagram = () => {
  if (!currentXml.value) return;
  
  // 导出为 XML 文件
  const blob = new Blob([currentXml.value], { type: 'application/xml' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.download = 'diagram.drawio';
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
  
  Message.success('图表已导出');
};

// 在 Draw.io 中打开
const openInDrawio = () => {
  if (!currentXml.value) return;
  
  // 使用 Draw.io 的打开功能
  const encoded = encodeURIComponent(currentXml.value);
  const url = `https://app.diagrams.net/?splash=0#R${encoded}`;
  window.open(url, '_blank');
};

// 新建对话（仅清空对话历史，保留图表）
const newChat = () => {
  messages.value = [];
  sessionId.value = '';  // 清除会话ID以开始新对话
  saveToStorage();
  Message.success('已开始新对话');
};

// 清空对话和图表
const clearChat = () => {
  messages.value = [];
  sessionId.value = '';  // 清除会话ID
  currentXml.value = '';
  pendingXml.value = '';
  // 清除 localStorage
  localStorage.removeItem(STORAGE_KEY);
  // 重置 Draw.io 为空白图表
  if (drawioReady.value && drawioIframeRef.value) {
    sendDrawioMessage({
      action: 'load',
      xml: '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>'
    });
  }
};

// 生命周期
onMounted(async () => {
  window.addEventListener('message', handleDrawioMessage);
  
  // 从 localStorage 恢复数据
  loadFromStorage();
  
  // 启动初始加载超时检测
  startLoadTimeout();
  
  // 页面加载时检查提示词是否存在
  await checkAndInitializePrompt();
  
  // 页面离开前保存最新内容
  window.addEventListener('beforeunload', handleBeforeUnload);
});

// 页面离开前同步保存
const handleBeforeUnload = () => {
  saveToStorage();
};

onUnmounted(() => {
  window.removeEventListener('message', handleDrawioMessage);
  window.removeEventListener('beforeunload', handleBeforeUnload);
  // 清除超时检测
  if (loadTimeoutId) {
    clearTimeout(loadTimeoutId);
  }
});
</script>

<style scoped>
.diagram-container {
  position: relative;
  height: calc(100vh - 86px - 20px);
  padding: 16px;
  background: var(--color-bg-1);
  box-sizing: border-box;
  overflow: hidden;
}

/* 图表面板 - 全屏 */
.diagram-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-2);
  border-radius: 8px;
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.diagram-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.diagram-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.diagram-content {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.drawio-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

/* 悬浮 AI 按钮 */
.chat-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50% !important;
  font-size: 22px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
}

/* AI 对话弹窗面板 */
.chat-popup {
  position: fixed;
  right: 24px;
  bottom: 90px;
  width: 400px;
  height: 500px;
  max-height: calc(100vh - 200px);
  background: var(--color-bg-2);
  border-radius: 12px;
  border: 1px solid var(--color-border);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  z-index: 999;
  overflow: hidden;
}

.chat-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-3);
}

.chat-popup-header h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
}

/* 消息区域 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-text-3);
  text-align: center;
}

.empty-state p {
  margin: 8px 0 0;
}

.empty-state .hint {
  font-size: 12px;
  color: var(--color-text-4);
}

/* 消息样式 */
.message {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  justify-content: flex-start; /* 消息靠左对齐 */
  align-items: flex-start; /* 头像和内容顶部对齐 */
}

.message-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
}

.user-message .message-avatar {
  background: var(--color-primary-light-1);
  color: rgb(var(--primary-6));
}

.ai-message .message-avatar {
  background: var(--color-success-light-1);
  color: rgb(var(--success-6));
}

/* 步骤分隔符 */
.step-separator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}

.step-line {
  flex: 1;
  height: 1px;
  background: var(--color-border-2);
}

.step-label {
  font-size: 12px;
  color: var(--color-text-3);
  white-space: nowrap;
}

/* 工具消息 */
.tool-message .message-avatar {
  background: var(--color-warning-light-1);
  color: rgb(var(--warning-6));
}

.tool-message .tool-avatar {
  background: var(--color-warning-light-1);
  color: rgb(var(--warning-6));
}

.tool-message .tool-content {
  background: var(--color-warning-light-1);
}

.tool-name {
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 4px;
  color: rgb(var(--warning-6));
}

.message-content {
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  max-width: calc(100% - 38px);
  word-break: break-word;
  font-size: 14px;
  line-height: 1.5;
  text-align: left; /* 文本靠左对齐 */
}

.user-message .message-content {
  background: var(--color-primary-light-1);
}

.ai-message .message-content {
  background: var(--color-fill-2);
}

/* 加载动画 */
.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-3);
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* 输入区域 */
.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--color-border);
  align-items: flex-end;
  background: var(--color-bg-3);
}

.chat-input :deep(.arco-textarea-wrapper) {
  flex: 1;
}

.chat-input :deep(.arco-btn) {
  height: 32px;
  flex-shrink: 0;
}

/* 弹窗动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* 打字机光标 */
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: rgb(var(--primary-6));
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

/* 紧凑版工具审批卡片样式 - 适配小对话窗口 */
.compact-approval-wrapper {
  padding: 8px;
  margin: 8px 0;
}

.compact-approval-wrapper :deep(.approval-card) {
  margin: 0;
  border-radius: 8px;
  font-size: 12px;
}

.compact-approval-wrapper :deep(.card-content) {
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.compact-approval-wrapper :deep(.tool-section) {
  width: 100%;
}

.compact-approval-wrapper :deep(.tool-info) {
  flex: 1;
}

.compact-approval-wrapper :deep(.tool-name) {
  font-size: 13px;
}

.compact-approval-wrapper :deep(.tool-args) {
  font-size: 11px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.compact-approval-wrapper :deep(.tool-args code) {
  font-size: 11px;
}

.compact-approval-wrapper :deep(.action-section) {
  width: 100%;
  justify-content: space-between;
}

.compact-approval-wrapper :deep(.remember-option) {
  flex: 1;
}

.compact-approval-wrapper :deep(.remember-option .arco-select) {
  width: 100% !important;
}

.compact-approval-wrapper :deep(.action-buttons) {
  gap: 6px;
}

.compact-approval-wrapper :deep(.action-buttons .arco-btn) {
  padding: 4px 10px;
  font-size: 12px;
}

.compact-approval-wrapper :deep(.args-detail) {
  font-size: 11px;
  max-height: 100px;
  overflow-y: auto;
}

.compact-approval-wrapper :deep(.arg-key),
.compact-approval-wrapper :deep(.arg-value) {
  font-size: 11px;
}
</style>

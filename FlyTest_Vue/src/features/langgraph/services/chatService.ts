import { ref } from 'vue';
import { request } from '@/utils/request';
import { useAuthStore } from '@/store/authStore';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  ChatRequest,
  ChatResponseData,
  ChatHistoryResponseData,
  ChatSessionsResponseData
} from '@/features/langgraph/types/chat';

interface StreamMessage {
  content: string;
  type: 'human' | 'ai' | 'tool' | 'system' | 'agent_step';
  time: string;
  toolName?: string;
  imageDataUrl?: string;
  isExpanded?: boolean;
  isThinkingProcess?: boolean;
  isThinkingExpanded?: boolean;
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
}

interface StreamState {
  content: string;
  error?: string;
  isComplete: boolean;
  messages: StreamMessage[];
  contextTokenCount?: number;
  contextLimit?: number;
  currentStep?: number;
  maxSteps?: number;
  userMessage?: string;
  userMessageTime?: string;
  taskId?: number;
  scriptGeneration?: {
    available: boolean;
    playwrightSteps: number;
    message: string;
  };
  interrupt?: {
    id: string;
    interrupt_id?: string;
    action_requests: Array<{
      name: string;
      args: Record<string, unknown>;
      description?: string;
      auto_reject?: boolean;
    }>;
  };
  isWaitingForApproval?: boolean;
}

export interface AgentLoopSseEvent {
  type: string;
  session_id?: string;
  context_limit?: number;
  context_token_count?: number;
  max_steps?: number | string;
  step?: number | string;
  summary?: string | Record<string, unknown>;
  message?: string;
  data?: string | { content?: string } | Record<string, unknown> | null;
}

const formatStreamTime = (): string => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

const buildAuthHeaders = (token: string | null, headers: Record<string, string>) =>
  token ? { ...headers, Authorization: `Bearer ${token}` } : headers

async function ensureAccessToken(): Promise<string | null> {
  const authStore = useAuthStore()
  if (authStore.getAccessToken) {
    return authStore.getAccessToken
  }
  const restored = await authStore.bootstrapSession()
  return restored ? authStore.getAccessToken : null
}

const formatIsoTime = (isoString: string | null | undefined): string => {
  if (!isoString) return formatStreamTime();
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return formatStreamTime();
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } catch {
    return formatStreamTime();
  }
};

const normalizeNumericField = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const parseMessageContent = (data: unknown): string => {
  if (typeof data === 'string') {
    if (data.includes('AIMessageChunk')) {
      const match = data.match(/content='((?:\\'|[^'])*)'/);
      if (match && match[1] !== undefined) {
        return match[1].replace(/\\'/g, "'");
      }
    }
    return data;
  }
  if (data && typeof data === 'object' && 'content' in data && typeof (data as Record<string, unknown>).content === 'string') {
    return (data as Record<string, unknown>).content as string;
  }
  return '';
};

const safeStringify = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value);
  } catch {
    return '[鏃犳硶搴忓垪鍖栫殑鏁版嵁]';
  }
};

interface ToolResultDisplayPayload {
  content: string;
  imageDataUrl?: string;
}

const HIDDEN_TOOL_MESSAGE_NAMES = new Set(['read_skill_content']);

const shouldHideToolMessage = (toolName?: unknown, rawContent?: unknown): boolean => {
  if (typeof toolName !== 'string') return false;
  if (HIDDEN_TOOL_MESSAGE_NAMES.has(toolName)) return true;
  if (toolName === 'execute_skill_script') return true;
  return false;
};

const tryParseJsonString = (value: string): unknown | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
};

const toImageDataUrl = (item: Record<string, unknown>): string | undefined => {
  const rawBase64 = item.base64;
  if (typeof rawBase64 !== 'string' || !rawBase64.trim()) return undefined;
  const base64 = rawBase64.trim();
  if (base64.startsWith('data:image/')) return base64;

  const mimeType =
    (typeof item.mime_type === 'string' && item.mime_type.trim()) ||
    (typeof item.mimeType === 'string' && item.mimeType.trim()) ||
    'image/jpeg';

  return `data:${mimeType};base64,${base64}`;
};

const buildToolResultDisplayPayload = (rawToolOutput: unknown): ToolResultDisplayPayload => {
  let normalized: unknown = rawToolOutput;
  if (typeof normalized === 'string') {
    const parsed = tryParseJsonString(normalized);
    if (parsed !== null) {
      normalized = parsed;
    }
  }

  if (Array.isArray(normalized)) {
    let imageDataUrl: string | undefined;
    const textParts: string[] = [];

    normalized.forEach((item) => {
      if (item && typeof item === 'object') {
        const obj = item as Record<string, unknown>;
        const itemType = typeof obj.type === 'string' ? obj.type.toLowerCase() : '';

        if (!imageDataUrl && (itemType === 'image' || typeof obj.base64 === 'string')) {
          imageDataUrl = toImageDataUrl(obj) || imageDataUrl;
          if (itemType === 'image') {
            return;
          }
        }

        if (typeof obj.text === 'string' && obj.text.trim()) {
          textParts.push(obj.text);
          return;
        }

        if (itemType !== 'image' && !('base64' in obj)) {
          const serialized = safeStringify(obj);
          if (serialized) {
            textParts.push(serialized);
          }
        }
        return;
      }

      if (typeof item === 'string') {
        textParts.push(item);
      } else {
        const serialized = safeStringify(item);
        if (serialized) {
          textParts.push(serialized);
        }
      }
    });

    const content = textParts.filter((part) => part && part.trim()).join('\n');
    if (content || imageDataUrl) {
      return {
        content: content || '[宸ュ叿杩斿洖浜嗗浘鐗嘳',
        imageDataUrl
      };
    }
    return { content: safeStringify(normalized) };
  }

  if (normalized && typeof normalized === 'object') {
    const obj = normalized as Record<string, unknown>;
    const itemType = typeof obj.type === 'string' ? obj.type.toLowerCase() : '';
    const imageDataUrl =
      itemType === 'image' || typeof obj.base64 === 'string'
        ? toImageDataUrl(obj)
        : undefined;

    const text =
      typeof obj.text === 'string' && obj.text.trim()
        ? obj.text
        : '';

    if (text || imageDataUrl) {
      return {
        content: text || '[宸ュ叿杩斿洖浜嗗浘鐗嘳',
        imageDataUrl
      };
    }

    return { content: safeStringify(normalized) };
  }

  return { content: safeStringify(normalized) };
};

interface ContextUsageSnapshot {
  tokenCount: number;
  limit: number;
}

export const activeStreams = ref<Record<string, StreamState>>({});
export const latestContextUsage = ref<Record<string, ContextUsageSnapshot>>({});

export const clearStreamState = (sessionId: string) => {
  if (activeStreams.value[sessionId]) {
    delete activeStreams.value[sessionId];
  }
};

const API_BASE_URL = '/lg/chat';
const AGENT_LOOP_API_URL = '/orchestrator/agent-loop';
const AGENT_LOOP_STOP_API_URL = '/orchestrator/agent-loop/stop';

function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;

  if (envUrl && (envUrl.startsWith('http://') || envUrl.startsWith('https://'))) {
    return envUrl;
  }

  return '/api';
}

export async function sendChatMessage(
  data: ChatRequest
): Promise<ApiResponse<ChatResponseData>> {
  const response = await request<ChatResponseData>({
    url: `${API_BASE_URL}/`,
    method: 'POST',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to send chat message',
      data: {} as ChatResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export interface AgentLoopNonStreamResponse {
  session_id: string;
  content: string;
  total_steps: number;
  tool_results: Array<{ summary: string; step: number }>;
  context_token_count: number;
  context_limit: number;
  interrupt?: {
    interrupt_id: string;
    action_requests: Array<{
      name: string;
      args: Record<string, unknown>;
      description?: string;
    }>;
  };
  script_generation?: {
    enabled: boolean;
    message: string;
  };
}

export async function sendChatMessageNonStream(
  data: ChatRequest
): Promise<ApiResponse<AgentLoopNonStreamResponse>> {
  const authStore = useAuthStore();
  let token = await ensureAccessToken();

  if (!token) {
    return {
      status: 'error',
      code: 401,
      message: '未登录或登录已过期',
      data: null as unknown as AgentLoopNonStreamResponse,
      errors: { detail: ['未登录'] }
    };
  }

  try {
    const requestData = {
      ...data,
      stream: false
    };

    const response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
      method: 'POST',
      headers: buildAuthHeaders(token, {
        'Content-Type': 'application/json',
      }),
      credentials: 'include',
      body: JSON.stringify(requestData)
    });

    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (!newToken) {
        return {
          status: 'error',
          code: 401,
          message: '登录已过期，请重新登录',
          data: null as unknown as AgentLoopNonStreamResponse,
          errors: { detail: ['Token 刷新失败'] }
        };
      }

      const retryResponse = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
        method: 'POST',
        headers: buildAuthHeaders(newToken, {
          'Content-Type': 'application/json',
        }),
        credentials: 'include',
        body: JSON.stringify(requestData)
      });

      const retryData = await retryResponse.json();
      if (retryData.status === 'success') {
        return {
          status: 'success',
          code: 200,
          message: retryData.message || 'success',
          data: retryData.data,
          errors: undefined
        };
      } else {
        return {
          status: 'error',
          code: retryData.code || 500,
          message: retryData.message || 'Request failed',
          data: null as unknown as AgentLoopNonStreamResponse,
          errors: retryData.errors || { detail: [retryData.message] }
        };
      }
    }

    const responseData = await response.json();

    if (responseData.status === 'success') {
      return {
        status: 'success',
        code: 200,
        message: responseData.message || 'success',
        data: responseData.data,
        errors: undefined
      };
    } else {
      return {
        status: 'error',
        code: responseData.code || 500,
        message: responseData.message || 'Request failed',
        data: null as unknown as AgentLoopNonStreamResponse,
        errors: responseData.errors || { detail: [responseData.message] }
      };
    }
  } catch (error: any) {
    console.error('[ChatService] Non-stream request error:', error);
    return {
      status: 'error',
      code: 500,
        message: error.message || '请求失败',
      data: null as unknown as AgentLoopNonStreamResponse,
      errors: { detail: [error.message || 'Unknown error'] }
    };
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const authStore = useAuthStore();

  try {
    const response = await fetch(`${getApiBaseUrl()}/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    });

    if (response.ok) {
      const data = await response.json();
      const payload = data?.data ?? data;
      if (payload.access) {
        authStore.updateAccessToken(payload.access);
        authStore.updateRefreshToken(payload.refresh || null);
        return payload.access;
      }
    }

    authStore.logout();
    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    authStore.logout();
    return null;
  }
}

export async function sendChatMessageStream(
  data: ChatRequest,
  onStart: (sessionId: string) => void,
  signal?: AbortSignal
): Promise<void> {
  let token = await ensureAccessToken();
  let streamSessionId: string | null = data.session_id || null;

  const handleError = (error: any, sessionId: string | null) => {
    const isAbortError = error?.name === 'AbortError' ||
                         error?.message?.includes('aborted') ||
                         error?.message?.includes('BodyStreamBuffer') ||
                         error?.message?.includes('The user aborted');

    if (isAbortError) {
      console.log('[ChatService] Stream aborted by user');
      if (sessionId && activeStreams.value[sessionId]) {
        activeStreams.value[sessionId].isComplete = true;
      }
      return;
    }

    console.error('Stream error:', error);
    if (sessionId && activeStreams.value[sessionId]) {
      activeStreams.value[sessionId].error = error.message || '流式请求失败';
      activeStreams.value[sessionId].isComplete = true;
    }
  };

  if (!token) {
    handleError(new Error('未登录或登录已过期'), streamSessionId);
    return;
  }

  try {
    let response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
      method: 'POST',
      headers: buildAuthHeaders(token, {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      }),
      credentials: 'include',
      body: JSON.stringify(data),
      signal,
    });

    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        token = newToken;
        response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
          method: 'POST',
          headers: buildAuthHeaders(token, {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          }),
          credentials: 'include',
          body: JSON.stringify(data),
          signal,
        });
      } else {
        handleError(new Error('登录已过期，请重新登录'), streamSessionId);
        return;
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.trim() === '' || !line.startsWith('data: ')) continue;
            
            const jsonData = line.slice(6);
            if (jsonData === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(jsonData);
              
              if (parsed.type === 'context_update' && streamSessionId) {
                const tokenCount = parsed.context_token_count ?? 0;
                const limit = parsed.context_limit ?? 128000;
                latestContextUsage.value[streamSessionId] = { tokenCount, limit };
                
                if (activeStreams.value[streamSessionId]) {
                  activeStreams.value[streamSessionId].contextTokenCount = tokenCount;
                  activeStreams.value[streamSessionId].contextLimit = limit;
                }
              }
              
              if (parsed.type === 'complete' && streamSessionId && activeStreams.value[streamSessionId]) {
                activeStreams.value[streamSessionId].isComplete = true;
              }
            } catch (e) {
              console.warn('Failed to parse remaining SSE data:', line);
            }
          }
        }
        
        if (streamSessionId && activeStreams.value[streamSessionId] && 
            !activeStreams.value[streamSessionId].isComplete &&
            !activeStreams.value[streamSessionId].isWaitingForApproval) {
            console.warn('[ChatService] Stream ended without complete event, possible network interruption');
            activeStreams.value[streamSessionId].error = '杩炴帴鎰忓涓柇锛岃閲嶈瘯';
            activeStreams.value[streamSessionId].isComplete = true;
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '' || !line.startsWith('data: ')) continue;
        
        const jsonData = line.slice(6);
        if (jsonData === '[DONE]') {
            if (streamSessionId && activeStreams.value[streamSessionId]) {
                if (!activeStreams.value[streamSessionId].isWaitingForApproval) {
                    activeStreams.value[streamSessionId].isComplete = true;
                }
            }
            continue;
        }

        try {
          const parsed = JSON.parse(jsonData);

          if (parsed.type === 'error') {
            handleError(new Error(parsed.message || '流式请求失败'), streamSessionId);
            return;
          }

          if (parsed.type === 'start' && parsed.session_id) {
            streamSessionId = parsed.session_id;
            if (streamSessionId) {
              const cachedUsage = latestContextUsage.value[streamSessionId];
              const prevTokenCount = cachedUsage?.tokenCount || 0;
              const contextLimit = parsed.context_limit || cachedUsage?.limit || 128000;
              const initialMaxSteps = normalizeNumericField(parsed.max_steps);

              activeStreams.value[streamSessionId] = {
                content: '',
                isComplete: false,
                messages: [],
                contextTokenCount: prevTokenCount,
                contextLimit: contextLimit,
                currentStep: 0,
                maxSteps: initialMaxSteps,
                userMessage: data.message,
                userMessageTime: formatIsoTime(parsed.created_at)
              };
              onStart(streamSessionId);
            }
          }

          if (parsed.type === 'context_update' && streamSessionId) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            
            latestContextUsage.value[streamSessionId] = { tokenCount, limit };
            
            if (activeStreams.value[streamSessionId]) {
              activeStreams.value[streamSessionId].contextTokenCount = tokenCount;
              activeStreams.value[streamSessionId].contextLimit = limit;
            }
          }

          if (parsed.type === 'warning' && streamSessionId && activeStreams.value[streamSessionId]) {
            const warningMessage = parsed.message || '璀﹀憡';
            console.warn('[Chat] Warning:', warningMessage);
            activeStreams.value[streamSessionId].messages.push({
              content: warningMessage,
              type: 'system',
              time: formatStreamTime()
            });
          }

          if (parsed.type === 'step_start' && streamSessionId && activeStreams.value[streamSessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            const maxSteps = normalizeNumericField(parsed.max_steps);
            console.log('[step_start] raw:', parsed.step, parsed.max_steps, '| normalized:', stepNumber, maxSteps);
            if (maxSteps !== undefined) {
              activeStreams.value[streamSessionId].maxSteps = maxSteps;
            }
            if (stepNumber !== undefined) {
              activeStreams.value[streamSessionId].currentStep = stepNumber;
            }
            activeStreams.value[streamSessionId].messages.push({
              content: '',
              type: 'agent_step',
              time: formatStreamTime(),
              stepNumber: stepNumber,
              maxSteps: maxSteps,
              stepStatus: 'start',
              isThinkingProcess: true
            });
            console.log('[step_start] pushed message with stepNumber:', stepNumber, 'maxSteps:', maxSteps);
          }

          if (parsed.type === 'step_complete' && streamSessionId && activeStreams.value[streamSessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[streamSessionId].currentStep = stepNumber;
            }
          }

          if (parsed.type === 'tool_result' && streamSessionId && activeStreams.value[streamSessionId]) {
            if (shouldHideToolMessage(parsed.tool_name, parsed.tool_output || parsed.content || parsed.summary)) {
              continue;
            }
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = buildToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              if (activeStreams.value[streamSessionId].content && activeStreams.value[streamSessionId].content.trim()) {
                activeStreams.value[streamSessionId].messages.push({
                  content: activeStreams.value[streamSessionId].content,
                  type: 'ai',
                  time: time,
                  isExpanded: false
                });
                activeStreams.value[streamSessionId].content = '';
              }
              activeStreams.value[streamSessionId].messages.push({
                content: toolPayload.content || '[宸ュ叿杩斿洖浜嗗浘鐗嘳',
                type: 'tool',
                time: time,
                toolName: typeof parsed.tool_name === 'string' ? parsed.tool_name : undefined,
                imageDataUrl: toolPayload.imageDataUrl,
                isExpanded: false
              });
            }
          }

          if (parsed.type === 'update' && streamSessionId && activeStreams.value[streamSessionId]) {
            const updateData = parsed.data;
            if (typeof updateData === 'string') {
              if (updateData.includes('ToolMessage')) {
                try {
                  const toolNameMatch = updateData.match(/name='([^']+)'/);
                  const toolName = toolNameMatch?.[1];
                  if (shouldHideToolMessage(toolName, updateData)) {
                    continue;
                  }
                  const contentMatch = updateData.match(/content='([^']*(?:\\'[^']*)*)'/);
                  
                  if (contentMatch) {
                    const toolContent = contentMatch[1].replace(/\\'/g, "'").replace(/\\n/g, '\n');
                    const time = formatStreamTime();
                    
                    if (activeStreams.value[streamSessionId].content && activeStreams.value[streamSessionId].content.trim()) {
                      activeStreams.value[streamSessionId].messages.push({
                        content: activeStreams.value[streamSessionId].content,
                        type: 'ai',
                        time: time,
                        isExpanded: false
                      });
                      activeStreams.value[streamSessionId].content = '';
                    }
                    
                    activeStreams.value[streamSessionId].messages.push({
                      content: toolContent,
                      type: 'tool',
                      time: time,
                      toolName: toolName,
                      isExpanded: false
                    });
                  }
                } catch (e) {
                  console.warn('Failed to parse tool message:', updateData);
                }
              }
            }
          }

          if (parsed.type === 'stream' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          if (parsed.type === 'stream_end' && streamSessionId && activeStreams.value[streamSessionId]) {
          }

          if (parsed.type === 'message' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parseMessageContent(parsed.data);
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          if (parsed.type === 'interrupt' && streamSessionId && activeStreams.value[streamSessionId]) {
            console.log('[ChatService] Interrupt event received:', parsed);
            activeStreams.value[streamSessionId].interrupt = {
              id: parsed.interrupt_id || parsed.id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || [],
            };
            activeStreams.value[streamSessionId].isWaitingForApproval = true;
          }

          if (parsed.type === 'complete' && streamSessionId && activeStreams.value[streamSessionId]) {
            activeStreams.value[streamSessionId].isComplete = true;
            
            if (parsed.task_id) {
              activeStreams.value[streamSessionId].taskId = parsed.task_id;
            }
            
            if (parsed.script_generation && parsed.script_generation.available) {
              activeStreams.value[streamSessionId].scriptGeneration = {
                available: true,
                playwrightSteps: parsed.script_generation.playwright_steps || 0,
                message: parsed.script_generation.message || '可生成自动化用例'
              };
              console.log('[ChatService] Script generation available:', parsed.script_generation);
            }
          }
        } catch (e) {
          console.warn('Failed to parse SSE data:', jsonData);
        }
      }
    }
  } catch (error) {
    handleError(error, streamSessionId);
  }
}

export async function getChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<ChatHistoryResponseData>> {
  const response = await request<ChatHistoryResponseData>({
    url: `${API_BASE_URL}/history/`,
    method: 'GET',
    params: {
      session_id: sessionId,
      project_id: String(projectId)
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat history',
      data: {} as ChatHistoryResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export async function deleteChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: `${API_BASE_URL}/history/`,
    method: 'DELETE',
    params: {
      session_id: sessionId,
      project_id: String(projectId)
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '聊天历史记录已成功删除',
      data: null,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to delete chat history',
      data: null,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export async function rollbackChatHistory(
  sessionId: string,
  projectId: number | string,
  keepCount: number
): Promise<ApiResponse<{ deleted_count: number; kept_count: number }>> {
  const response = await request<{ deleted_count: number; kept_count: number }>({
    url: `${API_BASE_URL}/history/`,
    method: 'PATCH',
    params: {
      session_id: sessionId,
      project_id: String(projectId)
    },
    data: {
      keep_count: keepCount
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '聊天历史已回滚',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to rollback chat history',
      data: { deleted_count: 0, kept_count: 0 },
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export async function getChatSessions(projectId: number): Promise<ApiResponse<ChatSessionsResponseData>> {
  const response = await request<ChatSessionsResponseData>({
    url: `${API_BASE_URL}/sessions/`,
    method: 'GET',
    params: {
      project_id: projectId
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat sessions',
      data: {} as ChatSessionsResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export async function batchDeleteChatHistory(
  sessionIds: string[],
  projectId: number | string
): Promise<ApiResponse<{ deleted_count: number; processed_sessions: number; failed_sessions: any[] }>> {
  const response = await request<{ deleted_count: number; processed_sessions: number; failed_sessions: any[] }>({
    url: `${API_BASE_URL}/batch-delete/`,
    method: 'POST',
    data: {
      session_ids: sessionIds,
      project_id: String(projectId)
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '批量删除成功',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '批量删除失败',
      data: { deleted_count: 0, processed_sessions: 0, failed_sessions: [] },
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

export async function stopAgentLoop(
  sessionId: string
): Promise<ApiResponse<{ success: boolean; session_id: string; message: string }>> {
  const token = await ensureAccessToken();

  try {
    const response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_STOP_API_URL}/`, {
      method: 'POST',
      headers: buildAuthHeaders(token, {
        'Content-Type': 'application/json',
      }),
      credentials: 'include',
      body: JSON.stringify({ session_id: sessionId })
    });

    const data = await response.json();

    if (response.ok && data.status === 'success') {
      return {
        status: 'success',
        code: 200,
        message: data.message || '已停止生成',
        data: data.data,
        errors: undefined
      };
    } else {
      return {
        status: 'error',
        code: response.status,
        message: data.message || '停止失败',
        data: { success: false, session_id: sessionId, message: '' },
        errors: data.errors || { detail: ['Unknown error'] }
      };
    }
  } catch (error) {
    console.error('[ChatService] Stop agent loop error:', error);
    return {
      status: 'error',
      code: 500,
      message: error instanceof Error ? error.message : '停止请求失败',
      data: { success: false, session_id: sessionId, message: '' },
      errors: { detail: [error instanceof Error ? error.message : 'Unknown error'] }
    };
  }
}

export async function resumeAgentLoop(
  sessionId: string,
  interruptId: string,
  decision: 'approve' | 'reject',
  projectId: number,
  signal?: AbortSignal,
  knowledgeBaseId?: string | null,
  useKnowledgeBase?: boolean,
  actionCount?: number
): Promise<void> {
  let token = await ensureAccessToken();

  if (!activeStreams.value[sessionId]) {
    activeStreams.value[sessionId] = {
      content: '',
      isComplete: false,
      messages: [],
      isWaitingForApproval: false,
    };
    console.log('[ChatService] Resume: Initialized activeStreams for session', sessionId);
  } else {
    if (activeStreams.value[sessionId].content?.trim()) {
      activeStreams.value[sessionId].messages.push({
        content: activeStreams.value[sessionId].content,
        type: 'ai',
        time: formatStreamTime(),
        isExpanded: false
      });
      activeStreams.value[sessionId].content = '';
    }
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
    activeStreams.value[sessionId].isComplete = false;
  }

  const handleError = (error: any) => {
    const isAbortError = error?.name === 'AbortError' ||
                         error?.message?.includes('aborted') ||
                         error?.message?.includes('The user aborted');

    if (isAbortError) {
      console.log('[ChatService] Resume stream aborted by user');
      if (activeStreams.value[sessionId]) {
        activeStreams.value[sessionId].isComplete = true;
      }
      return;
    }

    console.error('[ChatService] Resume stream error:', error);
    if (activeStreams.value[sessionId]) {
      activeStreams.value[sessionId].error = error.message || '恢复执行失败';
      activeStreams.value[sessionId].isComplete = true;
    }
  };

  if (!token) {
    handleError(new Error('未登录或登录已过期'));
    return;
  }

  try {
    const resumeData: Record<string, any> = {
      session_id: sessionId,
      project_id: projectId,
      resume: {
        [interruptId]: {
          decisions: [{ type: decision }],
          action_count: actionCount || 1
        }
      }
    };

    if (knowledgeBaseId && useKnowledgeBase) {
      resumeData.knowledge_base_id = knowledgeBaseId;
      resumeData.use_knowledge_base = useKnowledgeBase;
    }

    let response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/resume/`, {
      method: 'POST',
      headers: buildAuthHeaders(token, {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      }),
      credentials: 'include',
      body: JSON.stringify(resumeData),
      signal
    });

    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        token = newToken;
        response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/resume/`, {
          method: 'POST',
          headers: buildAuthHeaders(token, {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          }),
          credentials: 'include',
          body: JSON.stringify(resumeData),
          signal
        });
      } else {
        handleError(new Error('登录已过期，请重新登录'));
        return;
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.trim() === '' || !line.startsWith('data: ')) continue;
            const jsonData = line.slice(6);
            if (jsonData === '[DONE]') continue;

            try {
              const parsed = JSON.parse(jsonData);
              if (parsed.type === 'complete' && activeStreams.value[sessionId]) {
                activeStreams.value[sessionId].isComplete = true;
              }
            } catch {
            }
          }
        }

        if (activeStreams.value[sessionId] && !activeStreams.value[sessionId].isComplete) {
          console.warn('[ChatService] Resume stream ended without complete event');
          activeStreams.value[sessionId].isComplete = true;
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '' || !line.startsWith('data: ')) continue;

        const jsonData = line.slice(6);
        if (jsonData === '[DONE]') {
          if (activeStreams.value[sessionId]) {
            activeStreams.value[sessionId].isComplete = true;
          }
          continue;
        }

        try {
          const parsed = JSON.parse(jsonData);

          if (parsed.type === 'error') {
            handleError(new Error(parsed.message || '恢复执行失败'));
            return;
          }

          if (parsed.type === 'resume_start' && activeStreams.value[sessionId]) {
            console.log('[ChatService] Resume started:', parsed.decision);
          }

          if (parsed.type === 'context_update' && activeStreams.value[sessionId]) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            latestContextUsage.value[sessionId] = { tokenCount, limit };
            activeStreams.value[sessionId].contextTokenCount = tokenCount;
            activeStreams.value[sessionId].contextLimit = limit;
          }

          if (parsed.type === 'step_start' && activeStreams.value[sessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            const maxSteps = normalizeNumericField(parsed.max_steps);
            if (maxSteps !== undefined) {
              activeStreams.value[sessionId].maxSteps = maxSteps;
            }
            if (stepNumber !== undefined) {
              activeStreams.value[sessionId].currentStep = stepNumber;
            }
            activeStreams.value[sessionId].messages.push({
              content: '',
              type: 'agent_step',
              time: formatStreamTime(),
              stepNumber: stepNumber,
              maxSteps: maxSteps,
              stepStatus: 'start',
              isThinkingProcess: true
            });
          }

          if (parsed.type === 'step_complete' && activeStreams.value[sessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[sessionId].currentStep = stepNumber;
            }
          }

          if (parsed.type === 'tool_result' && activeStreams.value[sessionId]) {
            if (shouldHideToolMessage(parsed.tool_name, parsed.tool_output || parsed.content || parsed.summary)) {
              continue;
            }
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = buildToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              if (activeStreams.value[sessionId].content?.trim()) {
                activeStreams.value[sessionId].messages.push({
                  content: activeStreams.value[sessionId].content,
                  type: 'ai',
                  time: time,
                  isExpanded: false
                });
                activeStreams.value[sessionId].content = '';
              }
              activeStreams.value[sessionId].messages.push({
                content: toolPayload.content || '[宸ュ叿杩斿洖浜嗗浘鐗嘳',
                type: 'tool',
                time: time,
                toolName: typeof parsed.tool_name === 'string' ? parsed.tool_name : undefined,
                imageDataUrl: toolPayload.imageDataUrl,
                isExpanded: false
              });
            }
          }

          if (parsed.type === 'stream' && activeStreams.value[sessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[sessionId].content += content;
            }
          }

          if (parsed.type === 'interrupt' && activeStreams.value[sessionId]) {
            console.log('[ChatService] New interrupt after resume:', parsed);
            activeStreams.value[sessionId].interrupt = {
              id: parsed.interrupt_id || parsed.id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || []
            };
            activeStreams.value[sessionId].isWaitingForApproval = true;
          }

          if (parsed.type === 'complete' && activeStreams.value[sessionId]) {
            activeStreams.value[sessionId].isComplete = true;
          }
        } catch (e) {
          console.warn('[ChatService] Failed to parse resume SSE data:', jsonData);
        }
      }
    }
  } catch (error) {
    handleError(error);
  }
}

export async function resumeChatStream(
  sessionId: string,
  decision: 'approve' | 'reject',
  projectId: number,
  onMessage?: (content: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void,
  onInterrupt?: (interrupt: { id: string; action_requests: Array<{ name: string; args: Record<string, unknown>; description?: string }> }) => void
): Promise<void> {
  const authStore = useAuthStore();
  const token = authStore.getAccessToken;

  const resumeData = {
    session_id: sessionId,
    project_id: projectId,
    decision: decision
  };

  try {
    const response = await fetch(`${getApiBaseUrl()}/lg/chat/resume/`, {
      method: 'POST',
      headers: buildAuthHeaders(token, {
        'Content-Type': 'application/json',
      }),
      credentials: 'include',
      body: JSON.stringify(resumeData)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      onError?.(errorData.error || `Resume failed: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError?.('No response body');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') {
            onComplete?.();
            return;
          }

          try {
            const parsed = JSON.parse(dataStr);

            if (parsed.type === 'message' && parsed.data) {
              onMessage?.(parsed.data);
            } else if (parsed.type === 'interrupt') {
              onInterrupt?.({
                id: parsed.interrupt_id,
                action_requests: parsed.action_requests || []
              });
            } else if (parsed.type === 'error') {
              onError?.(parsed.message || 'Unknown error');
            } else if (parsed.type === 'complete') {
              onComplete?.();
            }
          } catch {
          }
        }
      }
    }

    clearInterruptState(sessionId);
    onComplete?.();
  } catch (error) {
    console.error('[ChatService] Resume chat stream error:', error);
    onError?.(error instanceof Error ? error.message : 'Resume failed');
  }
}

export function clearInterruptState(sessionId: string): void {
  if (activeStreams.value[sessionId]) {
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
  }
}




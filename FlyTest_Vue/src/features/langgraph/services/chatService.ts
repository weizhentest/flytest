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

// --- 鍏ㄥ眬娴佸紡鐘舵€佺鐞?---
interface StreamMessage {
  content: string;
  type: 'human' | 'ai' | 'tool' | 'system' | 'agent_step';
  time: string;
  toolName?: string;
  imageDataUrl?: string;
  isExpanded?: boolean;
  isThinkingProcess?: boolean;
  isThinkingExpanded?: boolean;
  // Agent Step 涓撶敤瀛楁
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
}

interface StreamState {
  content: string;
  error?: string;
  isComplete: boolean;
  messages: StreamMessage[]; // 瀛樺偍鎵€鏈夋秷鎭?鍖呮嫭宸ュ叿娑堟伅
  contextTokenCount?: number; // 褰撳墠涓婁笅鏂嘥oken鏁?
  contextLimit?: number; // 涓婁笅鏂嘥oken闄愬埗
  currentStep?: number;  // Agent Loop 褰撳墠姝ラ
  maxSteps?: number;     // Agent Loop 鏈€澶ф楠ゆ暟
  userMessage?: string;  // 鐢ㄦ埛鍙戦€佺殑娑堟伅鍐呭
  userMessageTime?: string;  // 鐢ㄦ埛娑堟伅鏃堕棿锛堜細璇濆垱寤烘椂闂达級
  taskId?: number;       // Agent Task ID
  // 猸?鑴氭湰鐢熸垚淇℃伅
  scriptGeneration?: {
    available: boolean;
    playwrightSteps: number;
    message: string;
  };
  // 猸?HITL 涓柇淇℃伅
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
  isWaitingForApproval?: boolean; // 鏄惁姝ｅ湪绛夊緟鐢ㄦ埛瀹℃壒
}

// Agent Loop SSE 浜嬩欢绫诲瀷瀹氫箟锛堜緵鏂囨。鍜岀被鍨嬪弬鑰冿級
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

// 鏍煎紡鍖栨椂闂磋緟鍔╁嚱鏁?
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

// 鏍煎紡鍖?ISO 鏃堕棿瀛楃涓蹭负鏄剧ず鏍煎紡
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

// 鏁板瓧瀛楁褰掍竴鍖栵紙澶勭悊瀛楃涓叉垨鏁板瓧绫诲瀷锛?
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

// 瑙ｆ瀽娑堟伅鍐呭 - 鏀寔 Agent Loop 绾枃鏈拰鏃?LangGraph 鏍煎紡
const parseMessageContent = (data: unknown): string => {
  if (typeof data === 'string') {
    // 鏃?LangGraph 鏍煎紡: AIMessageChunk(content='xxx')
    if (data.includes('AIMessageChunk')) {
      const match = data.match(/content='((?:\\'|[^'])*)'/);
      if (match && match[1] !== undefined) {
        return match[1].replace(/\\'/g, "'");
      }
    }
    // Agent Loop 绾枃鏈牸寮?
    return data;
  }
  // 瀵硅薄鏍煎紡 { content: string }
  if (data && typeof data === 'object' && 'content' in data && typeof (data as Record<string, unknown>).content === 'string') {
    return (data as Record<string, unknown>).content as string;
  }
  return '';
};

// 瀹夊叏鐨?JSON 搴忓垪鍖栵紙闃叉寰幆寮曠敤瀵艰嚧宕╂簝锛?
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

// 涓婁笅鏂囦娇鐢ㄥ揩鐓э紙鐙珛缂撳瓨锛屼笉鍙梒learStreamState褰卞搷锛?
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
  // 娉ㄦ剰锛氫笉娓呴櫎 latestContextUsage锛屼繚鐣欐渶鍚庣殑Token浣跨敤淇℃伅
};
// --- 鍏ㄥ眬娴佸紡鐘舵€佺鐞嗙粨鏉?---

const API_BASE_URL = '/lg/chat';
// Agent Loop API 绔偣 - 瑙ｅ喅 Token 绱Н闂
const AGENT_LOOP_API_URL = '/orchestrator/agent-loop';
// Agent Loop 鍋滄 API 绔偣
const AGENT_LOOP_STOP_API_URL = '/orchestrator/agent-loop/stop';

// 鑾峰彇API鍩虹URL
function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;

  // 濡傛灉鐜鍙橀噺鏄畬鏁碪RL锛堝寘鍚玥ttp/https锛夛紝鐩存帴浣跨敤
  if (envUrl && (envUrl.startsWith('http://') || envUrl.startsWith('https://'))) {
    return envUrl;
  }

  // 鍚﹀垯浣跨敤鐩稿璺緞锛岃娴忚鍣ㄨ嚜鍔ㄨВ鏋愬埌褰撳墠鍩熷悕
  return '/api';
}

/**
 * 鍙戦€佸璇濇秷鎭紙鏃х増 API锛屽凡搴熷純锛?
 * @deprecated 璇蜂娇鐢?sendChatMessageNonStream 璋冪敤缁熶竴鐨?Agent Loop 鎺ュ彛
 */
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

/**
 * Agent Loop 闈炴祦寮忓搷搴旀暟鎹被鍨?
 */
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

/**
 * 鍙戦€侀潪娴佸紡瀵硅瘽娑堟伅锛堢粺涓€ Agent Loop 鎺ュ彛锛?
 *
 * 浣跨敤 Agent Loop API 鐨?stream=false 妯″紡锛岃幏寰椾笌娴佸紡妯″紡涓€鑷寸殑鍔熻兘锛?
 * - HITL锛堜汉宸ュ鎵癸級鏀寔
 * - 涓婁笅鏂囨憳瑕佷腑闂翠欢
 * - MCP 宸ュ叿璋冪敤
 */
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
      stream: false  // 鍏抽敭锛氫娇鐢ㄩ潪娴佸紡妯″紡
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
      // Token 杩囨湡锛屽皾璇曞埛鏂?
      const newToken = await refreshAccessToken();
      if (!newToken) {
        return {
          status: 'error',
          code: 401,
          message: '登录已过期，请重新登录',
          data: null as unknown as AgentLoopNonStreamResponse,
          errors: { detail: ['Token 鍒锋柊澶辫触'] }
        };
      }

      // 浣跨敤鏂?token 閲嶈瘯
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
      message: error.message || '璇锋眰澶辫触',
      data: null as unknown as AgentLoopNonStreamResponse,
      errors: { detail: [error.message || 'Unknown error'] }
    };
  }
}

/**
 * 鍒锋柊token
 */
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

    // 鍒锋柊澶辫触锛岀櫥鍑虹敤鎴?
    authStore.logout();
    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    authStore.logout();
    return null;
  }
}

/**
 * 鍙戦€佹祦寮忓璇濇秷鎭?
 */
export async function sendChatMessageStream(
  data: ChatRequest,
  onStart: (sessionId: string) => void, // 绠€鍖栧洖璋冿紝鍙繚鐣?onStart
  signal?: AbortSignal
): Promise<void> {
  let token = await ensureAccessToken();
  let streamSessionId: string | null = data.session_id || null;

  // 閿欒澶勭悊鍑芥暟锛岀敤浜庢洿鏂板叏灞€鐘舵€?
  const handleError = (error: any, sessionId: string | null) => {
    // 鍒ゆ柇鏄惁鏄敤鎴蜂富鍔ㄤ腑鏂紙AbortError锛?
    const isAbortError = error?.name === 'AbortError' ||
                         error?.message?.includes('aborted') ||
                         error?.message?.includes('BodyStreamBuffer') ||
                         error?.message?.includes('The user aborted');

    if (isAbortError) {
      // 鐢ㄦ埛涓诲姩涓柇锛岄潤榛樺鐞嗭紝涓嶆樉绀洪敊璇?
      console.log('[ChatService] Stream aborted by user');
      if (sessionId && activeStreams.value[sessionId]) {
        activeStreams.value[sessionId].isComplete = true;
        // 涓嶈缃?error锛岄伩鍏嶆樉绀洪敊璇彁绀?
      }
      return;
    }

    // 鐪熸鐨勯敊璇?
    console.error('Stream error:', error);
    if (sessionId && activeStreams.value[sessionId]) {
      activeStreams.value[sessionId].error = error.message || '娴佸紡璇锋眰澶辫触';
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
        // 娴佺粨鏉熸椂锛屽鐞哹uffer涓墿浣欑殑鏁版嵁
        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.trim() === '' || !line.startsWith('data: ')) continue;
            
            const jsonData = line.slice(6);
            if (jsonData === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(jsonData);
              
              // 澶勭悊涓婁笅鏂嘥oken鏇存柊浜嬩欢
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
        
        // 鈿狅笍 娴佺粨鏉熶絾鏈敹鍒?complete/[DONE] 浜嬩欢 = 寮傚父涓柇
        // 涓嶈嚜鍔ㄨ缃?isComplete锛岃鍓嶇淇濇寔鍔犺浇鐘舵€佺洿鍒扮敤鎴锋墜鍔ㄥ埛鏂?
        // 杩欓伩鍏嶄簡缃戠粶娉㈠姩瀵艰嚧鍋滄鎸夐挳杩囨棭娑堝け鐨勯棶棰?
        // HITL: 濡傛灉姝ｅ湪绛夊緟瀹℃壒锛屼笉璁剧疆閿欒鐘舵€?
        if (streamSessionId && activeStreams.value[streamSessionId] && 
            !activeStreams.value[streamSessionId].isComplete &&
            !activeStreams.value[streamSessionId].isWaitingForApproval) {
            console.warn('[ChatService] Stream ended without complete event, possible network interruption');
            // 璁剧疆閿欒鐘舵€佽€岄潪瀹屾垚鐘舵€侊紝璁╃敤鎴风煡閬撳彲鑳介渶瑕侀噸璇?
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
                // HITL: 濡傛灉姝ｅ湪绛夊緟瀹℃壒锛屼笉璁剧疆 isComplete锛岃 resumeAgentLoop 澶勭悊鍚庣画娴佺▼
                if (!activeStreams.value[streamSessionId].isWaitingForApproval) {
                    activeStreams.value[streamSessionId].isComplete = true;
                }
            }
            continue;
        }

        try {
          const parsed = JSON.parse(jsonData);

          if (parsed.type === 'error') {
            handleError(new Error(parsed.message || '娴佸紡璇锋眰澶辫触'), streamSessionId);
            return;
          }

          if (parsed.type === 'start' && parsed.session_id) {
            streamSessionId = parsed.session_id;
            if (streamSessionId) {
              // 浠庣紦瀛樹腑鑾峰彇涓婁竴娆＄殑token浣跨敤淇℃伅锛岄伩鍏嶉棯鐑?
              const cachedUsage = latestContextUsage.value[streamSessionId];
              const prevTokenCount = cachedUsage?.tokenCount || 0;
              const contextLimit = parsed.context_limit || cachedUsage?.limit || 128000;
              const initialMaxSteps = normalizeNumericField(parsed.max_steps);

              // 鍒濆鍖栨垨閲嶇疆姝や細璇濈殑娴佺姸鎬侊紝淇濈暀涔嬪墠鐨則oken淇℃伅
              activeStreams.value[streamSessionId] = {
                content: '',
                isComplete: false,
                messages: [],
                contextTokenCount: prevTokenCount,
                contextLimit: contextLimit,
                currentStep: 0,
                maxSteps: initialMaxSteps,
                userMessage: data.message, // 淇濆瓨鐢ㄦ埛娑堟伅
                userMessageTime: formatIsoTime(parsed.created_at) // 浣跨敤浼氳瘽鍒涘缓鏃堕棿
              };
              onStart(streamSessionId);
            }
          }

          // 澶勭悊涓婁笅鏂嘥oken鏇存柊浜嬩欢
          if (parsed.type === 'context_update' && streamSessionId) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            
            // 鎬绘槸鏇存柊鐙珛缂撳瓨锛堜紭鍏堜繚璇佺紦瀛樿鏇存柊锛?
            latestContextUsage.value[streamSessionId] = { tokenCount, limit };
            
            // 濡傛灉娲昏穬娴佽繕瀛樺湪锛屼篃鏇存柊瀹?
            if (activeStreams.value[streamSessionId]) {
              activeStreams.value[streamSessionId].contextTokenCount = tokenCount;
              activeStreams.value[streamSessionId].contextLimit = limit;
            }
          }

          // 澶勭悊璀﹀憡浜嬩欢锛堝涓婁笅鏂囧嵆灏嗘弧锛?
          if (parsed.type === 'warning' && streamSessionId && activeStreams.value[streamSessionId]) {
            const warningMessage = parsed.message || '璀﹀憡';
            console.warn('[Chat] Warning:', warningMessage);
            activeStreams.value[streamSessionId].messages.push({
              content: warningMessage,
              type: 'system',
              time: formatStreamTime()
            });
          }

          // 澶勭悊 Agent Loop 姝ラ寮€濮嬩簨浠?
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

          // 澶勭悊 Agent Loop 姝ラ瀹屾垚浜嬩欢
          if (parsed.type === 'step_complete' && streamSessionId && activeStreams.value[streamSessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[streamSessionId].currentStep = stepNumber;
            }
            // 鉁?绉婚櫎step_complete鐨勯噸澶嶅垎闅旂鏄剧ず
            // step_start宸茬粡鎻掑叆浜嗗垎闅旂,step_complete涓嶉渶瑕佸啀鏄剧ず
          }

          // 澶勭悊 Agent Loop 宸ュ叿缁撴灉浜嬩欢
          if (parsed.type === 'tool_result' && streamSessionId && activeStreams.value[streamSessionId]) {
            if (shouldHideToolMessage(parsed.tool_name, parsed.tool_output || parsed.content || parsed.summary)) {
              continue;
            }
            // 浼樺厛浣跨敤 tool_output锛堝畬鏁村唴瀹癸級锛宖allback 鍒?summary锛堟埅鏂憳瑕侊級
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = buildToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              // 濡傛灉褰撳墠鏈堿I娴佸紡鍐呭,鍏堝皢鍏跺浐鍖栦负鐙珛娑堟伅
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

          // 澶勭悊宸ュ叿娑堟伅(update浜嬩欢) - 鍏煎鏃?LangGraph 鏍煎紡
          if (parsed.type === 'update' && streamSessionId && activeStreams.value[streamSessionId]) {
            const updateData = parsed.data;
            if (typeof updateData === 'string') {
              // 瑙ｆ瀽宸ュ叿娑堟伅
              // 鏍煎紡绫讳技: "{'agent': {'messages': [ToolMessage(content='...', name='tool_name', ...)]}}"
              if (updateData.includes('ToolMessage')) {
                try {
                  const toolNameMatch = updateData.match(/name='([^']+)'/);
                  const toolName = toolNameMatch?.[1];
                  if (shouldHideToolMessage(toolName, updateData)) {
                    continue;
                  }
                  // 鎻愬彇宸ュ叿娑堟伅鍐呭
                  const contentMatch = updateData.match(/content='([^']*(?:\\'[^']*)*)'/);
                  
                  if (contentMatch) {
                    const toolContent = contentMatch[1].replace(/\\'/g, "'").replace(/\\n/g, '\n');
                    const time = formatStreamTime();
                    
                    // 濡傛灉褰撳墠鏈堿I娴佸紡鍐呭,鍏堝皢鍏跺浐鍖栦负鐙珛娑堟伅
                    if (activeStreams.value[streamSessionId].content && activeStreams.value[streamSessionId].content.trim()) {
                      activeStreams.value[streamSessionId].messages.push({
                        content: activeStreams.value[streamSessionId].content,
                        type: 'ai',
                        time: time,
                        isExpanded: false
                      });
                      activeStreams.value[streamSessionId].content = '';
                    }
                    
                    // 娣诲姞宸ュ叿娑堟伅浣滀负鏂扮殑鐙珛娑堟伅
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

          // 猸?澶勭悊鐪熸鐨勬祦寮忚緭鍑?(type === 'stream') - Agent Loop 閫愬瓧娴佸紡
          if (parsed.type === 'stream' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          // 猸?娴佸紡缁撴潫浜嬩欢
          if (parsed.type === 'stream_end' && streamSessionId && activeStreams.value[streamSessionId]) {
            // 娴佸紡缁撴潫锛屽唴瀹瑰凡閫氳繃 stream 浜嬩欢绱Н
            // 涓嶉渶瑕佺壒娈婂鐞嗭紝绛夊緟 complete 浜嬩欢鏍囪瀹屾垚
          }

          // 澶勭悊AI娑堟伅(message浜嬩欢) - 鍏煎鏃ф牸寮忥紙闈炴祦寮忔ā寮忥級
          if (parsed.type === 'message' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parseMessageContent(parsed.data);
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          // 猸?澶勭悊 HITL 涓柇浜嬩欢
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
            // 鉁?淇锛氭爣璁板畬鎴愶紝淇濇寔content涓嶅彉锛圴ue缁勪欢浼氫粠content璇诲彇鏈€缁堟秷鎭級
            // 涓嶆竻绌篶ontent锛屽洜涓篸isplayedMessages鍜寃atch閮戒緷璧杝tream.content鏉ユ樉绀烘渶缁圓I鍥炲
            activeStreams.value[streamSessionId].isComplete = true;
            
            // 猸?淇濆瓨浠诲姟 ID
            if (parsed.task_id) {
              activeStreams.value[streamSessionId].taskId = parsed.task_id;
            }
            
            // 猸?澶勭悊鑴氭湰鐢熸垚淇℃伅
            if (parsed.script_generation && parsed.script_generation.available) {
              activeStreams.value[streamSessionId].scriptGeneration = {
                available: true,
                playwrightSteps: parsed.script_generation.playwright_steps || 0,
                message: parsed.script_generation.message || '鍙敓鎴愯嚜鍔ㄥ寲鐢ㄤ緥'
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

/**
 * 鑾峰彇鑱婂ぉ鍘嗗彶璁板綍
 * @param sessionId 浼氳瘽ID
 * @param projectId 椤圭洰ID
 */
export async function getChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<ChatHistoryResponseData>> {
  const response = await request<ChatHistoryResponseData>({
    url: `${API_BASE_URL}/history/`,
    method: 'GET',
    params: {
      session_id: sessionId,
      project_id: String(projectId) // 纭繚杞崲涓簊tring
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

/**
 * 鍒犻櫎鑱婂ぉ鍘嗗彶璁板綍
 * @param sessionId 瑕佸垹闄ゅ巻鍙茶褰曠殑浼氳瘽ID
 * @param projectId 椤圭洰ID
 */
export async function deleteChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: `${API_BASE_URL}/history/`,
    method: 'DELETE',
    params: {
      session_id: sessionId,
      project_id: String(projectId) // 纭繚杞崲涓簊tring
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

/**
 * 鍥炴粴鑱婂ぉ鍘嗗彶璁板綍鍒版寚瀹氭秷鎭暟閲?
 * @param sessionId 浼氳瘽ID
 * @param projectId 椤圭洰ID
 * @param keepCount 瑕佷繚鐣欑殑娑堟伅鏁伴噺
 */
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

/**
 * 鑾峰彇鐢ㄦ埛鐨勬墍鏈変細璇濆垪琛?
 * @param projectId 椤圭洰ID
 */
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

/**
 * 鎵归噺鍒犻櫎鑱婂ぉ鍘嗗彶璁板綍
 * @param sessionIds 瑕佸垹闄ょ殑浼氳瘽ID鏁扮粍
 * @param projectId 椤圭洰ID
 */
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
      message: response.message || '鎵归噺鍒犻櫎鎴愬姛',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '鎵归噺鍒犻櫎澶辫触',
      data: { deleted_count: 0, processed_sessions: 0, failed_sessions: [] },
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 鍋滄 Agent Loop 鐢熸垚
 * @param sessionId 瑕佸仠姝㈢殑浼氳瘽ID
 */
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
        message: data.message || '鍋滄澶辫触',
        data: { success: false, session_id: sessionId, message: '' },
        errors: data.errors || { detail: ['Unknown error'] }
      };
    }
  } catch (error) {
    console.error('[ChatService] Stop agent loop error:', error);
    return {
      status: 'error',
      code: 500,
      message: error instanceof Error ? error.message : '鍋滄璇锋眰澶辫触',
      data: { success: false, session_id: sessionId, message: '' },
      errors: { detail: [error instanceof Error ? error.message : 'Unknown error'] }
    };
  }
}

/**
 * 鎭㈠琚?HITL 涓柇鐨?Agent Loop 鎵ц (SSE 娴佸紡鐗堟湰)
 *
 * 鍚庣鐜板湪杩斿洖 SSE 娴佸紡鍝嶅簲锛屼笌涓绘祦鏍煎紡涓€鑷淬€?
 * 杩欐牱 resume 鍚庣殑宸ュ叿鎵ц缁撴灉銆丩LM 鍝嶅簲閮借兘瀹炴椂娴佸紡灞曠ず銆?
 *
 * @param sessionId 浼氳瘽ID
 * @param interruptId 涓柇浜嬩欢ID
 * @param decision 鐢ㄦ埛鍐崇瓥 ('approve' | 'reject')
 * @param projectId 椤圭洰ID
 * @param signal 鍙€夌殑 AbortSignal 鐢ㄤ簬涓柇璇锋眰
 */
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

  // 纭繚 activeStreams 瀛樺湪锛屽鏋滀笉瀛樺湪鍒欏垵濮嬪寲
  if (!activeStreams.value[sessionId]) {
    activeStreams.value[sessionId] = {
      content: '',
      isComplete: false,
      messages: [],
      isWaitingForApproval: false,
    };
    console.log('[ChatService] Resume: Initialized activeStreams for session', sessionId);
  } else {
    // 鍦ㄥ紑濮嬫柊鐨?resume 涔嬪墠锛屽皢褰撳墠绱Н鐨?content 鍥哄寲鍒?messages
    // 杩欐牱鎷掔粷鍚庣殑鏂板洖澶嶄細鏄剧ず涓虹嫭绔嬬殑娑堟伅妗?
    if (activeStreams.value[sessionId].content?.trim()) {
      activeStreams.value[sessionId].messages.push({
        content: activeStreams.value[sessionId].content,
        type: 'ai',
        time: formatStreamTime(),
        isExpanded: false
      });
      activeStreams.value[sessionId].content = '';
    }
    // 娓呴櫎涓柇鐘舵€侊紝鍑嗗鎺ユ敹鏂扮殑娴?
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
    activeStreams.value[sessionId].isComplete = false;
  }

  // 閿欒澶勭悊鍑芥暟
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
      activeStreams.value[sessionId].error = error.message || '鎭㈠鎵ц澶辫触';
      activeStreams.value[sessionId].isComplete = true;
    }
  };

  if (!token) {
    handleError(new Error('未登录或登录已过期'));
    return;
  }

  try {
    // 鏋勫缓 resume 鏁版嵁锛圠angChain Command 鏍煎紡锛?
    const resumeData: Record<string, any> = {
      session_id: sessionId,
      project_id: projectId,
      resume: {
        [interruptId]: {
          decisions: [{ type: decision }],
          action_count: actionCount || 1  // 浼犻€掑伐鍏疯皟鐢ㄦ暟閲?
        }
      }
    };

    // 娣诲姞鐭ヨ瘑搴撳弬鏁?
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

    // Token 杩囨湡閲嶈瘯
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
        // 娴佺粨鏉燂紝澶勭悊鍓╀綑鏁版嵁
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
              // 蹇界暐瑙ｆ瀽寮傚父
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
            handleError(new Error(parsed.message || '鎭㈠鎵ц澶辫触'));
            return;
          }

          // resume_start 浜嬩欢 - resume 寮€濮?
          if (parsed.type === 'resume_start' && activeStreams.value[sessionId]) {
            console.log('[ChatService] Resume started:', parsed.decision);
          }

          // 澶勭悊涓婁笅鏂?Token 鏇存柊
          if (parsed.type === 'context_update' && activeStreams.value[sessionId]) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            latestContextUsage.value[sessionId] = { tokenCount, limit };
            activeStreams.value[sessionId].contextTokenCount = tokenCount;
            activeStreams.value[sessionId].contextLimit = limit;
          }

          // 澶勭悊姝ラ寮€濮嬩簨浠?
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

          // 澶勭悊姝ラ瀹屾垚浜嬩欢
          if (parsed.type === 'step_complete' && activeStreams.value[sessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[sessionId].currentStep = stepNumber;
            }
          }

          // 澶勭悊宸ュ叿缁撴灉浜嬩欢
          if (parsed.type === 'tool_result' && activeStreams.value[sessionId]) {
            if (shouldHideToolMessage(parsed.tool_name, parsed.tool_output || parsed.content || parsed.summary)) {
              continue;
            }
            // 浼樺厛浣跨敤 tool_output锛堝畬鏁村唴瀹癸級锛宖allback 鍒?summary锛堟埅鏂憳瑕侊級
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = buildToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              // 鍏堝浐鍖栧綋鍓?AI 鍐呭
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

          // 澶勭悊 LLM 娴佸紡杈撳嚭
          if (parsed.type === 'stream' && activeStreams.value[sessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[sessionId].content += content;
            }
          }

          // 澶勭悊鏂扮殑 HITL 涓柇锛坮esume 鍚庡彲鑳藉張瑙﹀彂鏂颁腑鏂級
          if (parsed.type === 'interrupt' && activeStreams.value[sessionId]) {
            console.log('[ChatService] New interrupt after resume:', parsed);
            activeStreams.value[sessionId].interrupt = {
              id: parsed.interrupt_id || parsed.id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || []
            };
            activeStreams.value[sessionId].isWaitingForApproval = true;
          }

          // 澶勭悊瀹屾垚浜嬩欢
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

/**
 * 鎭㈠琚?HITL 涓柇鐨?LangGraph Chat 鎵ц锛圫SE 娴佸紡鍝嶅簲锛?
 * @param sessionId 浼氳瘽ID
 * @param decision 鐢ㄦ埛鍐崇瓥 ('approve' | 'reject')
 * @param projectId 椤圭洰ID
 * @param onMessage 娑堟伅鍥炶皟
 * @param onComplete 瀹屾垚鍥炶皟
 * @param onError 閿欒鍥炶皟
 */
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
            // 蹇界暐瑙ｆ瀽閿欒
          }
        }
      }
    }

    // 娓呴櫎涓柇鐘舵€?
    clearInterruptState(sessionId);
    onComplete?.();
  } catch (error) {
    console.error('[ChatService] Resume chat stream error:', error);
    onError?.(error instanceof Error ? error.message : 'Resume failed');
  }
}

/**
 * 娓呴櫎浼氳瘽鐨勪腑鏂姸鎬?
 * @param sessionId 浼氳瘽ID
 */
export function clearInterruptState(sessionId: string): void {
  if (activeStreams.value[sessionId]) {
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
  }
}



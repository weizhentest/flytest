// 认证服务
import axios from 'axios';
import { request } from '@/utils/request';

// 用户信息结构
interface UserInfo {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number?: string;
  real_name?: string;
  is_staff: boolean;
  is_active: boolean;
  groups: any[];
}

// API 响应的数据结构
interface ApiTokenResponseData {
  refresh: string;
  access: string;
  user: UserInfo;
}

interface ApiTokenResponse {
  status: string;
  code: number;
  message: string;
  data: ApiTokenResponseData;
}

// 注册 API 响应的数据结构
interface ApiRegisterResponseData {
  id: number;
  username: string;
  email: string;
  phone_number?: string;
  real_name?: string;
}

interface ApiRegisterResponse {
  status: string;
  code: number;
  message: string;
  data: ApiRegisterResponseData;
}

// 登录函数返回的结构
export interface AuthServiceLoginResponse {
  success: boolean;
  data?: ApiTokenResponseData; // 成功时包含 token 数据
  error?: string; // 失败时包含错误信息
  statusCode?: number; // API 返回的状态码
}

// 注册函数返回的结构
export interface AuthServiceRegisterResponse {
  success: boolean;
  data?: ApiRegisterResponseData; // 成功时包含用户数据
  error?: string; // 失败时包含错误信息
  statusCode?: number;
}

/**
 * 调用用户认证接口
 * @param username 用户名
 * @param password 密码
 * @returns 返回一个 Promise，解析为包含认证结果的对象
 */

function normalizeAuthErrorMessage(message?: string, fallback = '服务暂时不可用，请稍后重试。'): string {
  const normalizedMessage = (message || '').trim();
  if (!normalizedMessage) {
    return fallback;
  }

  const lowerMessage = normalizedMessage.toLowerCase();
  if (
    lowerMessage.includes('internal server error') ||
    lowerMessage.includes('request failed with status code 500')
  ) {
    return '服务器开小差了，请稍后重试。';
  }

  if (lowerMessage.includes('network error')) {
    return '网络连接异常，请检查网络后重试。';
  }

  if (lowerMessage.includes('expected available in')) {
    return '请求过于频繁，请稍后再试。';
  }

  return normalizedMessage;
}

export const login = async (username: string, password: string, rememberMe = false): Promise<AuthServiceLoginResponse> => {
  const API_URL = '/token/'; // 使用相对路径，由 axiosInstance 的 baseURL 处理

  try {
    const response = await request<ApiTokenResponseData>({
      url: API_URL,
      method: 'POST',
      data: {
        username,
        password,
        remember_me: rememberMe,
      },
      headers: {
        'X-FlyTest-Login-Source': 'login-page',
        'Content-Type': 'application/json',
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 200,
      };
    } else {
      // API 返回了非 success 状态或数据格式不正确
      const responseStatus = (response as any).status as number | undefined;
      let errorMessage = response.error || '认证失败：响应数据格式不正确。';

      if (responseStatus === 503) {
        errorMessage = response.error || '认证服务正在启动，请稍后重试。';
      } else if (errorMessage.includes('服务器无响应') || errorMessage.includes('Network Error')) {
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }

      return {
        success: false,
        error: normalizeAuthErrorMessage(errorMessage, '认证服务暂时不可用，请稍后重试。'),
        statusCode: responseStatus ?? 500,
      };
    }
  } catch (error) {
    let errorMessage = '认证服务暂时不可用，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        // 后端返回了错误响应
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (statusCode === 503) {
          errorMessage = '认证服务正在启动，请稍后重试。';
        } else if (responseData && typeof responseData.message === 'string') {
          errorMessage = normalizeAuthErrorMessage(responseData.message);
        } else if (responseData && typeof responseData.detail === 'string') { // Django REST framework 常见错误格式
          errorMessage = normalizeAuthErrorMessage(responseData.detail);
        } else if (responseData && responseData.username && Array.isArray(responseData.username) && responseData.username.length > 0) {
          errorMessage = responseData.username.join(', ');
        } else {
          errorMessage = `认证失败：服务器错误 (${statusCode})。`;
        }
      } else if (error.request) {
        // 请求已发出，但没有收到响应 (例如网络错误)
        errorMessage = '认证服务暂未就绪，请稍后重试。';
      }
    }
    // 对于其他类型的错误，保留通用消息
    return {
      success: false,
      error: normalizeAuthErrorMessage(errorMessage, '认证服务暂时不可用，请稍后重试。'),
      statusCode,
    };
  }
};

/**
 * 调用用户注册接口
 * @param realName 姓名
 * @param phoneNumber 手机号
 * @param password 密码
 * @returns 返回一个 Promise，解析为包含注册结果的对象
 */
export const register = async (realName: string, phoneNumber: string, password: string): Promise<AuthServiceRegisterResponse> => {
  const API_URL = '/accounts/register/'; // 使用相对路径，由 axiosInstance 的 baseURL 处理

  try {
    const response = await request<ApiRegisterResponseData>({
      url: API_URL,
      method: 'POST',
      data: {
        real_name: realName,
        phone_number: phoneNumber,
        password,
      },
      headers: {
        'Content-Type': 'application/json',
        'accept': 'application/json',
      }
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 201,
      };
    } else {
      return {
        success: false,
        error: response.error || '注册失败：响应数据格式不正确。',
        statusCode: 500,
      };
    }
  } catch (error) {
    let errorMessage = '注册服务暂时不可用，请稍后再试。';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;
        if (responseData && typeof responseData.message === 'string') {
          errorMessage = normalizeAuthErrorMessage(responseData.message, '???????????');
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = normalizeAuthErrorMessage(responseData.detail, '???????????');
        } else if (responseData && responseData.phone_number && Array.isArray(responseData.phone_number) && responseData.phone_number.length > 0) {
          errorMessage = responseData.phone_number.join(', ');
        } else if (responseData && responseData.real_name && Array.isArray(responseData.real_name) && responseData.real_name.length > 0) {
          errorMessage = responseData.real_name.join(', ');
        } else if (responseData && responseData.password && Array.isArray(responseData.password) && responseData.password.length > 0) {
          errorMessage = responseData.password.join(', ');
        } else if (statusCode === 400) {
          errorMessage = '请填写真实的手机号';
        }
         else {
          errorMessage = `注册失败：服务器错误 (${statusCode})。`;
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应。';
      }
    }
    return {
      success: false,
      error: normalizeAuthErrorMessage(errorMessage, '认证服务暂时不可用，请稍后重试。'),
      statusCode,
    };
  }
};

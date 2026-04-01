// 用例模版服务
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';

/**
 * 提取后端统一响应包装器中的实际数据
 * 后端使用 UnifiedResponseRenderer 包装所有响应，格式为:
 * 包含字段：status、code、message、data、errors
 */
function unwrapResponse<T>(responseData: any): T {
  if (responseData && typeof responseData === 'object' && 'status' in responseData && 'data' in responseData) {
    return responseData.data as T;
  }
  return responseData as T;
}

// 模版类型
export type TemplateType = 'import' | 'export' | 'both';

// 步骤解析模式
export type StepParsingMode = 'single_cell' | 'multi_row';

// 字段映射配置
export interface FieldMappings {
  name?: string;
  module?: string;
  precondition?: string;
  level?: string;
  notes?: string;
  steps?: string;
  expected_results?: string;
  [key: string]: string | undefined;
}

// 值转换规则
export interface ValueTransformations {
  [fieldName: string]: { [inputValue: string]: string };
}

// 步骤解析配置
export interface StepConfig {
  step_column?: string;
  expected_column?: string;
  pattern?: string;
  case_identifier_column?: string;
}

// 导入导出模版接口
export interface ImportExportTemplate {
  id: number;
  name: string;
  template_type: TemplateType;
  template_type_display: string;
  description?: string;
  sheet_name?: string;
  template_file?: string | null;
  template_headers: string[];
  header_row: number;
  data_start_row: number;
  field_mappings: FieldMappings;
  value_transformations: ValueTransformations;
  step_parsing_mode: StepParsingMode;
  step_parsing_mode_display: string;
  step_config: StepConfig;
  module_path_delimiter: string;
  is_active: boolean;
  creator?: number;
  creator_name?: string;
  created_at: string;
  updated_at: string;
}

// 模版列表项（简化版）
export interface ImportExportTemplateListItem {
  id: number;
  name: string;
  template_type: TemplateType;
  template_type_display: string;
  description?: string;
  is_active: boolean;
  creator_name?: string;
  created_at: string;
  updated_at: string;
}

// 创建/更新模版请求
export interface TemplateFormData {
  name: string;
  template_type: TemplateType;
  description?: string;
  sheet_name?: string;
  template_headers?: string[];
  header_row: number;
  data_start_row: number;
  field_mappings: FieldMappings;
  value_transformations: ValueTransformations;
  step_parsing_mode: StepParsingMode;
  step_config: StepConfig;
  module_path_delimiter: string;
  is_active: boolean;
}

// 解析表头响应
export interface ParseHeadersResponse {
  headers: string[];
  sheet_names: string[];
  row_count: number;
  sample_data: { [key: string]: string }[];
}

// 字段选项
export interface FieldOption {
  value: string;
  label: string;
  required: boolean;
  has_transform?: boolean;
  is_step_field?: boolean;
}

// 导入结果
export interface ImportResult {
  success: boolean;
  total_rows: number;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  duplicate_names: {
    row: number;
    name: string;
    module: string;
    existing_ids: number[];
  }[];
  errors: {
    row: number;
    error: string;
    name?: string;
  }[];
  created_testcase_ids: number[];
}

// API 操作响应
export interface OperationResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/**
 * 获取模版列表
 */
export const getTemplateList = async (params?: {
  template_type?: TemplateType;
  is_active?: boolean;
}): Promise<OperationResponse<ImportExportTemplateListItem[]>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/testcase-templates/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      params,
    });
    // 处理统一响应包装器，然后处理分页响应或直接数组响应
    const unwrapped = unwrapResponse<any>(response.data);
    const data = Array.isArray(unwrapped) ? unwrapped : (unwrapped?.results || []);
    return { success: true, data };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '获取模版列表失败',
    };
  }
};

/**
 * 获取模版详情
 */
export const getTemplateDetail = async (id: number): Promise<OperationResponse<ImportExportTemplate>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/testcase-templates/${id}/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true, data: unwrapResponse<ImportExportTemplate>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '获取模版详情失败',
    };
  }
};

/**
 * 创建模版
 */
export const createTemplate = async (data: TemplateFormData): Promise<OperationResponse<ImportExportTemplate>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/testcase-templates/`, data, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true, data: unwrapResponse<ImportExportTemplate>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.name?.[0] || error.message || '创建模版失败',
    };
  }
};

/**
 * 更新模版
 */
export const updateTemplate = async (id: number, data: Partial<TemplateFormData>): Promise<OperationResponse<ImportExportTemplate>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.patch(`${API_BASE_URL}/testcase-templates/${id}/`, data, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true, data: unwrapResponse<ImportExportTemplate>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '更新模版失败',
    };
  }
};

/**
 * 删除模版
 */
export const deleteTemplate = async (id: number): Promise<OperationResponse<void>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    await axios.delete(`${API_BASE_URL}/testcase-templates/${id}/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '删除模版失败',
    };
  }
};

/**
 * 解析 Excel 表头
 */
export const parseExcelHeaders = async (
  file: File,
  sheetName?: string,
  headerRow?: number
): Promise<OperationResponse<ParseHeadersResponse>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const formData = new FormData();
    formData.append('file', file);
    if (sheetName) formData.append('sheet_name', sheetName);
    if (headerRow) formData.append('header_row', String(headerRow));

    const response = await axios.post(`${API_BASE_URL}/testcase-templates/parse_headers/`, formData, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'multipart/form-data',
      },
    });
    return { success: true, data: unwrapResponse<ParseHeadersResponse>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '解析 Excel 表头失败',
    };
  }
};

/**
 * 获取可映射的字段选项
 */
export const getFieldOptions = async (): Promise<OperationResponse<{
  fields: FieldOption[];
  level_options: { value: string; label: string }[];
}>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/testcase-templates/field_options/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true, data: unwrapResponse<{ fields: FieldOption[]; level_options: { value: string; label: string }[] }>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '获取字段选项失败',
    };
  }
};

/**
 * 复制模版
 */
export const duplicateTemplate = async (id: number): Promise<OperationResponse<ImportExportTemplate>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/testcase-templates/${id}/duplicate/`, {}, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return { success: true, data: unwrapResponse<ImportExportTemplate>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '复制模版失败',
    };
  }
};

/**
 * 导入用例
 */
export const importTestCases = async (
  projectId: number,
  file: File,
  templateId: number
): Promise<OperationResponse<ImportResult>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_id', String(templateId));

    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/import-excel/`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return { success: true, data: unwrapResponse<ImportResult>(response.data) };
  } catch (error: any) {
    return {
      success: false,
      data: error.response?.data,
      error: error.response?.data?.error || error.message || '导入用例失败',
    };
  }
};

/**
 * 使用模版导出用例
 */
export const exportTestCasesWithTemplate = async (
  projectId: number,
  templateId?: number | null,
  testCaseIds?: number[],
  moduleIds?: number[]
): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const params: Record<string, string> = {};
    if (templateId) {
      params.template_id = String(templateId);
    }
    if (testCaseIds && testCaseIds.length > 0) {
      params.ids = testCaseIds.join(',');
    }
    if (moduleIds && moduleIds.length > 0) {
      params.module_ids = moduleIds.join(',');
    }

    const response = await axios.get(
      `${API_BASE_URL}/projects/${projectId}/testcases/export-excel/`,
      {
        params,
        headers: { Authorization: `Bearer ${accessToken}` },
        responseType: 'blob',
      }
    );

    if (response.data instanceof Blob) {
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;

      const contentDisposition = response.headers['content-disposition'];
      let filename = `测试用例导出_${new Date().toISOString().split('T')[0]}.xlsx`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      return { success: true, message: '导出成功' };
    }
    return { success: false, error: '服务器返回的不是有效的文件数据' };
  } catch (error: any) {
    let errorMessage = '导出用例失败';
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text();
        const errorData = JSON.parse(text);
        errorMessage = errorData.error || errorMessage;
      } catch {
        // 忽略解析错误
      }
    }
    return { success: false, error: errorMessage };
  }
};

/**
 * 上传并绑定模板文件（用于导出保留样式/合并单元格/标题行等）
 */
export const uploadTemplateFile = async (
  templateId: number,
  file: File
): Promise<OperationResponse<{ template_file?: string | null; template_headers?: string[] }>> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return { success: false, error: '未登录或会话已过期' };
  }

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post(
      `${API_BASE_URL}/testcase-templates/${templateId}/upload-template-file/`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return { success: true, data: unwrapResponse(response.data) };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.message || '上传模板文件失败',
    };
  }
};

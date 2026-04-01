import type { AxiosProgressEvent } from 'axios'
import request from '@/utils/request'
import type {
  ApiCollection,
  ApiCollectionForm,
  ApiEnvironment,
  ApiEnvironmentForm,
  ApiExecutionBatchResult,
  ApiExecutionRecord,
  ApiExecutionReport,
  ApiImportResult,
  ApiImportJob,
  ApiRequest,
  ApiRequestForm,
  ApiResponse,
  ApiTestCase,
  ApiTestCaseForm,
  ApiTestCaseGenerationResult,
} from '../types'

const BASE_URL = '/api-automation'

export const collectionApi = {
  list: (params?: { project?: number; parent?: number | null }) =>
    request.get<ApiResponse<ApiCollection[]>>(`${BASE_URL}/collections/`, { params }),

  tree: (projectId: number) =>
    request.get<ApiResponse<ApiCollection[]>>(`${BASE_URL}/collections/tree/`, { params: { project: projectId } }),

  create: (data: ApiCollectionForm) => request.post<ApiResponse<ApiCollection>>(`${BASE_URL}/collections/`, data),

  update: (id: number, data: Partial<ApiCollectionForm>) =>
    request.patch<ApiResponse<ApiCollection>>(`${BASE_URL}/collections/${id}/`, data),

  delete: (id: number) => request.delete<ApiResponse<null>>(`${BASE_URL}/collections/${id}/`),
}

export const apiRequestApi = {
  list: (params?: { project?: number; collection?: number; method?: string }) =>
    request.get<ApiResponse<ApiRequest[]>>(`${BASE_URL}/requests/`, { params }),

  create: (data: ApiRequestForm) => request.post<ApiResponse<ApiRequest>>(`${BASE_URL}/requests/`, data),

  importDocument: (
    collectionId: number,
    file: File,
    options?: {
      generateTestCases?: boolean
      enableAiParse?: boolean
      onUploadProgress?: (event: AxiosProgressEvent) => void
      asyncMode?: boolean
    }
  ) => {
    const formData = new FormData()
    formData.append('collection_id', String(collectionId))
    formData.append('file', file)
    if (options?.generateTestCases !== undefined) {
      formData.append('generate_test_cases', String(options.generateTestCases))
    }
    if (options?.enableAiParse !== undefined) {
      formData.append('enable_ai_parse', String(options.enableAiParse))
    }
    if (options?.asyncMode !== undefined) {
      formData.append('async_mode', String(options.asyncMode))
    }
    return request.post<ApiResponse<ApiImportJob | ApiImportResult>>(`${BASE_URL}/requests/import-document/`, formData, {
      onUploadProgress: options?.onUploadProgress,
      timeout: 10 * 60 * 1000,
    })
  },

  update: (id: number, data: Partial<ApiRequestForm>) =>
    request.patch<ApiResponse<ApiRequest>>(`${BASE_URL}/requests/${id}/`, data),

  delete: (id: number) => request.delete<ApiResponse<null>>(`${BASE_URL}/requests/${id}/`),

  execute: (id: number, environmentId?: number) =>
    request.post<ApiResponse<ApiExecutionRecord>>(`${BASE_URL}/requests/${id}/execute/`, {
      environment_id: environmentId,
    }),

  executeBatch: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  }) => request.post<ApiResponse<ApiExecutionBatchResult>>(`${BASE_URL}/requests/execute-batch/`, data),

  generateTestCases: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    mode: 'generate' | 'append' | 'regenerate'
    count_per_request?: number
  }) => request.post<ApiResponse<ApiTestCaseGenerationResult>>(`${BASE_URL}/requests/generate-test-cases/`, data),
}

export const importJobApi = {
  list: (params?: { project?: number; status?: string }) =>
    request.get<ApiResponse<ApiImportJob[]>>(`${BASE_URL}/import-jobs/`, { params }),

  get: (id: number) => request.get<ApiResponse<ApiImportJob>>(`${BASE_URL}/import-jobs/${id}/`),

  cancel: (id: number) => request.post<ApiResponse<ApiImportJob>>(`${BASE_URL}/import-jobs/${id}/cancel/`),
}

export const environmentApi = {
  list: (params?: { project?: number }) =>
    request.get<ApiResponse<ApiEnvironment[]>>(`${BASE_URL}/environments/`, { params }),

  create: (data: ApiEnvironmentForm) => request.post<ApiResponse<ApiEnvironment>>(`${BASE_URL}/environments/`, data),

  update: (id: number, data: Partial<ApiEnvironmentForm>) =>
    request.patch<ApiResponse<ApiEnvironment>>(`${BASE_URL}/environments/${id}/`, data),

  delete: (id: number) => request.delete<ApiResponse<null>>(`${BASE_URL}/environments/${id}/`),
}

export const executionRecordApi = {
  list: (params?: { project?: number; request?: number; collection?: number }) =>
    request.get<ApiResponse<ApiExecutionRecord[]>>(`${BASE_URL}/execution-records/`, { params }),

  get: (id: number) => request.get<ApiResponse<ApiExecutionRecord>>(`${BASE_URL}/execution-records/${id}/`),

  report: (params?: { project?: number; collection?: number; days?: number }) =>
    request.get<ApiResponse<ApiExecutionReport>>(`${BASE_URL}/execution-records/report/`, { params }),

  delete: (id: number) => request.delete<ApiResponse<null>>(`${BASE_URL}/execution-records/${id}/`),
}

export const testCaseApi = {
  list: (params?: { project?: number; request?: number; collection?: number }) =>
    request.get<ApiResponse<ApiTestCase[]>>(`${BASE_URL}/test-cases/`, { params }),

  get: (id: number) => request.get<ApiResponse<ApiTestCase>>(`${BASE_URL}/test-cases/${id}/`),

  update: (id: number, data: Partial<ApiTestCaseForm>) =>
    request.patch<ApiResponse<ApiTestCase>>(`${BASE_URL}/test-cases/${id}/`, data),

  execute: (id: number, environmentId?: number) =>
    request.post<ApiResponse<ApiExecutionRecord>>(`${BASE_URL}/test-cases/${id}/execute/`, {
      environment_id: environmentId,
    }),

  executeBatch: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  }) => request.post<ApiResponse<ApiExecutionBatchResult>>(`${BASE_URL}/test-cases/execute-batch/`, data),

  delete: (id: number) => request.delete<ApiResponse<null>>(`${BASE_URL}/test-cases/${id}/`),
}

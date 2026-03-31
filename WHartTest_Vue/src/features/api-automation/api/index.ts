import type { AxiosProgressEvent } from 'axios'
import request from '@/utils/request'
import type {
  ApiCollection,
  ApiCollectionForm,
  ApiEnvironment,
  ApiEnvironmentForm,
  ApiExecutionBatchResult,
  ApiExecutionRecord,
  ApiImportResult,
  ApiImportJob,
  ApiRequest,
  ApiRequestForm,
  ApiTestCase,
  ApiTestCaseGenerationResult,
} from '../types'

const BASE_URL = '/api-automation'

export const collectionApi = {
  list: (params?: { project?: number; parent?: number | null }) =>
    request.get<ApiCollection[]>(`${BASE_URL}/collections/`, { params }),

  tree: (projectId: number) =>
    request.get<ApiCollection[]>(`${BASE_URL}/collections/tree/`, { params: { project: projectId } }),

  create: (data: ApiCollectionForm) => request.post<ApiCollection>(`${BASE_URL}/collections/`, data),

  update: (id: number, data: Partial<ApiCollectionForm>) =>
    request.patch<ApiCollection>(`${BASE_URL}/collections/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/collections/${id}/`),
}

export const apiRequestApi = {
  list: (params?: { project?: number; collection?: number; method?: string }) =>
    request.get<ApiRequest[]>(`${BASE_URL}/requests/`, { params }),

  create: (data: ApiRequestForm) => request.post<ApiRequest>(`${BASE_URL}/requests/`, data),

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
    return request.post<ApiImportJob | ApiImportResult>(`${BASE_URL}/requests/import-document/`, formData, {
      onUploadProgress: options?.onUploadProgress,
      timeout: 10 * 60 * 1000,
    })
  },

  update: (id: number, data: Partial<ApiRequestForm>) =>
    request.patch<ApiRequest>(`${BASE_URL}/requests/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/requests/${id}/`),

  execute: (id: number, environmentId?: number) =>
    request.post<ApiExecutionRecord>(`${BASE_URL}/requests/${id}/execute/`, {
      environment_id: environmentId,
    }),

  executeBatch: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  }) => request.post<ApiExecutionBatchResult>(`${BASE_URL}/requests/execute-batch/`, data),

  generateTestCases: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    mode: 'generate' | 'append' | 'regenerate'
    count_per_request?: number
  }) => request.post<ApiTestCaseGenerationResult>(`${BASE_URL}/requests/generate-test-cases/`, data),
}

export const importJobApi = {
  list: (params?: { project?: number; status?: string }) =>
    request.get<ApiImportJob[]>(`${BASE_URL}/import-jobs/`, { params }),

  get: (id: number) => request.get<ApiImportJob>(`${BASE_URL}/import-jobs/${id}/`),
}

export const environmentApi = {
  list: (params?: { project?: number }) =>
    request.get<ApiEnvironment[]>(`${BASE_URL}/environments/`, { params }),

  create: (data: ApiEnvironmentForm) => request.post<ApiEnvironment>(`${BASE_URL}/environments/`, data),

  update: (id: number, data: Partial<ApiEnvironmentForm>) =>
    request.patch<ApiEnvironment>(`${BASE_URL}/environments/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/environments/${id}/`),
}

export const executionRecordApi = {
  list: (params?: { project?: number; request?: number }) =>
    request.get<ApiExecutionRecord[]>(`${BASE_URL}/execution-records/`, { params }),

  get: (id: number) => request.get<ApiExecutionRecord>(`${BASE_URL}/execution-records/${id}/`),

  delete: (id: number) => request.delete(`${BASE_URL}/execution-records/${id}/`),
}

export const testCaseApi = {
  list: (params?: { project?: number; request?: number; collection?: number }) =>
    request.get<ApiTestCase[]>(`${BASE_URL}/test-cases/`, { params }),

  get: (id: number) => request.get<ApiTestCase>(`${BASE_URL}/test-cases/${id}/`),

  execute: (id: number, environmentId?: number) =>
    request.post<ApiExecutionRecord>(`${BASE_URL}/test-cases/${id}/execute/`, {
      environment_id: environmentId,
    }),

  executeBatch: (data: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  }) => request.post<ApiExecutionBatchResult>(`${BASE_URL}/test-cases/execute-batch/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/test-cases/${id}/`),
}

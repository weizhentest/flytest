import request from '@/utils/request'
import type {
  DataFactoryCatalog,
  DataFactoryExecuteResult,
  DataFactoryPagination,
  DataFactoryRecord,
  DataFactoryReferencePayload,
  DataFactoryStatistics,
  DataFactoryTag,
} from '../types'

const BASE_URL = '/data-factory'

export const dataFactoryApi = {
  getCatalog: () => request.get<DataFactoryCatalog>(`${BASE_URL}/catalog/`),

  getScenarios: () => request.get(`${BASE_URL}/scenarios/`),

  execute: (data: {
    project: number
    tool_name: string
    input_data: Record<string, any>
    save_record?: boolean
    tag_names?: string[]
    tag_ids?: number[]
  }) => request.post<DataFactoryExecuteResult>(`${BASE_URL}/execute/`, data),

  getRecords: (params: {
    project: number
    page?: number
    page_size?: number
    search?: string
    tool_category?: string
    tool_scenario?: string
    tag_code?: string
    is_saved?: boolean
  }) => request.get<DataFactoryPagination<DataFactoryRecord>>(`${BASE_URL}/records/`, { params }),

  getRecord: (id: number) => request.get<DataFactoryRecord>(`${BASE_URL}/records/${id}/`),

  deleteRecord: (id: number) => request.delete(`${BASE_URL}/records/${id}/`),

  getTags: (params: { project: number; page?: number; page_size?: number; search?: string }) =>
    request.get<DataFactoryPagination<DataFactoryTag>>(`${BASE_URL}/tags/`, { params }),

  createTag: (data: { project: number; name: string; description?: string; color?: string }) =>
    request.post<DataFactoryTag>(`${BASE_URL}/tags/`, data),

  updateTag: (id: number, data: Partial<{ project: number; name: string; description: string; color: string }>) =>
    request.patch<DataFactoryTag>(`${BASE_URL}/tags/${id}/`, data),

  deleteTag: (id: number) => request.delete(`${BASE_URL}/tags/${id}/`),

  getStatistics: (project: number) =>
    request.get<DataFactoryStatistics>(`${BASE_URL}/statistics/`, { params: { project } }),

  getReferences: (params: { project: number; mode: 'api' | 'ui' }) =>
    request.get<DataFactoryReferencePayload>(`${BASE_URL}/references/`, { params }),
}

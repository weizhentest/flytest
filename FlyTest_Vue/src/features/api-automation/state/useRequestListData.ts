import { Message } from '@arco-design/web-vue'
import { ref, type Ref } from 'vue'

import { apiRequestApi, testCaseApi } from '../api'
import type { ApiRequest, ApiTestCase } from '../types'

const REQUEST_LIST_CACHE_TTL_MS = 30_000

type RequestPaginationState = {
  current: number
  pageSize: number
  total: number
  showTotal: boolean
  showPageSize: boolean
  pageSizeOptions: number[]
}

type UseRequestListDataOptions = {
  projectId: Ref<number | undefined>
  selectedCollectionId: Ref<number | undefined>
  searchKeyword: Ref<string>
  getErrorMessage: (error: unknown) => string
}

export function useRequestListData(options: UseRequestListDataOptions) {
  const loading = ref(false)
  const requests = ref<ApiRequest[]>([])
  const selectedRequestIds = ref<number[]>([])
  const expandedRequestKeys = ref<number[]>([])
  const requestTestCaseMap = ref<Record<number, ApiTestCase[]>>({})
  const requestTestCaseLoadingMap = ref<Record<number, boolean>>({})
  const requestDetailCache = ref<Record<number, ApiRequest>>({})
  const requestListCache = ref<Record<string, { items: ApiRequest[]; total: number; ts: number }>>({})
  const requestPagination = ref<RequestPaginationState>({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [20, 50, 100, 200],
  })

  const buildRequestListCacheKey = () =>
    JSON.stringify({
      project: options.projectId.value || null,
      collection: options.selectedCollectionId.value || null,
      search: options.searchKeyword.value.trim() || '',
      page: requestPagination.value.current,
      pageSize: requestPagination.value.pageSize,
    })

  const clearRequestListCache = () => {
    requestListCache.value = {}
  }

  const resetRequestState = () => {
    requests.value = []
    selectedRequestIds.value = []
    expandedRequestKeys.value = []
    requestTestCaseMap.value = {}
    requestDetailCache.value = {}
    requestPagination.value = {
      ...requestPagination.value,
      current: 1,
      total: 0,
    }
  }

  const loadRequests = async (force = false) => {
    if (!options.projectId.value || !options.selectedCollectionId.value) {
      requests.value = []
      selectedRequestIds.value = []
      expandedRequestKeys.value = []
      requestTestCaseMap.value = {}
      return
    }

    const cacheKey = buildRequestListCacheKey()
    const cached = requestListCache.value[cacheKey]
    if (!force && cached && Date.now() - cached.ts < REQUEST_LIST_CACHE_TTL_MS) {
      requests.value = cached.items.map(item => ({
        ...item,
        ...(requestDetailCache.value[item.id] || {}),
      }))
      requestPagination.value = {
        ...requestPagination.value,
        total: cached.total,
      }
      return
    }

    loading.value = true
    try {
      const res = await apiRequestApi.list({
        project: options.projectId.value,
        collection: options.selectedCollectionId.value,
        search: options.searchKeyword.value.trim() || undefined,
        page: requestPagination.value.current,
        page_size: requestPagination.value.pageSize,
      })
      const data = res.data?.data || []
      requests.value = (Array.isArray(data) ? data : []).map(item => ({
        ...item,
        ...(requestDetailCache.value[item.id] || {}),
      }))
      requestListCache.value = {
        ...requestListCache.value,
        [cacheKey]: {
          items: requests.value,
          total: Number(res.data?.total || 0),
          ts: Date.now(),
        },
      }
      requestPagination.value = {
        ...requestPagination.value,
        total: Number(res.data?.total || 0),
      }
      const availableIds = new Set(requests.value.map(item => item.id))
      selectedRequestIds.value = selectedRequestIds.value.filter(id => availableIds.has(id))
      expandedRequestKeys.value = expandedRequestKeys.value.filter(id => availableIds.has(id))
    } catch (error) {
      console.error('[RequestList] 获取接口失败:', error)
      Message.error(options.getErrorMessage(error))
      requests.value = []
      selectedRequestIds.value = []
      expandedRequestKeys.value = []
      requestTestCaseMap.value = {}
      requestPagination.value = {
        ...requestPagination.value,
        total: 0,
      }
    } finally {
      loading.value = false
    }
  }

  const handleSearch = async () => {
    requestPagination.value = {
      ...requestPagination.value,
      current: 1,
    }
    await loadRequests()
  }

  const handleSearchClear = async () => {
    options.searchKeyword.value = ''
    requestPagination.value = {
      ...requestPagination.value,
      current: 1,
    }
    await loadRequests()
  }

  const handlePageChange = async (page: number) => {
    requestPagination.value = {
      ...requestPagination.value,
      current: page,
    }
    await loadRequests()
  }

  const handlePageSizeChange = async (pageSize: number) => {
    requestPagination.value = {
      ...requestPagination.value,
      current: 1,
      pageSize,
    }
    await loadRequests()
  }

  const cacheRequestDetail = (detail: ApiRequest) => {
    requestDetailCache.value = {
      ...requestDetailCache.value,
      [detail.id]: detail,
    }
    requests.value = requests.value.map(item => (item.id === detail.id ? { ...item, ...detail } : item))
    return detail
  }

  const ensureRequestDetail = async (record: ApiRequest) => {
    const cached = requestDetailCache.value[record.id]
    if (cached?.request_spec) return cached
    if (record.request_spec) return cacheRequestDetail(record)
    const res = await apiRequestApi.get(record.id)
    const detail = res.data?.data
    if (!detail) {
      throw new Error('获取接口详情失败')
    }
    return cacheRequestDetail(detail)
  }

  const loadRequestTestCases = async (requestId: number, force = false) => {
    if (!options.projectId.value) return
    if (!force && requestTestCaseMap.value[requestId]) return

    requestTestCaseLoadingMap.value = {
      ...requestTestCaseLoadingMap.value,
      [requestId]: true,
    }
    try {
      const res = await testCaseApi.list({
        project: options.projectId.value,
        request: requestId,
      })
      const data = res.data?.data || []
      requestTestCaseMap.value = {
        ...requestTestCaseMap.value,
        [requestId]: Array.isArray(data) ? data : [],
      }
    } catch (error) {
      console.error('[RequestList] 获取接口下测试用例失败:', error)
      Message.error('获取接口下测试用例失败')
      requestTestCaseMap.value = {
        ...requestTestCaseMap.value,
        [requestId]: [],
      }
    } finally {
      requestTestCaseLoadingMap.value = {
        ...requestTestCaseLoadingMap.value,
        [requestId]: false,
      }
    }
  }

  const handleRequestExpand = async (rowKey: string | number) => {
    const requestId = Number(rowKey)
    if (!Number.isFinite(requestId)) return
    if (expandedRequestKeys.value.includes(requestId)) {
      await loadRequestTestCases(requestId)
    }
  }

  return {
    loading,
    requests,
    selectedRequestIds,
    expandedRequestKeys,
    requestTestCaseMap,
    requestTestCaseLoadingMap,
    requestPagination,
    clearRequestListCache,
    resetRequestState,
    loadRequests,
    handleSearch,
    handleSearchClear,
    handlePageChange,
    handlePageSizeChange,
    ensureRequestDetail,
    loadRequestTestCases,
    handleRequestExpand,
  }
}

import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import { useElementImageCategories } from '../../composables/useElementImageCategories'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppElement } from '../../types'
import {
  buildElementFormPatchFromRecord,
  buildElementPayloadFromForm,
  buildElementPayloadFromRecord,
  createDefaultElementFormModel,
  resolveElementImageCategory,
} from './elementFormUtils'
import type {
  ElementsEditorFormModel,
  ElementsPaginationState,
} from './elementViewModels'

export function useAppAutomationElements() {
  const projectStore = useProjectStore()
  const route = useRoute()

  const loading = ref(false)
  const visible = ref(false)
  const detailVisible = ref(false)
  const captureVisible = ref(false)
  const uploading = ref(false)
  const batchDeleting = ref(false)
  const search = ref('')
  const typeFilter = ref<string>()
  const elements = ref<AppElement[]>([])
  const localPreviewUrl = ref('')
  const detailRecord = ref<AppElement | null>(null)
  const selectedElementIds = ref<number[]>([])
  const previewUrlCache = reactive<Record<string, string>>({})
  const previewLoadState = reactive<Record<string, 'loading' | 'loaded' | 'failed'>>({})

  const pagination = reactive<ElementsPaginationState>({
    current: 1,
    pageSize: 10,
  })

  const typeLabelMap: Record<string, string> = {
    image: '图片',
    pos: '坐标',
    region: '区域',
  }

  const typeColorMap: Record<string, string> = {
    image: 'arcoblue',
    pos: 'green',
    region: 'orange',
  }

  const form = reactive<ElementsEditorFormModel>(createDefaultElementFormModel())
  const {
    imageCategories,
    newCategoryName,
    categorySaving,
    categoryDeleting,
    loadCategories,
    createCategory: createImageCategory,
    deleteCategory: deleteImageCategory,
  } = useElementImageCategories({
    getProjectId: () => projectStore.currentProjectId ?? null,
    getSelectedCategory: () => form.imageCategory,
    setSelectedCategory: value => {
      form.imageCategory = value
    },
  })

  const imagePreviewUrl = computed(() => {
    if (localPreviewUrl.value) {
      return localPreviewUrl.value
    }
    const imagePath = String(form.image_path || '').trim()
    if (imagePath) {
      return previewUrlCache[imagePath] || ''
    }
    return ''
  })

  const pagedElements = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return elements.value.slice(start, start + pagination.pageSize)
  })

  const formatDateTime = (value?: string) => {
    if (!value) {
      return '-'
    }
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN')
  }

  const formatConfig = (value: Record<string, unknown>) => JSON.stringify(value || {}, null, 2)

  const getTypeLabel = (value: string) => typeLabelMap[value] || value || '未知'

  const getTypeColor = (value: string) => typeColorMap[value] || 'gray'

  const updateLocalPreviewUrl = (value: string) => {
    if (localPreviewUrl.value && localPreviewUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(localPreviewUrl.value)
    }
    localPreviewUrl.value = value
  }

  const normalizePreviewPath = (imagePath?: string) => String(imagePath || '').trim()

  const revokePreviewUrl = (imagePath?: string) => {
    const key = normalizePreviewPath(imagePath)
    if (!key) {
      return
    }
    const currentUrl = previewUrlCache[key]
    if (currentUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(currentUrl)
    }
    delete previewUrlCache[key]
    delete previewLoadState[key]
  }

  const clearPreviewCache = () => {
    Object.keys(previewUrlCache).forEach(imagePath => {
      revokePreviewUrl(imagePath)
    })
    Object.keys(previewLoadState).forEach(imagePath => {
      delete previewLoadState[imagePath]
    })
  }

  const allowPreviewRetry = (imagePath?: string) => {
    const key = normalizePreviewPath(imagePath)
    if (!key || previewLoadState[key] !== 'failed') {
      return
    }
    delete previewLoadState[key]
  }

  const ensurePreviewUrl = async (imagePath?: string) => {
    const key = normalizePreviewPath(imagePath)
    if (!key) {
      return ''
    }
    if (previewUrlCache[key]) {
      return previewUrlCache[key]
    }
    if (previewLoadState[key] === 'loading' || previewLoadState[key] === 'failed') {
      return previewUrlCache[key] || ''
    }

    previewLoadState[key] = 'loading'
    try {
      const blobUrl = await AppAutomationService.fetchElementAssetBlobUrl(key)
      previewUrlCache[key] = blobUrl
      previewLoadState[key] = 'loaded'
      return blobUrl
    } catch {
      previewLoadState[key] = 'failed'
      return ''
    }
  }

  const getPreviewUrl = (imagePath?: string) => {
    const key = normalizePreviewPath(imagePath)
    if (!key) {
      return ''
    }
    if (!previewUrlCache[key] && previewLoadState[key] !== 'loading' && previewLoadState[key] !== 'failed') {
      void ensurePreviewUrl(key)
    }
    return previewUrlCache[key] || ''
  }

  const getImageCategory = (record: AppElement) => resolveElementImageCategory(record)

  const renderPos = (record: AppElement) => {
    const config = record.config as Record<string, unknown>
    return `X: ${config?.x ?? '-'} / Y: ${config?.y ?? '-'}`
  }

  const renderRegion = (record: AppElement) => {
    const config = record.config as Record<string, unknown>
    return `(${config?.x1 ?? '-'}, ${config?.y1 ?? '-'}) - (${config?.x2 ?? '-'}, ${config?.y2 ?? '-'})`
  }

  const resetForm = () => {
    Object.assign(form, createDefaultElementFormModel())
    newCategoryName.value = ''
    updateLocalPreviewUrl('')
  }

  const closeEditor = () => {
    visible.value = false
    resetForm()
  }

  const findAvailableName = (baseName: string) => {
    const existingNames = new Set(elements.value.map(item => item.name.toLowerCase()))
    const baseCandidate = `${baseName}_副本`
    if (!existingNames.has(baseCandidate.toLowerCase())) {
      return baseCandidate
    }

    let index = 2
    while (existingNames.has(`${baseName}_副本(${index})`.toLowerCase())) {
      index += 1
    }
    return `${baseName}_副本(${index})`
  }

  const loadElements = async () => {
    if (!projectStore.currentProjectId) {
      elements.value = []
      selectedElementIds.value = []
      clearPreviewCache()
      return
    }

    loading.value = true
    try {
      elements.value = await AppAutomationService.getElements(
        projectStore.currentProjectId,
        search.value,
        typeFilter.value,
      )
      selectedElementIds.value = selectedElementIds.value.filter(id =>
        elements.value.some(item => item.id === id),
      )
      if (detailRecord.value?.id) {
        const nextDetail = elements.value.find(item => item.id === detailRecord.value?.id) || null
        if (nextDetail) {
          detailRecord.value = nextDetail
        } else {
          detailVisible.value = false
          detailRecord.value = null
        }
      }
      const maxPage = Math.max(1, Math.ceil(elements.value.length / pagination.pageSize))
      if (pagination.current > maxPage) {
        pagination.current = maxPage
      }
    } catch (error: any) {
      Message.error(error.message || '加载元素失败')
    } finally {
      loading.value = false
    }
  }

  const handleSearch = async () => {
    pagination.current = 1
    await loadElements()
  }

  const handleTypeChange = async () => {
    pagination.current = 1
    await loadElements()
  }

  const openCreate = async () => {
    resetForm()
    await loadCategories()
    visible.value = true
  }

  const openEdit = async (record: AppElement) => {
    resetForm()
    await loadCategories()
    Object.assign(form, buildElementFormPatchFromRecord(record))
    allowPreviewRetry(form.image_path)
    void ensurePreviewUrl(form.image_path)
    visible.value = true
  }

  const openDetail = (record: AppElement) => {
    detailRecord.value = record
    allowPreviewRetry(record.image_path)
    void ensurePreviewUrl(record.image_path)
    detailVisible.value = true
  }

  const handleFileChange = async (file: File | null) => {
    if (!file || !projectStore.currentProjectId) {
      return
    }

    updateLocalPreviewUrl(URL.createObjectURL(file))
    uploading.value = true
    try {
      const result = await AppAutomationService.uploadElementAsset(
        file,
        projectStore.currentProjectId,
        form.imageCategory || 'common',
        form.id || undefined,
      )
      form.image_path = result.image_path
      form.imageCategory = result.image_category || form.imageCategory
      form.fileHash = result.file_hash
      if (!form.selector_value.trim()) {
        form.selector_type = 'image'
      }
      Message.success(result.duplicate ? '检测到重复图片，已复用现有资源' : '图片已上传')
      await loadCategories()
    } catch (error: any) {
      Message.error(error.message || '上传图片失败')
    } finally {
      uploading.value = false
    }
  }

  const createCategory = async () => {
    await createImageCategory()
  }

  const deleteCurrentCategory = () => {
    if (!form.imageCategory || form.imageCategory === 'common') {
      Message.warning('默认分类不可删除')
      return
    }

    Modal.confirm({
      title: '删除图片分类',
      content: `确认删除分类 “${form.imageCategory}” 吗？分类必须为空才能删除。`,
      onOk: async () => {
        await deleteImageCategory(form.imageCategory)
      },
    })
  }

  const duplicateElement = async (record: AppElement) => {
    try {
      const nextName = findAvailableName(record.name)
      await AppAutomationService.createElement(buildElementPayloadFromRecord(record, { name: nextName }))
      Message.success(`元素已复制为 ${nextName}`)
      await loadElements()
    } catch (error: any) {
      Message.error(error.message || '复制元素失败')
    }
  }

  const toggleActive = async (record: AppElement, nextValue: boolean) => {
    const previousValue = record.is_active
    record.is_active = nextValue
    try {
      const updated = await AppAutomationService.updateElement(
        record.id,
        buildElementPayloadFromRecord(record, { is_active: nextValue }),
      )
      if (detailRecord.value?.id === record.id) {
        detailRecord.value = updated
      }
      Message.success(nextValue ? '元素已启用' : '元素已停用')
    } catch (error: any) {
      record.is_active = previousValue
      Message.error(error.message || '更新元素状态失败')
    }
  }

  const submit = async () => {
    if (!projectStore.currentProjectId) {
      return
    }

    try {
      const payload = buildElementPayloadFromForm(form, projectStore.currentProjectId as number)
      if (!payload.name) {
        Message.warning('请输入元素名称')
        return
      }
      if (payload.element_type === 'image' && !payload.image_path) {
        Message.warning('请先上传图片资源')
        return
      }

      if (form.id) {
        await AppAutomationService.updateElement(form.id, payload)
        Message.success('元素已更新')
      } else {
        await AppAutomationService.createElement(payload)
        Message.success('元素已创建')
      }

      closeEditor()
      await Promise.all([loadElements(), loadCategories()])
    } catch (error: any) {
      Message.error(error.message || '保存元素失败，请检查扩展配置 JSON')
    }
  }

  const remove = (id: number) => {
    Modal.confirm({
      title: '删除元素',
      content: '确认删除这个元素吗？',
      onOk: async () => {
        await AppAutomationService.deleteElement(id)
        if (detailRecord.value?.id === id) {
          detailVisible.value = false
          detailRecord.value = null
        }
        if (form.id === id) {
          closeEditor()
        }
        Message.success('元素已删除')
        await loadElements()
      },
    })
  }

  const clearSelection = () => {
    selectedElementIds.value = []
  }

  const removeSelected = () => {
    if (!selectedElementIds.value.length) {
      Message.warning('请先选择要删除的元素')
      return
    }

    const ids = [...selectedElementIds.value]
    Modal.confirm({
      title: '批量删除元素',
      content: `确认删除已选择的 ${ids.length} 个元素吗？此操作不可恢复。`,
      onOk: async () => {
        batchDeleting.value = true
        try {
          const results = await Promise.allSettled(ids.map(id => AppAutomationService.deleteElement(id)))
          const successCount = results.filter(result => result.status === 'fulfilled').length
          const failedCount = ids.length - successCount

          if (!successCount) {
            Message.error('批量删除失败')
            return
          }

          if (detailRecord.value?.id && ids.includes(detailRecord.value.id)) {
            detailVisible.value = false
            detailRecord.value = null
          }
          if (form.id && ids.includes(form.id)) {
            closeEditor()
          }
          selectedElementIds.value = []
          if (failedCount) {
            Message.warning(`已删除 ${successCount} 个元素，${failedCount} 个删除失败`)
          } else {
            Message.success(`已删除 ${successCount} 个元素`)
          }
          await loadElements()
        } finally {
          batchDeleting.value = false
        }
      },
    })
  }

  const handleCaptureSuccess = async () => {
    await Promise.all([loadElements(), loadCategories()])
  }

  watch(
    () => route.query.tab,
    tab => {
      if (tab === 'elements') {
        return
      }
      closeEditor()
      detailVisible.value = false
      captureVisible.value = false
    },
  )

  watch(
    () => detailVisible.value,
    value => {
      if (!value) {
        detailRecord.value = null
      }
    },
  )

  watch(
    () => captureVisible.value,
    value => {
      if (!value) {
        updateLocalPreviewUrl('')
      }
    },
  )

  watch(
    () => visible.value,
    value => {
      if (!value) {
        resetForm()
      }
    },
  )

  watch(
    () => form.element_type,
    value => {
      if (value === 'image' && !form.selector_type.trim()) {
        form.selector_type = 'image'
      }
      if (value === 'pos' && !form.selector_type.trim()) {
        form.selector_type = 'pos'
      }
      if (value === 'region' && !form.selector_type.trim()) {
        form.selector_type = 'region'
      }
    },
  )

  watch(
    () => form.image_path,
    imagePath => {
      if (localPreviewUrl.value) {
        return
      }
      allowPreviewRetry(imagePath)
      void ensurePreviewUrl(imagePath)
    },
  )

  watch(
    () => projectStore.currentProjectId,
    () => {
      clearPreviewCache()
      captureVisible.value = false
      detailVisible.value = false
      detailRecord.value = null
      closeEditor()
      void Promise.all([loadElements(), loadCategories()])
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    updateLocalPreviewUrl('')
    clearPreviewCache()
  })

  return {
    projectStore,
    loading,
    visible,
    detailVisible,
    captureVisible,
    uploading,
    batchDeleting,
    categorySaving,
    categoryDeleting,
    search,
    typeFilter,
    elements,
    imageCategories,
    newCategoryName,
    detailRecord,
    selectedElementIds,
    pagination,
    form,
    imagePreviewUrl,
    pagedElements,
    formatDateTime,
    formatConfig,
    getTypeLabel,
    getTypeColor,
    getPreviewUrl,
    getImageCategory,
    renderPos,
    renderRegion,
    loadElements,
    handleSearch,
    handleTypeChange,
    openCreate,
    openEdit,
    openDetail,
    handleFileChange,
    createCategory,
    deleteCurrentCategory,
    submit,
    closeEditor,
    duplicateElement,
    toggleActive,
    remove,
    clearSelection,
    removeSelected,
    handleCaptureSuccess,
  }
}

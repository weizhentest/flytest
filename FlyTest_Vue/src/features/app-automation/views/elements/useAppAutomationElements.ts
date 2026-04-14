import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppElement, AppImageCategory } from '../../types'
import type {
  ElementsEditorFormModel,
  ElementsPaginationState,
} from './elementViewModels'

export function useAppAutomationElements() {
  const projectStore = useProjectStore()

  const loading = ref(false)
  const visible = ref(false)
  const detailVisible = ref(false)
  const captureVisible = ref(false)
  const uploading = ref(false)
  const batchDeleting = ref(false)
  const categorySaving = ref(false)
  const categoryDeleting = ref(false)
  const search = ref('')
  const typeFilter = ref<string>()
  const elements = ref<AppElement[]>([])
  const imageCategories = ref<AppImageCategory[]>([])
  const newCategoryName = ref('')
  const localPreviewUrl = ref('')
  const detailRecord = ref<AppElement | null>(null)
  const selectedElementIds = ref<number[]>([])

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

  const form = reactive<ElementsEditorFormModel>({
    id: 0,
    name: '',
    element_type: 'image',
    selector_type: 'image',
    selector_value: '',
    description: '',
    tagsText: '',
    configText: '{\n  "threshold": 0.7\n}',
    image_path: '',
    imageCategory: 'common',
    fileHash: '',
    is_active: true,
    threshold: 0.7,
    rgb: false,
    posX: 0,
    posY: 0,
    regionX1: 0,
    regionY1: 0,
    regionX2: 0,
    regionY2: 0,
  })

  const imagePreviewUrl = computed(() => {
    if (localPreviewUrl.value) {
      return localPreviewUrl.value
    }
    if (form.image_path) {
      return AppAutomationService.getElementAssetUrl(form.image_path)
    }
    return ''
  })

  const pagedElements = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return elements.value.slice(start, start + pagination.pageSize)
  })

  const cloneValue = <T>(value: T): T => JSON.parse(JSON.stringify(value))

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

  const parseObjectText = (text: string) => {
    const raw = String(text || '').trim()
    if (!raw) {
      return {}
    }
    const parsed = JSON.parse(raw)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('扩展配置 JSON 必须是对象')
    }
    return parsed as Record<string, unknown>
  }

  const getPreviewUrl = (imagePath?: string) =>
    imagePath ? AppAutomationService.getElementAssetUrl(imagePath) : ''

  const getImageCategory = (record: AppElement) => {
    const config = record.config as Record<string, unknown>
    if (config?.image_category) return String(config.image_category)
    if (record.image_path?.includes('/')) return record.image_path.split('/')[0]
    return ''
  }

  const renderPos = (record: AppElement) => {
    const config = record.config as Record<string, unknown>
    return `X: ${config?.x ?? '-'} / Y: ${config?.y ?? '-'}`
  }

  const renderRegion = (record: AppElement) => {
    const config = record.config as Record<string, unknown>
    return `(${config?.x1 ?? '-'}, ${config?.y1 ?? '-'}) - (${config?.x2 ?? '-'}, ${config?.y2 ?? '-'})`
  }

  const parseConfig = (record: AppElement) => {
    const config = cloneValue(record.config || {})
    const imageCategory =
      String((config as Record<string, unknown>).image_category || '') ||
      (record.image_path?.includes('/') ? record.image_path.split('/')[0] : '') ||
      'common'
    return {
      config,
      imageCategory,
      fileHash: String((config as Record<string, unknown>).file_hash || ''),
      threshold: Number((config as Record<string, unknown>).threshold ?? 0.7) || 0.7,
      rgb: Boolean((config as Record<string, unknown>).rgb),
      posX: Number((config as Record<string, unknown>).x ?? 0) || 0,
      posY: Number((config as Record<string, unknown>).y ?? 0) || 0,
      regionX1: Number((config as Record<string, unknown>).x1 ?? 0) || 0,
      regionY1: Number((config as Record<string, unknown>).y1 ?? 0) || 0,
      regionX2: Number((config as Record<string, unknown>).x2 ?? 0) || 0,
      regionY2: Number((config as Record<string, unknown>).y2 ?? 0) || 0,
    }
  }

  const resetForm = () => {
    form.id = 0
    form.name = ''
    form.element_type = 'image'
    form.selector_type = 'image'
    form.selector_value = ''
    form.description = ''
    form.tagsText = ''
    form.configText = '{\n  "threshold": 0.7\n}'
    form.image_path = ''
    form.imageCategory = 'common'
    form.fileHash = ''
    form.is_active = true
    form.threshold = 0.7
    form.rgb = false
    form.posX = 0
    form.posY = 0
    form.regionX1 = 0
    form.regionY1 = 0
    form.regionX2 = 0
    form.regionY2 = 0
    newCategoryName.value = ''
    updateLocalPreviewUrl('')
  }

  const closeEditor = () => {
    visible.value = false
    resetForm()
  }

  const buildSelectorValue = () => {
    if (form.selector_value.trim()) {
      return form.selector_value.trim()
    }
    if (form.element_type === 'image') {
      return form.image_path.trim()
    }
    if (form.element_type === 'pos') {
      return `${form.posX},${form.posY}`
    }
    return `${form.regionX1},${form.regionY1},${form.regionX2},${form.regionY2}`
  }

  const buildSelectorType = () => {
    if (form.selector_type.trim()) {
      return form.selector_type.trim()
    }
    return form.element_type === 'image' ? 'image' : form.element_type
  }

  const buildConfigPayload = () => {
    const parsedConfig = parseObjectText(form.configText)
    if (form.element_type === 'image') {
      parsedConfig.image_category = form.imageCategory || 'common'
      parsedConfig.image_path = form.image_path
      parsedConfig.threshold = form.threshold
      parsedConfig.rgb = form.rgb
      if (form.fileHash) {
        parsedConfig.file_hash = form.fileHash
      } else {
        delete parsedConfig.file_hash
      }
      return parsedConfig
    }

    if (form.element_type === 'pos') {
      parsedConfig.x = form.posX
      parsedConfig.y = form.posY
      return parsedConfig
    }

    parsedConfig.x1 = form.regionX1
    parsedConfig.y1 = form.regionY1
    parsedConfig.x2 = form.regionX2
    parsedConfig.y2 = form.regionY2
    parsedConfig.width = Math.max(form.regionX2 - form.regionX1, 0)
    parsedConfig.height = Math.max(form.regionY2 - form.regionY1, 0)
    return parsedConfig
  }

  const buildPayloadFromForm = () => ({
    project_id: projectStore.currentProjectId as number,
    name: form.name.trim(),
    element_type: form.element_type,
    selector_type: buildSelectorType(),
    selector_value: buildSelectorValue(),
    description: form.description.trim(),
    tags: form.tagsText
      .split(',')
      .map(item => item.trim())
      .filter(Boolean),
    config: buildConfigPayload(),
    image_path: form.image_path,
    is_active: form.is_active,
  })

  const buildPayloadFromRecord = (
    record: AppElement,
    overrides?: Partial<AppElement> & { name?: string; is_active?: boolean },
  ) => ({
    project_id: record.project_id,
    name: String(overrides?.name ?? record.name).trim(),
    element_type: String(overrides?.element_type ?? record.element_type),
    selector_type: String(overrides?.selector_type ?? record.selector_type),
    selector_value: String(overrides?.selector_value ?? record.selector_value),
    description: String(overrides?.description ?? record.description),
    tags: [...record.tags],
    config: cloneValue(record.config || {}),
    image_path: String(overrides?.image_path ?? record.image_path),
    is_active: typeof overrides?.is_active === 'boolean' ? overrides.is_active : record.is_active,
  })

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

  const loadCategories = async () => {
    try {
      imageCategories.value = await AppAutomationService.getElementImageCategories()
      if (!imageCategories.value.some(item => item.name === form.imageCategory)) {
        form.imageCategory = imageCategories.value[0]?.name || 'common'
      }
    } catch (error: any) {
      Message.error(error.message || '加载图片分类失败')
    }
  }

  const loadElements = async () => {
    if (!projectStore.currentProjectId) {
      elements.value = []
      selectedElementIds.value = []
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
    form.id = record.id
    form.name = record.name
    form.element_type = record.element_type
    form.selector_type = record.selector_type
    form.selector_value = record.selector_value
    form.description = record.description
    form.tagsText = record.tags.join(', ')
    form.image_path = record.image_path
    form.is_active = record.is_active

    const parsed = parseConfig(record)
    form.imageCategory = parsed.imageCategory
    form.fileHash = parsed.fileHash
    form.threshold = parsed.threshold
    form.rgb = parsed.rgb
    form.posX = parsed.posX
    form.posY = parsed.posY
    form.regionX1 = parsed.regionX1
    form.regionY1 = parsed.regionY1
    form.regionX2 = parsed.regionX2
    form.regionY2 = parsed.regionY2
    form.configText = JSON.stringify(parsed.config, null, 2)
    visible.value = true
  }

  const openDetail = (record: AppElement) => {
    detailRecord.value = record
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
    const name = newCategoryName.value.trim()
    if (!name) {
      Message.warning('请输入分类名称')
      return
    }
    categorySaving.value = true
    try {
      const created = await AppAutomationService.createElementImageCategory(name)
      form.imageCategory = created.name
      newCategoryName.value = ''
      Message.success('图片分类已创建')
      await loadCategories()
    } catch (error: any) {
      Message.error(error.message || '创建图片分类失败')
    } finally {
      categorySaving.value = false
    }
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
        categoryDeleting.value = true
        try {
          await AppAutomationService.deleteElementImageCategory(form.imageCategory)
          form.imageCategory = 'common'
          Message.success('图片分类已删除')
          await loadCategories()
        } finally {
          categoryDeleting.value = false
        }
      },
    })
  }

  const duplicateElement = async (record: AppElement) => {
    try {
      const nextName = findAvailableName(record.name)
      await AppAutomationService.createElement(buildPayloadFromRecord(record, { name: nextName }))
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
      await AppAutomationService.updateElement(
        record.id,
        buildPayloadFromRecord(record, { is_active: nextValue }),
      )
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
      const payload = buildPayloadFromForm()
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
    () => projectStore.currentProjectId,
    () => {
      detailVisible.value = false
      detailRecord.value = null
      closeEditor()
      void Promise.all([loadElements(), loadCategories()])
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    updateLocalPreviewUrl('')
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

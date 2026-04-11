import { computed, ref } from 'vue'

type ImportProgressStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error'

export function useRequestImportState() {
  const documentFile = ref<File | null>(null)
  const documentInputRef = ref<HTMLInputElement | null>(null)
  const documentDragging = ref(false)
  const documentImportMode = ref<'file' | 'text'>('file')
  const documentText = ref('')
  const documentSourceName = ref('')
  const createMode = ref<'manual' | 'document'>('manual')
  const generateTestCases = ref(true)
  const enableAiParse = ref(true)
  const selectedRequestDraftIndex = ref(0)

  const importProgressActive = ref(false)
  const importProgressPercent = ref(0)
  const importProgressStage = ref(0)
  const importProgressStatus = ref<ImportProgressStatus>('idle')
  const importProgressMessage = ref('')
  const importProgressError = ref('')
  const importProgressFileName = ref('')

  const importProgressSteps = [
    { title: '上传接口文档', description: '将 Word、PDF、Swagger 等接口文档上传到 FlyTest。' },
    { title: '提取文档正文', description: '转换文档内容并抽取接口结构线索。' },
    { title: '识别接口定义', description: '结合规则与 AI 解析请求方式、路径、参数和断言。' },
    { title: '生成脚本与用例', description: '为识别出的接口批量生成可执行脚本和测试用例。' },
    { title: '写入 FlyTest', description: '把接口、脚本和测试用例保存到当前集合。' },
  ]

  const documentFileSummary = computed(() => {
    if (!documentFile.value) return ''
    const size = documentFile.value.size
    if (size < 1024) return `${size} B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    return `${(size / 1024 / 1024).toFixed(2)} MB`
  })

  const documentTextSummary = computed(() => {
    const text = documentText.value.trim()
    if (!text) return '未输入接口文档内容'
    return `已输入 ${text.length} 个字符，将按正文切片后交给 AI 解析`
  })

  const importProgressRatio = computed(() => {
    const clamped = Math.max(0, Math.min(importProgressPercent.value, 100))
    return clamped / 100
  })

  let importProgressTimer: ReturnType<typeof window.setInterval> | null = null

  const clearImportProgressTimer = () => {
    if (importProgressTimer) {
      window.clearInterval(importProgressTimer)
      importProgressTimer = null
    }
  }

  const resetImportProgress = () => {
    clearImportProgressTimer()
    importProgressActive.value = false
    importProgressPercent.value = 0
    importProgressStage.value = 0
    importProgressStatus.value = 'idle'
    importProgressMessage.value = ''
    importProgressError.value = ''
    importProgressFileName.value = ''
  }

  const syncProcessingStage = () => {
    const milestones = [28, 50, 74, 90, 97]

    if (importProgressPercent.value < milestones[1]) {
      importProgressStage.value = 1
      importProgressMessage.value = '文档上传完成，正在抽取正文与接口结构。'
      return
    }
    if (importProgressPercent.value < milestones[2]) {
      importProgressStage.value = 2
      importProgressMessage.value = '正在识别接口名称、请求方式、路径、参数与断言。'
      return
    }
    if (importProgressPercent.value < milestones[3]) {
      importProgressStage.value = 3
      importProgressMessage.value = '正在生成可执行接口脚本和测试用例。'
      return
    }

    importProgressStage.value = 4
    importProgressMessage.value = '正在把解析结果写入当前接口集合。'
  }

  const startImportProgress = (fileName: string) => {
    resetImportProgress()
    importProgressActive.value = true
    importProgressFileName.value = fileName
    importProgressStatus.value = 'uploading'
    importProgressStage.value = 0
    importProgressPercent.value = 6
    importProgressMessage.value = `正在上传 ${fileName}，并校验文档格式。`

    clearImportProgressTimer()
    importProgressTimer = window.setInterval(() => {
      if (importProgressStatus.value === 'uploading') {
        importProgressPercent.value = Math.min(importProgressPercent.value + 3, 24)
        return
      }
      if (importProgressStatus.value !== 'processing') return

      importProgressPercent.value = Math.min(importProgressPercent.value + 4, 97)
      syncProcessingStage()
    }, 700)
  }

  const handleImportUploadProgress = (event: { loaded?: number; total?: number }) => {
    if (!importProgressActive.value) return

    const total = event.total || 0
    if (total > 0) {
      const percent = Math.max(6, Math.min(28, Math.round((((event.loaded || 0) / total) * 28))))
      importProgressPercent.value = Math.max(importProgressPercent.value, percent)
    }

    if (total > 0 && (event.loaded || 0) >= total) {
      importProgressStatus.value = 'processing'
      importProgressPercent.value = Math.max(importProgressPercent.value, 34)
      syncProcessingStage()
    }
  }

  const completeImportProgress = async (createdCount: number, testcaseCount: number) => {
    clearImportProgressTimer()
    importProgressActive.value = true
    importProgressStatus.value = 'success'
    importProgressStage.value = importProgressSteps.length - 1
    importProgressPercent.value = 100
    importProgressMessage.value = `解析完成，已生成 ${createdCount} 个接口和 ${testcaseCount} 个测试用例。`
    await new Promise(resolve => window.setTimeout(resolve, 360))
  }

  const failImportProgress = (message: string) => {
    clearImportProgressTimer()
    importProgressActive.value = true
    importProgressStatus.value = 'error'
    importProgressError.value = message
    importProgressPercent.value = Math.max(importProgressPercent.value, 20)
    syncProcessingStage()
  }

  const getImportStepClass = (index: number) => {
    if (importProgressStatus.value === 'error') {
      if (index < importProgressStage.value) return 'is-finished'
      if (index === importProgressStage.value) return 'is-error'
      return 'is-pending'
    }
    if (importProgressStatus.value === 'success') {
      return 'is-finished'
    }
    if (index < importProgressStage.value) return 'is-finished'
    if (index === importProgressStage.value) return 'is-active'
    return 'is-pending'
  }

  const triggerDocumentSelect = () => {
    documentInputRef.value?.click()
  }

  const clearDocumentFile = () => {
    documentFile.value = null
    documentDragging.value = false
    if (documentInputRef.value) {
      documentInputRef.value.value = ''
    }
  }

  const handleDocumentImportModeChange = (value?: string | number | boolean) => {
    const nextMode = value === 'text' ? 'text' : 'file'
    documentImportMode.value = nextMode
    documentDragging.value = false

    if (nextMode === 'text') {
      clearDocumentFile()
      enableAiParse.value = true
      return
    }

    documentText.value = ''
    documentSourceName.value = ''
  }

  const handleDocumentChange = (event: Event) => {
    const input = event.target as HTMLInputElement
    documentFile.value = input.files?.[0] || null
    documentDragging.value = false
  }

  const buildInlineDocumentSourceName = () => {
    const raw = documentSourceName.value.trim()
    if (!raw) return 'inline-api-document.md'
    return raw
  }

  const handleDocumentDrop = (event: DragEvent) => {
    event.preventDefault()
    documentDragging.value = false
    const file = event.dataTransfer?.files?.[0] || null
    if (file) {
      documentFile.value = file
      if (documentInputRef.value) {
        documentInputRef.value.value = ''
      }
    }
  }

  const resetImportDraft = () => {
    documentFile.value = null
    documentDragging.value = false
    documentImportMode.value = 'file'
    documentText.value = ''
    documentSourceName.value = ''
    createMode.value = 'manual'
    generateTestCases.value = true
    enableAiParse.value = true
    selectedRequestDraftIndex.value = 0

    if (documentInputRef.value) {
      documentInputRef.value.value = ''
    }
  }

  return {
    documentFile,
    documentInputRef,
    documentDragging,
    documentImportMode,
    documentText,
    documentSourceName,
    createMode,
    generateTestCases,
    enableAiParse,
    selectedRequestDraftIndex,
    importProgressActive,
    importProgressPercent,
    importProgressStage,
    importProgressStatus,
    importProgressMessage,
    importProgressError,
    importProgressFileName,
    importProgressSteps,
    documentFileSummary,
    documentTextSummary,
    importProgressRatio,
    clearImportProgressTimer,
    resetImportProgress,
    startImportProgress,
    handleImportUploadProgress,
    completeImportProgress,
    failImportProgress,
    getImportStepClass,
    triggerDocumentSelect,
    handleDocumentImportModeChange,
    handleDocumentChange,
    clearDocumentFile,
    buildInlineDocumentSourceName,
    handleDocumentDrop,
    resetImportDraft,
  }
}

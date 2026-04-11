import { Message } from '@arco-design/web-vue'
import { ref, type Ref } from 'vue'

import { apiRequestApi } from '../api'
import {
  bodyModeToLegacyBodyType,
  createEmptyHttpEditorModel,
  httpEditorModelToAssertionSpecs,
  httpEditorModelToExtractorSpecs,
  httpEditorModelToRequestSpec,
  requestFormToHttpEditorModel,
  requestSpecToLegacyBody,
  requestSpecToLegacyHeaders,
  requestSpecToLegacyParams,
  requestToHttpEditorModel,
} from './httpEditor'
import type { ApiHttpEditorModel, ApiRequest, ApiRequestForm } from '../types'

export interface RequestEditorForm {
  name: string
  description: string
  editor: ApiHttpEditorModel
}

type RequestDraft = {
  form: ApiRequestForm
}

type UseRequestEditorOptions = {
  selectedCollectionId: Ref<number | undefined>
  ensureRequestDetail: (record: ApiRequest) => Promise<ApiRequest>
  getRequestDraft: (draftIndex?: number) => RequestDraft | undefined
  hasRequestDrafts: Ref<boolean>
  resetImportDraft: () => void
  resetImportProgress: () => void
  clearDrafts: () => void
  getErrorMessage: (error: unknown) => string
  setLoading: (value: boolean) => void
}

const createInitialFormState = (): RequestEditorForm => ({
  name: '',
  description: '',
  editor: createEmptyHttpEditorModel(),
})

export function useRequestEditor(options: UseRequestEditorOptions) {
  const editorVisible = ref(false)
  const submitLoading = ref(false)
  const editingRequest = ref<ApiRequest | null>(null)
  const formState = ref<RequestEditorForm>(createInitialFormState())

  const resetEditor = () => {
    editingRequest.value = null
    options.resetImportDraft()
    options.resetImportProgress()
    formState.value = createInitialFormState()
  }

  const fillFormFromRequestDraft = (draftIndex = 0) => {
    const draft = options.getRequestDraft(draftIndex)
    if (!draft) return

    formState.value = {
      name: draft.form.name,
      description: draft.form.description || '',
      editor: requestFormToHttpEditorModel(draft.form),
    }
  }

  const openCreateModal = () => {
    resetEditor()
    if (options.hasRequestDrafts.value) {
      fillFormFromRequestDraft(0)
    }
    editorVisible.value = true
  }

  const openEditModal = async (record: ApiRequest, setCreateMode: (mode: 'manual' | 'document') => void) => {
    try {
      options.setLoading(true)
      const detail = await options.ensureRequestDetail(record)
      editingRequest.value = detail
      setCreateMode('manual')
      formState.value = {
        name: detail.name,
        description: detail.description || '',
        editor: requestToHttpEditorModel(detail),
      }
      editorVisible.value = true
    } catch (error) {
      console.error('[RequestList] 获取接口详情失败:', error)
      Message.error(options.getErrorMessage(error))
    } finally {
      options.setLoading(false)
    }
  }

  const applySelectedRequestDraft = (draftIndex: number) => {
    fillFormFromRequestDraft(draftIndex)
  }

  const clearDraftsAndReset = () => {
    options.clearDrafts()
    resetEditor()
  }

  const submitManualRequest = async () => {
    if (!options.selectedCollectionId.value) {
      throw new Error('请先选择接口集合')
    }

    const requestSpec = httpEditorModelToRequestSpec(formState.value.editor)
    const payload: ApiRequestForm = {
      collection: options.selectedCollectionId.value,
      name: formState.value.name.trim(),
      description: formState.value.description.trim(),
      method: requestSpec.method,
      url: requestSpec.url.trim(),
      headers: requestSpecToLegacyHeaders(requestSpec),
      params: requestSpecToLegacyParams(requestSpec),
      body_type: bodyModeToLegacyBodyType(requestSpec.body_mode),
      body: requestSpecToLegacyBody(requestSpec),
      assertions: [],
      request_spec: requestSpec,
      assertion_specs: httpEditorModelToAssertionSpecs(formState.value.editor),
      extractor_specs: httpEditorModelToExtractorSpecs(formState.value.editor),
      timeout_ms: requestSpec.timeout_ms,
    }

    if (editingRequest.value) {
      await apiRequestApi.update(editingRequest.value.id, payload)
      Message.success('接口更新成功')
      return
    }

    await apiRequestApi.create(payload)
    Message.success('接口创建成功')
  }

  return {
    editorVisible,
    submitLoading,
    editingRequest,
    formState,
    resetEditor,
    fillFormFromRequestDraft,
    openCreateModal,
    openEditModal,
    applySelectedRequestDraft,
    clearDraftsAndReset,
    submitManualRequest,
  }
}

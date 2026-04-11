<template>
  <div class="request-list">
    <div class="page-header api-page-header">
      <div class="page-summary">
        <div class="page-summary__eyebrow">项目 / 接口 / 用例</div>
        <div class="page-summary__title">接口管理</div>
        <div class="page-summary__meta">
          <span>{{ projectName }}</span>
          <span>{{ selectedCollectionName || '未选择接口集合' }}</span>
          <span>共 {{ requests.length }} 个接口</span>
          <span>共 {{ requestCaseTotal }} 条测试用例</span>
        </div>
      </div>
      <div class="page-toolbar">
        <a-input-search
          v-model="searchKeyword"
          class="toolbar-search"
          placeholder="搜索接口名称或 URL"
          allow-clear
          @search="handleSearch"
          @clear="handleSearchClear"
        />
        <div class="toolbar-group toolbar-group--filter">
          <a-select
            v-model="selectedEnvironmentId"
            class="toolbar-select"
            :loading="environmentLoading"
            allow-clear
            placeholder="执行环境"
          >
            <a-option v-for="item in environments" :key="item.id" :value="item.id" :label="item.name" />
          </a-select>
        </div>
        <div class="toolbar-group toolbar-group--actions">
          <a-button :disabled="!selectedRequestIds.length" @click="executeSelectedRequests">
            执行选中
          </a-button>
          <a-button :disabled="!selectedCollectionId" @click="executeCollectionRequests">
            执行当前集合
          </a-button>
          <a-button :disabled="!projectId" @click="executeProjectRequests">
            执行当前项目
          </a-button>
          <a-dropdown trigger="click" @select="handleSelectedCaseGenerationAction">
            <a-button :disabled="!selectedRequestIds.length">
              AI生成用例
            </a-button>
            <template #content>
              <a-doption value="generate" :disabled="!selectedRequestIds.length">批量生成</a-doption>
              <a-doption value="regenerate" :disabled="!selectedRequestIds.length">重新生成</a-doption>
              <a-doption value="append" :disabled="!selectedRequestIds.length">追加生成</a-doption>
            </template>
          </a-dropdown>
          <a-button type="primary" :disabled="!selectedCollectionId" @click="openCreateModal">
            新增接口
          </a-button>
        </div>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="empty-tip-card">
      <a-empty description="请先在左侧选择一个接口集合" />
    </div>

    <div v-else class="content-section">
      <a-table
        v-model:selectedKeys="selectedRequestIds"
        v-model:expanded-keys="expandedRequestKeys"
        :data="filteredRequests"
        :loading="loading"
        :pagination="requestPagination"
        row-key="id"
        size="large"
        :scroll="{ x: 1240 }"
        :row-selection="requestRowSelection"
        :expandable="{ width: 48 }"
        @expand="handleRequestExpand"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #columns>
          <a-table-column title="方法" :width="90">
            <template #cell="{ record }">
              <a-tag :color="methodColorMap[record.method] || 'arcoblue'">{{ record.method }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="接口名称" data-index="name" :width="220" ellipsis tooltip />
          <a-table-column title="请求地址" data-index="url" ellipsis tooltip />
          <a-table-column title="断言" :width="90" align="center">
            <template #cell="{ record }">
              <a-tag color="cyan">{{ record.assertion_count ?? (record.assertions?.length || 0) }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="测试用例" :width="110" align="center">
            <template #cell="{ record }">
              <a-tag color="purple">{{ record.test_case_count || 0 }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="更新时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="330" align="center" fixed="right">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="executeRequest(record)">执行</a-button>
                <a-dropdown trigger="click" @select="value => handleSingleCaseGenerationAction(record, value)">
                  <a-button type="text" size="small">AI用例</a-button>
                  <template #content>
                    <a-doption value="generate">生成</a-doption>
                    <a-doption value="regenerate">重新生成</a-doption>
                    <a-doption value="append">追加生成</a-doption>
                  </template>
                </a-dropdown>
                <a-button type="text" size="small" @click="void openEditModal(record)">编辑</a-button>
                <a-button type="text" size="small" @click="void viewRequest(record)">详情</a-button>
                <a-popconfirm content="确认删除该接口吗？" @ok="deleteRequest(record.id)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>

        <template #expand-row="{ record }">
          <div class="request-case-panel">
            <div class="request-case-panel__header">
              <div>
                <div class="request-case-panel__title">接口测试用例</div>
                <div class="request-case-panel__subtitle">
                  当前接口下的测试用例会直接绑定到该接口，可在这里查看和继续生成。
                </div>
              </div>
              <div class="request-case-panel__actions">
                <a-button size="small" @click="generateCasesForRequest(record, 'generate')">AI生成</a-button>
                <a-button size="small" @click="generateCasesForRequest(record, 'regenerate')">重新生成</a-button>
                <a-button size="small" @click="generateCasesForRequest(record, 'append')">追加生成</a-button>
              </div>
            </div>

            <div v-if="requestTestCaseLoadingMap[record.id]" class="request-case-panel__loading">
              <a-spin />
            </div>
            <a-empty
              v-else-if="!(requestTestCaseMap[record.id]?.length)"
              description="当前接口下还没有测试用例，可直接使用 AI 生成。"
            />
            <div v-else class="request-case-list">
              <div v-for="testCase in requestTestCaseMap[record.id]" :key="testCase.id" class="request-case-card">
                <div class="request-case-card__main">
                  <div class="request-case-card__name">{{ testCase.name }}</div>
                  <div class="request-case-card__desc">{{ testCase.description || '暂无描述' }}</div>
                  <a-space wrap>
                    <a-tag :color="statusTagColorMap[testCase.status]">{{ statusLabelMap[testCase.status] }}</a-tag>
                    <a-tag v-for="tag in testCase.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
                  </a-space>
                </div>
                <div class="request-case-card__meta">
                  <span>{{ formatDate(testCase.updated_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:visible="editorVisible"
      :title="editingRequest ? '编辑接口' : '新增接口'"
      width="900px"
      :ok-loading="submitLoading"
      :mask-closable="!submitLoading"
      :closable="!submitLoading"
      @before-ok="submitRequest"
      @cancel="resetEditor"
    >
      <div v-if="!editingRequest" class="create-mode-switch">
        <a-radio-group v-model="createMode" type="button">
          <a-radio value="manual">手动创建</a-radio>
          <a-radio value="document">文档导入</a-radio>
        </a-radio-group>
      </div>

      <a-form v-if="editingRequest || createMode === 'manual'" :model="formState" layout="vertical">
        <div v-if="!editingRequest && createMode === 'manual' && hasRequestDrafts" class="import-prefill-banner">
          <div class="prefill-copy">
            <div class="prefill-title">已同步最近一次文档解析结果</div>
            <div class="prefill-description">
              {{ draftSummary || '可以直接把解析结果回填到手动创建表单。' }}
            </div>
          </div>
          <div class="prefill-actions">
            <a-select
              v-model="selectedRequestDraftIndex"
              style="width: 260px"
              @change="applySelectedRequestDraft"
            >
              <a-option
                v-for="(draft, index) in requestDrafts"
                :key="`${draft.label}-${index}`"
                :value="index"
                :label="draft.label"
              />
            </a-select>
            <a-button @click="applySelectedRequestDraft()">鍥炲～瀛楁</a-button>
            <a-button type="text" @click="clearDraftsAndReset">娓呴櫎鑽夌</a-button>
          </div>
        </div>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="name" label="接口名称" :rules="[{ required: true, message: '请输入接口名称' }]">
              <a-input v-model="formState.name" placeholder="例如：获取用户信息" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="description" label="描述">
              <a-textarea v-model="formState.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
            </a-form-item>
          </a-col>
        </a-row>

        <StructuredHttpEditor v-model="formState.editor" />
      </a-form>

      <div v-else-if="importProgressActive" class="document-import-panel import-progress-panel">
        <div class="import-progress-hero">
          <div class="import-progress-badge">
            {{
              importProgressStatus === 'error'
                ? '解析失败'
                : importProgressStatus === 'success'
                  ? '解析完成'
                  : '智能解析中'
            }}
          </div>
          <div class="import-progress-title">{{ importProgressFileName || '接口文档' }}</div>
          <div class="import-progress-description">{{ importProgressMessage }}</div>
        </div>

        <div class="import-progress-bar">
          <a-progress
            :percent="importProgressRatio"
            :show-text="false"
            :status="
              importProgressStatus === 'error'
                ? 'danger'
                : importProgressStatus === 'success'
                  ? 'success'
                  : undefined
            "
          />
          <span class="import-progress-percent">{{ importProgressPercent }}%</span>
        </div>

        <div class="import-progress-step-list">
          <div
            v-for="(step, index) in importProgressSteps"
            :key="step.title"
            class="import-progress-step"
            :class="getImportStepClass(index)"
          >
            <div class="import-progress-step-marker">{{ index + 1 }}</div>
            <div class="import-progress-step-copy">
              <div class="import-progress-step-title">{{ step.title }}</div>
              <div class="import-progress-step-description">{{ step.description }}</div>
            </div>
          </div>
        </div>

        <a-alert v-if="importProgressStatus === 'error'" type="error" class="import-progress-alert">
          <template #title>本次导入没有成功</template>
          {{ importProgressError || '请检查文档是否包含接口名称、请求方式、请求地址、参数说明和成功响应描述。' }}
        </a-alert>

        <div class="import-progress-actions" :class="{ 'is-error-only': importProgressStatus === 'error' }">
          <a-button
            v-if="currentImportJob && canCancelImportJob(currentImportJob)"
            status="danger"
            @click="handleCancelImportJob(currentImportJob)"
          >
            停止解析
          </a-button>
          <a-button @click="resetImportProgress">返回重新导入</a-button>
        </div>
      </div>

      <div v-else class="document-import-panel">
        <div class="import-hero-card">
          <div class="import-hero-badge">AI文档解析</div>
          <div class="import-hero-title">接口文档导入与自动化生成</div>
          <div class="import-hero-description">
            支持 Swagger / OpenAPI / Postman，以及 PDF、图片、PPTX、DOCX、XLSX、HTML、EPUB 等格式。
            导入时会直接调用系统设置中的当前激活模型进行 AI 文档解析，按正文切片提取接口定义，并批量生成脚本与测试用例。
          </div>
          <div class="import-hero-meta">
            <span class="hero-pill">系统设置 &gt; AI大模型配置</span>
            <span class="hero-pill">提示词管理 &gt; API自动化解析</span>
            <span class="hero-pill">长文档自动切片解析</span>
          </div>
        </div>

        <div class="document-source-switch">
          <a-radio-group v-model="documentImportMode" type="button" @change="handleDocumentImportModeChange">
            <a-radio value="file">文件上传</a-radio>
            <a-radio value="text">直接输入</a-radio>
          </a-radio-group>
        </div>

        <div
          v-if="documentImportMode === 'file'"
          class="document-dropzone"
          :class="{ 'is-dragging': documentDragging, 'has-file': !!documentFile }"
          @click="triggerDocumentSelect"
          @dragenter.prevent="documentDragging = true"
          @dragover.prevent="documentDragging = true"
          @dragleave.prevent="documentDragging = false"
          @drop="handleDocumentDrop"
        >
          <input
            ref="documentInputRef"
            class="file-input-hidden"
            type="file"
            accept=".json,.yaml,.yml,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.html,.htm,.epub"
            @change="handleDocumentChange"
          />
          <div class="dropzone-icon">AI</div>
          <div class="dropzone-title">
            {{ documentFile ? '已选择接口文档，导入时将自动解析' : '拖拽接口文档到这里，或点击选择文件' }}
          </div>
          <div class="dropzone-subtitle">
            推荐优先上传 OpenAPI / Swagger / Postman。非结构化文档会直接使用 AI 文档解析提取接口信息。
          </div>

          <div v-if="documentFile" class="selected-file-card" @click.stop>
            <div class="selected-file-main">
              <div class="selected-file-name">{{ documentFile.name }}</div>
              <div class="selected-file-meta">{{ documentFileSummary }}</div>
            </div>
            <a-button type="text" size="small" @click="clearDocumentFile">重新选择</a-button>
          </div>
        </div>

        <div v-if="documentImportMode === 'text'" class="document-text-panel">
          <div class="document-text-panel__header">
            <div>
              <div class="document-text-panel__title">直接粘贴接口文档正文</div>
              <div class="document-text-panel__description">
                支持单个或多个接口说明直接输入。提交后会和文件导入一样走 AI 切片解析，内容过长时会自动分片并发处理。
              </div>
            </div>
            <div class="document-text-panel__summary">{{ documentTextSummary }}</div>
          </div>
          <a-input
            v-model="documentSourceName"
            class="document-text-name"
            placeholder="文档名称（选填），例如：CMS接口文档.md"
            allow-clear
          />
          <a-textarea
            v-model="documentText"
            class="document-textarea"
            :auto-size="{ minRows: 14, maxRows: 22 }"
            placeholder="直接粘贴接口文档正文。可以是单个接口，也可以一次粘贴多个接口说明、请求示例、参数表和返回说明等内容。"
          />
        </div>

        <div class="import-option-grid">
          <div class="import-option-card import-option-card-primary">
            <div class="option-copy">
              <div class="option-title">AI 文档解析</div>
              <div class="option-description">
                使用系统设置中当前激活的 AI 接口，并读取“提示词管理”中的 API 自动化解析提示词；长文档会自动切片后并发解析，再统一汇总。
              </div>
              <a-alert
                v-if="importAiCompatibility"
                :type="importAiCompatibilityAlertType"
                class="import-option-status"
              >
                <template #title>{{ importAiCompatibility.title }}</template>
                <div>{{ importAiCompatibility.message }}</div>
                <div v-if="importAiCompatibility.action_hint" class="import-option-status__hint">
                  {{ importAiCompatibility.action_hint }}
                </div>
              </a-alert>
              <div v-else-if="importAiCompatibilityLoading" class="import-option-status__loading">
                姝ｅ湪妫€娴嬪綋鍓?AI 閰嶇疆涓庢枃妗ｅ鍏ョ殑鍏煎鎬?..
              </div>
            </div>
            <a-switch v-model="enableAiParse" :disabled="importAiParseBlocked || documentImportMode === 'text'" />
          </div>
          <div class="import-option-card">
            <div class="option-copy">
              <div class="option-title">批量生成测试用例</div>
              <div class="option-description">
                基于解析出的接口请求自动生成接口自动化脚本和测试用例，适合导入后直接进入回归设计。
              </div>
            </div>
            <a-switch v-model="generateTestCases" />
          </div>
        </div>

        <a-alert type="info" class="import-alert">
          <template #title>导入说明</template>
          文档导入完成后，结果面板会显示本次是否启用了 AI 文档解析、采用了哪个模型、提示词来源，以及解析耗时与结果说明。
        </a-alert>
      </div>
    </a-modal>

    <RequestExecutionResultModal
      v-model:visible="resultVisible"
      :result="currentResult"
    />

    <RequestImportResultDrawer
      v-model:visible="importResultVisible"
      :result="importResult"
      :alert-title="importResultAlertTitle"
      :alert-message="importResultAlertMessage"
      :alert-action-hint="importResultAlertActionHint"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import RequestExecutionResultModal from '../components/RequestExecutionResultModal.vue'
import RequestImportResultDrawer from '../components/RequestImportResultDrawer.vue'
import StructuredHttpEditor from '../components/StructuredHttpEditor.vue'
import { apiRequestApi, environmentApi, testCaseApi } from '../api'
import { useApiImportDrafts } from '../state/importDraft'
import { useApiCaseGenerationJobs } from '../state/caseGenerationJobs'
import {
  bodyModeToLegacyBodyType,
  httpEditorModelToRequestSpec,
  requestSpecToLegacyBody,
  requestSpecToLegacyHeaders,
  requestSpecToLegacyParams,
  requestToHttpEditorModel,
} from '../state/httpEditor'
import { useApiImportJobs } from '../state/importJobs'
import { useRequestCaseGeneration, type CaseGenerationMode } from '../state/useRequestCaseGeneration'
import { useRequestEditor } from '../state/useRequestEditor'
import { useRequestExecution } from '../state/useRequestExecution'
import { useRequestImportFeedback } from '../state/useRequestImportFeedback'
import { useRequestImportState } from '../state/useRequestImportState'
import { useRequestListData } from '../state/useRequestListData'
import type {
  ApiEnvironment,
  ApiImportJob,
  ApiRequest,
  ApiTestCase,
} from '../types'

const props = defineProps<{
  selectedCollectionId?: number
  selectedCollectionName?: string
}>()

const emit = defineEmits<{
  (e: 'executed'): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const projectName = computed(() => projectStore.currentProject?.name || '鏈€夋嫨椤圭洰')
const {
  requestDrafts,
  draftSummary,
  hasRequestDrafts,
  saveDraftsFromImport,
  getRequestDraft,
  clearDrafts,
} = useApiImportDrafts()
const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const statusLabelMap: Record<ApiTestCase['status'], string> = {
  draft: '鑽夌',
  ready: '灏辩华',
  disabled: '鍋滅敤',
}

const statusTagColorMap: Record<ApiTestCase['status'], string> = {
  draft: 'gray',
  ready: 'green',
  disabled: 'red',
}

const environmentLoading = ref(false)
const searchKeyword = ref('')
const environments = ref<ApiEnvironment[]>([])
const selectedEnvironmentId = ref<number | undefined>(undefined)
const {
  activeImportJobs,
  syncProject: syncImportProject,
  trackImportJob,
  registerFinishedHandler,
  cancelImportJob,
} = useApiImportJobs()
const {
  syncProject: syncCaseGenerationProject,
  createCaseGenerationJob,
  waitForCaseGenerationJob,
  applyCaseGenerationJob,
} = useApiCaseGenerationJobs()
const {
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
} = useRequestImportState()

function getErrorMessage(error: any) {
  const rawMessage = error?.error || error?.data?.error || error?.message || '处理接口失败'
  const rawText = String(rawMessage)
  if (rawText.includes('鏈繑鍥炲彲瑙ｆ瀽姝ｆ枃') || rawText.includes('LLM returned empty content')) {
    return '当前激活的 AI 网关调用成功，但未返回可解析正文，请切换到能正常返回正文的模型或网关后再试。'
  }
  if (error?.status === 408 || /timeout/i.test(String(rawMessage))) {
    return '接口文档解析超时，请稍后重试；如果文档较大，建议缩小文档范围或切换更快的模型。'
  }
  if (rawText.includes('服务端无响应')) {
    return '接口文档解析等待时间过长，请稍后重试；如果文档较大，建议缩小文档范围或切换更快的模型。'
  }
  return rawMessage
}

const {
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
} = useRequestListData({
  projectId,
  selectedCollectionId: computed(() => props.selectedCollectionId),
  searchKeyword,
  getErrorMessage,
})

const filteredRequests = computed(() => requests.value)

const requestCaseTotal = computed(() =>
  requests.value.reduce((sum, item) => sum + Number(item.test_case_count || 0), 0)
)

const requestRowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
}

const loadEnvironments = async () => {
  if (!projectId.value) {
    environments.value = []
    return
  }
  environmentLoading.value = true
  try {
    const res = await environmentApi.list({ project: projectId.value })
    const data = res.data?.data || []
    environments.value = Array.isArray(data) ? data : []
    if (!selectedEnvironmentId.value) {
      const defaultEnv = environments.value.find(item => item.is_default)
      if (defaultEnv) selectedEnvironmentId.value = defaultEnv.id
    }
  } catch (error) {
    console.error('[RequestList] 获取环境失败:', error)
    environments.value = []
  } finally {
    environmentLoading.value = false
  }
}
const {
  importResult,
  importResultVisible,
  importAiCompatibility,
  importAiCompatibilityLoading,
  importAiCompatibilityAlertType,
  importAiParseBlocked,
  importResultAlertTitle,
  importResultAlertMessage,
  importResultAlertActionHint,
  currentImportJob,
  canCancelImportJob,
  loadImportAiCompatibility,
  handleCancelImportJob,
  unregisterImportFinishedHandler,
} = useRequestImportFeedback({
  projectId,
  activeImportJobs,
  cancelImportJob,
  registerFinishedHandler,
  clearImportProgressTimer,
  importProgressActive,
  importProgressStatus,
  importProgressMessage,
  importProgressError,
  saveDraftsFromImport,
  clearRequestListCache,
  loadRequests,
  onUpdated: () => emit('updated'),
})

const {
  editorVisible,
  submitLoading,
  editingRequest,
  formState,
  resetEditor,
  openCreateModal,
  openEditModal: openEditModalBase,
  applySelectedRequestDraft: applySelectedRequestDraftBase,
  clearDraftsAndReset,
  submitManualRequest,
} = useRequestEditor({
  selectedCollectionId: computed(() => props.selectedCollectionId),
  ensureRequestDetail,
  getRequestDraft,
  hasRequestDrafts,
  resetImportDraft,
  resetImportProgress,
  clearDrafts,
  getErrorMessage,
  setLoading: value => {
    loading.value = value
  },
})

const openEditModal = async (record: ApiRequest) => {
  await openEditModalBase(record, mode => {
    createMode.value = mode
  })
}

const applySelectedRequestDraft = (value?: string | number | boolean) => {
  const index = typeof value === 'number' ? value : selectedRequestDraftIndex.value
  selectedRequestDraftIndex.value = index
  applySelectedRequestDraftBase(index)
}

const _submitDocumentImportLegacy = async () => {
  if (!documentFile.value) {
    throw new Error('请先选择接口文档')
  }

  startImportProgress(documentFile.value.name)
  try {
    const res = await apiRequestApi.importDocument(props.selectedCollectionId!, { file: documentFile.value }, {
      generateTestCases: generateTestCases.value,
      enableAiParse: enableAiParse.value,
      onUploadProgress: handleImportUploadProgress,
      asyncMode: true,
    })
    const job = res.data.data as ApiImportJob
    clearImportProgressTimer()
    resetImportProgress()
    trackImportJob(job)
    Message.success('接口文档解析任务已提交，后台会继续执行，完成后会自动提示你。')
  } catch (error: any) {
    failImportProgress(getErrorMessage(error))
    throw error
  }
}

const submitDocumentImport = async () => {
  const inlineText = documentText.value.trim()

  if (documentImportMode.value === 'file' && !documentFile.value) {
    throw new Error('请先选择接口文档')
  }
  if (documentImportMode.value === 'text' && !inlineText) {
    throw new Error('请先输入接口文档内容')
  }
  if (documentImportMode.value === 'text' && importAiParseBlocked.value) {
    throw new Error(importAiCompatibility.value?.message || '当前 AI 配置暂不支持直接输入解析，请先切换可用模型。')
  }

  const sourceName = documentImportMode.value === 'file' ? documentFile.value!.name : buildInlineDocumentSourceName()
  startImportProgress(sourceName)
  try {
    const res = await apiRequestApi.importDocument(
      props.selectedCollectionId!,
      documentImportMode.value === 'file'
        ? { file: documentFile.value! }
        : { rawText: inlineText, sourceName },
      {
        generateTestCases: generateTestCases.value,
        enableAiParse: documentImportMode.value === 'text' ? true : enableAiParse.value,
        onUploadProgress: handleImportUploadProgress,
        asyncMode: true,
      }
    )
    const job = res.data.data as ApiImportJob
    clearImportProgressTimer()
    resetImportProgress()
    trackImportJob(job)
    Message.success('接口文档解析任务已提交，后台会继续执行，完成后会自动提示你。')
  } catch (error: any) {
    failImportProgress(getErrorMessage(error))
    throw error
  }
}

const submitRequest = async (done: (closed: boolean) => void) => {
  if (!projectId.value || !props.selectedCollectionId) {
    Message.warning('请先选择接口集合')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    if (editingRequest.value || createMode.value === 'manual') {
      await submitManualRequest()
      done(true)
      editorVisible.value = false
      resetEditor()
      emit('updated')
      clearRequestListCache()
      loadRequests(true)
    } else {
      await submitDocumentImport()
      done(true)
      editorVisible.value = false
      resetEditor()
    }
  } catch (error: any) {
    console.error('[RequestList] 保存接口失败:', error)
    Message.error(getErrorMessage(error))
    done(false)
  } finally {
    submitLoading.value = false
  }
}

const deleteRequest = async (id: number) => {
  try {
    await apiRequestApi.delete(id)
    Message.success('接口删除成功')
    emit('updated')
    clearRequestListCache()
    loadRequests(true)
  } catch (error: any) {
    Message.error(error?.error || '删除接口失败')
  }
}

const { generateCasesByScope } = useRequestCaseGeneration({
  createCaseGenerationJob,
  waitForCaseGenerationJob,
  applyCaseGenerationJob,
  clearRequestListCache,
  loadRequests,
  expandedRequestKeys,
  loadRequestTestCases,
  onUpdated: () => emit('updated'),
})

const {
  currentResult,
  resultVisible,
  stringifyBlock,
  formatDate,
  formatDuration,
  executeRequestBatch,
  executeRequest,
  viewRequest,
} = useRequestExecution({
  projectId,
  selectedEnvironmentId,
  ensureRequestDetail,
  requestToSnapshot: detail => {
    const requestSpec = detail.request_spec || httpEditorModelToRequestSpec(requestToHttpEditorModel(detail))
    return {
      id: 0,
      project: detail.project_id || projectId.value || 0,
      request: detail.id,
      environment: null,
      request_name: detail.name,
      method: detail.method,
      url: detail.url,
      status: 'success',
      passed: false,
      status_code: null,
      response_time: null,
      request_snapshot: {
        headers: requestSpecToLegacyHeaders(requestSpec),
        params: requestSpecToLegacyParams(requestSpec),
        body_type: bodyModeToLegacyBodyType(requestSpec.body_mode),
        body: requestSpecToLegacyBody(requestSpec),
        assertions: detail.assertion_specs || detail.assertions,
        request_spec: requestSpec,
        assertion_specs: detail.assertion_specs || [],
        extractor_specs: detail.extractor_specs || [],
        generated_script: detail.generated_script,
      },
      response_snapshot: {},
      assertions_results: [],
      created_at: detail.updated_at,
      executor: null,
    }
  },
  getErrorMessage,
  setLoading: value => {
    loading.value = value
  },
  onExecuted: () => emit('executed'),
})

const generateCasesForRequest = async (record: ApiRequest, mode: CaseGenerationMode) => {
  await generateCasesByScope(
    {
      scope: 'selected',
      ids: [record.id],
      mode,
      count_per_request: 3,
    },
    [record.id]
  )
}

const handleSingleCaseGenerationAction = async (record: ApiRequest, value: string | number | boolean) => {
  const mode = String(value) as CaseGenerationMode
  if (!['generate', 'append', 'regenerate'].includes(mode)) return
  await generateCasesForRequest(record, mode)
}

const handleSelectedCaseGenerationAction = async (value: string | number | boolean) => {
  const mode = String(value) as CaseGenerationMode
  if (!['generate', 'append', 'regenerate'].includes(mode)) return
  if (!selectedRequestIds.value.length) {
    Message.warning('请先选择要生成测试用例的接口')
    return
  }
  await generateCasesByScope(
    {
      scope: 'selected',
      ids: selectedRequestIds.value,
      mode,
      count_per_request: 3,
    },
    selectedRequestIds.value
  )
}

const executeSelectedRequests = async () => {
  if (!selectedRequestIds.value.length) {
    Message.warning('请先选择要执行的接口')
    return
  }
  await executeRequestBatch(
    {
      scope: 'selected',
      ids: selectedRequestIds.value,
      environment_id: selectedEnvironmentId.value,
    },
    '选中接口执行'
  )
}

const executeCollectionRequests = async () => {
  if (!props.selectedCollectionId) {
    Message.warning('请先选择接口集合')
    return
  }
  await executeRequestBatch(
    {
      scope: 'collection',
      collection_id: props.selectedCollectionId,
      environment_id: selectedEnvironmentId.value,
    },
    '当前集合执行'
  )
}

const executeProjectRequests = async () => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    return
  }
  await executeRequestBatch(
    {
      scope: 'project',
      project_id: projectId.value,
      environment_id: selectedEnvironmentId.value,
    },
    '项目接口执行'
  )
}

watch(
  [editorVisible, createMode],
  ([visible, mode]) => {
    if (visible && mode === 'document') {
      void loadImportAiCompatibility()
    }
  }
)

watch(
  importAiCompatibility,
  value => {
    if (value && !value.compatible) {
      enableAiParse.value = false
    }
  }
)

watch(
  [() => projectId.value, () => props.selectedCollectionId],
  ([nextProjectId, nextCollectionId], [prevProjectId, prevCollectionId]) => {
    syncImportProject(nextProjectId)
    syncCaseGenerationProject(nextProjectId)
    resetRequestState()

    if (nextProjectId !== prevProjectId) {
      loadEnvironments()
    }

    if (nextProjectId !== prevProjectId || nextCollectionId !== prevCollectionId) {
      loadRequests()
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  clearImportProgressTimer()
  unregisterImportFinishedHandler()
})

defineExpose({
  refresh: loadRequests,
})
</script>

<style scoped>
.request-list {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.api-page-header {
  display: grid;
  grid-template-columns: minmax(260px, 1.1fr) minmax(520px, 1.6fr);
  align-items: end;
  justify-content: space-between;
  gap: 22px;
  padding: 24px 26px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.9));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.06);
}

.page-summary,
.page-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.page-summary {
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.page-summary__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.page-summary__title {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.08;
  color: #0f172a;
}

.page-summary__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.page-summary__meta span {
  position: relative;
  padding-right: 12px;
}

.page-summary__meta span:not(:last-child)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.9);
  transform: translateY(-50%);
}

.page-toolbar {
  justify-content: flex-end;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-group--filter {
  flex: 0 1 auto;
}

.toolbar-group--actions {
  justify-content: flex-end;
}

.toolbar-select {
  width: 240px;
}

.toolbar-search {
  width: 320px;
  max-width: 100%;
}

.page-toolbar :deep(.arco-input-wrapper),
.toolbar-group :deep(.arco-select-view),
.toolbar-group :deep(.arco-btn) {
  min-height: 42px;
}

.toolbar-group :deep(.arco-btn) {
  padding-inline: 16px;
  border-radius: 14px;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.content-section :deep(.arco-table-container) {
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.content-section :deep(.arco-table-th) {
  padding-top: 16px;
  padding-bottom: 16px;
}

.content-section :deep(.arco-table-td) {
  padding-top: 15px;
  padding-bottom: 15px;
}

.request-case-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px 26px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.96));
}

.request-case-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.request-case-panel__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.request-case-panel__subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.request-case-panel__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.request-case-panel__loading {
  padding: 18px 0;
  display: flex;
  justify-content: center;
}

.request-case-list {
  display: grid;
  gap: 12px;
}

.request-case-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
}

.request-case-card__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.request-case-card__name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.request-case-card__desc {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-word;
}

.request-case-card__meta {
  flex: 0 0 auto;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .api-page-header {
    grid-template-columns: 1fr;
  }

  .page-toolbar {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .api-page-header {
    align-items: stretch;
    padding: 20px;
  }

  .page-summary,
  .page-toolbar,
  .toolbar-group,
  .toolbar-search,
  .toolbar-select {
    width: 100%;
  }

  .page-summary__title {
    font-size: 24px;
  }

  .toolbar-select {
    min-width: 0;
  }

  .request-case-card {
    flex-direction: column;
  }

  .request-case-card__meta {
    white-space: normal;
  }
}

.create-mode-switch {
  margin-bottom: 16px;
}

.import-prefill-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(59, 130, 246, 0.14);
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(20, 184, 166, 0.08)),
    rgba(255, 255, 255, 0.92);
}

.prefill-copy {
  min-width: 0;
}

.prefill-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.prefill-description {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.prefill-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.document-import-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.document-source-switch {
  display: flex;
  justify-content: flex-start;
}

.import-alert {
  margin-bottom: 0;
}

.import-progress-panel {
  gap: 18px;
}

.import-progress-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-progress-percent {
  min-width: 52px;
  text-align: right;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.import-progress-hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(15, 118, 110, 0.12)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 252, 0.92));
  border: 1px solid rgba(59, 130, 246, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.import-progress-badge {
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.import-progress-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.import-progress-description {
  font-size: 14px;
  line-height: 1.7;
  color: #475569;
}

.import-progress-step-list {
  display: grid;
  gap: 12px;
}

.import-progress-step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.86);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.import-progress-step.is-active {
  border-color: rgba(59, 130, 246, 0.26);
  box-shadow: 0 16px 34px rgba(59, 130, 246, 0.12);
  transform: translateY(-1px);
}

.import-progress-step.is-finished {
  border-color: rgba(20, 184, 166, 0.22);
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.08), rgba(255, 255, 255, 0.96)),
    rgba(255, 255, 255, 0.92);
}

.import-progress-step.is-error {
  border-color: rgba(239, 68, 68, 0.24);
  background:
    linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(255, 255, 255, 0.96)),
    rgba(255, 255, 255, 0.92);
}

.import-progress-step-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.import-progress-step.is-active .import-progress-step-marker {
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  color: #fff;
}

.import-progress-step.is-finished .import-progress-step-marker {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
}

.import-progress-step.is-error .import-progress-step-marker {
  background: linear-gradient(135deg, #dc2626, #f97316);
  color: #fff;
}

.import-progress-step-copy {
  min-width: 0;
}

.import-progress-step-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.import-progress-step-description {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.import-progress-alert {
  margin-bottom: 0;
}

.import-progress-actions {
  display: flex;
  justify-content: flex-end;
}

.import-hero-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(13, 148, 136, 0.14), rgba(15, 23, 42, 0.06)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 252, 0.92));
  border: 1px solid rgba(13, 148, 136, 0.16);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.08);
}

.import-hero-badge {
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(13, 148, 136, 0.12);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.import-hero-title {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.import-hero-description {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
}

.import-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.document-dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 24px;
  border-radius: 26px;
  border: 1.5px dashed rgba(15, 118, 110, 0.26);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(244, 250, 249, 0.88));
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.document-dropzone:hover,
.document-dropzone.is-dragging {
  transform: translateY(-1px);
  border-color: rgba(13, 148, 136, 0.5);
  box-shadow: 0 18px 40px rgba(15, 118, 110, 0.12);
}

.document-dropzone.has-file {
  border-style: solid;
  border-color: rgba(13, 148, 136, 0.24);
}

.file-input-hidden {
  display: none;
}

.dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 68px;
  height: 68px;
  border-radius: 20px;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 18px 36px rgba(15, 118, 110, 0.2);
}

.dropzone-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.dropzone-subtitle {
  max-width: 640px;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.selected-file-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  max-width: 680px;
  margin-top: 8px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.selected-file-main {
  min-width: 0;
}

.selected-file-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-all;
}

.selected-file-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.document-text-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid rgba(13, 148, 136, 0.14);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(244, 250, 249, 0.88));
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.document-text-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.document-text-panel__title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.document-text-panel__description {
  margin-top: 6px;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.document-text-panel__summary {
  flex: 0 0 auto;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(13, 148, 136, 0.08);
  color: #0f766e;
  font-size: 12px;
  font-weight: 600;
}

.document-text-name {
  max-width: 420px;
}

.document-textarea :deep(textarea) {
  font-family: 'JetBrains Mono', 'Consolas', 'Microsoft YaHei UI', monospace;
  line-height: 1.7;
}

.import-option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-option-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.import-option-card-primary {
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(59, 130, 246, 0.08)),
    rgba(255, 255, 255, 0.92);
}

.option-copy {
  min-width: 0;
}

.option-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.option-description {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.import-option-status {
  margin-top: 12px;
}

.import-option-status__hint,
.import-option-status__loading {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #7c2d12;
}

.empty-tip-card {
  padding: 44px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.result-drawer,
.import-result-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-result-alert {
  margin-bottom: 4px;
}

.import-result-alert__hint {
  margin-top: 8px;
  color: #7c2d12;
  font-size: 12px;
  line-height: 1.7;
}

.import-task-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-task-alert {
  margin-bottom: 0;
}

.import-task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.import-task-card {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.import-task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.import-task-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.import-task-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.import-task-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.import-task-progress-text {
  min-width: 44px;
  text-align: right;
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.import-task-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 14px;
}

.import-task-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.import-task-step-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.5);
  flex-shrink: 0;
}

.import-task-step.is-finished {
  color: #0f766e;
}

.import-task-step.is-finished .import-task-step-dot {
  background: #14b8a6;
}

.import-task-step.is-active {
  color: #2563eb;
}

.import-task-step.is-active .import-task-step-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.14);
}

.import-task-step.is-failed {
  color: #dc2626;
}

.import-task-step.is-failed .import-task-step-dot {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.12);
}

.import-task-error {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(254, 242, 242, 0.96);
  border: 1px solid rgba(248, 113, 113, 0.22);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-word;
}

.import-task-float {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 1200;
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 280px;
  padding: 14px 16px;
  border: 1px solid rgba(59, 130, 246, 0.16);
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(20, 184, 166, 0.1)),
    rgba(255, 255, 255, 0.94);
  box-shadow: 0 22px 40px rgba(15, 23, 42, 0.14);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.import-task-float:hover {
  transform: translateY(-2px);
  box-shadow: 0 26px 44px rgba(15, 23, 42, 0.18);
}

.import-task-float-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.import-task-float-copy {
  min-width: 0;
  flex: 1;
}

.import-task-float-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.import-task-float-desc {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.import-task-float-progress {
  width: 96px;
  flex-shrink: 0;
}

.import-tags {
  margin-bottom: 12px;
}

.json-block {
  margin: 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.95);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-modal :deep(.arco-modal) {
  max-width: min(1120px, calc(100vw - 32px));
}

.detail-modal :deep(.arco-modal-body) {
  padding: 20px 24px 24px;
}

@media (max-width: 900px) {
  .import-option-grid {
    grid-template-columns: 1fr;
  }

  .import-prefill-banner,
  .selected-file-card,
  .import-option-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .import-task-float {
    right: 16px;
    bottom: 16px;
    left: 16px;
    min-width: 0;
  }
}
</style>



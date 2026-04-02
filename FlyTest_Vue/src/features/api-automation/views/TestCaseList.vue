<template>
  <div class="test-case-list">
    <div class="page-header">
      <div class="page-header__copy">
        <div class="page-header__eyebrow">项目 / 接口 / 用例</div>
        <div class="page-header__title">测试用例</div>
        <div class="page-header__meta">
          <span>{{ projectName }}</span>
          <span>{{ selectedCollectionName || '未选择接口目录' }}</span>
          <span>{{ selectedRequestName || '全部接口' }}</span>
          <span>{{ groupedTestCases.length }} 个接口</span>
          <span>{{ filteredTestCases.length }} 条用例</span>
        </div>
      </div>
      <div class="page-header__tools">
        <a-input-search
          v-model="searchKeyword"
          class="tools-search"
          placeholder="搜索测试用例、接口名称或请求地址"
          allow-clear
          @search="loadTestCases"
          @clear="loadTestCases"
        />
        <a-select
          v-model="selectedEnvironmentId"
          class="tools-select"
          :loading="environmentLoading"
          allow-clear
          placeholder="执行环境"
        >
          <a-option v-for="item in environments" :key="item.id" :value="item.id" :label="item.name" />
        </a-select>
        <div v-if="selectedRequestId" class="tools-group">
          <a-button :loading="caseGenerationLoadingMode === 'generate'" :disabled="isCaseGenerationLoading" @click="generateCases('generate')">AI生成</a-button>
          <a-button :loading="caseGenerationLoadingMode === 'regenerate'" :disabled="isCaseGenerationLoading" @click="generateCases('regenerate')">重新生成</a-button>
          <a-button :loading="caseGenerationLoadingMode === 'append'" :disabled="isCaseGenerationLoading" @click="generateCases('append')">追加生成</a-button>
        </div>
        <div class="tools-group">
          <a-button :disabled="!selectedTestCaseIds.length" @click="executeSelectedTestCases">批量执行</a-button>
          <a-button status="danger" :disabled="!selectedTestCaseIds.length" @click="confirmDeleteSelectedTestCases">批量删除</a-button>
          <a-button :disabled="!canExecuteCurrentScope" @click="executeCurrentScopeTestCases">{{ currentScopeExecuteLabel }}</a-button>
          <a-button @click="loadTestCases">刷新</a-button>
        </div>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="state-card"><a-empty description="请先在左侧选择接口目录或具体接口。" /></div>
    <div v-else-if="loading" class="state-card"><a-spin size="large" /></div>
    <div v-else-if="!groupedTestCases.length" class="state-card">
      <a-empty :description="selectedRequestId ? '当前接口下暂无测试用例。' : '当前接口目录下暂无测试用例。'" />
    </div>

    <div v-else class="group-list">
      <section v-for="group in groupedTestCases" :key="group.key" class="group-card">
        <div class="group-card__head">
          <div class="group-card__copy">
            <div class="group-card__title">
              <a-tag :color="methodColorMap[group.requestMethod] || 'arcoblue'">{{ group.requestMethod }}</a-tag>
              <span>{{ group.requestName }}</span>
            </div>
            <div class="group-card__meta">
              <span>{{ group.requestUrl || '-' }}</span>
              <span>{{ group.totalCount }} 条用例</span>
              <span>{{ group.readyCount }} 条就绪</span>
            </div>
          </div>
          <div class="tools-group">
            <a-button size="small" @click="toggleGroupSelection(group)">{{ isGroupFullySelected(group) ? '取消全选' : '全选该接口用例' }}</a-button>
            <a-button size="small" @click="executeGroupTestCases(group)">执行该接口</a-button>
          </div>
        </div>

        <a-table :data="group.cases" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="选择" :width="72" align="center">
              <template #cell="{ record }">
                <a-checkbox :model-value="isCaseSelected(record.id)" @change="value => toggleTestCaseSelection(record.id, value)" />
              </template>
            </a-table-column>
            <a-table-column title="测试用例" :width="320">
              <template #cell="{ record }">
                <div class="case-name">
                  <div class="case-name__title">{{ record.name }}</div>
                  <div class="case-name__desc">{{ record.description || '暂无描述' }}</div>
                </div>
              </template>
            </a-table-column>
            <a-table-column title="状态" :width="120" align="center">
              <template #cell="{ record }"><a-tag :color="statusColorMap[record.status]">{{ statusLabelMap[record.status] }}</a-tag></template>
            </a-table-column>
            <a-table-column title="标签" :width="120" align="center">
              <template #cell="{ record }"><a-tag color="cyan">{{ record.tags?.length || 0 }}</a-tag></template>
            </a-table-column>
            <a-table-column title="更新时间" :width="180">
              <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
            </a-table-column>
            <a-table-column title="操作" :width="250" align="center">
              <template #cell="{ record }">
                <a-space :size="4">
                  <a-button type="text" size="small" @click="executeTestCase(record)">执行</a-button>
                  <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
                  <a-button type="text" size="small" @click="viewTestCase(record)">详情</a-button>
                  <a-popconfirm content="确认删除该测试用例吗？" @ok="deleteTestCases([record.id])">
                    <a-button type="text" size="small" status="danger">删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </section>
    </div>

    <a-modal
      v-model:visible="editorVisible"
      title="编辑测试用例"
      width="1240px"
      :align-center="true"
      :ok-loading="editorSubmitting"
      :mask-closable="!editorSubmitting"
      :closable="!editorSubmitting"
      :body-style="{ maxHeight: '78vh', overflowY: 'auto' }"
      @before-ok="submitTestCase"
      @cancel="resetEditor"
    >
      <a-form :model="formState" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12"><a-form-item label="测试用例名称"><a-input v-model="formState.name" /></a-form-item></a-col>
          <a-col :span="6">
            <a-form-item label="状态">
              <a-select v-model="formState.status">
                <a-option value="draft" label="草稿" />
                <a-option value="ready" label="就绪" />
                <a-option value="disabled" label="停用" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6"><a-form-item label="标签"><a-input v-model="formState.tagsText" placeholder="多个标签用逗号分隔" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="描述"><a-textarea v-model="formState.description" :auto-size="{ minRows: 2, maxRows: 4 }" /></a-form-item>

        <a-divider orientation="left">主请求覆盖</a-divider>
        <div class="section-note">配置该测试用例对主接口的请求覆盖、断言和提取器。</div>
        <StructuredHttpEditor v-model="formState.editor" :allow-empty-auth="true" :allow-inherited-transport="true" />

        <a-divider orientation="left">工作流步骤</a-divider>
        <div class="section-note">工作流步骤和主请求共用同一次执行上下文、变量和 Cookie 会话。</div>
        <WorkflowStepEditor v-model="formState.workflow_steps" :requests="availableRequests" :main-request="editingMainRequest" :loading="requestLoading" />
      </a-form>
    </a-modal>

    <a-modal v-model:visible="detailVisible" title="测试用例详情" width="1200px" :align-center="true" :footer="false" :body-style="{ maxHeight: '80vh', overflowY: 'auto' }">
      <div v-if="currentTestCase" class="detail-panel">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="测试用例">{{ currentTestCase.name }}</a-descriptions-item>
          <a-descriptions-item label="状态"><a-tag :color="statusColorMap[currentTestCase.status]">{{ statusLabelMap[currentTestCase.status] }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="接口名称">{{ currentTestCase.request_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="请求方法"><a-tag :color="methodColorMap[currentTestCase.request_method || ''] || 'arcoblue'">{{ currentTestCase.request_method || '-' }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="请求地址" :span="2">{{ currentTestCase.request_url || '-' }}</a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">{{ currentTestCase.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="标签" :span="2">
            <a-space wrap>
              <a-tag v-for="tag in currentTestCase.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
              <span v-if="!currentTestCase.tags?.length">-</span>
            </a-space>
          </a-descriptions-item>
        </a-descriptions>
        <a-divider>主请求覆盖</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.request_override_spec || currentTestCase.script) }}</pre>
        <a-divider>断言规则</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.assertion_specs || currentTestCase.assertions) }}</pre>
        <a-divider>提取器</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.extractor_specs || []) }}</pre>
        <a-divider>工作流步骤</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentWorkflowSteps.length ? currentWorkflowSteps : []) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import StructuredHttpEditor from '../components/StructuredHttpEditor.vue'
import WorkflowStepEditor from '../components/WorkflowStepEditor.vue'
import { apiRequestApi, environmentApi, testCaseApi } from '../api'
import { createEmptyHttpEditorModel, httpEditorModelToAssertionSpecs, httpEditorModelToExtractorSpecs, httpEditorModelToTestCaseOverrideSpec, testCaseToHttpEditorModel, workflowEditorStepToPayload, workflowStepToEditorStep } from '../state/httpEditor'
import type { ApiEnvironment, ApiExecutionBatchResult, ApiHttpEditorModel, ApiRequest, ApiTestCase, ApiTestCaseForm, ApiTestCaseGenerationResult, ApiTestCaseWorkflowEditorStep, ApiTestCaseWorkflowStep } from '../types'

interface TestCaseGroup { key: string; requestId: number | null; requestName: string; requestMethod: string; requestUrl: string; totalCount: number; readyCount: number; updatedAt?: string; cases: ApiTestCase[] }
interface TestCaseEditorForm { name: string; description: string; status: ApiTestCase['status']; tagsText: string; editor: ApiHttpEditorModel; workflow_steps: ApiTestCaseWorkflowEditorStep[]; scriptExtras: Record<string, any> }
type CaseGenerationMode = 'generate' | 'append' | 'regenerate'
type CaseGenerationPayload = { scope: 'selected' | 'collection' | 'project'; ids?: number[]; collection_id?: number; project_id?: number; mode: CaseGenerationMode; count_per_request?: number; apply_changes?: boolean }

const props = defineProps<{ selectedCollectionId?: number; selectedCollectionName?: string; selectedRequestId?: number; selectedRequestName?: string }>()
const emit = defineEmits<{ (e: 'executed'): void }>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const projectName = computed(() => projectStore.currentProject?.name || '未选择项目')

const loading = ref(false)
const requestLoading = ref(false)
const environmentLoading = ref(false)
const editorVisible = ref(false)
const detailVisible = ref(false)
const editorSubmitting = ref(false)
const caseGenerationLoadingMode = ref<CaseGenerationMode | ''>('')
const searchKeyword = ref('')
const testCases = ref<ApiTestCase[]>([])
const currentTestCase = ref<ApiTestCase | null>(null)
const editingTestCase = ref<ApiTestCase | null>(null)
const environments = ref<ApiEnvironment[]>([])
const availableRequests = ref<ApiRequest[]>([])
const selectedEnvironmentId = ref<number | undefined>()
const selectedTestCaseIds = ref<number[]>([])

const createInitialFormState = (): TestCaseEditorForm => ({ name: '', description: '', status: 'draft', tagsText: '', editor: createEmptyHttpEditorModel(), workflow_steps: [], scriptExtras: {} })
const formState = ref<TestCaseEditorForm>(createInitialFormState())

const methodColorMap: Record<string, string> = { GET: 'green', POST: 'arcoblue', PUT: 'orange', PATCH: 'purple', DELETE: 'red', HEAD: 'gray', OPTIONS: 'cyan' }
const statusColorMap: Record<ApiTestCase['status'], string> = { draft: 'gray', ready: 'green', disabled: 'red' }
const statusLabelMap: Record<ApiTestCase['status'], string> = { draft: '草稿', ready: '就绪', disabled: '停用' }

const isCaseGenerationLoading = computed(() => Boolean(caseGenerationLoadingMode.value))
const currentScopeExecuteLabel = computed(() => props.selectedRequestId ? '执行当前接口' : props.selectedCollectionId ? '执行当前目录' : '执行当前项目')
const canExecuteCurrentScope = computed(() => props.selectedRequestId ? testCases.value.length > 0 : props.selectedCollectionId ? true : Boolean(projectId.value))
const selectedIdSet = computed(() => new Set(selectedTestCaseIds.value))
const requestMap = computed(() => new Map(availableRequests.value.map(item => [item.id, item])))
const editingMainRequest = computed(() => editingTestCase.value ? resolveRequestById(editingTestCase.value.request) : null)
const currentWorkflowSteps = computed<ApiTestCaseWorkflowStep[]>(() => Array.isArray(currentTestCase.value?.script?.workflow_steps) ? currentTestCase.value!.script.workflow_steps as ApiTestCaseWorkflowStep[] : [])

const filteredTestCases = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return testCases.value
  return testCases.value.filter(item => [item.name, item.description || '', item.request_name || '', item.request_url || ''].some(text => text.toLowerCase().includes(keyword)))
})

const groupedTestCases = computed<TestCaseGroup[]>(() => {
  const groups = new Map<string, TestCaseGroup>()
  ;[...filteredTestCases.value].sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at)).forEach(item => {
    const key = `${item.request ?? 'unknown'}-${item.collection_id ?? 'unknown'}`
    const group = groups.get(key)
    if (group) {
      group.cases.push(item)
      group.totalCount += 1
      if (item.status === 'ready') group.readyCount += 1
      if (!group.updatedAt || +new Date(item.updated_at) > +new Date(group.updatedAt)) group.updatedAt = item.updated_at
      return
    }
    groups.set(key, { key, requestId: item.request ?? null, requestName: item.request_name || '未命名接口', requestMethod: item.request_method || 'GET', requestUrl: item.request_url || '', totalCount: 1, readyCount: item.status === 'ready' ? 1 : 0, updatedAt: item.updated_at, cases: [item] })
  })
  return Array.from(groups.values()).sort((a, b) => +new Date(b.updatedAt || 0) - +new Date(a.updatedAt || 0))
})

const cloneJson = <T>(value: T): T => JSON.parse(JSON.stringify(value))
const isPlainObject = (value: unknown): value is Record<string, any> => Boolean(value && typeof value === 'object')
const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const stringifyBlock = (value: any) => value === null || value === undefined ? '-' : typeof value === 'string' ? value : JSON.stringify(value, null, 2)
const parseTagsText = (text: string) => text.split(/[\n,，]/).map(item => item.trim()).filter(Boolean)
const isCaseSelected = (id: number) => selectedIdSet.value.has(id)
const resolveRequestById = (requestId?: number | null) => requestId === null || requestId === undefined ? null : requestMap.value.get(Number(requestId)) || null
const resolveRequestByName = (name?: string) => { const keyword = String(name || '').trim(); return keyword ? availableRequests.value.find(item => item.name === keyword) || availableRequests.value.find(item => item.name.includes(keyword)) || null : null }
const resolveWorkflowRequest = (testCase: ApiTestCase, step: ApiTestCaseWorkflowStep) => step.request_id !== null && step.request_id !== undefined ? resolveRequestById(step.request_id) : step.request_name ? resolveRequestByName(step.request_name) : resolveRequestById(testCase.request)
const buildWorkflowEditorSteps = (testCase: ApiTestCase) => {
  const mainRequest = resolveRequestById(testCase.request)
  const rawSteps = Array.isArray(testCase.script?.workflow_steps) ? testCase.script.workflow_steps : []
  return rawSteps.filter(isPlainObject).map((step, index) => workflowStepToEditorStep(step as ApiTestCaseWorkflowStep, { request: resolveWorkflowRequest(testCase, step as ApiTestCaseWorkflowStep), mainRequest, index }))
}

const toggleTestCaseSelection = (id: number, checked: boolean | string | number) => {
  const enabled = Boolean(checked)
  if (enabled && !selectedIdSet.value.has(id)) selectedTestCaseIds.value = [...selectedTestCaseIds.value, id]
  else if (!enabled && selectedIdSet.value.has(id)) selectedTestCaseIds.value = selectedTestCaseIds.value.filter(item => item !== id)
}

const isGroupFullySelected = (group: TestCaseGroup) => group.cases.length > 0 && group.cases.every(item => selectedIdSet.value.has(item.id))
const toggleGroupSelection = (group: TestCaseGroup) => {
  if (isGroupFullySelected(group)) {
    const ids = new Set(group.cases.map(item => item.id))
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id => !ids.has(id))
    return
  }
  const merged = new Set(selectedTestCaseIds.value)
  group.cases.forEach(item => merged.add(item.id))
  selectedTestCaseIds.value = Array.from(merged)
}

let requestLoadPromise: Promise<void> | null = null
const loadAvailableRequests = async () => {
  if (!projectId.value) { availableRequests.value = []; return }
  if (requestLoadPromise) { await requestLoadPromise; return }
  requestLoadPromise = (async () => {
    requestLoading.value = true
    try {
      const res = await apiRequestApi.list({ project: projectId.value })
      availableRequests.value = Array.isArray(res.data?.data) ? res.data.data : []
    } catch (error) {
      console.error('[TestCaseList] 获取接口列表失败:', error)
      availableRequests.value = []
    } finally {
      requestLoading.value = false
      requestLoadPromise = null
    }
  })()
  await requestLoadPromise
}

const loadEnvironments = async () => {
  if (!projectId.value) { environments.value = []; selectedEnvironmentId.value = undefined; return }
  environmentLoading.value = true
  try {
    const res = await environmentApi.list({ project: projectId.value })
    environments.value = Array.isArray(res.data?.data) ? res.data.data : []
    if (!selectedEnvironmentId.value) {
      const defaultEnv = environments.value.find(item => item.is_default)
      if (defaultEnv) selectedEnvironmentId.value = defaultEnv.id
    }
  } catch (error) {
    console.error('[TestCaseList] 获取环境失败:', error)
    environments.value = []
  } finally {
    environmentLoading.value = false
  }
}

const loadTestCases = async () => {
  if (!projectId.value || !props.selectedCollectionId) { testCases.value = []; selectedTestCaseIds.value = []; currentTestCase.value = null; return }
  loading.value = true
  try {
    const res = await testCaseApi.list({ project: projectId.value, collection: props.selectedCollectionId, request: props.selectedRequestId })
    testCases.value = Array.isArray(res.data?.data) ? res.data.data : []
    const ids = new Set(testCases.value.map(item => item.id))
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id => ids.has(id))
    if (currentTestCase.value) {
      currentTestCase.value = testCases.value.find(item => item.id === currentTestCase.value?.id) || null
      if (!currentTestCase.value) detailVisible.value = false
    }
  } catch (error) {
    console.error('[TestCaseList] 获取测试用例失败:', error)
    Message.error('获取测试用例失败')
    testCases.value = []
    selectedTestCaseIds.value = []
    currentTestCase.value = null
  } finally {
    loading.value = false
  }
}

const resetEditor = () => { editorVisible.value = false; editingTestCase.value = null; formState.value = createInitialFormState() }
const viewTestCase = (record: ApiTestCase) => { currentTestCase.value = record; detailVisible.value = true }

const openEditModal = async (record: ApiTestCase) => {
  await loadAvailableRequests()
  editingTestCase.value = record
  const scriptExtras = isPlainObject(record.script) ? cloneJson(record.script) : {}
  delete scriptExtras.workflow_steps
  formState.value = { name: record.name, description: record.description || '', status: record.status, tagsText: (record.tags || []).join(', '), editor: testCaseToHttpEditorModel(record), workflow_steps: buildWorkflowEditorSteps(record), scriptExtras }
  editorVisible.value = true
}

const submitTestCase = async (done: (closed: boolean) => void) => {
  if (!editingTestCase.value) return done(false)
  if (!formState.value.name.trim()) { Message.warning('请输入测试用例名称'); return done(false) }
  const unresolved = formState.value.workflow_steps.find(step => step.request_id && !resolveRequestById(step.request_id))
  if (unresolved) { Message.warning(`工作流步骤“${unresolved.name || '未命名步骤'}”绑定的接口不存在，请重新选择`); return done(false) }

  editorSubmitting.value = true
  try {
    const mainRequest = resolveRequestById(editingTestCase.value.request)
    const script = cloneJson(formState.value.scriptExtras || {})
    const workflowSteps = formState.value.workflow_steps.map(step => workflowEditorStepToPayload(step, { request: step.request_id ? resolveRequestById(step.request_id) : mainRequest, mainRequest }))
    if (workflowSteps.length) script.workflow_steps = workflowSteps
    else delete script.workflow_steps

    const payload: Partial<ApiTestCaseForm> = {
      project: editingTestCase.value.project,
      request: editingTestCase.value.request,
      name: formState.value.name.trim(),
      description: formState.value.description.trim() || '',
      status: formState.value.status,
      tags: parseTagsText(formState.value.tagsText),
      script,
      request_override_spec: httpEditorModelToTestCaseOverrideSpec(formState.value.editor),
      assertion_specs: httpEditorModelToAssertionSpecs(formState.value.editor),
      extractor_specs: httpEditorModelToExtractorSpecs(formState.value.editor),
    }

    const res = await testCaseApi.update(editingTestCase.value.id, payload)
    const updated = res.data?.data || null
    Message.success('测试用例更新成功')
    if (updated && currentTestCase.value?.id === updated.id) currentTestCase.value = updated
    done(true)
    resetEditor()
    await loadTestCases()
  } catch (error: any) {
    Message.error(error?.error || '测试用例更新失败')
    done(false)
  } finally {
    editorSubmitting.value = false
  }
}

const deleteTestCases = async (ids: number[]) => {
  if (!ids.length) return
  let successCount = 0
  let failureCount = 0
  let lastError = ''
  for (const id of ids) {
    try { await testCaseApi.delete(id); successCount += 1 } catch (error: any) { failureCount += 1; lastError = error?.error || '删除测试用例失败' }
  }
  if (successCount && !failureCount) Message.success(successCount === 1 ? '测试用例删除成功' : `已删除 ${successCount} 条测试用例`)
  else if (successCount && failureCount) Message.warning(`已删除 ${successCount} 条，失败 ${failureCount} 条${lastError ? `：${lastError}` : ''}`)
  else Message.error(lastError || '删除测试用例失败')
  const removed = new Set(ids)
  selectedTestCaseIds.value = selectedTestCaseIds.value.filter(item => !removed.has(item))
  if (currentTestCase.value && removed.has(currentTestCase.value.id)) { currentTestCase.value = null; detailVisible.value = false }
  await loadTestCases()
}

const confirmDeleteSelectedTestCases = () => {
  if (!selectedTestCaseIds.value.length) return Message.warning('请先选择要删除的测试用例')
  Modal.warning({ title: '确认批量删除', content: `确定要删除选中的 ${selectedTestCaseIds.value.length} 条测试用例吗？`, okText: '确认', cancelText: '取消', onOk: async () => deleteTestCases([...selectedTestCaseIds.value]) })
}

const showBatchExecutionMessage = (label: string, summary: ApiExecutionBatchResult) => {
  const text = `${label}完成：共 ${summary.total_count} 条，成功 ${summary.success_count} 条，断言失败 ${summary.failed_count} 条，异常 ${summary.error_count} 条。`
  summary.failed_count || summary.error_count ? Message.warning(text) : Message.success(text)
}

const executeTestCase = async (record: ApiTestCase) => {
  try {
    const res = await testCaseApi.execute(record.id, selectedEnvironmentId.value)
    Message.success(res.data.data.passed ? '测试用例执行通过' : '测试用例执行完成')
    emit('executed')
  } catch (error: any) {
    console.error('[TestCaseList] 执行测试用例失败:', error)
    Message.error(error?.error || '执行测试用例失败')
  }
}

const executeBatch = async (payload: { scope: 'selected' | 'collection' | 'project'; ids?: number[]; collection_id?: number; project_id?: number; environment_id?: number }, label: string) => {
  try {
    const res = await testCaseApi.executeBatch(payload)
    showBatchExecutionMessage(label, res.data.data)
    emit('executed')
  } catch (error: any) {
    console.error('[TestCaseList] 批量执行测试用例失败:', error)
    Message.error(error?.error || '批量执行测试用例失败')
  }
}

const executeSelectedTestCases = async () => {
  if (!selectedTestCaseIds.value.length) return Message.warning('请先选择要执行的测试用例')
  await executeBatch({ scope: 'selected', ids: selectedTestCaseIds.value, environment_id: selectedEnvironmentId.value }, '选中测试用例执行')
}

const executeGroupTestCases = async (group: TestCaseGroup) => executeBatch({ scope: 'selected', ids: group.cases.map(item => item.id), environment_id: selectedEnvironmentId.value }, `${group.requestName} 接口用例执行`)

const executeCurrentScopeTestCases = async () => {
  if (props.selectedRequestId) {
    if (!testCases.value.length) return Message.warning('当前接口下没有可执行的测试用例')
    return executeBatch({ scope: 'selected', ids: testCases.value.map(item => item.id), environment_id: selectedEnvironmentId.value }, `${props.selectedRequestName || '当前接口'}用例执行`)
  }
  if (props.selectedCollectionId) return executeBatch({ scope: 'collection', collection_id: props.selectedCollectionId, environment_id: selectedEnvironmentId.value }, '当前目录测试用例执行')
  if (!projectId.value) return Message.warning('请先选择项目')
  return executeBatch({ scope: 'project', project_id: projectId.value, environment_id: selectedEnvironmentId.value }, '项目测试用例执行')
}

const legacyBuildCaseSummaryLines = (summary: ApiTestCaseGenerationResult) => {
  const lines: string[] = []
  summary.items.forEach(item => {
    if (item.skipped || !item.case_summaries?.length) return
    const metaParts = [
      item.ai_used ? 'AI生成' : '模板回退',
      item.ai_cache_hit ? '命中缓存' : null,
      item.ai_duration_ms ? `耗时 ${Math.round(item.ai_duration_ms)} ms` : null,
    ].filter(Boolean)
    lines.push(`${item.request_name} (${item.request_method} ${item.request_url})`)
    if (metaParts.length) lines.push(`  ${metaParts.join(' / ')}`)
    item.case_summaries.forEach(caseItem => {
      lines.push(`  - ${caseItem.name}`)
      lines.push(
        `    断言: ${caseItem.assertion_types.length ? caseItem.assertion_types.join(', ') : '-'} | 提取变量: ${
          caseItem.extractor_variables.length ? caseItem.extractor_variables.join(', ') : '-'
        } | 覆盖字段: ${caseItem.override_sections.length ? caseItem.override_sections.join(', ') : '无额外覆盖'}`
      )
    })
  })
  return lines
}

const legacyShowCaseGenerationInsight = (summary: ApiTestCaseGenerationResult, mode: CaseGenerationMode) => {
  const lines = buildCaseSummaryLines(summary)
  if (!lines.length) return
  const title = mode === 'append' ? 'AI追加结果' : mode === 'regenerate' ? 'AI重生成结果' : 'AI生成结果'
  Modal.info({
    title,
    okText: '知道了',
    alignCenter: true,
    width: 880,
    content: () => h('div', { style: 'white-space: pre-wrap; line-height: 1.75; font-size: 13px;' }, lines.join('\n')),
  })
}

const legacyGenerateCases = async (mode: CaseGenerationMode) => {
  if (!props.selectedRequestId) return Message.warning('请先在左侧选择一个接口')
  caseGenerationLoadingMode.value = mode
  try {
    const res = await apiRequestApi.generateTestCases({ scope: 'selected', ids: [props.selectedRequestId], mode, count_per_request: 3 })
    const summary: ApiTestCaseGenerationResult = res.data.data
    showCaseGenerationInsight(summary, mode)
    const modeLabel = mode === 'append' ? '追加生成' : mode === 'regenerate' ? '重新生成' : '生成'
    const cacheText = summary.ai_cache_hit_count ? ` 命中缓存 ${summary.ai_cache_hit_count} 个接口。` : ''
    const text = `${modeLabel}完成：处理 ${summary.processed_requests}/${summary.total_requests} 个接口，新增 ${summary.created_testcase_count} 条测试用例。${cacheText}`
    summary.skipped_requests ? Message.warning(`${text} 跳过 ${summary.skipped_requests} 个已有用例的接口。`) : Message.success(text)
    await loadTestCases()
  } catch (error: any) {
    console.error('[TestCaseList] AI 生成测试用例失败:', error)
    Message.error(error?.error || 'AI 生成测试用例失败')
  } finally {
    caseGenerationLoadingMode.value = ''
  }
}

const formatCaseSummaryLine = (caseItem: NonNullable<ApiTestCaseGenerationResult['items'][number]['case_summaries']>[number]) => [
  `  - ${caseItem.name}`,
  `    断言: ${caseItem.assertion_types.length ? caseItem.assertion_types.join(', ') : '-'} | 提取变量: ${
    caseItem.extractor_variables.length ? caseItem.extractor_variables.join(', ') : '-'
  } | 覆盖字段: ${caseItem.override_sections.length ? caseItem.override_sections.join(', ') : '无额外覆盖'}`,
]

const buildCaseSummaryLines = (summary: ApiTestCaseGenerationResult) => {
  const lines: string[] = []
  summary.items.forEach(item => {
    if (item.skipped || !item.case_summaries?.length) return
    const metaParts = [
      item.ai_used ? 'AI生成' : '模板回退',
      item.ai_cache_hit ? '命中缓存' : null,
      item.ai_duration_ms ? `耗时 ${Math.round(item.ai_duration_ms)} ms` : null,
    ].filter(Boolean)
    lines.push(`${item.request_name} (${item.request_method} ${item.request_url})`)
    if (metaParts.length) lines.push(`  ${metaParts.join(' / ')}`)
    item.case_summaries.forEach(caseItem => {
      lines.push(...formatCaseSummaryLine(caseItem))
    })
  })
  return lines
}

const buildRegeneratePreviewLines = (summary: ApiTestCaseGenerationResult) => {
  const lines: string[] = []
  summary.items.forEach(item => {
    if (!item.preview_only) return
    const replacement = item.replacement_summary
    lines.push(`${item.request_name} (${item.request_method} ${item.request_url})`)
    lines.push(
      `  当前 ${replacement?.existing_count ?? item.existing_case_summaries?.length ?? 0} 条用例，候选 ${replacement?.proposed_count ?? item.proposed_case_summaries?.length ?? 0} 条用例`
    )
    if (replacement?.removed_case_names?.length) {
      lines.push(`  将移除: ${replacement.removed_case_names.join(', ')}`)
    }
    if (replacement?.added_case_names?.length) {
      lines.push(`  将新增: ${replacement.added_case_names.join(', ')}`)
    }
    if (replacement?.unchanged_case_names?.length) {
      lines.push(`  同名替换: ${replacement.unchanged_case_names.join(', ')}`)
    }
    if (item.existing_case_summaries?.length) {
      lines.push('  当前用例:')
      item.existing_case_summaries.forEach(caseItem => {
        lines.push(...formatCaseSummaryLine(caseItem).map(line => `  ${line}`))
      })
    }
    if (item.proposed_case_summaries?.length) {
      lines.push('  候选用例:')
      item.proposed_case_summaries.forEach(caseItem => {
        lines.push(...formatCaseSummaryLine(caseItem).map(line => `  ${line}`))
      })
    }
  })
  return lines
}

const showCaseGenerationInsight = (summary: ApiTestCaseGenerationResult, mode: CaseGenerationMode) => {
  const lines = buildCaseSummaryLines(summary)
  if (!lines.length) return
  const title = mode === 'append' ? 'AI追加结果' : mode === 'regenerate' ? 'AI重生成结果' : 'AI生成结果'
  Modal.info({
    title,
    okText: '知道了',
    alignCenter: true,
    width: 880,
    content: () => h('div', { style: 'white-space: pre-wrap; line-height: 1.75; font-size: 13px;' }, lines.join('\n')),
  })
}

const confirmRegeneratePreview = (summary: ApiTestCaseGenerationResult) =>
  new Promise<boolean>(resolve => {
    const lines = buildRegeneratePreviewLines(summary)
    let settled = false
    const finish = (value: boolean) => {
      if (settled) return
      settled = true
      resolve(value)
    }
    Modal.confirm({
      title: 'AI重生成预览',
      okText: '确认替换',
      cancelText: '取消',
      alignCenter: true,
      width: 980,
      maskClosable: false,
      content: () =>
        h(
          'div',
          {
            style:
              'white-space: pre-wrap; line-height: 1.75; font-size: 13px; max-height: 68vh; overflow-y: auto;',
          },
          lines.join('\n')
        ),
      onOk: () => finish(true),
      onCancel: () => finish(false),
    })
  })

const runCaseGeneration = async (payload: CaseGenerationPayload) => {
  const res = await apiRequestApi.generateTestCases(payload)
  const summary: ApiTestCaseGenerationResult = res.data.data
  if (summary.preview_only && payload.mode === 'regenerate' && !payload.apply_changes) {
    const confirmed = await confirmRegeneratePreview(summary)
    if (!confirmed) {
      Message.info('已取消替换当前测试用例')
      return null
    }
    return runCaseGeneration({ ...payload, apply_changes: true })
  }
  return summary
}

const generateCases = async (mode: CaseGenerationMode) => {
  if (!props.selectedRequestId) return Message.warning('请先在左侧选择一个接口')
  caseGenerationLoadingMode.value = mode
  try {
    const summary = await runCaseGeneration({ scope: 'selected', ids: [props.selectedRequestId], mode, count_per_request: 3 })
    if (!summary) return
    showCaseGenerationInsight(summary, mode)
    const modeLabel = mode === 'append' ? '追加生成' : mode === 'regenerate' ? '重新生成' : '生成'
    const cacheText = summary.ai_cache_hit_count ? ` 命中缓存 ${summary.ai_cache_hit_count} 个接口。` : ''
    const text = `${modeLabel}完成：处理 ${summary.processed_requests}/${summary.total_requests} 个接口，新增 ${summary.created_testcase_count} 条测试用例。${cacheText}`
    summary.skipped_requests ? Message.warning(`${text} 跳过 ${summary.skipped_requests} 个已有用例的接口。`) : Message.success(text)
    await loadTestCases()
  } catch (error: any) {
    console.error('[TestCaseList] AI 生成测试用例失败:', error)
    Message.error(error?.error || 'AI 生成测试用例失败')
  } finally {
    caseGenerationLoadingMode.value = ''
  }
}

watch(() => projectId.value, () => { selectedTestCaseIds.value = []; loadEnvironments(); loadAvailableRequests(); loadTestCases() }, { immediate: true })
watch(() => [props.selectedCollectionId, props.selectedRequestId], () => { selectedTestCaseIds.value = []; loadTestCases() }, { immediate: true })

defineExpose({ refresh: loadTestCases })
</script>

<style scoped>
.test-case-list { display: flex; flex-direction: column; gap: 20px; }
.page-header, .state-card, .group-card { border: 1px solid rgba(148,163,184,.16); border-radius: 24px; background: rgba(255,255,255,.92); box-shadow: 0 16px 36px rgba(15,23,42,.05); }
.page-header { display: grid; grid-template-columns: minmax(260px,1fr) minmax(520px,1.4fr); gap: 18px; padding: 24px; }
.page-header__copy, .page-header__tools, .tools-group, .group-list, .case-name, .detail-panel { display: flex; }
.page-header__copy, .group-list, .case-name, .detail-panel { flex-direction: column; }
.page-header__copy { gap: 8px; }
.page-header__tools, .tools-group { align-items: center; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
.page-header__eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #0f766e; }
.page-header__title { font-size: 28px; font-weight: 800; color: #0f172a; }
.page-header__meta, .group-card__meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; color: #64748b; }
.tools-search { width: 320px; max-width: 100%; }
.tools-select { width: 220px; }
.state-card { min-height: 220px; display: flex; align-items: center; justify-content: center; padding: 24px; }
.group-list { gap: 16px; }
.group-card { padding: 20px; }
.group-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; }
.group-card__copy { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.group-card__title { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 700; color: #0f172a; }
.case-name { gap: 4px; }
.case-name__title { font-size: 14px; font-weight: 700; color: #0f172a; word-break: break-word; }
.case-name__desc, .section-note { font-size: 12px; line-height: 1.7; color: #64748b; }
.section-note { margin-bottom: 14px; padding: 12px 14px; border-radius: 14px; background: rgba(248,250,252,.9); }
.detail-panel { gap: 16px; }
.json-block { margin: 0; padding: 16px; border-radius: 18px; background: rgba(15,23,42,.95); color: #e2e8f0; font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.group-card :deep(.arco-table-container) { overflow: hidden; border-radius: 18px; border: 1px solid rgba(148,163,184,.12); }
.page-header :deep(.arco-input-wrapper), .page-header :deep(.arco-select-view), .page-header :deep(.arco-btn) { min-height: 42px; border-radius: 14px; }
@media (max-width: 1200px) { .page-header { grid-template-columns: 1fr; } .page-header__tools { justify-content: flex-start; } }
@media (max-width: 768px) { .page-header { padding: 18px; } .page-header__tools, .tools-group, .tools-search, .tools-select { width: 100%; } .group-card__head { flex-direction: column; } }
</style>

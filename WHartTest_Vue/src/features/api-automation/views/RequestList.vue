<template>
  <div class="request-list">
    <div class="page-header api-page-header">
      <div class="header-left">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索接口名称或 URL"
          allow-clear
          style="width: 260px"
          @search="loadRequests"
          @clear="loadRequests"
        />
      </div>
      <div class="header-right">
        <a-select
          v-model="selectedEnvironmentId"
          :loading="environmentLoading"
          allow-clear
          placeholder="执行环境"
          style="width: 220px"
        >
          <a-option v-for="item in environments" :key="item.id" :value="item.id" :label="item.name" />
        </a-select>
        <a-button type="primary" :disabled="!selectedCollectionId" @click="openCreateModal">
          新增接口
        </a-button>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="empty-tip-card">
      <a-empty description="请先在左侧选择一个接口集合" />
    </div>

    <div v-else class="content-section">
      <a-table :data="filteredRequests" :loading="loading" :pagination="false" row-key="id">
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
              <a-tag color="cyan">{{ record.assertions?.length || 0 }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="更新时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="260" align="center" fixed="right">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="executeRequest(record)">执行</a-button>
                <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
                <a-button type="text" size="small" @click="viewRequest(record)">详情</a-button>
                <a-popconfirm content="确定删除该接口吗？" @ok="deleteRequest(record.id)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:visible="editorVisible"
      :title="editingRequest ? '编辑接口' : '新增接口'"
      width="900px"
      :ok-loading="submitLoading"
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
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="name" label="接口名称" :rules="[{ required: true, message: '请输入接口名称' }]">
              <a-input v-model="formState.name" placeholder="例如：获取用户信息" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="method" label="请求方法">
              <a-select v-model="formState.method">
                <a-option v-for="method in methods" :key="method" :value="method" :label="method" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="timeout_ms" label="超时(ms)">
              <a-input-number v-model="formState.timeout_ms" :min="1000" :step="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="url" label="请求地址" :rules="[{ required: true, message: '请输入请求地址' }]">
          <a-input
            v-model="formState.url"
            placeholder="支持完整 URL 或相对路径，例如 /api/users 或 {{base_url}}/users"
          />
        </a-form-item>

        <a-form-item field="description" label="描述">
          <a-textarea v-model="formState.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="headersText" label="请求头(JSON)">
              <a-textarea
                v-model="formState.headersText"
                :auto-size="{ minRows: 6, maxRows: 12 }"
                placeholder='例如：{"Authorization":"Bearer {{token}}"}'
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="paramsText" label="查询参数(JSON)">
              <a-textarea
                v-model="formState.paramsText"
                :auto-size="{ minRows: 6, maxRows: 12 }"
                placeholder='例如：{"page":1,"size":20}'
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="body_type" label="请求体类型">
              <a-select v-model="formState.body_type">
                <a-option value="none" label="none" />
                <a-option value="json" label="json" />
                <a-option value="form" label="form" />
                <a-option value="raw" label="raw" />
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item v-if="formState.body_type !== 'none'" field="bodyText" label="请求体">
          <a-textarea
            v-model="formState.bodyText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            :placeholder="formState.body_type === 'raw' ? '请输入原始文本' : '请输入 JSON 对象'"
          />
        </a-form-item>

        <a-form-item field="assertionsText" label="断言规则(JSON数组)">
          <a-textarea
            v-model="formState.assertionsText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            placeholder='例如：[{"type":"status_code","expected":200},{"type":"body_contains","expected":"success"}]'
          />
        </a-form-item>
      </a-form>

      <div v-else class="document-import-panel">
        <a-alert type="info" class="import-alert">
          <template #title>接口文档导入</template>
          支持 Swagger / OpenAPI / Postman，以及 PDF、图片、PPTX、DOCX、XLSX、HTML、EPUB 等文档格式。
          导入后会自动解析生成前端接口脚本，并可选批量生成测试用例。
        </a-alert>

        <div class="document-import-form">
          <label class="file-picker">
            <span class="file-picker-label">选择接口文档</span>
            <input
              class="file-input"
              type="file"
              accept=".json,.yaml,.yml,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.html,.htm,.epub"
              @change="handleDocumentChange"
            />
          </label>
          <div v-if="documentFile" class="selected-file">当前文件：{{ documentFile.name }}</div>
          <div class="import-options">
            <span class="import-option-label">自动批量生成测试用例</span>
            <a-switch v-model="generateTestCases" />
          </div>
          <div class="import-tip">
            推荐优先上传 OpenAPI / Swagger / Postman 文件。非结构化文档会尝试自动抽取接口定义，效果取决于文档质量与本地解析环境。
          </div>
        </div>
      </div>
    </a-modal>

    <a-drawer v-model:visible="resultVisible" width="760px" title="执行结果" :footer="false">
      <div v-if="currentResult" class="result-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="接口名称">{{ currentResult.request_name }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="currentResult.passed ? 'green' : currentResult.status === 'error' ? 'red' : 'orange'">
              {{ currentResult.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态码">{{ currentResult.status_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="响应时间">{{ formatDuration(currentResult.response_time) }}</a-descriptions-item>
          <a-descriptions-item label="最终地址" :span="2">{{ currentResult.url }}</a-descriptions-item>
          <a-descriptions-item label="错误信息" :span="2">
            {{ currentResult.error_message || '-' }}
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>断言结果</a-divider>
        <a-table :data="currentResult.assertions_results || []" :pagination="false" row-key="index">
          <template #columns>
            <a-table-column title="#" data-index="index" :width="60" />
            <a-table-column title="类型" data-index="type" :width="120" />
            <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
            <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
            <a-table-column title="结果" :width="90">
              <template #cell="{ record }">
                <a-tag :color="record.passed ? 'green' : 'red'">{{ record.passed ? '通过' : '失败' }}</a-tag>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <a-divider>请求快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentResult.request_snapshot) }}</pre>

        <template v-if="currentResult.request_snapshot?.generated_script">
          <a-divider>接口脚本</a-divider>
          <pre class="json-block">{{ stringifyBlock(currentResult.request_snapshot.generated_script) }}</pre>
        </template>

        <a-divider>响应快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentResult.response_snapshot) }}</pre>
      </div>
    </a-drawer>

    <a-drawer v-model:visible="importResultVisible" width="920px" title="文档导入结果" :footer="false">
      <div v-if="importResult" class="import-result-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="导入来源">{{ importResult.source_type || '-' }}</a-descriptions-item>
          <a-descriptions-item label="使用 Marker">
            <a-tag :color="importResult.marker_used ? 'arcoblue' : 'gray'">
              {{ importResult.marker_used ? '是' : '否' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="生成接口">{{ importResult.created_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="生成脚本">{{ importResult.generated_script_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="生成测试用例">{{ importResult.created_testcase_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="解析说明" :span="2">{{ importResult.note || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-tabs type="rounded">
          <a-tab-pane key="scripts" title="接口脚本">
            <a-empty v-if="!importResult.generated_scripts?.length" description="暂无生成脚本" />
            <a-collapse v-else>
              <a-collapse-item
                v-for="item in importResult.generated_scripts"
                :key="item.request_id"
                :header="`${item.request_name}${item.collection_name ? ` · ${item.collection_name}` : ''}`"
              >
                <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
              </a-collapse-item>
            </a-collapse>
          </a-tab-pane>
          <a-tab-pane key="test-cases" title="测试用例">
            <a-empty v-if="!importResult.test_cases?.length" description="本次未生成测试用例" />
            <a-collapse v-else>
              <a-collapse-item
                v-for="item in importResult.test_cases"
                :key="item.id"
                :header="`${item.name}${item.request_name ? ` · ${item.request_name}` : ''}`"
              >
                <a-space wrap class="import-tags">
                  <a-tag v-for="tag in item.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
                </a-space>
                <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
                <a-divider>断言规则</a-divider>
                <pre class="json-block">{{ stringifyBlock(item.assertions) }}</pre>
              </a-collapse-item>
            </a-collapse>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { apiRequestApi, environmentApi } from '../api'
import type {
  ApiEnvironment,
  ApiExecutionRecord,
  ApiImportResult,
  ApiRequest,
  ApiRequestForm,
} from '../types'

const props = defineProps<{
  selectedCollectionId?: number
}>()

const emit = defineEmits<{
  (e: 'executed'): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const loading = ref(false)
const environmentLoading = ref(false)
const submitLoading = ref(false)
const searchKeyword = ref('')
const requests = ref<ApiRequest[]>([])
const environments = ref<ApiEnvironment[]>([])
const selectedEnvironmentId = ref<number | undefined>(undefined)
const editorVisible = ref(false)
const resultVisible = ref(false)
const importResultVisible = ref(false)
const editingRequest = ref<ApiRequest | null>(null)
const currentResult = ref<ApiExecutionRecord | null>(null)
const importResult = ref<ApiImportResult | null>(null)
const documentFile = ref<File | null>(null)
const createMode = ref<'manual' | 'document'>('manual')
const generateTestCases = ref(true)

const formState = ref({
  name: '',
  description: '',
  method: 'GET',
  url: '',
  headersText: '{}',
  paramsText: '{}',
  body_type: 'none' as 'none' | 'json' | 'form' | 'raw',
  bodyText: '{}',
  assertionsText: '[]',
  timeout_ms: 30000,
})

const filteredRequests = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return requests.value
  return requests.value.filter(item => {
    return item.name.toLowerCase().includes(keyword) || item.url.toLowerCase().includes(keyword)
  })
})

const stringifyJson = (value: any, fallback = '{}') => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const parseJsonText = (text: string, fallback: any) => {
  if (!text.trim()) return fallback
  return JSON.parse(text)
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}

const loadEnvironments = async () => {
  if (!projectId.value) {
    environments.value = []
    return
  }
  environmentLoading.value = true
  try {
    const res = await environmentApi.list({ project: projectId.value })
    const data = res.data?.data || res.data || []
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

const loadRequests = async () => {
  if (!projectId.value || !props.selectedCollectionId) {
    requests.value = []
    return
  }
  loading.value = true
  try {
    const res = await apiRequestApi.list({
      project: projectId.value,
      collection: props.selectedCollectionId,
    })
    const data = res.data?.data || res.data || []
    requests.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('[RequestList] 获取接口失败:', error)
    Message.error('获取接口列表失败')
    requests.value = []
  } finally {
    loading.value = false
  }
}

const resetEditor = () => {
  editingRequest.value = null
  documentFile.value = null
  createMode.value = 'manual'
  generateTestCases.value = true
  formState.value = {
    name: '',
    description: '',
    method: 'GET',
    url: '',
    headersText: '{}',
    paramsText: '{}',
    body_type: 'none',
    bodyText: '{}',
    assertionsText: '[]',
    timeout_ms: 30000,
  }
}

const openCreateModal = () => {
  resetEditor()
  editorVisible.value = true
}

const openEditModal = (record: ApiRequest) => {
  editingRequest.value = record
  createMode.value = 'manual'
  formState.value = {
    name: record.name,
    description: record.description || '',
    method: record.method,
    url: record.url,
    headersText: stringifyJson(record.headers),
    paramsText: stringifyJson(record.params),
    body_type: record.body_type,
    bodyText: record.body_type === 'raw' ? stringifyJson(record.body, '') : stringifyJson(record.body, '{}'),
    assertionsText: stringifyJson(record.assertions, '[]'),
    timeout_ms: record.timeout_ms,
  }
  editorVisible.value = true
}

const handleDocumentChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  documentFile.value = input.files?.[0] || null
}

const viewRequest = (record: ApiRequest) => {
  currentResult.value = {
    id: 0,
    project: record.project_id || projectId.value || 0,
    request: record.id,
    environment: null,
    request_name: record.name,
    method: record.method,
    url: record.url,
    status: 'success',
    passed: false,
    status_code: null,
    response_time: null,
    request_snapshot: {
      headers: record.headers,
      params: record.params,
      body_type: record.body_type,
      body: record.body,
      assertions: record.assertions,
      generated_script: record.generated_script,
    },
    response_snapshot: {},
    assertions_results: [],
    created_at: record.updated_at,
    executor: null,
  }
  resultVisible.value = true
}

const submitManualRequest = async () => {
  const payload: ApiRequestForm = {
    collection: props.selectedCollectionId!,
    name: formState.value.name.trim(),
    description: formState.value.description.trim(),
    method: formState.value.method,
    url: formState.value.url.trim(),
    headers: parseJsonText(formState.value.headersText, {}),
    params: parseJsonText(formState.value.paramsText, {}),
    body_type: formState.value.body_type,
    body:
      formState.value.body_type === 'none'
        ? {}
        : formState.value.body_type === 'raw'
          ? formState.value.bodyText
          : parseJsonText(formState.value.bodyText, {}),
    assertions: parseJsonText(formState.value.assertionsText, []),
    timeout_ms: formState.value.timeout_ms,
  }

  if (editingRequest.value) {
    await apiRequestApi.update(editingRequest.value.id, payload)
    Message.success('接口更新成功')
  } else {
    await apiRequestApi.create(payload)
    Message.success('接口创建成功')
  }
}

const submitDocumentImport = async () => {
  if (!documentFile.value) {
    throw new Error('请先选择接口文档')
  }
  const res = await apiRequestApi.importDocument(props.selectedCollectionId!, documentFile.value, {
    generateTestCases: generateTestCases.value,
  })
  const result = (res.data?.data || res.data) as ApiImportResult
  importResult.value = result
  importResultVisible.value = true
  Message.success(`文档导入成功，已生成 ${result.created_count || 0} 个接口和 ${result.created_testcase_count || 0} 个测试用例`)
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
    } else {
      await submitDocumentImport()
    }
    done(true)
    editorVisible.value = false
    resetEditor()
    emit('updated')
    loadRequests()
  } catch (error: any) {
    console.error('[RequestList] 保存接口失败:', error)
    Message.error(error?.error || error?.message || '处理接口失败')
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
    loadRequests()
  } catch (error: any) {
    Message.error(error?.error || '删除接口失败')
  }
}

const executeRequest = async (record: ApiRequest) => {
  try {
    const res = await apiRequestApi.execute(record.id, selectedEnvironmentId.value)
    currentResult.value = (res.data?.data || res.data) as ApiExecutionRecord
    resultVisible.value = true
    Message.success(currentResult.value.passed ? '接口执行通过' : '接口执行完成')
    emit('executed')
  } catch (error: any) {
    console.error('[RequestList] 执行接口失败:', error)
    Message.error(error?.error || '执行接口失败')
  }
}

watch(
  () => projectId.value,
  () => {
    loadEnvironments()
    loadRequests()
  },
  { immediate: true }
)

watch(
  () => props.selectedCollectionId,
  () => {
    loadRequests()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadRequests,
})
</script>

<style scoped>
.request-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.api-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.create-mode-switch {
  margin-bottom: 16px;
}

.document-import-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-alert {
  margin-bottom: 4px;
}

.document-import-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-picker-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
}

.file-input {
  border: 1px dashed var(--color-border-2);
  border-radius: 12px;
  padding: 14px;
  background: var(--color-fill-1);
}

.selected-file,
.import-tip {
  font-size: 13px;
  color: var(--color-text-2);
}

.import-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.04);
}

.import-option-label {
  font-size: 13px;
  color: var(--color-text-1);
  font-weight: 600;
}

.empty-tip-card {
  padding: 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.result-drawer,
.import-result-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
</style>

<template>
  <div class="test-case-list">
    <div class="page-header api-page-header">
      <div class="page-summary">
        <div class="page-summary__eyebrow">项目 / 接口 / 用例</div>
        <div class="page-summary__title">测试用例</div>
        <div class="page-summary__meta">
          <span>{{ projectName }}</span>
          <span>{{ selectedCollectionName || '未选择接口目录' }}</span>
          <span>{{ selectedRequestName || '全部接口' }}</span>
          <span>{{ groupedTestCases.length }} 个接口</span>
          <span>{{ filteredTestCases.length }} 条用例</span>
        </div>
      </div>
      <div class="page-toolbar">
        <a-input-search
          v-model="searchKeyword"
          class="toolbar-search"
          placeholder="搜索测试用例、接口名称或请求地址"
          allow-clear
          @search="loadTestCases"
          @clear="loadTestCases"
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
          <a-button :disabled="!selectedTestCaseIds.length" @click="executeSelectedTestCases">批量执行</a-button>
          <a-button status="danger" :disabled="!selectedTestCaseIds.length" @click="confirmDeleteSelectedTestCases">
            批量删除
          </a-button>
          <a-button :disabled="!canExecuteCurrentScope" @click="executeCurrentScopeTestCases">
            {{ currentScopeExecuteLabel }}
          </a-button>
          <a-button @click="loadTestCases">刷新</a-button>
        </div>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="empty-tip-card">
      <a-empty description="请先在左侧选择接口目录或具体接口，再查看测试用例。" />
    </div>

    <div v-else-if="loading" class="loading-card">
      <a-spin size="large" />
    </div>

    <div v-else-if="!groupedTestCases.length" class="empty-tip-card">
      <a-empty :description="selectedRequestId ? '当前接口下暂无测试用例。' : '当前接口目录下暂无测试用例。'" />
    </div>

    <div v-else class="content-section">
      <section v-for="group in groupedTestCases" :key="group.key" class="group-card">
        <div class="group-card__header">
          <div class="group-card__copy">
            <div class="group-card__eyebrow">接口</div>
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
          <div class="group-card__actions">
            <a-button size="small" @click="toggleGroupSelection(group)">
              {{ isGroupFullySelected(group) ? '取消全选' : '全选该接口用例' }}
            </a-button>
            <a-button size="small" @click="executeGroupTestCases(group)">执行该接口</a-button>
          </div>
        </div>

        <a-table :data="group.cases" :pagination="false" row-key="id" size="small">
          <template #columns>
            <a-table-column title="选择" :width="72" align="center">
              <template #cell="{ record }">
                <a-checkbox
                  :model-value="isCaseSelected(record.id)"
                  @change="value => toggleTestCaseSelection(record.id, value)"
                />
              </template>
            </a-table-column>
            <a-table-column title="测试用例" :width="320">
              <template #cell="{ record }">
                <div class="case-name-cell">
                  <div class="case-name-cell__title">{{ record.name }}</div>
                  <div class="case-name-cell__desc">{{ record.description || '暂无描述' }}</div>
                </div>
              </template>
            </a-table-column>
            <a-table-column title="状态" :width="120" align="center">
              <template #cell="{ record }">
                <a-tag :color="statusColorMap[record.status]">{{ statusLabelMap[record.status] }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="标签" :width="140" align="center">
              <template #cell="{ record }">
                <a-tag color="cyan">{{ record.tags?.length || 0 }}</a-tag>
              </template>
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
      width="960px"
      :ok-loading="editorSubmitting"
      :mask-closable="!editorSubmitting"
      :closable="!editorSubmitting"
      @before-ok="submitTestCase"
      @cancel="resetEditor"
    >
      <a-form :model="formState" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="name" label="测试用例名称" :rules="[{ required: true, message: '请输入测试用例名称' }]">
              <a-input v-model="formState.name" placeholder="请输入测试用例名称" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="status" label="状态">
              <a-select v-model="formState.status">
                <a-option value="draft" label="草稿" />
                <a-option value="ready" label="就绪" />
                <a-option value="disabled" label="停用" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="tagsText" label="标签">
              <a-input v-model="formState.tagsText" placeholder="多个标签用逗号分隔" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="description" label="描述">
          <a-textarea v-model="formState.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>

        <a-form-item field="scriptText" label="接口脚本(JSON)">
          <a-textarea
            v-model="formState.scriptText"
            :auto-size="{ minRows: 8, maxRows: 18 }"
            placeholder='例如：{"request_overrides":{"body_type":"json","body":{"username":"admin"}}}'
          />
        </a-form-item>

        <a-form-item field="assertionsText" label="断言规则(JSON数组)">
          <a-textarea
            v-model="formState.assertionsText"
            :auto-size="{ minRows: 8, maxRows: 18 }"
            placeholder='例如：[{"type":"status_code","expected":200}]'
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="detailVisible"
      class="detail-modal detail-modal--wide"
      title="测试用例详情"
      width="1120px"
      :footer="false"
      :mask-closable="true"
      :body-style="{ maxHeight: '78vh', overflowY: 'auto' }"
    >
      <div v-if="currentTestCase" class="detail-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="测试用例">{{ currentTestCase.name }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColorMap[currentTestCase.status]">
              {{ statusLabelMap[currentTestCase.status] }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="接口名称">{{ currentTestCase.request_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="请求方法">
            <a-tag :color="methodColorMap[currentTestCase.request_method || ''] || 'arcoblue'">
              {{ currentTestCase.request_method || '-' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="请求地址" :span="2">{{ currentTestCase.request_url || '-' }}</a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">{{ currentTestCase.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="标签" :span="2">
            <a-space wrap>
              <a-tag v-for="tag in currentTestCase.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
              <span v-if="!currentTestCase.tags?.length">-</span>
            </a-space>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>接口脚本</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.script) }}</pre>

        <a-divider>断言规则</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentTestCase.assertions) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { environmentApi, testCaseApi } from '../api'
import type { ApiEnvironment, ApiExecutionBatchResult, ApiTestCase, ApiTestCaseForm } from '../types'

interface TestCaseGroup {
  key: string
  requestId: number | null
  requestName: string
  requestMethod: string
  requestUrl: string
  totalCount: number
  readyCount: number
  updatedAt?: string
  cases: ApiTestCase[]
}

interface TestCaseEditorForm {
  name: string
  description: string
  status: ApiTestCase['status']
  tagsText: string
  scriptText: string
  assertionsText: string
}

const props = defineProps<{
  selectedCollectionId?: number
  selectedCollectionName?: string
  selectedRequestId?: number
  selectedRequestName?: string
}>()

const emit = defineEmits<{
  (e: 'executed'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const projectName = computed(() => projectStore.currentProject?.name || '未选择项目')

const loading = ref(false)
const environmentLoading = ref(false)
const detailVisible = ref(false)
const editorVisible = ref(false)
const editorSubmitting = ref(false)
const searchKeyword = ref('')
const testCases = ref<ApiTestCase[]>([])
const currentTestCase = ref<ApiTestCase | null>(null)
const editingTestCase = ref<ApiTestCase | null>(null)
const environments = ref<ApiEnvironment[]>([])
const selectedEnvironmentId = ref<number | undefined>(undefined)
const selectedTestCaseIds = ref<number[]>([])
const formState = ref<TestCaseEditorForm>({
  name: '',
  description: '',
  status: 'draft',
  tagsText: '',
  scriptText: '{}',
  assertionsText: '[]',
})

const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const statusColorMap: Record<ApiTestCase['status'], string> = {
  draft: 'gray',
  ready: 'green',
  disabled: 'red',
}

const statusLabelMap: Record<ApiTestCase['status'], string> = {
  draft: '草稿',
  ready: '就绪',
  disabled: '停用',
}

const currentScopeExecuteLabel = computed(() => {
  if (props.selectedRequestId) return '执行当前接口'
  if (props.selectedCollectionId) return '执行当前目录'
  return '执行当前项目'
})

const canExecuteCurrentScope = computed(() => {
  if (props.selectedRequestId) return testCases.value.length > 0
  if (props.selectedCollectionId) return true
  return Boolean(projectId.value)
})

const filteredTestCases = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return testCases.value
  return testCases.value.filter(item => {
    return (
      item.name.toLowerCase().includes(keyword) ||
      (item.description || '').toLowerCase().includes(keyword) ||
      (item.request_name || '').toLowerCase().includes(keyword) ||
      (item.request_url || '').toLowerCase().includes(keyword)
    )
  })
})

const groupedTestCases = computed<TestCaseGroup[]>(() => {
  const groups = new Map<string, TestCaseGroup>()
  const items = [...filteredTestCases.value].sort((left, right) => {
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  })

  items.forEach(item => {
    const key = `${item.request ?? 'unknown'}-${item.collection_id ?? 'unknown'}`
    const existing = groups.get(key)
    if (existing) {
      existing.cases.push(item)
      existing.totalCount += 1
      if (item.status === 'ready') existing.readyCount += 1
      if (!existing.updatedAt || new Date(item.updated_at).getTime() > new Date(existing.updatedAt).getTime()) {
        existing.updatedAt = item.updated_at
      }
      return
    }

    groups.set(key, {
      key,
      requestId: item.request ?? null,
      requestName: item.request_name || '未命名接口',
      requestMethod: item.request_method || 'GET',
      requestUrl: item.request_url || '',
      totalCount: 1,
      readyCount: item.status === 'ready' ? 1 : 0,
      updatedAt: item.updated_at,
      cases: [item],
    })
  })

  return Array.from(groups.values()).sort((left, right) => {
    return new Date(right.updatedAt || 0).getTime() - new Date(left.updatedAt || 0).getTime()
  })
})

const selectedIdSet = computed(() => new Set(selectedTestCaseIds.value))

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const stringifyJson = (value: any, fallback = '{}') => {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const parseJsonText = <T>(text: string, fallback: T): T => {
  if (!text.trim()) return fallback
  return JSON.parse(text) as T
}

const parseTagsText = (text: string) =>
  text
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean)

const isCaseSelected = (id: number) => selectedIdSet.value.has(id)

const toggleTestCaseSelection = (id: number, checked: boolean | string | number) => {
  const enabled = Boolean(checked)
  if (enabled && !selectedIdSet.value.has(id)) {
    selectedTestCaseIds.value = [...selectedTestCaseIds.value, id]
    return
  }
  if (!enabled && selectedIdSet.value.has(id)) {
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(item => item !== id)
  }
}

const isGroupFullySelected = (group: TestCaseGroup) => {
  return group.cases.length > 0 && group.cases.every(item => selectedIdSet.value.has(item.id))
}

const toggleGroupSelection = (group: TestCaseGroup) => {
  if (isGroupFullySelected(group)) {
    const groupIds = new Set(group.cases.map(item => item.id))
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id => !groupIds.has(id))
    return
  }

  const merged = new Set(selectedTestCaseIds.value)
  group.cases.forEach(item => merged.add(item.id))
  selectedTestCaseIds.value = Array.from(merged)
}

const resetEditor = () => {
  editorVisible.value = false
  editingTestCase.value = null
  formState.value = {
    name: '',
    description: '',
    status: 'draft',
    tagsText: '',
    scriptText: '{}',
    assertionsText: '[]',
  }
}

const loadEnvironments = async () => {
  if (!projectId.value) {
    environments.value = []
    selectedEnvironmentId.value = undefined
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
    console.error('[TestCaseList] 获取环境失败:', error)
    environments.value = []
  } finally {
    environmentLoading.value = false
  }
}

const loadTestCases = async () => {
  if (!projectId.value || !props.selectedCollectionId) {
    testCases.value = []
    selectedTestCaseIds.value = []
    currentTestCase.value = null
    return
  }

  loading.value = true
  try {
    const res = await testCaseApi.list({
      project: projectId.value,
      collection: props.selectedCollectionId,
      request: props.selectedRequestId,
    })
    const data = res.data?.data || []
    testCases.value = Array.isArray(data) ? data : []

    const availableIds = new Set(testCases.value.map(item => item.id))
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id => availableIds.has(id))

    if (currentTestCase.value) {
      currentTestCase.value = testCases.value.find(item => item.id === currentTestCase.value?.id) || null
      if (!currentTestCase.value) {
        detailVisible.value = false
      }
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

const viewTestCase = (record: ApiTestCase) => {
  currentTestCase.value = record
  detailVisible.value = true
}

const openEditModal = (record: ApiTestCase) => {
  editingTestCase.value = record
  formState.value = {
    name: record.name,
    description: record.description || '',
    status: record.status,
    tagsText: (record.tags || []).join(', '),
    scriptText: stringifyJson(record.script),
    assertionsText: stringifyJson(record.assertions, '[]'),
  }
  editorVisible.value = true
}

const submitTestCase = async (done: (closed: boolean) => void) => {
  if (!editingTestCase.value) {
    done(false)
    return
  }

  if (!formState.value.name.trim()) {
    Message.warning('请输入测试用例名称')
    done(false)
    return
  }

  editorSubmitting.value = true
  try {
    const payload: Partial<ApiTestCaseForm> = {
      project: editingTestCase.value.project,
      request: editingTestCase.value.request,
      name: formState.value.name.trim(),
      description: formState.value.description.trim() || '',
      status: formState.value.status,
      tags: parseTagsText(formState.value.tagsText),
      script: parseJsonText(formState.value.scriptText, {}),
      assertions: parseJsonText(formState.value.assertionsText, []),
    }

    const res = await testCaseApi.update(editingTestCase.value.id, payload)
    const updatedRecord = res.data?.data || null
    Message.success('测试用例更新成功')

    if (updatedRecord && currentTestCase.value?.id === updatedRecord.id) {
      currentTestCase.value = updatedRecord
    }

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
    try {
      await testCaseApi.delete(id)
      successCount += 1
    } catch (error: any) {
      failureCount += 1
      lastError = error?.error || '删除测试用例失败'
    }
  }

  if (successCount && !failureCount) {
    Message.success(successCount === 1 ? '测试用例删除成功' : `已删除 ${successCount} 条测试用例`)
  } else if (successCount && failureCount) {
    Message.warning(`已删除 ${successCount} 条，失败 ${failureCount} 条${lastError ? `：${lastError}` : ''}`)
  } else {
    Message.error(lastError || '删除测试用例失败')
  }

  const removedIds = new Set(ids)
  selectedTestCaseIds.value = selectedTestCaseIds.value.filter(item => !removedIds.has(item))

  if (currentTestCase.value && removedIds.has(currentTestCase.value.id)) {
    currentTestCase.value = null
    detailVisible.value = false
  }

  await loadTestCases()
}

const confirmDeleteSelectedTestCases = () => {
  if (!selectedTestCaseIds.value.length) {
    Message.warning('请先选择要删除的测试用例')
    return
  }

  Modal.warning({
    title: '确认批量删除',
    content: `确定要删除选中的 ${selectedTestCaseIds.value.length} 条测试用例吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      await deleteTestCases([...selectedTestCaseIds.value])
    },
  })
}

const showBatchExecutionMessage = (label: string, summary: ApiExecutionBatchResult) => {
  const text = `${label}完成：共 ${summary.total_count} 条，成功 ${summary.success_count} 条，断言失败 ${summary.failed_count} 条，异常 ${summary.error_count} 条。`
  if (summary.failed_count || summary.error_count) {
    Message.warning(text)
    return
  }
  Message.success(text)
}

const executeTestCase = async (record: ApiTestCase) => {
  try {
    const res = await testCaseApi.execute(record.id, selectedEnvironmentId.value)
    const execution = res.data.data
    Message.success(execution.passed ? '测试用例执行通过' : '测试用例执行完成')
    emit('executed')
  } catch (error: any) {
    console.error('[TestCaseList] 执行测试用例失败:', error)
    Message.error(error?.error || '执行测试用例失败')
  }
}

const executeTestCaseBatch = async (
  payload: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    environment_id?: number
  },
  label: string
) => {
  try {
    const res = await testCaseApi.executeBatch(payload)
    const summary = res.data.data
    showBatchExecutionMessage(label, summary)
    emit('executed')
  } catch (error: any) {
    console.error('[TestCaseList] 批量执行测试用例失败:', error)
    Message.error(error?.error || '批量执行测试用例失败')
  }
}

const executeSelectedTestCases = async () => {
  if (!selectedTestCaseIds.value.length) {
    Message.warning('请先选择要执行的测试用例')
    return
  }

  await executeTestCaseBatch(
    {
      scope: 'selected',
      ids: selectedTestCaseIds.value,
      environment_id: selectedEnvironmentId.value,
    },
    '选中测试用例执行'
  )
}

const executeGroupTestCases = async (group: TestCaseGroup) => {
  await executeTestCaseBatch(
    {
      scope: 'selected',
      ids: group.cases.map(item => item.id),
      environment_id: selectedEnvironmentId.value,
    },
    `${group.requestName} 接口用例执行`
  )
}

const executeCurrentScopeTestCases = async () => {
  if (props.selectedRequestId) {
    if (!testCases.value.length) {
      Message.warning('当前接口下没有可执行的测试用例')
      return
    }

    await executeTestCaseBatch(
      {
        scope: 'selected',
        ids: testCases.value.map(item => item.id),
        environment_id: selectedEnvironmentId.value,
      },
      `${props.selectedRequestName || '当前接口'}用例执行`
    )
    return
  }

  if (props.selectedCollectionId) {
    await executeTestCaseBatch(
      {
        scope: 'collection',
        collection_id: props.selectedCollectionId,
        environment_id: selectedEnvironmentId.value,
      },
      '当前目录测试用例执行'
    )
    return
  }

  if (!projectId.value) {
    Message.warning('请先选择项目')
    return
  }

  await executeTestCaseBatch(
    {
      scope: 'project',
      project_id: projectId.value,
      environment_id: selectedEnvironmentId.value,
    },
    '项目测试用例执行'
  )
}

watch(
  () => projectId.value,
  () => {
    selectedTestCaseIds.value = []
    loadEnvironments()
    loadTestCases()
  },
  { immediate: true }
)

watch(
  () => [props.selectedCollectionId, props.selectedRequestId],
  () => {
    selectedTestCaseIds.value = []
    loadTestCases()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadTestCases,
})
</script>

<style scoped>
.test-case-list {
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
  color: #0f766e;
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

.loading-card,
.empty-tip-card {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  padding: 32px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.group-card {
  padding: 20px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.group-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.group-card__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.group-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.group-card__title span {
  min-width: 0;
  word-break: break-word;
}

.group-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.group-card__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.group-card :deep(.arco-table-container) {
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-name-cell__title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.case-name-cell__desc {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-word;
}

.detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

  .group-card {
    padding: 18px;
  }

  .group-card__header {
    flex-direction: column;
  }
}
</style>

<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再管理 APP 测试套件" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>测试套件</h3>
          <p>组合多个 APP 用例形成可批量执行的套件，支持历史回看和设备运行。</p>
        </div>
        <a-space>
          <a-input-search v-model="search" placeholder="搜索套件" allow-clear @search="loadData" />
          <a-button @click="loadData">刷新</a-button>
          <a-button type="primary" @click="openCreate">新建套件</a-button>
        </a-space>
      </div>

      <a-card class="table-card">
        <a-table :data="suites" :loading="loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="套件名称" data-index="name" />
            <a-table-column title="用例数">
              <template #cell="{ record }">{{ record.test_case_count }}</template>
            </a-table-column>
            <a-table-column title="执行状态">
              <template #cell="{ record }">
                <a-tag :color="suiteStatusColor(record)">{{ suiteStatusText(record) }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="最近执行">
              <template #cell="{ record }">{{ formatDateTime(record.last_run_at) }}</template>
            </a-table-column>
            <a-table-column title="操作" :width="260">
              <template #cell="{ record }">
                <a-space>
                  <a-button type="text" @click="openRun(record)">执行</a-button>
                  <a-button type="text" @click="openEdit(record)">编辑</a-button>
                  <a-button type="text" @click="openHistory(record)">历史</a-button>
                  <a-button type="text" status="danger" @click="remove(record.id)">删除</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>

      <a-modal v-model:visible="visible" :title="form.id ? '编辑测试套件' : '新建测试套件'" width="840px" @ok="saveSuite">
        <a-form :model="form" layout="vertical">
          <a-form-item field="name" label="套件名称">
            <a-input v-model="form.name" />
          </a-form-item>
          <a-form-item field="description" label="描述">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
          </a-form-item>
          <a-form-item field="test_case_ids" label="选择用例">
            <a-select v-model="form.test_case_ids" multiple allow-clear placeholder="选择要纳入套件的测试用例">
              <a-option v-for="item in testCases" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <div v-if="selectedCases.length" class="selected-preview">
            <div class="preview-title">当前顺序</div>
            <div class="preview-list">
              <div v-for="(item, index) in selectedCases" :key="item.id" class="preview-item">
                <span>{{ index + 1 }}. {{ item.name }}</span>
                <a-space>
                  <a-button size="mini" type="text" :disabled="index === 0" @click="moveCase(index, -1)">上移</a-button>
                  <a-button size="mini" type="text" :disabled="index === selectedCases.length - 1" @click="moveCase(index, 1)">下移</a-button>
                </a-space>
              </div>
            </div>
          </div>
        </a-form>
      </a-modal>

      <a-modal v-model:visible="runVisible" title="执行测试套件" @ok="runSuite">
        <a-form :model="runForm" layout="vertical">
          <a-form-item field="device_id" label="执行设备">
            <a-select v-model="runForm.device_id" placeholder="请选择可用设备">
              <a-option v-for="item in availableDevices" :key="item.id" :value="item.id">
                {{ item.name || item.device_id }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>

      <a-modal v-model:visible="historyVisible" title="套件执行历史" width="920px" :footer="false">
        <a-table :data="history" :loading="historyLoading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="用例" data-index="case_name" />
            <a-table-column title="设备" data-index="device_name" />
            <a-table-column title="状态">
              <template #cell="{ record }">
                <a-tag :color="executionStatusColor(record.status, record.result)">{{ record.result || record.status }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="步骤通过率">
              <template #cell="{ record }">{{ record.pass_rate }}%</template>
            </a-table-column>
            <a-table-column title="执行时间">
              <template #cell="{ record }">{{ formatDateTime(record.started_at) }}</template>
            </a-table-column>
          </template>
        </a-table>
      </a-modal>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppDevice, AppExecution, AppTestCase, AppTestSuite } from '../types'

const authStore = useAuthStore()
const projectStore = useProjectStore()
const loading = ref(false)
const visible = ref(false)
const runVisible = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const search = ref('')
const suites = ref<AppTestSuite[]>([])
const testCases = ref<AppTestCase[]>([])
const devices = ref<AppDevice[]>([])
const history = ref<AppExecution[]>([])
const currentSuiteId = ref<number | null>(null)

const form = reactive({
  id: 0,
  name: '',
  description: '',
  test_case_ids: [] as number[],
})

const runForm = reactive({
  device_id: undefined as number | undefined,
})

const availableDevices = computed(() => devices.value.filter(item => item.status === 'available' || item.status === 'online'))
const selectedCases = computed(() => form.test_case_ids.map(id => testCases.value.find(item => item.id === id)).filter(Boolean) as AppTestCase[])

const resetForm = () => {
  form.id = 0
  form.name = ''
  form.description = ''
  form.test_case_ids = []
}

const loadData = async () => {
  if (!projectStore.currentProjectId) {
    suites.value = []
    return
  }
  loading.value = true
  try {
    const [suiteList, caseList, deviceList] = await Promise.all([
      AppAutomationService.getTestSuites(projectStore.currentProjectId, search.value),
      AppAutomationService.getTestCases(projectStore.currentProjectId),
      AppAutomationService.getDevices(),
    ])
    suites.value = suiteList
    testCases.value = caseList
    devices.value = deviceList
  } catch (error: any) {
    Message.error(error.message || '加载测试套件失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  visible.value = true
}

const openEdit = (record: AppTestSuite) => {
  form.id = record.id
  form.name = record.name
  form.description = record.description
  form.test_case_ids = record.suite_cases.map(item => item.test_case_id)
  visible.value = true
}

const saveSuite = async () => {
  if (!projectStore.currentProjectId) {
    return
  }
  if (!form.name.trim()) {
    Message.warning('请输入套件名称')
    return
  }
  const payload = {
    project_id: projectStore.currentProjectId,
    name: form.name.trim(),
    description: form.description.trim(),
    test_case_ids: form.test_case_ids,
  }
  try {
    if (form.id) {
      await AppAutomationService.updateTestSuite(form.id, payload)
      Message.success('测试套件已更新')
    } else {
      await AppAutomationService.createTestSuite(payload)
      Message.success('测试套件已创建')
    }
    visible.value = false
    resetForm()
    await loadData()
  } catch (error: any) {
    Message.error(error.message || '保存测试套件失败')
  }
}

const moveCase = (index: number, delta: -1 | 1) => {
  const target = index + delta
  if (target < 0 || target >= form.test_case_ids.length) {
    return
  }
  const next = [...form.test_case_ids]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  form.test_case_ids = next
}

const openRun = (record: AppTestSuite) => {
  currentSuiteId.value = record.id
  runForm.device_id = availableDevices.value[0]?.id
  runVisible.value = true
}

const runSuite = async () => {
  if (!currentSuiteId.value || !runForm.device_id) {
    Message.warning('请选择执行设备')
    return
  }
  try {
    await AppAutomationService.runTestSuite(currentSuiteId.value, {
      device_id: runForm.device_id,
      triggered_by: authStore.currentUser?.username || 'FlyTest',
    })
    runVisible.value = false
    Message.success('测试套件已提交执行')
    await loadData()
  } catch (error: any) {
    Message.error(error.message || '执行测试套件失败')
  }
}

const openHistory = async (record: AppTestSuite) => {
  historyVisible.value = true
  historyLoading.value = true
  try {
    history.value = await AppAutomationService.getTestSuiteExecutions(record.id)
  } catch (error: any) {
    Message.error(error.message || '加载执行历史失败')
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

const remove = (id: number) => {
  Modal.confirm({
    title: '删除测试套件',
    content: '确认删除该测试套件吗？',
    onOk: async () => {
      await AppAutomationService.deleteTestSuite(id)
      Message.success('测试套件已删除')
      await loadData()
    },
  })
}

const suiteStatusText = (record: AppTestSuite) => {
  if (record.execution_status === 'running') return '执行中'
  if (record.execution_status === 'completed' && record.execution_result === 'passed') return '通过'
  if (record.execution_status === 'completed' && record.execution_result === 'failed') return '失败'
  return '未执行'
}

const suiteStatusColor = (record: AppTestSuite) => {
  if (record.execution_status === 'running') return 'arcoblue'
  if (record.execution_status === 'completed' && record.execution_result === 'passed') return 'green'
  if (record.execution_status === 'completed' && record.execution_result === 'failed') return 'red'
  return 'gray'
}

const executionStatusColor = (status: string, result: string) => {
  if (status === 'running') return 'arcoblue'
  if (result === 'passed') return 'green'
  if (result === 'failed') return 'red'
  if (status === 'stopped') return 'orange'
  return 'gray'
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

watch(
  () => projectStore.currentProjectId,
  () => {
    void loadData()
  },
  { immediate: true },
)
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.selected-preview {
  margin-top: 8px;
  border-radius: 14px;
  border: 1px dashed var(--theme-card-border);
  padding: 14px;
}

.preview-title {
  margin-bottom: 10px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(var(--theme-accent-rgb), 0.06);
}
</style>

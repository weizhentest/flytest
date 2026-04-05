<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后管理 APP 测试用例" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>测试用例</h3>
          <p>维护 APP 自动化场景、变量配置与执行入口。</p>
        </div>
        <a-space>
          <a-input-search v-model="search" placeholder="搜索测试用例" allow-clear @search="loadData" />
          <a-button type="primary" @click="openCreate">新增测试用例</a-button>
        </a-space>
      </div>

      <a-card class="table-card">
        <a-table :data="testCases" :loading="loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="名称" data-index="name" />
            <a-table-column title="应用包">
              <template #cell="{ record }">{{ record.package_display_name || '-' }}</template>
            </a-table-column>
            <a-table-column title="最近结果">
              <template #cell="{ record }">
                <a-tag :color="record.last_result === 'passed' ? 'green' : record.last_result === 'failed' ? 'red' : 'gray'">
                  {{ record.last_result || '未执行' }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="超时" data-index="timeout" />
            <a-table-column title="操作" :width="220">
              <template #cell="{ record }">
                <a-space>
                  <a-button type="text" @click="openExecute(record)">执行</a-button>
                  <a-button type="text" @click="openEdit(record)">编辑</a-button>
                  <a-button type="text" status="danger" @click="remove(record.id)">删除</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>

      <a-modal v-model:visible="visible" :title="form.id ? '编辑测试用例' : '新增测试用例'" width="860px" @ok="submit">
        <a-form :model="form" layout="vertical">
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="name" label="用例名称">
                <a-input v-model="form.name" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item field="package_id" label="应用包">
                <a-select v-model="form.package_id" allow-clear>
                  <a-option v-for="pkg in packages" :key="pkg.id" :value="pkg.id">{{ pkg.name }}</a-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="timeout" label="超时时间">
                <a-input-number v-model="form.timeout" :min="1" :max="7200" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item field="retry_count" label="失败重试">
                <a-input-number v-model="form.retry_count" :min="0" :max="10" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item field="description" label="描述">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" />
          </a-form-item>
          <a-form-item field="variablesText" label="变量 JSON">
            <a-textarea v-model="form.variablesText" :auto-size="{ minRows: 4, maxRows: 8 }" />
          </a-form-item>
          <a-form-item field="uiFlowText" label="UI Flow JSON">
            <a-textarea v-model="form.uiFlowText" :auto-size="{ minRows: 8, maxRows: 14 }" />
          </a-form-item>
        </a-form>
      </a-modal>

      <a-modal v-model:visible="executeVisible" title="执行测试用例" @ok="executeCase">
        <a-form :model="executeForm" layout="vertical">
          <a-form-item field="device_id" label="执行设备">
            <a-select v-model="executeForm.device_id" placeholder="请选择设备">
              <a-option v-for="device in availableDevices" :key="device.id" :value="device.id">
                {{ device.name || device.device_id }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-form>
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
import type { AppDevice, AppPackage, AppTestCase } from '../types'

const authStore = useAuthStore()
const projectStore = useProjectStore()
const loading = ref(false)
const visible = ref(false)
const executeVisible = ref(false)
const search = ref('')
const testCases = ref<AppTestCase[]>([])
const packages = ref<AppPackage[]>([])
const devices = ref<AppDevice[]>([])
const currentExecutionCaseId = ref<number | null>(null)

const form = reactive({
  id: 0,
  name: '',
  description: '',
  package_id: undefined as number | undefined,
  timeout: 300,
  retry_count: 0,
  variablesText: '[]',
  uiFlowText: '{\n  "steps": []\n}',
})

const executeForm = reactive({
  device_id: undefined as number | undefined,
})

const availableDevices = computed(() => devices.value.filter(device => device.status === 'available' || device.status === 'online'))

const resetForm = () => {
  form.id = 0
  form.name = ''
  form.description = ''
  form.package_id = undefined
  form.timeout = 300
  form.retry_count = 0
  form.variablesText = '[]'
  form.uiFlowText = '{\n  "steps": []\n}'
}

const loadData = async () => {
  if (!projectStore.currentProjectId) {
    testCases.value = []
    packages.value = []
    return
  }
  loading.value = true
  try {
    const [caseList, packageList, deviceList] = await Promise.all([
      AppAutomationService.getTestCases(projectStore.currentProjectId, search.value),
      AppAutomationService.getPackages(projectStore.currentProjectId),
      AppAutomationService.getDevices(),
    ])
    testCases.value = caseList
    packages.value = packageList
    devices.value = deviceList
  } catch (error: any) {
    Message.error(error.message || '加载测试用例失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  visible.value = true
}

const openEdit = (record: AppTestCase) => {
  form.id = record.id
  form.name = record.name
  form.description = record.description
  form.package_id = record.package_id || undefined
  form.timeout = record.timeout
  form.retry_count = record.retry_count
  form.variablesText = JSON.stringify(record.variables, null, 2)
  form.uiFlowText = JSON.stringify(record.ui_flow, null, 2)
  visible.value = true
}

const submit = async () => {
  try {
    const payload = {
      project_id: projectStore.currentProjectId || 0,
      name: form.name,
      description: form.description,
      package_id: form.package_id ?? null,
      ui_flow: JSON.parse(form.uiFlowText || '{}'),
      variables: JSON.parse(form.variablesText || '[]'),
      tags: [],
      timeout: form.timeout,
      retry_count: form.retry_count,
    }
    if (form.id) {
      await AppAutomationService.updateTestCase(form.id, payload)
      Message.success('测试用例已更新')
    } else {
      await AppAutomationService.createTestCase(payload)
      Message.success('测试用例已创建')
    }
    visible.value = false
    await loadData()
  } catch (error: any) {
    Message.error(error.message || '保存测试用例失败，请检查 JSON')
  }
}

const openExecute = (record: AppTestCase) => {
  currentExecutionCaseId.value = record.id
  executeForm.device_id = availableDevices.value[0]?.id
  executeVisible.value = true
}

const executeCase = async () => {
  if (!currentExecutionCaseId.value || !executeForm.device_id) {
    Message.warning('请选择执行设备')
    return
  }
  try {
    await AppAutomationService.executeTestCase(currentExecutionCaseId.value, {
      device_id: executeForm.device_id,
      trigger_mode: 'manual',
      triggered_by: authStore.currentUser?.username || 'FlyTest',
    })
    executeVisible.value = false
    Message.success('执行任务已启动')
    await loadData()
  } catch (error: any) {
    Message.error(error.message || '启动执行失败')
  }
}

const remove = (id: number) => {
  Modal.confirm({
    title: '删除测试用例',
    content: '确认删除该测试用例吗？',
    onOk: async () => {
      await AppAutomationService.deleteTestCase(id)
      Message.success('测试用例已删除')
      await loadData()
    },
  })
}

watch(
  () => projectStore.currentProjectId,
  () => {
    resetForm()
    void loadData()
  },
  { immediate: true }
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
</style>

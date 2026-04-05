<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后管理 APP 应用包" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>应用包</h3>
          <p>管理当前项目下的包名、启动 Activity 与描述信息。</p>
        </div>
        <a-space>
          <a-input-search v-model="search" placeholder="搜索应用包" allow-clear @search="loadPackages" />
          <a-button type="primary" @click="openCreate">新增应用包</a-button>
        </a-space>
      </div>

      <a-card class="table-card">
        <a-table :data="packages" :loading="loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="应用名称" data-index="name" />
            <a-table-column title="包名" data-index="package_name" />
            <a-table-column title="Activity" data-index="activity_name" />
            <a-table-column title="平台" data-index="platform" />
            <a-table-column title="操作" :width="160">
              <template #cell="{ record }">
                <a-space>
                  <a-button type="text" @click="openEdit(record)">编辑</a-button>
                  <a-button type="text" status="danger" @click="remove(record.id)">删除</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>

      <a-modal v-model:visible="visible" :title="form.id ? '编辑应用包' : '新增应用包'" @ok="submit">
        <a-form :model="form" layout="vertical">
          <a-form-item field="name" label="应用名称">
            <a-input v-model="form.name" />
          </a-form-item>
          <a-form-item field="package_name" label="包名">
            <a-input v-model="form.package_name" />
          </a-form-item>
          <a-form-item field="activity_name" label="启动 Activity">
            <a-input v-model="form.activity_name" />
          </a-form-item>
          <a-form-item field="description" label="描述">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" />
          </a-form-item>
        </a-form>
      </a-modal>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppPackage } from '../types'

const projectStore = useProjectStore()
const loading = ref(false)
const visible = ref(false)
const search = ref('')
const packages = ref<AppPackage[]>([])
const form = reactive({
  id: 0,
  project_id: 0,
  name: '',
  package_name: '',
  activity_name: '',
  platform: 'android',
  description: '',
})

const resetForm = () => {
  form.id = 0
  form.project_id = projectStore.currentProjectId || 0
  form.name = ''
  form.package_name = ''
  form.activity_name = ''
  form.platform = 'android'
  form.description = ''
}

const loadPackages = async () => {
  if (!projectStore.currentProjectId) {
    packages.value = []
    return
  }
  loading.value = true
  try {
    packages.value = await AppAutomationService.getPackages(projectStore.currentProjectId, search.value)
  } catch (error: any) {
    Message.error(error.message || '加载应用包失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  visible.value = true
}

const openEdit = (record: AppPackage) => {
  form.id = record.id
  form.project_id = record.project_id
  form.name = record.name
  form.package_name = record.package_name
  form.activity_name = record.activity_name
  form.platform = record.platform
  form.description = record.description
  visible.value = true
}

const submit = async () => {
  try {
    const payload = {
      project_id: projectStore.currentProjectId || form.project_id,
      name: form.name,
      package_name: form.package_name,
      activity_name: form.activity_name,
      platform: form.platform,
      description: form.description,
    }
    if (form.id) {
      await AppAutomationService.updatePackage(form.id, payload)
      Message.success('应用包已更新')
    } else {
      await AppAutomationService.createPackage(payload)
      Message.success('应用包已创建')
    }
    visible.value = false
    await loadPackages()
  } catch (error: any) {
    Message.error(error.message || '保存应用包失败')
  }
}

const remove = (id: number) => {
  Modal.confirm({
    title: '删除应用包',
    content: '确认删除该应用包吗？',
    onOk: async () => {
      await AppAutomationService.deletePackage(id)
      Message.success('应用包已删除')
      await loadPackages()
    },
  })
}

watch(
  () => projectStore.currentProjectId,
  () => {
    resetForm()
    void loadPackages()
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

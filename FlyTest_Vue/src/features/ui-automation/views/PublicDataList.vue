<template>
  <div class="public-data-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.type"
          placeholder="数据类型"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, value) in PUBLIC_DATA_TYPE_LABELS" :key="value" :value="Number(value)">
            {{ label }}
          </a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索变量名"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增数据
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="publicData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 800 }"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #type="{ record }">
        <a-tag :color="typeColors[record.type as PublicDataType]">
          {{ PUBLIC_DATA_TYPE_LABELS[record.type as PublicDataType] }}
        </a-tag>
      </template>
      <template #value="{ record }">
        <a-tooltip :content="record.value" position="top">
          <div class="ellipsis-text">{{ record.value }}</div>
        </a-tooltip>
      </template>
      <template #is_enabled="{ record }">
        <a-switch :model-value="record.is_enabled" size="small" @change="toggleEnabled(record)" />
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="editData(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除？" @ok="deleteData(record)">
            <a-button type="text" status="danger" size="mini">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑数据' : '新增数据'"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="key" label="变量名" required>
              <a-input v-model="formData.key" placeholder="请输入变量名" :max-length="100" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="type" label="数据类型" required>
              <a-select v-model="formData.type">
                <a-option v-for="(label, value) in PUBLIC_DATA_TYPE_LABELS" :key="value" :value="Number(value)">
                  {{ label }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item field="value" label="变量值" required>
          <a-textarea v-model="formData.value" placeholder="请输入变量值" :auto-size="{ minRows: 2, maxRows: 6 }" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="formData.description" placeholder="可选描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
        <a-form-item field="is_enabled" label="启用状态">
          <a-switch v-model="formData.is_enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { publicDataApi } from '../api'
import type { UiPublicData, UiPublicDataForm, PublicDataType } from '../types'
import { PUBLIC_DATA_TYPE_LABELS, extractPaginationData } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const publicData = ref<UiPublicData[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const currentData = ref<UiPublicData | null>(null)
const formRef = ref()

const filters = reactive({ type: undefined as number | undefined, search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiPublicDataForm>({
  project: 0,
  type: 0,
  key: '',
  value: '',
  description: '',
  is_enabled: true,
})

const rules = {
  key: [{ required: true, message: '请输入变量名' }],
  type: [{ required: true, message: '请选择数据类型' }],
  value: [{ required: true, message: '请输入变量值' }],
}

const typeColors: Record<PublicDataType, string> = { 0: 'blue', 1: 'green', 2: 'orange', 3: 'purple' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '变量名', dataIndex: 'key', width: 150, align: 'center' as const },
  { title: '类型', slotName: 'type', width: 90, align: 'center' as const },
  { title: '变量值', slotName: 'value', width: 200, align: 'center' as const },
  { title: '启用', slotName: 'is_enabled', width: 80, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 180, fixed: 'right' as const, align: 'center' as const },
]

const fetchData = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await publicDataApi.list({
      project: projectId.value,
      type: filters.type,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    publicData.value = items
    pagination.total = count
  } catch {
    Message.error('获取公共数据失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchData()
}

const resetForm = () => {
  Object.assign(formData, { project: projectId.value || 0, type: 0, key: '', value: '', description: '', is_enabled: true })
  formRef.value?.clearValidate()
}

const showAddModal = () => {
  isEdit.value = false
  resetForm()
  modalVisible.value = true
}

const editData = (record: UiPublicData) => {
  isEdit.value = true
  currentData.value = record
  Object.assign(formData, {
    project: record.project,
    type: record.type,
    key: record.key,
    value: record.value,
    description: record.description || '',
    is_enabled: record.is_enabled,
  })
  modalVisible.value = true
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }
  submitting.value = true
  try {
    if (isEdit.value && currentData.value) {
      await publicDataApi.update(currentData.value.id, formData)
      Message.success('更新成功')
    } else {
      await publicDataApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchData()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? '更新失败' : '创建失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteData = async (record: UiPublicData) => {
  try {
    await publicDataApi.delete(record.id)
    Message.success('删除成功')
    fetchData()
  } catch {
    Message.error('删除失败')
  }
}

const toggleEnabled = async (record: UiPublicData) => {
  try {
    await publicDataApi.update(record.id, { is_enabled: !record.is_enabled })
    Message.success('状态已更新')
    fetchData()
  } catch {
    Message.error('更新失败')
  }
}

const refresh = () => fetchData()

defineExpose({ refresh })

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchData()
  }
}, { immediate: true })
</script>

<style scoped>
.public-data-list {
  padding: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.search-box {
  display: flex;
  align-items: center;
}
.ellipsis-text {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

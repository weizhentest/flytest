<template>
  <div class="page-step-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.page"
          placeholder="选择页面"
          allow-clear
          allow-search
          style="width: 200px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="p in pageOptions" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索步骤名称"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增步骤
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="pageStepData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 900 }"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #page_name="{ record }">
        <a-tag color="arcoblue">{{ record.page_name }}</a-tag>
      </template>
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as ExecutionStatus]">
          {{ STATUS_LABELS[record.status as ExecutionStatus] }}
        </a-tag>
      </template>
      <template #step_count="{ record }">
        <a-tag color="cyan">{{ record.step_count || 0 }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewStepDetails(record)">
            <template #icon><icon-settings /></template>
            添加步骤
          </a-button>
          <a-button type="text" size="mini" @click="editPageStep(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除该步骤？" @ok="deletePageStep(record)">
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
      :title="isEdit ? '编辑页面步骤' : '新增页面步骤'"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="module" label="所属模块" required>
              <a-select v-model="formData.module" placeholder="请选择模块" @change="onFormModuleChange">
                <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
                  {{ mod.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="page" label="所属页面" required>
              <a-select v-model="formData.page" placeholder="请选择页面" :disabled="!formData.module">
                <a-option v-for="p in filteredPageOptions" :key="p.id" :value="p.id">
                  {{ p.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item field="name" label="步骤名称" required>
          <a-input v-model="formData.name" placeholder="请输入步骤名称" :max-length="64" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="formData.description" placeholder="请输入描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 步骤详情抽屉 -->
    <a-drawer
      v-model:visible="detailDrawerVisible"
      :title="`步骤详情 - ${currentPageStep?.name || ''}`"
      width="50%"
      :footer="false"
    >
      <StepDetailList v-if="currentPageStep" :page-step="currentPageStep" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconSettings } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { pageStepsApi, pageApi, moduleApi } from '../api'
import type { UiPageSteps, UiPageStepsForm, UiPage, UiModule, ExecutionStatus } from '../types'
import { STATUS_LABELS, extractListData, extractPaginationData, extractResponseData } from '../types'
import StepDetailList from './StepDetailList.vue'

const props = defineProps<{
  selectedModuleId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const pageStepData = ref<UiPageSteps[]>([])
const pageOptions = ref<UiPage[]>([])
const moduleOptions = ref<UiModule[]>([])
const modalVisible = ref(false)
const detailDrawerVisible = ref(false)
const isEdit = ref(false)
const currentPageStep = ref<UiPageSteps | null>(null)
const formRef = ref()

// 根据表单选择的模块过滤页面选项
const filteredPageOptions = computed(() => {
  if (!formData.module) return []
  return pageOptions.value.filter((p) => p.module === formData.module)
})

const filters = reactive({ page: undefined as number | undefined, module: undefined as number | undefined, search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiPageStepsForm>({
  project: 0,
  page: undefined as unknown as number,
  module: undefined as unknown as number,
  name: '',
  description: '',
  run_flow: '',
  flow_data: {},
})

const rules = {
  page: [{ required: true, message: '请选择页面' }],
  module: [{ required: true, message: '请选择模块' }],
  name: [{ required: true, message: '请输入步骤名称' }],
}

const statusColors: Record<ExecutionStatus, string> = { 0: 'gray', 1: 'blue', 2: 'green', 3: 'red' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '页面', slotName: 'page_name', width: 120, align: 'center' as const },
  { title: '步骤名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 150, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '操作数', slotName: 'step_count', width: 80, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 220, fixed: 'right' as const, align: 'center' as const },
]

const formatDate = (dateStr: string) => dateStr ? new Date(dateStr).toLocaleString('zh-CN') : '-'

const fetchPages = async () => {
  if (!projectId.value) return
  try {
    const res = await pageApi.list({ project: projectId.value })
    pageOptions.value = extractListData<UiPage>(res)
  } catch {
    Message.error('获取页面列表失败')
  }
}

// 表单中模块选择变化时，清空页面选择
const onFormModuleChange = () => {
  formData.page = undefined as unknown as number
}

const flattenModules = (modules: UiModule[], level = 0, visited = new Set<number>()): UiModule[] => {
  const result: UiModule[] = []
  for (const mod of modules) {
    if (visited.has(mod.id)) continue
    visited.add(mod.id)
    result.push({ ...mod, name: '\u00A0\u00A0'.repeat(level) + mod.name })
    if (mod.children?.length) {
      result.push(...flattenModules(mod.children as UiModule[], level + 1, visited))
    }
  }
  return result
}

const fetchModules = async () => {
  if (!projectId.value) return
  try {
    const res = await moduleApi.tree(projectId.value)
    const modules = extractResponseData<UiModule[]>(res) || []
    moduleOptions.value = flattenModules(modules)
  } catch {
    Message.error('获取模块列表失败')
  }
}

const fetchPageSteps = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await pageStepsApi.list({
      project: projectId.value,
      page: filters.page,
      module: filters.module,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    pageStepData.value = items
    pagination.total = count
  } catch {
    Message.error('获取页面步骤列表失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchPageSteps()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchPageSteps()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchPageSteps()
}

const resetForm = () => {
  Object.assign(formData, { project: projectId.value || 0, page: undefined, module: undefined, name: '', description: '', run_flow: '', flow_data: {} })
  formRef.value?.clearValidate()
}

const showAddModal = async () => {
  isEdit.value = false
  resetForm()
  if (props.selectedModuleId) {
    formData.module = props.selectedModuleId
  }
  if (!moduleOptions.value.length) await fetchModules()
  if (!pageOptions.value.length) await fetchPages()
  modalVisible.value = true
}

const editPageStep = async (record: UiPageSteps) => {
  isEdit.value = true
  currentPageStep.value = record
  // 获取详情数据（包含完整字段）
  try {
    const res = await pageStepsApi.get(record.id)
    const detail = extractResponseData<UiPageSteps>(res)
    if (detail) {
      Object.assign(formData, {
        project: detail.project,
        page: detail.page,
        module: detail.module,
        name: detail.name,
        description: detail.description || '',
        run_flow: detail.run_flow || '',
        flow_data: detail.flow_data || {},
      })
    }
  } catch {
    // 降级使用列表数据
    Object.assign(formData, {
      project: record.project,
      page: record.page,
      module: record.module,
      name: record.name,
      description: record.description || '',
      run_flow: record.run_flow || '',
      flow_data: record.flow_data || {},
    })
  }
  if (!moduleOptions.value.length) await fetchModules()
  if (!pageOptions.value.length) await fetchPages()
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
    if (isEdit.value && currentPageStep.value) {
      await pageStepsApi.update(currentPageStep.value.id, formData)
      Message.success('更新成功')
    } else {
      await pageStepsApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchPageSteps()
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

const deletePageStep = async (record: UiPageSteps) => {
  try {
    await pageStepsApi.delete(record.id)
    Message.success('删除成功')
    fetchPageSteps()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '存在关联，无法删除。请先解除关联')
  }
}

const viewStepDetails = (record: UiPageSteps) => {
  currentPageStep.value = record
  detailDrawerVisible.value = true
}

watch(() => props.selectedModuleId, (newVal) => {
  filters.module = newVal
  pagination.current = 1
  fetchPageSteps()
})

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchPages()
    fetchModules()
    fetchPageSteps()
  }
}, { immediate: true })

const refresh = () => {
  fetchPages()
  fetchModules()
  fetchPageSteps()
}

defineExpose({ refresh })
</script>

<style scoped>
.page-step-list {
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
</style>

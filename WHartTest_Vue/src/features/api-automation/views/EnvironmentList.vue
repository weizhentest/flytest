<template>
  <div class="environment-list">
    <div class="page-header api-page-header">
      <div class="header-left">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索环境名称"
          allow-clear
          style="width: 260px"
          @search="loadEnvironments"
          @clear="loadEnvironments"
        />
      </div>
      <div class="header-right">
        <a-button type="primary" @click="openCreateModal">新增环境</a-button>
      </div>
    </div>

    <div class="content-section">
      <a-table :data="filteredEnvironments" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="环境名称" data-index="name" :width="220" />
          <a-table-column title="基础地址" data-index="base_url" ellipsis tooltip />
          <a-table-column title="默认" :width="90" align="center">
            <template #cell="{ record }">
              <a-tag :color="record.is_default ? 'green' : 'gray'">{{ record.is_default ? '是' : '否' }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="超时" :width="120">
            <template #cell="{ record }">{{ record.timeout_ms }} ms</template>
          </a-table-column>
          <a-table-column title="更新时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="180" align="center">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
                <a-popconfirm content="确定删除该环境吗？" @ok="deleteEnvironment(record.id)">
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
      :title="editingEnvironment ? '编辑环境' : '新增环境'"
      width="760px"
      :ok-loading="submitLoading"
      @before-ok="submitEnvironment"
      @cancel="resetEditor"
    >
      <div v-if="!editingEnvironment && environmentDraft" class="env-prefill-banner">
        <div class="env-prefill-copy">
          <div class="env-prefill-title">已根据最近一次文档解析准备环境草稿</div>
          <div class="env-prefill-description">
            {{ draftSummary || '基础地址、公共请求头和环境变量已经自动回填。' }}
          </div>
        </div>
        <div class="env-prefill-actions">
          <a-button @click="fillEnvironmentFromDraft">重新回填</a-button>
          <a-button type="text" @click="clearDrafts">清除草稿</a-button>
        </div>
      </div>

      <a-form ref="formRef" :model="formState" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="name" label="环境名称" :rules="[{ required: true, message: '请输入环境名称' }]">
              <a-input v-model="formState.name" placeholder="例如：测试环境 / 预发环境" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="base_url" label="基础地址">
              <a-input v-model="formState.base_url" placeholder="例如：https://api.example.com/v1" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="timeout_ms" label="默认超时(ms)">
              <a-input-number v-model="formState.timeout_ms" :min="1000" :step="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_default" label="设为默认环境">
              <a-switch v-model="formState.is_default" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="commonHeadersText" label="公共请求头(JSON)">
          <a-textarea
            v-model="formState.commonHeadersText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            placeholder='例如：{"Authorization":"Bearer {{token}}"}'
          />
        </a-form-item>

        <a-form-item field="variablesText" label="环境变量(JSON)">
          <a-textarea
            v-model="formState.variablesText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            placeholder='例如：{"token":"xxx","tenant_id":"demo"}'
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { environmentApi } from '../api'
import { useApiImportDrafts } from '../state/importDraft'
import type { ApiEnvironment, ApiEnvironmentForm } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const { environmentDraft, draftSummary, getEnvironmentDraft, clearDrafts } = useApiImportDrafts()

const loading = ref(false)
const submitLoading = ref(false)
const searchKeyword = ref('')
const environments = ref<ApiEnvironment[]>([])
const editorVisible = ref(false)
const editingEnvironment = ref<ApiEnvironment | null>(null)

const formState = ref({
  name: '',
  base_url: '',
  commonHeadersText: '{}',
  variablesText: '{}',
  timeout_ms: 30000,
  is_default: false,
})

const filteredEnvironments = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return environments.value
  return environments.value.filter(item => item.name.toLowerCase().includes(keyword))
})

const stringifyJson = (value: any, fallback = '{}') => {
  if (value === null || value === undefined || value === '') return fallback
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

const loadEnvironments = async () => {
  if (!projectId.value) {
    environments.value = []
    return
  }
  loading.value = true
  try {
    const res = await environmentApi.list({ project: projectId.value })
    const data = res.data?.data || res.data || []
    environments.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('[EnvironmentList] 获取环境失败:', error)
    Message.error('获取环境列表失败')
  } finally {
    loading.value = false
  }
}

const resetEditor = () => {
  editingEnvironment.value = null
  formState.value = {
    name: '',
    base_url: '',
    commonHeadersText: '{}',
    variablesText: '{}',
    timeout_ms: 30000,
    is_default: false,
  }
}

const fillEnvironmentFromDraft = () => {
  const draft = getEnvironmentDraft()
  if (!draft) return
  formState.value = {
    name: draft.name || '文档解析环境草稿',
    base_url: draft.base_url || '',
    commonHeadersText: stringifyJson(draft.common_headers || {}),
    variablesText: stringifyJson(draft.variables || {}),
    timeout_ms: draft.timeout_ms || 30000,
    is_default: draft.is_default || false,
  }
}

const openCreateModal = () => {
  resetEditor()
  fillEnvironmentFromDraft()
  editorVisible.value = true
}

const openEditModal = (record: ApiEnvironment) => {
  editingEnvironment.value = record
  formState.value = {
    name: record.name,
    base_url: record.base_url,
    commonHeadersText: stringifyJson(record.common_headers),
    variablesText: stringifyJson(record.variables),
    timeout_ms: record.timeout_ms,
    is_default: record.is_default,
  }
  editorVisible.value = true
}

const submitEnvironment = async (done: (closed: boolean) => void) => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    const payload: ApiEnvironmentForm = {
      project: projectId.value,
      name: formState.value.name.trim(),
      base_url: formState.value.base_url.trim(),
      common_headers: parseJsonText(formState.value.commonHeadersText, {}),
      variables: parseJsonText(formState.value.variablesText, {}),
      timeout_ms: formState.value.timeout_ms,
      is_default: formState.value.is_default,
    }

    if (editingEnvironment.value) {
      await environmentApi.update(editingEnvironment.value.id, payload)
      Message.success('环境更新成功')
    } else {
      await environmentApi.create(payload)
      Message.success('环境创建成功')
    }

    done(true)
    editorVisible.value = false
    resetEditor()
    loadEnvironments()
  } catch (error: any) {
    console.error('[EnvironmentList] 保存环境失败:', error)
    Message.error(error?.error || '保存环境失败，请检查 JSON 格式是否正确')
    done(false)
  } finally {
    submitLoading.value = false
  }
}

const deleteEnvironment = async (id: number) => {
  try {
    await environmentApi.delete(id)
    Message.success('环境删除成功')
    loadEnvironments()
  } catch (error: any) {
    Message.error(error?.error || '删除环境失败')
  }
}

watch(
  () => projectId.value,
  () => {
    loadEnvironments()
  },
  { immediate: true }
)

defineExpose({
  refresh: loadEnvironments,
})
</script>

<style scoped>
.environment-list {
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

.env-prefill-banner {
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

.env-prefill-copy {
  min-width: 0;
}

.env-prefill-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.env-prefill-description {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.env-prefill-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>

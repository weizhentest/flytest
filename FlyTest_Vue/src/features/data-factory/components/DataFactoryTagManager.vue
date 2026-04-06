<template>
  <a-drawer
    :visible="modelValue"
    title="标签管理"
    width="560px"
    @cancel="emit('update:modelValue', false)"
  >
    <div class="tag-manager">
      <div class="tag-manager__toolbar">
        <a-input-search v-model="search" allow-clear placeholder="搜索标签名称或编码" />
        <a-button type="primary" @click="openCreate">新增标签</a-button>
      </div>

      <a-spin :loading="loading">
        <a-table :data="tags" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="标签名称" data-index="name" />
            <a-table-column title="引用编码" :width="150">
              <template #cell="{ record }">
                <a-tag :color="record.color || 'arcoblue'">{{ record.code }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="记录数" data-index="record_count" :width="90" />
            <a-table-column title="最新预览" data-index="latest_preview" ellipsis tooltip />
            <a-table-column title="快捷引用" :width="180" align="center">
              <template #cell="{ record }">
                <a-space wrap size="mini">
                  <a-button size="mini" @click="copyReference(record.code, 'api')">API</a-button>
                  <a-button size="mini" @click="copyReference(record.code, 'ui')">UI</a-button>
                </a-space>
              </template>
            </a-table-column>
            <a-table-column title="操作" :width="140" align="center">
              <template #cell="{ record }">
                <a-space>
                  <a-button size="mini" @click="openEdit(record)">编辑</a-button>
                  <a-popconfirm content="确定删除该标签吗？" @ok="handleDelete(record.id)">
                    <a-button size="mini" status="danger">删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-spin>

      <a-modal
        :visible="modalVisible"
        :title="editingTag ? '编辑标签' : '新增标签'"
        :ok-loading="submitting"
        @cancel="closeModal"
        @before-ok="handleSubmit"
      >
        <a-form :model="form" layout="vertical">
          <a-form-item field="name" label="标签名称" required>
            <a-input v-model="form.name" placeholder="请输入标签名称" />
          </a-form-item>
          <a-form-item field="color" label="标签颜色">
            <a-input v-model="form.color" placeholder="例如：arcoblue / #1677ff" />
          </a-form-item>
          <a-form-item field="description" label="说明">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
          </a-form-item>
        </a-form>
      </a-modal>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { dataFactoryApi } from '../api'
import type { DataFactoryTag } from '../types'
import { buildDataFactoryPlaceholder, extractDataFactoryData, type DataFactoryReferenceMode } from '../types'

const props = defineProps<{
  modelValue: boolean
  projectId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'updated'): void
}>()

const loading = ref(false)
const submitting = ref(false)
const modalVisible = ref(false)
const editingTag = ref<DataFactoryTag | null>(null)
const search = ref('')
const tags = ref<DataFactoryTag[]>([])

const form = reactive({
  name: '',
  color: 'arcoblue',
  description: '',
})

const resetForm = () => {
  form.name = ''
  form.color = 'arcoblue'
  form.description = ''
  editingTag.value = null
}

const loadTags = async () => {
  if (!props.projectId) {
    tags.value = []
    return
  }

  loading.value = true
  try {
    const response = await dataFactoryApi.getTags({
      project: props.projectId,
      page_size: 200,
      search: search.value.trim() || undefined,
    })
    const data = extractDataFactoryData<any>(response)
    tags.value = data?.results ?? []
  } catch (error: any) {
    Message.error(error?.error || '加载标签失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  modalVisible.value = true
}

const openEdit = (tag: DataFactoryTag) => {
  editingTag.value = tag
  form.name = tag.name
  form.color = tag.color || 'arcoblue'
  form.description = tag.description || ''
  modalVisible.value = true
}

const closeModal = () => {
  modalVisible.value = false
  resetForm()
}

const handleSubmit = async () => {
  if (!props.projectId) {
    Message.warning('请先选择项目')
    return false
  }

  if (!form.name.trim()) {
    Message.warning('请输入标签名称')
    return false
  }

  submitting.value = true
  try {
    if (editingTag.value) {
      await dataFactoryApi.updateTag(editingTag.value.id, {
        project: props.projectId,
        name: form.name.trim(),
        color: form.color.trim(),
        description: form.description.trim(),
      })
      Message.success('标签已更新')
    } else {
      await dataFactoryApi.createTag({
        project: props.projectId,
        name: form.name.trim(),
        color: form.color.trim(),
        description: form.description.trim(),
      })
      Message.success('标签已创建')
    }

    closeModal()
    emit('updated')
    await loadTags()
    return true
  } catch (error: any) {
    Message.error(error?.error || '保存标签失败')
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await dataFactoryApi.deleteTag(id)
    Message.success('标签已删除')
    emit('updated')
    await loadTags()
  } catch (error: any) {
    Message.error(error?.error || '删除标签失败')
  }
}

const copyReference = async (code: string, mode: DataFactoryReferenceMode) => {
  try {
    await navigator.clipboard.writeText(buildDataFactoryPlaceholder('tag', code, mode))
    Message.success(`已复制 ${mode === 'api' ? 'API' : 'UI'} 标签引用`)
  } catch (error) {
    Message.error('复制引用失败，请稍后重试')
  }
}

watch(
  () => [props.modelValue, props.projectId, search.value] as const,
  ([visible]) => {
    if (visible) {
      void loadTags()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.tag-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tag-manager__toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
}
</style>

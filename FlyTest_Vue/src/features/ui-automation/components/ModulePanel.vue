<template>
  <div class="module-panel-wrapper">
    <a-card class="module-panel" :bordered="false">
      <div class="module-panel-content">
        <div class="module-panel-head">
          <div class="module-panel-head__eyebrow">Module Directory</div>
          <div class="module-panel-head__title">模块层级</div>
          <div class="module-panel-head__desc">
            左侧维护 UI 自动化模块树，切换菜单后右侧内容会保持和 API 自动化一致的双栏工作区布局。
          </div>
        </div>

        <div class="module-panel-header">
          <a-input-search
            v-model="searchKeyword"
            class="module-search"
            placeholder="搜索模块名称"
            allow-clear
            @search="onSearch"
            @input="onSearch"
          />
          <div class="module-actions">
            <a-dropdown @select="handleAction" trigger="hover" position="bottom">
              <a-button type="primary" size="small" class="module-action-button">操作</a-button>
              <template #content>
                <a-doption value="addRoot">新增根模块</a-doption>
                <a-doption value="addChild" :disabled="!selectedModuleId">新增子模块</a-doption>
                <a-doption value="edit" :disabled="!selectedModuleId">编辑模块</a-doption>
                <a-doption value="delete" :disabled="!selectedModuleId">删除模块</a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div class="tree-container">
          <div v-if="loading" class="module-loading-container">
            <a-spin />
          </div>
          <a-tree
            v-else-if="treeData.length > 0"
            :data="filteredTreeData"
            :field-names="{ key: 'id', title: 'name', children: 'children' }"
            show-line
            block-node
            v-model:selected-keys="selectedKeys"
            v-model:expanded-keys="expandedKeys"
            @select="onSelect"
          >
            <template #title="nodeData">
              <div class="tree-node">
                <span class="tree-node__name">{{ nodeData.name }}</span>
              </div>
            </template>
          </a-tree>
          <a-empty v-else description="暂无模块数据" />
        </div>
      </div>
    </a-card>

    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? '编辑模块' : '新增模块'"
      :ok-loading="submitLoading"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" layout="vertical">
        <a-form-item v-if="parentModule" label="父模块">
          <a-input :model-value="parentModule.name" disabled />
        </a-form-item>
        <a-form-item field="name" label="模块名称" :rules="[{ required: true, message: '请输入模块名称' }]">
          <a-input v-model="formData.name" placeholder="请输入模块名称" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { moduleApi } from '../api'
import type { UiModule, UiModuleForm } from '../types'

const emit = defineEmits<{
  (e: 'select', module: UiModule | null): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const searchKeyword = ref('')
const treeData = ref<UiModule[]>([])
const selectedModuleId = ref<number | null>(null)
const selectedKeys = ref<(string | number)[]>([])
const expandedKeys = ref<(string | number)[]>([])

const modalVisible = ref(false)
const isEditing = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const parentModule = ref<UiModule | null>(null)
const currentModule = ref<UiModule | null>(null)
const formData = ref<UiModuleForm>({
  project: 0,
  name: '',
  parent: null,
})

const filteredTreeData = computed(() => {
  if (!searchKeyword.value.trim()) return treeData.value

  const keyword = searchKeyword.value.toLowerCase()
  const filterTree = (nodes: UiModule[]): UiModule[] =>
    nodes.reduce((acc, node) => {
      const nodeName = (node.name || '').toLowerCase()
      const children = node.children ? filterTree(node.children) : []

      if (nodeName.includes(keyword) || children.length > 0) {
        acc.push({ ...node, children })
      }

      return acc
    }, [] as UiModule[])

  return filterTree(treeData.value)
})

const resetSelection = () => {
  selectedModuleId.value = null
  selectedKeys.value = []
  expandedKeys.value = []
  emit('select', null)
}

const fetchModules = async () => {
  if (!projectId.value) {
    treeData.value = []
    resetSelection()
    return
  }

  loading.value = true
  try {
    const response = await moduleApi.tree(projectId.value)
    const data = response.data?.data || []
    treeData.value = Array.isArray(data) ? data : []

    if (!selectedModuleId.value) {
      expandedKeys.value = treeData.value.map(item => item.id)
    }
  } catch (error) {
    console.error('[ModulePanel] 获取模块树失败:', error)
    Message.error('获取模块树失败')
    treeData.value = []
    resetSelection()
  } finally {
    loading.value = false
  }
}

const onSearch = () => {}

const onSelect = (keys: (string | number)[], data: { node?: UiModule }) => {
  selectedModuleId.value = keys.length > 0 ? Number(keys[0]) : null
  selectedKeys.value = keys
  emit('select', data.node || null)
}

const resetForm = () => {
  formData.value = {
    project: projectId.value || 0,
    name: '',
    parent: null,
  }
  formRef.value?.clearValidate?.()
}

const findNode = (nodes: UiModule[], id: number): UiModule | null => {
  for (const node of nodes) {
    if (node.id === id) return node

    if (node.children) {
      const found = findNode(node.children, id)
      if (found) return found
    }
  }

  return null
}

const handleAction = async (value: string) => {
  switch (value) {
    case 'addRoot':
      isEditing.value = false
      currentModule.value = null
      parentModule.value = null
      resetForm()
      modalVisible.value = true
      break
    case 'addChild':
      if (!selectedModuleId.value) {
        Message.warning('请先选择父模块')
        return
      }
      isEditing.value = false
      currentModule.value = null
      parentModule.value = findNode(treeData.value, selectedModuleId.value)
      resetForm()
      formData.value.parent = selectedModuleId.value
      modalVisible.value = true
      break
    case 'edit': {
      if (!selectedModuleId.value) {
        Message.warning('请先选择模块')
        return
      }

      const moduleToEdit = findNode(treeData.value, selectedModuleId.value)
      if (!moduleToEdit) return

      isEditing.value = true
      currentModule.value = moduleToEdit
      parentModule.value = moduleToEdit.parent ? findNode(treeData.value, moduleToEdit.parent) : null
      formData.value = {
        project: moduleToEdit.project,
        name: moduleToEdit.name,
        parent: moduleToEdit.parent,
      }
      modalVisible.value = true
      break
    }
    case 'delete': {
      if (!selectedModuleId.value) {
        Message.warning('请先选择模块')
        return
      }

      const moduleToDelete = findNode(treeData.value, selectedModuleId.value)
      if (!moduleToDelete) return

      if (moduleToDelete.children && moduleToDelete.children.length > 0) {
        Message.error('该模块下仍有子模块，请先删除子模块')
        return
      }

      Modal.warning({
        title: '确认删除',
        content: `确定要删除模块“${moduleToDelete.name}”吗？`,
        okText: '确认',
        cancelText: '取消',
        onOk: async () => {
          try {
            await moduleApi.delete(selectedModuleId.value!)
            Message.success('删除成功')
            resetSelection()
            emit('updated')
            await fetchModules()
          } catch (error: unknown) {
            const err = error as { error?: string }
            Message.error(err?.error || '存在关联数据，暂时无法删除模块')
          }
        },
      })
      break
    }
  }
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  if (!formRef.value) {
    done(false)
    return
  }

  try {
    await formRef.value.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    if (isEditing.value && currentModule.value) {
      await moduleApi.update(currentModule.value.id, formData.value)
      Message.success('模块更新成功')
    } else {
      await moduleApi.create(formData.value)
      Message.success('模块创建成功')
    }

    done(true)
    emit('updated')
    await fetchModules()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors

    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, messages]) => `${field}: ${Array.isArray(messages) ? messages.join(', ') : messages}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEditing.value ? '模块更新失败' : '模块创建失败'))
    }

    done(false)
  } finally {
    submitLoading.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

watch(
  projectId,
  newId => {
    searchKeyword.value = ''
    treeData.value = []
    resetSelection()

    if (newId) {
      void fetchModules()
    }
  },
  { immediate: true }
)

defineExpose({
  refresh: fetchModules,
})
</script>

<style scoped>
.module-panel-wrapper {
  width: 100%;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.module-panel {
  min-height: 0;
  height: 100%;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.module-panel :deep(.arco-card-body) {
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 22px;
}

.module-panel-content {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  gap: 20px;
}

.module-panel-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.module-panel-head__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.module-panel-head__title {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.module-panel-head__desc {
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.module-panel-header {
  display: flex;
  gap: 12px;
  align-items: center;
}

.module-search {
  flex: 1;
}

.module-panel-header :deep(.arco-input-wrapper),
.module-actions :deep(.arco-btn) {
  min-height: 42px;
}

.module-actions {
  display: flex;
  align-items: center;
}

.module-action-button {
  min-width: 84px;
  padding-inline: 18px;
  border-radius: 14px;
}

.tree-container {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 4px 2px 0 0;
  overscroll-behavior: contain;
}

.tree-container :deep(.arco-tree-node) {
  margin-bottom: 8px;
}

.tree-container :deep(.arco-tree-node-title) {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
}

.tree-container :deep(.arco-tree-node-title:hover) {
  background: rgba(59, 130, 246, 0.08);
}

.tree-container :deep(.arco-tree-node-selected .arco-tree-node-title) {
  background: rgba(59, 130, 246, 0.12);
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.tree-node__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
}

.module-loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

@media (max-width: 768px) {
  .module-panel-wrapper {
    width: 100%;
    height: 320px;
    min-width: 0;
  }

  .module-panel-head__title {
    font-size: 24px;
  }
}
</style>

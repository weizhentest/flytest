<template>
  <div class="collection-panel-wrapper">
    <a-card class="collection-panel" :bordered="false" title="接口集合">
      <div class="collection-panel-content">
        <div class="collection-panel-header">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索接口集合"
            allow-clear
            @search="onSearch"
            @input="onSearch"
          />
          <div class="collection-actions">
            <a-dropdown @select="handleAction" trigger="hover" position="bottom">
              <a-button type="primary" size="small" class="collection-action-button">操作</a-button>
              <template #content>
                <a-doption value="addRoot">添加根集合</a-doption>
                <a-doption value="addChild" :disabled="!selectedCollectionId">添加子集合</a-doption>
                <a-doption value="edit" :disabled="!selectedCollectionId">编辑集合</a-doption>
                <a-doption value="delete" :disabled="!selectedCollectionId">删除集合</a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div class="tree-container">
          <div v-if="loading" class="collection-loading-container">
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
              <span>{{ nodeData.name }}</span>
            </template>
          </a-tree>
          <a-empty v-else description="暂无接口集合" />
        </div>
      </div>
    </a-card>

    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? '编辑接口集合' : '新增接口集合'"
      :ok-loading="submitLoading"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" layout="vertical">
        <a-form-item v-if="parentCollection" label="父集合">
          <a-input :model-value="parentCollection.name" disabled />
        </a-form-item>
        <a-form-item field="name" label="集合名称" :rules="[{ required: true, message: '请输入集合名称' }]">
          <a-input v-model="formData.name" placeholder="请输入集合名称" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { collectionApi } from '../api'
import type { ApiCollection, ApiCollectionForm } from '../types'

const emit = defineEmits<{
  (e: 'select', collection: ApiCollection | null): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const searchKeyword = ref('')
const treeData = ref<ApiCollection[]>([])
const selectedCollectionId = ref<number | null>(null)
const selectedKeys = ref<(string | number)[]>([])
const expandedKeys = ref<(string | number)[]>([])

const modalVisible = ref(false)
const isEditing = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const parentCollection = ref<ApiCollection | null>(null)
const currentCollection = ref<ApiCollection | null>(null)
const formData = ref<ApiCollectionForm>({
  project: 0,
  name: '',
  parent: null,
})

const filteredTreeData = computed(() => {
  if (!searchKeyword.value.trim()) return treeData.value
  const keyword = searchKeyword.value.toLowerCase()
  const filterTree = (nodes: ApiCollection[]): ApiCollection[] =>
    nodes.reduce((acc, node) => {
      const children = node.children ? filterTree(node.children) : []
      if ((node.name || '').toLowerCase().includes(keyword) || children.length > 0) {
        acc.push({ ...node, children })
      }
      return acc
    }, [] as ApiCollection[])
  return filterTree(treeData.value)
})

const fetchCollections = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await collectionApi.tree(projectId.value)
    const data = res.data?.data || res.data || []
    treeData.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('[CollectionPanel] 获取接口集合失败:', error)
    Message.error('获取接口集合失败')
    treeData.value = []
  } finally {
    loading.value = false
  }
}

const onSearch = () => {}

const findNode = (nodes: ApiCollection[], id: number): ApiCollection | null => {
  for (const node of nodes) {
    if (node.id === id) return node
    if (node.children?.length) {
      const found = findNode(node.children, id)
      if (found) return found
    }
  }
  return null
}

const onSelect = (keys: (string | number)[], data: { node?: ApiCollection }) => {
  selectedCollectionId.value = keys.length > 0 ? Number(keys[0]) : null
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

const handleAction = async (value: string) => {
  switch (value) {
    case 'addRoot':
      isEditing.value = false
      currentCollection.value = null
      parentCollection.value = null
      resetForm()
      modalVisible.value = true
      break
    case 'addChild':
      if (!selectedCollectionId.value) {
        Message.warning('请先选择父集合')
        return
      }
      isEditing.value = false
      currentCollection.value = null
      parentCollection.value = findNode(treeData.value, selectedCollectionId.value)
      resetForm()
      formData.value.parent = selectedCollectionId.value
      modalVisible.value = true
      break
    case 'edit': {
      if (!selectedCollectionId.value) {
        Message.warning('请先选择集合')
        return
      }
      const target = findNode(treeData.value, selectedCollectionId.value)
      if (!target) return
      isEditing.value = true
      currentCollection.value = target
      parentCollection.value = target.parent ? findNode(treeData.value, target.parent) : null
      formData.value = {
        project: target.project,
        name: target.name,
        parent: target.parent,
        order: target.order,
      }
      modalVisible.value = true
      break
    }
    case 'delete': {
      if (!selectedCollectionId.value) {
        Message.warning('请先选择集合')
        return
      }
      const target = findNode(treeData.value, selectedCollectionId.value)
      if (!target) return
      Modal.warning({
        title: '确认删除',
        content: `确定要删除接口集合 "${target.name}" 吗？其子集合和接口将一并删除。`,
        okText: '确认',
        cancelText: '取消',
        onOk: async () => {
          try {
            await collectionApi.delete(selectedCollectionId.value!)
            Message.success('删除成功')
            selectedCollectionId.value = null
            selectedKeys.value = []
            emit('select', null)
            emit('updated')
            fetchCollections()
          } catch (error: any) {
            Message.error(error?.error || '删除接口集合失败')
          }
        },
      })
      break
    }
  }
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    done(false)
    return
  }

  if (!formData.value.name.trim()) {
    Message.warning('请输入集合名称')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    if (isEditing.value && currentCollection.value) {
      await collectionApi.update(currentCollection.value.id, formData.value)
      Message.success('更新成功')
    } else {
      await collectionApi.create(formData.value)
      Message.success('创建成功')
    }
    done(true)
    emit('updated')
    fetchCollections()
  } catch (error: any) {
    Message.error(error?.error || (isEditing.value ? '更新失败' : '创建失败'))
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
    if (newId) {
      treeData.value = []
      selectedCollectionId.value = null
      selectedKeys.value = []
      searchKeyword.value = ''
      fetchCollections()
    }
  },
  { immediate: true }
)

defineExpose({
  refresh: fetchCollections,
})
</script>

<style scoped>
.collection-panel-wrapper {
  width: 320px;
  min-width: 280px;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.collection-panel {
  height: 100%;
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
}

.collection-panel :deep(.arco-card-header) {
  padding: 22px 22px 10px;
  border-bottom: none;
}

.collection-panel :deep(.arco-card-body) {
  height: 100%;
  padding: 0 22px 22px;
}

.collection-panel-content {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 18px;
}

.collection-panel-header {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
}

.collection-actions {
  display: flex;
  align-items: center;
}

.collection-action-button {
  min-width: 72px;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 8px 4px 4px 0;
}

.tree-container :deep(.arco-tree-node) {
  margin-bottom: 8px;
}

.tree-container :deep(.arco-tree-node-title) {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
}

.tree-container :deep(.arco-tree-node-title:hover) {
  background: rgba(59, 130, 246, 0.08);
}

.tree-container :deep(.arco-tree-node-selected .arco-tree-node-title) {
  background: rgba(59, 130, 246, 0.12);
}

.collection-loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

@media (max-width: 768px) {
  .collection-panel-wrapper {
    width: 100%;
    height: 340px;
    min-width: 0;
  }
}
</style>

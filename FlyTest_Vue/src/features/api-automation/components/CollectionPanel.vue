<template>
  <div class="collection-panel-wrapper">
    <a-card class="collection-panel" :bordered="false">
      <div class="collection-panel-content">
        <div class="collection-panel-head">
          <div class="collection-panel-head__eyebrow">Collection Directory</div>
          <div class="collection-panel-head__title">接口层级</div>
          <div class="collection-panel-head__desc">
            左侧按“目录 / 接口”展示结构，点击接口后右侧会直接切换到该接口对应的测试用例。
          </div>
        </div>
        <div class="collection-panel-header">
          <a-input-search
            v-model="searchKeyword"
            class="collection-search"
            placeholder="搜索目录或接口中文名"
            allow-clear
            @search="onSearch"
            @input="onSearch"
          />
          <div class="collection-actions">
            <a-dropdown @select="handleAction" trigger="hover" position="bottom">
              <a-button type="primary" size="small" class="collection-action-button">操作</a-button>
              <template #content>
                <a-doption value="addRoot">新增根目录</a-doption>
                <a-doption value="addChild" :disabled="!actionCollectionId">新增子目录</a-doption>
                <a-doption value="edit" :disabled="!actionCollectionId">编辑目录</a-doption>
                <a-doption value="delete" :disabled="!actionCollectionId">删除目录</a-doption>
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
            :field-names="{ key: 'key', title: 'name', children: 'children' }"
            show-line
            block-node
            v-model:selected-keys="selectedKeys"
            v-model:expanded-keys="expandedKeys"
            @select="onSelect"
          >
            <template #title="nodeData">
              <div class="tree-node" :class="`tree-node--${nodeData.type}`">
                <div class="tree-node__copy">
                  <span class="tree-node__name">{{ nodeData.name }}</span>
                  <span v-if="nodeData.type === 'request'" class="tree-node__method">
                    {{ nodeData.method }}
                  </span>
                </div>
                <span v-if="nodeData.type === 'collection'" class="tree-node__count">
                  {{ nodeData.requestCount || 0 }} 接口
                </span>
              </div>
            </template>
          </a-tree>
          <a-empty v-else description="暂无接口目录" />
        </div>
      </div>
    </a-card>

    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? '编辑接口目录' : '新增接口目录'"
      :ok-loading="submitLoading"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" layout="vertical">
        <a-form-item v-if="parentCollection" label="父目录">
          <a-input :model-value="parentCollection.name" disabled />
        </a-form-item>
        <a-form-item field="name" label="目录名称" :rules="[{ required: true, message: '请输入目录名称' }]">
          <a-input v-model="formData.name" placeholder="请输入目录名称" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { apiRequestApi, collectionApi } from '../api'
import type { ApiAutomationSelection, ApiCollection, ApiCollectionForm, ApiRequest } from '../types'

interface CollectionTreeCollectionNode extends Omit<ApiCollection, 'children'> {
  type: 'collection'
  key: string
  requestCount: number
  children?: CollectionTreeNode[]
}

interface CollectionTreeRequestNode extends ApiRequest {
  type: 'request'
  key: string
}

type CollectionTreeNode = CollectionTreeCollectionNode | CollectionTreeRequestNode

const emit = defineEmits<{
  (e: 'select', selection: ApiAutomationSelection): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const searchKeyword = ref('')
const treeData = ref<CollectionTreeCollectionNode[]>([])
const selectedKeys = ref<string[]>([])
const expandedKeys = ref<string[]>([])
const currentTreeSelection = ref<CollectionTreeNode | null>(null)
const collectionMap = ref(new Map<number, ApiCollection>())

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

const actionCollectionId = computed(() =>
  currentTreeSelection.value?.type === 'collection' ? currentTreeSelection.value.id : null
)

const localeCompareZh = (left: string, right: string) => left.localeCompare(right, 'zh-CN')

const flattenCollectionMap = (nodes: ApiCollection[], map = new Map<number, ApiCollection>()) => {
  nodes.forEach(node => {
    map.set(node.id, node)
    if (node.children?.length) {
      flattenCollectionMap(node.children, map)
    }
  })
  return map
}

const buildTreeData = (collections: ApiCollection[], requests: ApiRequest[]) => {
  const requestMap = requests.reduce((acc, request) => {
    const list = acc.get(request.collection) || []
    list.push(request)
    acc.set(request.collection, list)
    return acc
  }, new Map<number, ApiRequest[]>())

  const createCollectionNodes = (nodes: ApiCollection[]): CollectionTreeCollectionNode[] =>
    [...nodes]
      .sort((left, right) => {
        if ((left.order || 0) !== (right.order || 0)) {
          return (left.order || 0) - (right.order || 0)
        }
        return localeCompareZh(left.name || '', right.name || '')
      })
      .map(node => {
        const childCollections = createCollectionNodes(node.children || [])
        const requestNodes: CollectionTreeRequestNode[] = [...(requestMap.get(node.id) || [])]
          .sort((left, right) => {
            if ((left.order || 0) !== (right.order || 0)) {
              return (left.order || 0) - (right.order || 0)
            }
            return localeCompareZh(left.name || '', right.name || '')
          })
          .map(request => ({
            ...request,
            type: 'request',
            key: `request-${request.id}`,
          }))

        const requestCount =
          requestNodes.length + childCollections.reduce((sum, child) => sum + (child.requestCount || 0), 0)

        return {
          ...node,
          type: 'collection',
          key: `collection-${node.id}`,
          requestCount,
          children: [...childCollections, ...requestNodes],
        }
      })

  return createCollectionNodes(collections)
}

const cloneCollectionNode = (
  node: CollectionTreeCollectionNode,
  children: CollectionTreeNode[]
): CollectionTreeCollectionNode => ({
  ...node,
  children,
})

const filteredTreeData = computed<CollectionTreeCollectionNode[]>(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return treeData.value

  const filterTree = (nodes: CollectionTreeNode[]): CollectionTreeNode[] =>
    nodes.reduce((acc, node) => {
      const matched = (node.name || '').toLowerCase().includes(keyword)
      if (node.type === 'request') {
        if (matched) acc.push(node)
        return acc
      }

      const children = filterTree(node.children || [])
      if (matched || children.length > 0) {
        acc.push(cloneCollectionNode(node, children))
      }
      return acc
    }, [] as CollectionTreeNode[])

  return filterTree(treeData.value) as CollectionTreeCollectionNode[]
})

const findNodeByKey = (nodes: CollectionTreeNode[], key: string): CollectionTreeNode | null => {
  for (const node of nodes) {
    if (node.key === key) return node
    if (node.type === 'collection' && node.children?.length) {
      const found = findNodeByKey(node.children, key)
      if (found) return found
    }
  }
  return null
}

const emitSelection = (node: CollectionTreeNode | null) => {
  if (!node) {
    emit('select', {
      type: null,
      collection: null,
      request: null,
    })
    return
  }

  if (node.type === 'request') {
    emit('select', {
      type: 'request',
      collection: collectionMap.value.get(node.collection) || null,
      request: node,
    })
    return
  }

  emit('select', {
    type: 'collection',
    collection: collectionMap.value.get(node.id) || null,
    request: null,
  })
}

const syncSelectionState = () => {
  const currentSelectedKey = selectedKeys.value[0]
  const nextSelectedNode = currentSelectedKey ? findNodeByKey(treeData.value, currentSelectedKey) : null
  currentTreeSelection.value = nextSelectedNode

  const nextExpandedKeys = expandedKeys.value.filter(key => Boolean(findNodeByKey(treeData.value, key)))
  expandedKeys.value = nextExpandedKeys.length ? nextExpandedKeys : treeData.value.map(node => node.key)

  if (!nextSelectedNode) {
    selectedKeys.value = []
  }

  emitSelection(nextSelectedNode)
}

const fetchCollections = async () => {
  if (!projectId.value) {
    treeData.value = []
    collectionMap.value = new Map()
    currentTreeSelection.value = null
    selectedKeys.value = []
    expandedKeys.value = []
    emitSelection(null)
    return
  }

  loading.value = true
  try {
    const [collectionRes, requestRes] = await Promise.all([
      collectionApi.tree(projectId.value),
      apiRequestApi.list({ project: projectId.value }),
    ])
    const collections = Array.isArray(collectionRes.data?.data) ? collectionRes.data.data : []
    const requests = Array.isArray(requestRes.data?.data) ? requestRes.data.data : []

    collectionMap.value = flattenCollectionMap(collections)
    treeData.value = buildTreeData(collections, requests)
    syncSelectionState()
  } catch (error) {
    console.error('[CollectionPanel] 获取接口层级失败:', error)
    Message.error('获取接口层级失败')
    treeData.value = []
    collectionMap.value = new Map()
    currentTreeSelection.value = null
    selectedKeys.value = []
    expandedKeys.value = []
    emitSelection(null)
  } finally {
    loading.value = false
  }
}

const onSearch = () => {}

const onSelect = (keys: (string | number)[], data: { node?: CollectionTreeNode }) => {
  const selectedKey = keys.length > 0 ? String(keys[0]) : ''
  const node = data.node || (selectedKey ? findNodeByKey(treeData.value, selectedKey) : null)
  selectedKeys.value = selectedKey ? [selectedKey] : []
  currentTreeSelection.value = node || null
  emitSelection(node || null)
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
      if (!actionCollectionId.value) {
        Message.warning('请先选择一个目录')
        return
      }
      isEditing.value = false
      currentCollection.value = null
      parentCollection.value = collectionMap.value.get(actionCollectionId.value) || null
      resetForm()
      formData.value.parent = actionCollectionId.value
      modalVisible.value = true
      break
    case 'edit': {
      if (!actionCollectionId.value) {
        Message.warning('请先选择一个目录')
        return
      }
      const target = collectionMap.value.get(actionCollectionId.value)
      if (!target) return
      isEditing.value = true
      currentCollection.value = target
      parentCollection.value = target.parent ? collectionMap.value.get(target.parent) || null : null
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
      if (!actionCollectionId.value) {
        Message.warning('请先选择一个目录')
        return
      }
      const target = collectionMap.value.get(actionCollectionId.value)
      if (!target) return
      Modal.warning({
        title: '确认删除',
        content: `确定要删除接口目录“${target.name}”吗？其子目录和接口会一并删除。`,
        okText: '确认',
        cancelText: '取消',
        onOk: async () => {
          try {
            await collectionApi.delete(actionCollectionId.value!)
            Message.success('目录删除成功')
            currentTreeSelection.value = null
            selectedKeys.value = []
            emitSelection(null)
            emit('updated')
            fetchCollections()
          } catch (error: any) {
            Message.error(error?.error || '删除接口目录失败')
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
    Message.warning('请输入目录名称')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    if (isEditing.value && currentCollection.value) {
      await collectionApi.update(currentCollection.value.id, formData.value)
      Message.success('目录更新成功')
    } else {
      await collectionApi.create(formData.value)
      Message.success('目录创建成功')
    }
    done(true)
    emit('updated')
    fetchCollections()
  } catch (error: any) {
    Message.error(error?.error || (isEditing.value ? '目录更新失败' : '目录创建失败'))
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
      searchKeyword.value = ''
      fetchCollections()
      return
    }

    treeData.value = []
    collectionMap.value = new Map()
    currentTreeSelection.value = null
    selectedKeys.value = []
    expandedKeys.value = []
    emitSelection(null)
  },
  { immediate: true }
)

defineExpose({
  refresh: fetchCollections,
})
</script>

<style scoped>
.collection-panel-wrapper {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.collection-panel {
  height: 100%;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.collection-panel :deep(.arco-card-body) {
  height: 100%;
  padding: 22px;
}

.collection-panel-content {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 20px;
}

.collection-panel-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.collection-panel-head__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.collection-panel-head__title {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.collection-panel-head__desc {
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.collection-panel-header {
  display: flex;
  gap: 12px;
  align-items: center;
}

.collection-search {
  flex: 1;
}

.collection-panel-header :deep(.arco-input-wrapper),
.collection-actions :deep(.arco-btn) {
  min-height: 42px;
}

.collection-actions {
  display: flex;
  align-items: center;
}

.collection-action-button {
  min-width: 84px;
  padding-inline: 18px;
  border-radius: 14px;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 4px 2px 0 0;
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

.tree-node__copy {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.tree-node__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-node__method,
.tree-node__count {
  flex: 0 0 auto;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.4;
}

.tree-node__method {
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
  font-weight: 700;
}

.tree-node__count {
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

.tree-node--request .tree-node__name {
  color: #0f172a;
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
    height: 320px;
    min-width: 0;
  }

  .collection-panel-head__title {
    font-size: 24px;
  }
}
</style>

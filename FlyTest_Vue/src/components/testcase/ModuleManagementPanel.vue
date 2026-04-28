<template>
  <div class="module-panel-wrapper">
    <a-card class="module-panel" :bordered="false" :title="panelTitle">
      <div class="module-panel-content">
        <div class="module-panel-header">
          <a-input-search
            v-model="moduleSearchKeyword"
            placeholder="请输入模块名称"
            allow-clear
            @search="onModuleSearch"
            @input="onModuleSearch"
          />
          <div class="module-actions">
            <a-dropdown
              trigger="hover"
              position="bottom"
              :popup-max-width="false"
              class="module-dropdown"
              @select="handleModuleAction"
            >
              <a-button type="primary" size="small" class="module-action-button">
                操作
              </a-button>
              <template #content>
                <a-doption
                  v-for="item in moduleActionMenuItems"
                  :key="item.value"
                  :value="item.value"
                  :disabled="item.requiresSelection && !selectedModuleKey"
                  class="centered-dropdown-item"
                >
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div class="tree-container">
          <div v-if="moduleLoading" class="module-loading-container">
            <a-spin />
          </div>
          <a-tree
            v-else-if="moduleTreeData.length > 0"
            :data="filteredModuleTreeData"
            :field-names="{ key: 'id', title: 'name' }"
            show-line
            block-node
            v-model:selected-keys="selectedModuleKeys"
            v-model:expanded-keys="expandedKeys"
            @select="onModuleSelect"
            @expand="onTreeExpand"
          >
            <template #title="nodeData">
              <a-dropdown
                trigger="contextMenu"
                position="br"
                :popup-max-width="false"
                @select="handleModuleAction"
              >
                <span class="module-node-title" @contextmenu="handleModuleNodeContextMenu(nodeData)">
                  <span>{{ nodeData.name }}</span>
                  <span class="module-count">({{ nodeData.testcase_count || nodeData.test_case_count || 0 }})</span>
                </span>
                <template #content>
                  <a-doption
                    v-for="item in moduleActionMenuItems"
                    :key="item.value"
                    :value="item.value"
                    :disabled="item.requiresSelection && !selectedModuleKey"
                    class="centered-dropdown-item"
                  >
                    {{ item.label }}
                  </a-doption>
                </template>
              </a-dropdown>
            </template>
          </a-tree>
          <a-empty v-else description="暂无模块数据" />
        </div>
      </div>

      <ModuleEditModal
        :visible="moduleModalVisible"
        :is-editing="isEditingModule"
        :initial-data="moduleForm"
        :module-tree="moduleTreeForSelect"
        :project-id="currentProjectId"
        @submit="handleModuleSubmit"
        @close="closeModuleModal"
      />

      <a-modal
        v-model:visible="testCaseTransferModalVisible"
        :title="testCaseTransferMode === 'move' ? '移动测试用例' : '复制测试用例'"
        :confirm-loading="testCaseTransferSubmitting"
        width="920px"
        :ok-button-props="{ disabled: !canSubmitTestCaseTransfer }"
        @ok="submitTestCaseTransfer"
        @cancel="closeTestCaseTransferModal"
      >
        <div class="testcase-transfer-modal">
          <div class="testcase-transfer-toolbar">
            <div class="testcase-transfer-source-group">
              <div class="testcase-transfer-source">
                当前模块：<strong>{{ selectedModuleName || '未选择模块' }}</strong>
              </div>
              <div class="testcase-transfer-actions">
                <a-button size="mini" @click="selectAllTransferCases">全选</a-button>
                <a-button size="mini" @click="invertTransferCasesSelection">反选</a-button>
                <a-button size="mini" @click="clearTransferCasesSelection">清空</a-button>
              </div>
            </div>
            <a-input-search
              v-model="testCaseTransferSearchKeyword"
              placeholder="搜索当前模块中的测试用例"
              allow-clear
              style="width: 260px;"
              @search="fetchModuleTestCasesForTransfer"
              @clear="fetchModuleTestCasesForTransfer"
            />
          </div>

          <div class="testcase-transfer-body">
            <div class="testcase-transfer-table">
              <a-table
                :columns="testCaseTransferColumns"
                :data="moduleTestCaseOptions"
                :loading="testCaseTransferLoading"
                :pagination="false"
                row-key="id"
                :scroll="{ y: 360 }"
              >
                <template #selection="{ record }">
                  <a-checkbox
                    :model-value="selectedTransferTestCaseIds.includes(record.id)"
                    @change="(checked: boolean) => handleTransferCaseSelect(record.id, checked)"
                  />
                </template>
                <template #selectAll>
                  <a-checkbox
                    :model-value="isAllTransferCasesSelected"
                    :indeterminate="isTransferCasesIndeterminate"
                    @change="handleSelectAllTransferCases"
                  />
                </template>
              </a-table>
            </div>

            <div class="testcase-transfer-target">
              <a-form layout="vertical">
                <a-form-item label="目标模块" required>
                  <a-select
                    v-model="targetTransferModuleId"
                    placeholder="请选择目标根模块或子模块"
                    allow-search
                  >
                    <a-option
                      v-for="module in selectableTargetModules"
                      :key="module.id"
                      :value="module.id"
                    >
                      {{ module.indentName }}
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-form>

              <div class="testcase-transfer-summary">
                已选 <strong>{{ selectedTransferTestCaseIds.length }}</strong> 条测试用例
              </div>
              <div class="testcase-transfer-summary">
                目标位置：<strong>{{ selectedTransferTargetPath || '未选择目标模块' }}</strong>
              </div>
            </div>
          </div>
        </div>
      </a-modal>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, toRefs, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import type { TreeNodeData } from '@arco-design/web-vue';
import {
  deleteTestCaseModule,
  getTestCaseModules,
  type CreateTestCaseModuleRequest,
  type TestCaseModule,
} from '@/services/testcaseModuleService';
import {
  batchCopyTestCases,
  batchMoveTestCases,
  getTestCaseList,
  type TestCase,
} from '@/services/testcaseService';
import ModuleEditModal from './ModuleEditModal.vue';

const props = withDefaults(defineProps<{
  currentProjectId: number | null;
  panelTitle?: string;
  entityName?: string;
}>(), {
  panelTitle: '模块管理',
  entityName: '模块',
});

const emit = defineEmits<{
  (e: 'moduleSelected', moduleId: number | null): void;
  (e: 'moduleUpdated'): void;
}>();

const { currentProjectId } = toRefs(props);

const moduleLoading = ref(false);
const moduleSearchKeyword = ref('');
const testCaseModules = ref<TestCaseModule[]>([]);
const selectedModuleKey = ref<number | null>(null);
const selectedModuleKeys = ref<(number | string)[]>([]);
const expandedKeys = ref<(number | string)[]>([]);
const moduleActionMenuItems = computed(() => [
  { value: 'addRoot', label: `添加根${props.entityName}`, requiresSelection: false },
  { value: 'addChild', label: `添加子${props.entityName}`, requiresSelection: true },
  { value: 'moveCases', label: '移动测试用例', requiresSelection: true },
  { value: 'copyCases', label: '复制测试用例', requiresSelection: true },
  { value: 'edit', label: `编辑${props.entityName}`, requiresSelection: true },
  { value: 'delete', label: `删除${props.entityName}`, requiresSelection: true },
]);
const testCaseTransferModalVisible = ref(false);
const testCaseTransferMode = ref<'move' | 'copy'>('move');
const testCaseTransferLoading = ref(false);
const testCaseTransferSubmitting = ref(false);
const testCaseTransferSearchKeyword = ref('');
const moduleTestCaseOptions = ref<TestCase[]>([]);
const selectedTransferTestCaseIds = ref<number[]>([]);
const targetTransferModuleId = ref<number | null>(null);
const testCaseTransferColumns = [
  { title: '选择', slotName: 'selection', width: 54, titleSlotName: 'selectAll', align: 'center' as const },
  { title: 'ID', dataIndex: 'id', width: 76 },
  { title: '用例名称', dataIndex: 'name', ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', width: 88 },
  { title: '测试类型', dataIndex: 'test_type', width: 110 },
];

const moduleModalVisible = ref(false);
const isEditingModule = ref(false);
const moduleForm = reactive<CreateTestCaseModuleRequest & { id?: number }>({
  name: '',
  parent: undefined,
});

const fetchTestCaseModules = async () => {
  if (!currentProjectId.value) {
    testCaseModules.value = [];
    return;
  }

  moduleLoading.value = true;
  try {
    const response = await getTestCaseModules(currentProjectId.value, {
      search: moduleSearchKeyword.value,
    });
    if (response.success && response.data) {
      testCaseModules.value = response.data;
    } else {
      Message.error(response.error || '获取模块列表失败');
      testCaseModules.value = [];
    }
  } catch (error) {
    console.error('获取模块列表出错:', error);
    Message.error('获取模块列表时发生错误');
    testCaseModules.value = [];
  } finally {
    moduleLoading.value = false;
  }
};

const buildModuleTree = (modules: TestCaseModule[], parentId: number | null = null): TreeNodeData[] => {
  return modules
    .filter((module) => module.parent === parentId || module.parent_id === parentId)
    .map((module) => {
      const children = buildModuleTree(modules, module.id);
      const directCount = Number((module as any).testcase_count || module.test_case_count || 0);
      const childrenCount = children.reduce(
        (total, child) => total + Number((child as any).testcase_count || (child as any).test_case_count || 0),
        0
      );

      return {
        ...module,
        id: module.id,
        key: module.id,
        title: module.name,
        children,
        testcase_count: directCount + childrenCount,
      };
    });
};

const moduleTreeData = computed(() => buildModuleTree(testCaseModules.value));

const getAllChildModuleIds = (modules: TestCaseModule[], parentId: number): Set<number> => {
  const childrenIds = new Set<number>();

  const findChildren = (currentParentId: number) => {
    modules.forEach((module) => {
      if (module.parent === currentParentId || module.parent_id === currentParentId) {
        childrenIds.add(module.id);
        findChildren(module.id);
      }
    });
  };

  findChildren(parentId);
  return childrenIds;
};

const moduleTreeForSelect = computed(() => {
  if (isEditingModule.value && moduleForm.id) {
    const excludedIds = getAllChildModuleIds(testCaseModules.value, moduleForm.id);
    excludedIds.add(moduleForm.id);
    const filteredModules = testCaseModules.value.filter((module) => !excludedIds.has(module.id));
    return buildModuleTree(filteredModules);
  }
  return moduleTreeData.value;
});

const filteredModuleTreeData = computed(() => {
  const keyword = moduleSearchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return moduleTreeData.value;
  }

  const filterTree = (nodes: TreeNodeData[]): TreeNodeData[] => {
    return nodes.reduce((acc, node) => {
      const nodeName = String((node as any).name || '').toLowerCase();
      const children = node.children ? filterTree(node.children as TreeNodeData[]) : [];

      if (nodeName.includes(keyword) || children.length > 0) {
        acc.push({ ...node, children: children.length > 0 ? children : undefined });
      }

      return acc;
    }, [] as TreeNodeData[]);
  };

  return filterTree(moduleTreeData.value);
});

const selectedModuleName = computed(() => {
  const moduleItem = testCaseModules.value.find((module) => module.id === selectedModuleKey.value);
  return moduleItem?.name || '';
});

const selectableTargetModules = computed(() => {
  const result: Array<TestCaseModule & { indentName: string; fullPath: string }> = [];
  const build = (modules: TreeNodeData[], level = 0, parentPath = '') => {
    modules.forEach((node) => {
      const nodeId = Number((node as any).id ?? node.key);
      const nodeName = String((node as any).name || node.title || '');
      const fullPath = parentPath ? `${parentPath} / ${nodeName}` : nodeName;
      if (nodeId && nodeId !== selectedModuleKey.value) {
        result.push({
          ...(node as unknown as TestCaseModule),
          id: nodeId,
          indentName: `${'　'.repeat(level)}${nodeName}`,
          fullPath,
        });
      }
      if (Array.isArray(node.children) && node.children.length > 0) {
        build(node.children as TreeNodeData[], level + 1, fullPath);
      }
    });
  };

  build(moduleTreeData.value);
  return result;
});

const selectedTransferTargetPath = computed(() => {
  const targetModule = selectableTargetModules.value.find((module) => module.id === targetTransferModuleId.value);
  return targetModule?.fullPath || '';
});

const isAllTransferCasesSelected = computed(() => {
  return moduleTestCaseOptions.value.length > 0
    && moduleTestCaseOptions.value.every((testCase) => selectedTransferTestCaseIds.value.includes(testCase.id));
});

const isTransferCasesIndeterminate = computed(() => {
  const selectedCount = moduleTestCaseOptions.value.filter((testCase) =>
    selectedTransferTestCaseIds.value.includes(testCase.id)
  ).length;
  return selectedCount > 0 && selectedCount < moduleTestCaseOptions.value.length;
});

const canSubmitTestCaseTransfer = computed(() => {
  return selectedTransferTestCaseIds.value.length > 0 && !!targetTransferModuleId.value;
});

const onModuleSearch = () => {
  // 前端实时过滤，保持当前交互简洁。
};

const setSelectedModule = (moduleId: number | null) => {
  selectedModuleKey.value = moduleId;
  selectedModuleKeys.value = moduleId ? [moduleId] : [];
  emit('moduleSelected', moduleId);
};

const fetchModuleTestCasesForTransfer = async () => {
  if (!currentProjectId.value || !selectedModuleKey.value) {
    moduleTestCaseOptions.value = [];
    return;
  }

  testCaseTransferLoading.value = true;
  try {
    const response = await getTestCaseList(currentProjectId.value, {
      page: 1,
      pageSize: 1000,
      module_id: selectedModuleKey.value,
      search: testCaseTransferSearchKeyword.value.trim() || undefined,
    });

    if (response.success && response.data) {
      moduleTestCaseOptions.value = response.data;
      selectedTransferTestCaseIds.value = selectedTransferTestCaseIds.value.filter((id) =>
        response.data!.some((testCase) => testCase.id === id)
      );
    } else {
      Message.error(response.error || '获取模块测试用例失败');
      moduleTestCaseOptions.value = [];
      selectedTransferTestCaseIds.value = [];
    }
  } catch (error) {
    Message.error('获取模块测试用例时发生错误');
    moduleTestCaseOptions.value = [];
    selectedTransferTestCaseIds.value = [];
  } finally {
    testCaseTransferLoading.value = false;
  }
};

const openTestCaseTransferModal = async (mode: 'move' | 'copy') => {
  if (!selectedModuleKey.value) {
    Message.warning('请先选择一个模块');
    return;
  }

  testCaseTransferMode.value = mode;
  testCaseTransferModalVisible.value = true;
  testCaseTransferSearchKeyword.value = '';
  selectedTransferTestCaseIds.value = [];
  targetTransferModuleId.value = null;
  await fetchModuleTestCasesForTransfer();
};

const closeTestCaseTransferModal = () => {
  testCaseTransferModalVisible.value = false;
  testCaseTransferSearchKeyword.value = '';
  moduleTestCaseOptions.value = [];
  selectedTransferTestCaseIds.value = [];
  targetTransferModuleId.value = null;
};

const handleTransferCaseSelect = (testCaseId: number, checked: boolean) => {
  if (checked) {
    if (!selectedTransferTestCaseIds.value.includes(testCaseId)) {
      selectedTransferTestCaseIds.value.push(testCaseId);
    }
    return;
  }

  selectedTransferTestCaseIds.value = selectedTransferTestCaseIds.value.filter((id) => id !== testCaseId);
};

const handleSelectAllTransferCases = (checked: boolean) => {
  if (checked) {
    selectedTransferTestCaseIds.value = moduleTestCaseOptions.value.map((testCase) => testCase.id);
    return;
  }
  selectedTransferTestCaseIds.value = [];
};

const selectAllTransferCases = () => {
  selectedTransferTestCaseIds.value = moduleTestCaseOptions.value.map((testCase) => testCase.id);
};

const clearTransferCasesSelection = () => {
  selectedTransferTestCaseIds.value = [];
};

const invertTransferCasesSelection = () => {
  const selectedSet = new Set(selectedTransferTestCaseIds.value);
  selectedTransferTestCaseIds.value = moduleTestCaseOptions.value
    .map((testCase) => testCase.id)
    .filter((id) => !selectedSet.has(id));
};

const submitTestCaseTransfer = async () => {
  if (!currentProjectId.value || !selectedModuleKey.value) {
    Message.warning('请先选择一个模块');
    return;
  }
  if (selectedTransferTestCaseIds.value.length === 0) {
    Message.warning('请先选择要处理的测试用例');
    return;
  }
  if (!targetTransferModuleId.value) {
    Message.warning('请选择目标模块');
    return;
  }

  testCaseTransferSubmitting.value = true;
  try {
    const response = testCaseTransferMode.value === 'move'
      ? await batchMoveTestCases(currentProjectId.value, selectedTransferTestCaseIds.value, targetTransferModuleId.value)
      : await batchCopyTestCases(currentProjectId.value, selectedTransferTestCaseIds.value, targetTransferModuleId.value);

    if (!response.success) {
      Message.error(response.error || (testCaseTransferMode.value === 'move' ? '移动测试用例失败' : '复制测试用例失败'));
      return;
    }

    Message.success(
      response.message || (testCaseTransferMode.value === 'move' ? '测试用例移动成功' : '测试用例复制成功')
    );
    await fetchTestCaseModules();
    emit('moduleSelected', selectedModuleKey.value);
    closeTestCaseTransferModal();
    emit('moduleUpdated');
  } catch (error) {
    Message.error(testCaseTransferMode.value === 'move' ? '移动测试用例时发生错误' : '复制测试用例时发生错误');
  } finally {
    testCaseTransferSubmitting.value = false;
  }
};

const onModuleSelect = (
  _selectedKeys: (string | number)[],
  data: { selected?: boolean; node?: TreeNodeData }
) => {
  if (data.selected && data.node) {
    setSelectedModule(data.node.key as number);
  } else {
    setSelectedModule(null);
  }
};

const onTreeExpand = (newExpandedKeys: (string | number)[]) => {
  expandedKeys.value = newExpandedKeys;
};

const handleModuleNodeContextMenu = (nodeData: TreeNodeData) => {
  const nodeKey = Number(nodeData.key ?? nodeData.id);
  if (Number.isFinite(nodeKey) && nodeKey > 0) {
    setSelectedModule(nodeKey);
  }
};

const handleModuleAction = (action: string | number | Record<string, any> | undefined) => {
  const actionValue = action as string;

  if (actionValue === 'addRoot') {
    isEditingModule.value = false;
    moduleForm.id = undefined;
    moduleForm.name = '';
    moduleForm.parent = undefined;
    moduleModalVisible.value = true;
    return;
  }

  if (actionValue === 'addChild') {
    if (!selectedModuleKey.value) {
      Message.warning('请先选择一个父模块');
      return;
    }
    isEditingModule.value = false;
    moduleForm.id = undefined;
    moduleForm.name = '';
    moduleForm.parent = selectedModuleKey.value;
    moduleModalVisible.value = true;
    return;
  }

  if (actionValue === 'moveCases') {
    void openTestCaseTransferModal('move');
    return;
  }

  if (actionValue === 'copyCases') {
    void openTestCaseTransferModal('copy');
    return;
  }

  if (actionValue === 'edit') {
    if (!selectedModuleKey.value) {
      Message.warning('请先选择要编辑的模块');
      return;
    }
    const moduleToEdit = testCaseModules.value.find((module) => module.id === selectedModuleKey.value);
    if (!moduleToEdit) {
      return;
    }
    isEditingModule.value = true;
    moduleForm.id = moduleToEdit.id;
    moduleForm.name = moduleToEdit.name;
    moduleForm.parent = moduleToEdit.parent || undefined;
    moduleModalVisible.value = true;
    return;
  }

  if (actionValue === 'delete') {
    if (!selectedModuleKey.value) {
      Message.warning('请先选择要删除的模块');
      return;
    }

    const moduleToDelete = testCaseModules.value.find((module) => module.id === selectedModuleKey.value);
    if (!moduleToDelete) {
      return;
    }

    const children = testCaseModules.value.filter(
      (module) => module.parent === selectedModuleKey.value || module.parent_id === selectedModuleKey.value
    );

    if (children.length > 0) {
      Message.error('该模块下还有子模块，请先删除子模块');
      return;
    }

    if (moduleToDelete.test_case_count && moduleToDelete.test_case_count > 0) {
      Message.error(`模块“${moduleToDelete.name}”下包含 ${moduleToDelete.test_case_count} 个测试用例，请先处理测试用例`);
      return;
    }

    Modal.warning({
      title: '确认删除',
      content: `确定要删除模块“${moduleToDelete.name}”吗？此操作不可恢复。`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        if (!currentProjectId.value || !selectedModuleKey.value) {
          return;
        }
        try {
          const response = await deleteTestCaseModule(currentProjectId.value, selectedModuleKey.value);
          if (response.success) {
            Message.success('模块删除成功');
            await fetchTestCaseModules();
            selectedModuleKey.value = null;
            selectedModuleKeys.value = [];
            emit('moduleUpdated');
          } else {
            Message.error(response.error || '删除模块失败');
          }
        } catch (error) {
          Message.error('删除模块时发生错误');
        }
      },
    });
  }
};

const closeModuleModal = () => {
  moduleModalVisible.value = false;
};

const handleModuleSubmit = async (success: boolean) => {
  if (!success) {
    return;
  }
  await fetchTestCaseModules();
  closeModuleModal();
  emit('moduleUpdated');
};

onMounted(() => {
  if (currentProjectId.value) {
    fetchTestCaseModules();
  }
});

watch(currentProjectId, (newProjectId) => {
  selectedModuleKey.value = null;
  selectedModuleKeys.value = [];
  moduleSearchKeyword.value = '';

  if (newProjectId) {
    fetchTestCaseModules();
  } else {
    testCaseModules.value = [];
  }
});

defineExpose({
  refreshModules: fetchTestCaseModules,
});
</script>

<style scoped>
.module-panel-wrapper {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .module-panel-wrapper {
    width: 100%;
    height: 200px;
    min-height: 150px;
  }
}

.module-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

:deep(.module-panel .arco-card-header) {
  border-bottom: 1px solid var(--color-border-2);
  padding: 12px 16px;
  flex-shrink: 0;
}

:deep(.module-panel .arco-card-body) {
  padding: 0;
  flex-grow: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.module-panel-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tree-container {
  flex-grow: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.tree-container::-webkit-scrollbar {
  display: none;
}

:deep(.tree-container .arco-empty) {
  margin: auto;
}

.module-loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 100px;
}

.module-count {
  color: var(--color-text-3);
  font-size: 0.85em;
  margin-left: 4px;
}

.module-node-title {
  display: inline-flex;
  align-items: center;
  width: 100%;
}

.testcase-transfer-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.testcase-transfer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.testcase-transfer-source-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.testcase-transfer-source {
  color: var(--color-text-2);
}

.testcase-transfer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.testcase-transfer-body {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr);
  gap: 16px;
}

.testcase-transfer-table,
.testcase-transfer-target {
  min-width: 0;
}

.testcase-transfer-summary {
  margin-top: 12px;
  color: var(--color-text-2);
  word-break: break-word;
}

.module-panel-header {
  flex-shrink: 0;
  padding: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.module-actions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  margin-bottom: 16px;
}

.module-dropdown {
  width: 100%;
}

.module-action-button {
  width: 80px;
  background-color: #ffffff;
  border-color: #ffffff;
}

.module-action-button:hover {
  background-color: #ffffff;
  border-color: #ffffff;
}

:deep(.arco-dropdown-option) {
  text-align: center !important;
  padding: 5px 12px !important;
}

:deep(.arco-dropdown-option-content) {
  display: block !important;
  text-align: center !important;
  width: 100% !important;
}

:deep(.arco-dropdown-list) {
  min-width: 120px;
  width: 100%;
}

:deep(.arco-dropdown) {
  width: 100%;
}

:deep(.arco-dropdown-menu) {
  width: 100%;
  padding: 4px 0;
}

@media (max-width: 768px) {
  .testcase-transfer-toolbar,
  .testcase-transfer-body {
    display: flex;
    flex-direction: column;
  }
}
</style>

<template>
  <div class="module-panel-wrapper">
    <a-card class="module-panel" :bordered="false" title="模块管理">
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
                <a-doption value="addRoot" class="centered-dropdown-item">添加根模块</a-doption>
                <a-doption value="addChild" :disabled="!selectedModuleKey" class="centered-dropdown-item">
                  添加子模块
                </a-doption>
                <a-doption value="edit" :disabled="!selectedModuleKey" class="centered-dropdown-item">
                  编辑模块
                </a-doption>
                <a-doption value="delete" :disabled="!selectedModuleKey" class="centered-dropdown-item">
                  删除模块
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
              <span>{{ nodeData.name }}</span>
              <span class="module-count">({{ nodeData.testcase_count || nodeData.test_case_count || 0 }})</span>
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
import ModuleEditModal from './ModuleEditModal.vue';

const props = defineProps<{
  currentProjectId: number | null;
}>();

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
        (total, child) => total + Number((child as any).test_case_count || 0),
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

const onModuleSearch = () => {
  // 前端实时过滤，保持当前交互简洁。
};

const onModuleSelect = (
  _selectedKeys: (string | number)[],
  data: { selected?: boolean; node?: TreeNodeData }
) => {
  if (data.selected && data.node) {
    selectedModuleKey.value = data.node.key as number;
    emit('moduleSelected', selectedModuleKey.value);
  } else {
    selectedModuleKey.value = null;
    emit('moduleSelected', null);
  }
};

const onTreeExpand = (newExpandedKeys: (string | number)[]) => {
  expandedKeys.value = newExpandedKeys;
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
</style>

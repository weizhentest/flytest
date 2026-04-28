<template>
  <div class="suite-panel-wrapper">
    <a-card class="suite-panel" :bordered="false" title="套件管理">
      <div class="suite-panel-content">
        <div class="suite-panel-header">
          <a-input-search
            v-model="searchKeyword"
            placeholder="请输入套件名称"
            allow-clear
          />
          <div class="suite-actions">
            <a-dropdown
              trigger="hover"
              position="bottom"
              :popup-max-width="false"
              class="suite-dropdown"
              @select="handleSuiteAction"
            >
              <a-button type="primary" size="small" class="suite-action-button">
                操作
              </a-button>
              <template #content>
                <a-doption
                  v-for="item in suiteActionMenuItems"
                  :key="item.value"
                  :value="item.value"
                  :disabled="item.requiresSelection && !selectedSuiteKey"
                  class="centered-dropdown-item"
                >
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div class="tree-container">
          <div v-if="loading" class="suite-loading-container">
            <a-spin />
          </div>
          <a-tree
            v-else-if="filteredTreeData.length > 0"
            :data="filteredTreeData"
            :field-names="{ key: 'id', title: 'name' }"
            show-line
            block-node
            v-model:selected-keys="selectedSuiteKeys"
            v-model:expanded-keys="expandedKeys"
            @select="onTreeSelect"
            @expand="onTreeExpand"
          >
            <template #title="nodeData">
              <a-dropdown
                trigger="contextMenu"
                position="br"
                :popup-max-width="false"
                @select="handleSuiteAction"
              >
                <span class="suite-node-title" @contextmenu="handleContextMenu(nodeData)">
                  <span>{{ nodeData.name }}</span>
                  <span class="suite-count">({{ nodeData.testcase_count || 0 }})</span>
                </span>
                <template #content>
                  <a-doption
                    v-for="item in suiteActionMenuItems"
                    :key="item.value"
                    :value="item.value"
                    :disabled="item.requiresSelection && !selectedSuiteKey"
                    class="centered-dropdown-item"
                  >
                    {{ item.label }}
                  </a-doption>
                </template>
              </a-dropdown>
            </template>
          </a-tree>
          <a-empty v-else description="暂无套件数据" />
        </div>
      </div>
    </a-card>

    <TestSuiteFormModal
      v-model:visible="showSuiteForm"
      :current-project-id="currentProjectId"
      :suite-id="editingSuiteId"
      :initial-parent-id="editingParentId"
      @success="handleFormSuccess"
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
              当前套件：<strong>{{ selectedSuiteName || '未选择套件' }}</strong>
            </div>
            <div class="testcase-transfer-actions">
              <a-button size="mini" @click="selectAllTransferCases">全选</a-button>
              <a-button size="mini" @click="invertTransferCasesSelection">反选</a-button>
              <a-button size="mini" @click="clearTransferCasesSelection">清空</a-button>
            </div>
          </div>
          <a-input-search
            v-model="testCaseTransferSearchKeyword"
            placeholder="搜索当前套件中的测试用例"
            allow-clear
            style="width: 260px;"
            @search="fetchSuiteTestCasesForTransfer"
            @clear="fetchSuiteTestCasesForTransfer"
          />
        </div>

        <div class="testcase-transfer-body">
          <div class="testcase-transfer-table">
            <a-table
              :columns="testCaseTransferColumns"
              :data="suiteTestCaseOptions"
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
              <a-form-item label="目标套件" required>
                <a-select
                  v-model="targetTransferSuiteId"
                  placeholder="请选择目标根套件或子套件"
                  allow-search
                >
                  <a-option
                    v-for="suite in selectableTargetSuites"
                    :key="suite.id"
                    :value="suite.id"
                  >
                    {{ suite.indentName }}
                  </a-option>
                </a-select>
              </a-form-item>
            </a-form>

            <div class="testcase-transfer-summary">
              已选 <strong>{{ selectedTransferTestCaseIds.length }}</strong> 条测试用例
            </div>
            <div class="testcase-transfer-summary">
              目标位置：<strong>{{ selectedTransferTargetPath || '未选择目标套件' }}</strong>
            </div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import type { TreeNodeData } from '@arco-design/web-vue';
import TestSuiteFormModal from '@/components/testcase/TestSuiteFormModal.vue';
import {
  copySuiteTestCases,
  deleteTestSuite,
  getTestSuiteList,
  moveSuiteTestCases,
  type TestSuite,
} from '@/services/testSuiteService';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';

const props = defineProps<{
  currentProjectId: number | null;
}>();

const emit = defineEmits<{
  (e: 'suiteSelected', suiteId: number | null): void;
  (e: 'suiteUpdated'): void;
}>();

const loading = ref(false);
const searchKeyword = ref('');
const suites = ref<TestSuite[]>([]);
const selectedSuiteKey = ref<number | null>(null);
const selectedSuiteKeys = ref<(number | string)[]>([]);
const expandedKeys = ref<(number | string)[]>([]);
const showSuiteForm = ref(false);
const editingSuiteId = ref<number | null>(null);
const editingParentId = ref<number | null>(null);

const testCaseTransferModalVisible = ref(false);
const testCaseTransferMode = ref<'move' | 'copy'>('move');
const testCaseTransferLoading = ref(false);
const testCaseTransferSubmitting = ref(false);
const testCaseTransferSearchKeyword = ref('');
const suiteTestCaseOptions = ref<TestCase[]>([]);
const selectedTransferTestCaseIds = ref<number[]>([]);
const targetTransferSuiteId = ref<number | null>(null);

const suiteActionMenuItems = [
  { value: 'addRoot', label: '添加根套件', requiresSelection: false },
  { value: 'addChild', label: '添加子套件', requiresSelection: true },
  { value: 'moveCases', label: '移动测试用例', requiresSelection: true },
  { value: 'copyCases', label: '复制测试用例', requiresSelection: true },
  { value: 'edit', label: '编辑套件', requiresSelection: true },
  { value: 'delete', label: '删除套件', requiresSelection: true },
];

const testCaseTransferColumns = [
  { title: '选择', slotName: 'selection', width: 54, titleSlotName: 'selectAll', align: 'center' as const },
  { title: 'ID', dataIndex: 'id', width: 76 },
  { title: '用例名称', dataIndex: 'name', ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', width: 88 },
  { title: '测试类型', dataIndex: 'test_type', width: 110 },
];

const fetchSuites = async () => {
  if (!props.currentProjectId) {
    suites.value = [];
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteList(props.currentProjectId, {
      search: searchKeyword.value.trim() || undefined,
    });

    if (response.success && response.data) {
      suites.value = response.data;
      return;
    }

    Message.error(response.error || '获取测试套件失败');
    suites.value = [];
  } catch (error) {
    console.error('获取测试套件失败:', error);
    Message.error('获取测试套件失败');
    suites.value = [];
  } finally {
    loading.value = false;
  }
};

const buildTree = (items: TestSuite[], parentId: number | null = null): TreeNodeData[] =>
  items
    .filter((suite) => (suite.parent ?? suite.parent_id ?? null) === parentId)
    .map((suite) => {
      const children = buildTree(items, suite.id);
      const childrenCount = children.reduce(
        (sum, child) => sum + Number((child as any).testcase_count || 0),
        0,
      );

      return {
        ...suite,
        id: suite.id,
        key: suite.id,
        title: suite.name,
        children,
        testcase_count: Number(suite.testcase_count || 0) + childrenCount,
      };
    });

const treeData = computed(() => buildTree(suites.value));

const selectedSuiteName = computed(() => {
  const suite = suites.value.find((item) => item.id === selectedSuiteKey.value);
  return suite?.name || '';
});

const selectableTargetSuites = computed(() => {
  const result: Array<TestSuite & { indentName: string; fullPath: string }> = [];
  const build = (nodes: TreeNodeData[], level = 0, parentPath = '') => {
    nodes.forEach((node) => {
      const nodeId = Number((node as any).id ?? node.key);
      const nodeName = String((node as any).name || node.title || '');
      const fullPath = parentPath ? `${parentPath} / ${nodeName}` : nodeName;
      if (nodeId && nodeId !== selectedSuiteKey.value) {
        result.push({
          ...(node as unknown as TestSuite),
          id: nodeId,
          indentName: `${'  '.repeat(level)}${nodeName}`,
          fullPath,
        });
      }
      if (Array.isArray(node.children) && node.children.length > 0) {
        build(node.children as TreeNodeData[], level + 1, fullPath);
      }
    });
  };

  build(treeData.value);
  return result;
});

const selectedTransferTargetPath = computed(() => {
  const suite = selectableTargetSuites.value.find((item) => item.id === targetTransferSuiteId.value);
  return suite?.fullPath || '';
});

const isAllTransferCasesSelected = computed(() => {
  return suiteTestCaseOptions.value.length > 0
    && suiteTestCaseOptions.value.every((testCase) => selectedTransferTestCaseIds.value.includes(testCase.id));
});

const isTransferCasesIndeterminate = computed(() => {
  const selectedCount = suiteTestCaseOptions.value.filter((testCase) =>
    selectedTransferTestCaseIds.value.includes(testCase.id)
  ).length;
  return selectedCount > 0 && selectedCount < suiteTestCaseOptions.value.length;
});

const canSubmitTestCaseTransfer = computed(() => {
  return selectedTransferTestCaseIds.value.length > 0 && !!targetTransferSuiteId.value;
});

const filteredTreeData = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return treeData.value;
  }

  const filterTree = (nodes: TreeNodeData[]): TreeNodeData[] =>
    nodes.reduce((acc, node) => {
      const nodeName = String((node as any).name || '').toLowerCase();
      const children = Array.isArray(node.children) ? filterTree(node.children as TreeNodeData[]) : [];

      if (nodeName.includes(keyword) || children.length > 0) {
        acc.push({ ...node, children: children.length > 0 ? children : undefined });
      }

      return acc;
    }, [] as TreeNodeData[]);

  return filterTree(treeData.value);
});

const setSelectedSuite = (suiteId: number | null) => {
  selectedSuiteKey.value = suiteId;
  selectedSuiteKeys.value = suiteId ? [suiteId] : [];
  emit('suiteSelected', suiteId);
};

const fetchSuiteTestCasesForTransfer = async () => {
  if (!props.currentProjectId || !selectedSuiteKey.value) {
    suiteTestCaseOptions.value = [];
    return;
  }

  testCaseTransferLoading.value = true;
  try {
    const response = await getTestCaseList(props.currentProjectId, {
      page: 1,
      pageSize: 1000,
      suite_id: selectedSuiteKey.value,
      search: testCaseTransferSearchKeyword.value.trim() || undefined,
    });

    if (response.success && response.data) {
      suiteTestCaseOptions.value = response.data;
      selectedTransferTestCaseIds.value = selectedTransferTestCaseIds.value.filter((id) =>
        response.data!.some((testCase) => testCase.id === id)
      );
      return;
    }

    Message.error(response.error || '获取套件测试用例失败');
    suiteTestCaseOptions.value = [];
    selectedTransferTestCaseIds.value = [];
  } catch (error) {
    Message.error('获取套件测试用例时发生错误');
    suiteTestCaseOptions.value = [];
    selectedTransferTestCaseIds.value = [];
  } finally {
    testCaseTransferLoading.value = false;
  }
};

const openTestCaseTransferModal = async (mode: 'move' | 'copy') => {
  if (!selectedSuiteKey.value) {
    Message.warning('请先选择一个套件');
    return;
  }

  testCaseTransferMode.value = mode;
  testCaseTransferModalVisible.value = true;
  testCaseTransferSearchKeyword.value = '';
  selectedTransferTestCaseIds.value = [];
  targetTransferSuiteId.value = null;
  await fetchSuiteTestCasesForTransfer();
};

const closeTestCaseTransferModal = () => {
  testCaseTransferModalVisible.value = false;
  testCaseTransferSearchKeyword.value = '';
  suiteTestCaseOptions.value = [];
  selectedTransferTestCaseIds.value = [];
  targetTransferSuiteId.value = null;
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
    selectedTransferTestCaseIds.value = suiteTestCaseOptions.value.map((testCase) => testCase.id);
    return;
  }
  selectedTransferTestCaseIds.value = [];
};

const selectAllTransferCases = () => {
  selectedTransferTestCaseIds.value = suiteTestCaseOptions.value.map((testCase) => testCase.id);
};

const clearTransferCasesSelection = () => {
  selectedTransferTestCaseIds.value = [];
};

const invertTransferCasesSelection = () => {
  const selectedSet = new Set(selectedTransferTestCaseIds.value);
  selectedTransferTestCaseIds.value = suiteTestCaseOptions.value
    .map((testCase) => testCase.id)
    .filter((id) => !selectedSet.has(id));
};

const submitTestCaseTransfer = async () => {
  if (!props.currentProjectId || !selectedSuiteKey.value) {
    Message.warning('请先选择一个套件');
    return;
  }
  if (selectedTransferTestCaseIds.value.length === 0) {
    Message.warning('请先选择要处理的测试用例');
    return;
  }
  if (!targetTransferSuiteId.value) {
    Message.warning('请选择目标套件');
    return;
  }

  testCaseTransferSubmitting.value = true;
  try {
    const response = testCaseTransferMode.value === 'move'
      ? await moveSuiteTestCases(
        props.currentProjectId,
        selectedSuiteKey.value,
        selectedTransferTestCaseIds.value,
        targetTransferSuiteId.value
      )
      : await copySuiteTestCases(
        props.currentProjectId,
        selectedSuiteKey.value,
        selectedTransferTestCaseIds.value,
        targetTransferSuiteId.value
      );

    if (!response.success) {
      Message.error(response.error || (testCaseTransferMode.value === 'move' ? '移动测试用例失败' : '复制测试用例失败'));
      return;
    }

    Message.success(
      response.message || (testCaseTransferMode.value === 'move' ? '测试用例移动成功' : '测试用例复制成功')
    );
    await fetchSuites();
    emit('suiteUpdated');
    closeTestCaseTransferModal();
  } catch (error) {
    Message.error(testCaseTransferMode.value === 'move' ? '移动测试用例时发生错误' : '复制测试用例时发生错误');
  } finally {
    testCaseTransferSubmitting.value = false;
  }
};

const handleFormSuccess = async () => {
  await fetchSuites();
  emit('suiteUpdated');
};

const handleSuiteAction = (action: string | number | Record<string, any> | undefined) => {
  const actionValue = action as string;

  if (actionValue === 'addRoot') {
    editingSuiteId.value = null;
    editingParentId.value = null;
    showSuiteForm.value = true;
    return;
  }

  if (actionValue === 'addChild') {
    if (!selectedSuiteKey.value) {
      Message.warning('请先选择父套件');
      return;
    }
    editingSuiteId.value = null;
    editingParentId.value = selectedSuiteKey.value;
    showSuiteForm.value = true;
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
    if (!selectedSuiteKey.value) {
      Message.warning('请先选择要编辑的套件');
      return;
    }
    editingSuiteId.value = selectedSuiteKey.value;
    editingParentId.value = null;
    showSuiteForm.value = true;
    return;
  }

  if (actionValue === 'delete') {
    if (!props.currentProjectId || !selectedSuiteKey.value) {
      Message.warning('请先选择要删除的套件');
      return;
    }

    const suite = suites.value.find((item) => item.id === selectedSuiteKey.value);
    if (!suite) {
      return;
    }

    Modal.warning({
      title: '确认删除',
      content: `确定删除套件“${suite.name}”吗？`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        const response = await deleteTestSuite(props.currentProjectId!, suite.id);
        if (!response.success) {
          Message.error(response.error || '删除套件失败');
          return;
        }

        Message.success(response.message || '套件删除成功');
        if (selectedSuiteKey.value === suite.id) {
          setSelectedSuite(null);
        }
        await fetchSuites();
        emit('suiteUpdated');
      },
    });
  }
};

const handleContextMenu = (nodeData: TreeNodeData) => {
  const suiteId = Number(nodeData.key ?? nodeData.id);
  if (Number.isFinite(suiteId) && suiteId > 0) {
    setSelectedSuite(suiteId);
  }
};

const onTreeSelect = (
  _selectedKeys: (string | number)[],
  data: { selected?: boolean; node?: TreeNodeData },
) => {
  if (data.selected && data.node) {
    setSelectedSuite(Number(data.node.key));
    return;
  }
  setSelectedSuite(null);
};

const onTreeExpand = (keys: (string | number)[]) => {
  expandedKeys.value = keys;
};

watch(
  () => props.currentProjectId,
  async (projectId) => {
    selectedSuiteKey.value = null;
    selectedSuiteKeys.value = [];
    expandedKeys.value = [];
    searchKeyword.value = '';

    if (!projectId) {
      suites.value = [];
      return;
    }

    await fetchSuites();
  },
);

onMounted(async () => {
  if (props.currentProjectId) {
    await fetchSuites();
  }
});

defineExpose({
  refreshSuites: fetchSuites,
});
</script>

<style scoped>
.suite-panel-wrapper {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.suite-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

:deep(.suite-panel .arco-card-header) {
  border-bottom: 1px solid var(--color-border-2);
  padding: 12px 16px;
  flex-shrink: 0;
}

:deep(.suite-panel .arco-card-body) {
  padding: 0;
  flex-grow: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.suite-panel-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.suite-panel-header {
  flex-shrink: 0;
  padding: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.suite-actions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  margin-bottom: 16px;
}

.suite-dropdown {
  width: 100%;
}

.suite-action-button {
  width: 80px;
  background-color: #ffffff;
  border-color: #ffffff;
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

.suite-loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 100px;
}

.suite-node-title {
  display: inline-flex;
  align-items: center;
  width: 100%;
}

.suite-count {
  color: var(--color-text-3);
  font-size: 0.85em;
  margin-left: 4px;
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

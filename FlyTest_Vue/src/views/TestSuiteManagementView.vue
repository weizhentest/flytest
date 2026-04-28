<template>
  <div class="testsuite-management-container">
    <div v-if="!currentProjectId" class="empty-state">
      <a-empty description="请先选择项目" />
    </div>

    <div v-else class="list-view-layout">
      <div class="suite-panel-resizable-shell" :style="suitePanelShellStyle">
        <TestSuiteTreePanel
          ref="suitePanelRef"
          :current-project-id="currentProjectId"
          @suite-selected="handleSuiteSelected"
          @suite-updated="handleSuiteUpdated"
        />
      </div>

      <div class="suite-panel-resizer" @mousedown="startSuitePanelResize" />

      <div class="right-content-area">
        <template v-if="selectedSuiteId">
          <div class="suite-toolbar">
            <div class="suite-toolbar-info">
              <div class="suite-title">{{ selectedSuiteDetail?.name || '测试套件' }}</div>
              <div class="suite-subtitle">
                {{ selectedSuiteDetail?.description || '当前套件中的测试用例列表' }}
              </div>
            </div>
            <div class="suite-toolbar-actions">
              <a-button @click="showExecutionList = true">执行历史</a-button>
              <a-button @click="showDetailModal = true">套件详情</a-button>
              <a-button
                type="primary"
                :disabled="!selectedSuiteDetail || (selectedSuiteDetail.testcase_count || 0) === 0"
                @click="showExecutionConfirm = true"
              >
                执行套件
              </a-button>
            </div>
          </div>

          <div v-show="viewMode === 'list'" class="suite-list-stack">
            <TestCaseList
              ref="testCaseListRef"
              :current-project-id="currentProjectId"
              :selected-suite-id="selectedSuiteId"
              :selected-module-id="selectedModuleId"
              :module-tree="moduleTreeForForm"
              :show-create-actions="false"
              :show-review-status="false"
              action-mode="suite"
              time-column-mode="assigned"
              @edit-test-case="showEditTestCaseForm"
              @view-test-case="showViewTestCaseDetail"
              @test-case-deleted="handleTestCaseDeleted"
              @module-filter-change="handleModuleFilterChange"
              @request-optimization="handleRequestOptimization"
            />
          </div>

          <TestCaseForm
            v-if="viewMode === 'edit'"
            :is-editing="true"
            :test-case-id="currentEditingTestCaseId"
            :current-project-id="currentProjectId"
            :initial-selected-module-id="selectedModuleId"
            :module-tree="moduleTreeForForm"
            :test-case-ids="testCaseIdsForNavigation"
            @close="backToList"
            @submit-success="handleFormSubmitSuccess"
            @navigate="handleNavigateTestCase"
            @review-status-changed="handleReviewStatusChanged"
          />

          <TestCaseDetail
            v-if="viewMode === 'view'"
            :test-case-id="currentViewingTestCaseId"
            :current-project-id="currentProjectId"
            :modules="allModules"
            :test-case-ids="testCaseIdsForNavigation"
            @close="backToList"
            @edit-test-case="showEditTestCaseForm"
            @test-case-deleted="handleTestCaseDeletedFromDetail"
            @navigate="handleNavigateViewTestCase"
            @review-status-changed="handleReviewStatusChanged"
          />
        </template>

        <div v-else class="suite-empty">
          <a-empty description="点击左侧根套件或子套件后，这里会显示套件中的测试用例列表" />
        </div>
      </div>
    </div>

    <OptimizationSuggestionModal
      v-if="isOptimizationModalVisible"
      v-model="isOptimizationModalVisible"
      :test-case="pendingOptimizationTestCase"
      @submit="handleOptimizationSubmit"
    />

    <TestSuiteDetailModal
      v-model:visible="showDetailModal"
      :current-project-id="currentProjectId"
      :suite-id="selectedSuiteId"
    />

    <TestExecutionConfirmModal
      v-model:visible="showExecutionConfirm"
      :current-project-id="currentProjectId"
      :suite="selectedSuiteDetail"
      @success="handleExecutionSuccess"
    />

    <TestExecutionListModal
      v-if="showExecutionList"
      v-model:visible="showExecutionList"
      :current-project-id="currentProjectId"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Message, Notification } from '@arco-design/web-vue';
import type { TreeNodeData } from '@arco-design/web-vue';
import TestCaseList from '@/components/testcase/TestCaseList.vue';
import TestExecutionConfirmModal from '@/components/testcase/TestExecutionConfirmModal.vue';
import TestExecutionListModal from '@/components/testcase/TestExecutionListModal.vue';
import TestSuiteDetailModal from '@/components/testcase/TestSuiteDetailModal.vue';
import TestSuiteTreePanel from '@/components/testcase/TestSuiteTreePanel.vue';
import { sendChatMessageStream } from '@/features/langgraph/services/chatService';
import { getTestSuiteDetail, type TestSuite } from '@/services/testSuiteService';
import { getTestCaseModules, type TestCaseModule } from '@/services/testcaseModuleService';
import { type TestCase, updateTestCaseReviewStatus } from '@/services/testcaseService';
import { useProjectStore } from '@/store/projectStore';

const TestCaseForm = defineAsyncComponent(() => import('@/components/testcase/TestCaseForm.vue'));
const TestCaseDetail = defineAsyncComponent(() => import('@/components/testcase/TestCaseDetail.vue'));
const OptimizationSuggestionModal = defineAsyncComponent(
  () => import('@/components/testcase/OptimizationSuggestionModal.vue')
);

const router = useRouter();
const projectStore = useProjectStore();
const currentProjectId = computed(() => projectStore.currentProjectId || null);

const suitePanelRef = ref<InstanceType<typeof TestSuiteTreePanel> | null>(null);
const testCaseListRef = ref<InstanceType<typeof TestCaseList> | null>(null);

const selectedSuiteId = ref<number | null>(null);
const selectedSuiteDetail = ref<TestSuite | null>(null);
const selectedModuleId = ref<number | null>(null);

const showExecutionConfirm = ref(false);
const showExecutionList = ref(false);
const showDetailModal = ref(false);

const allModules = ref<TestCaseModule[]>([]);
const moduleTreeForForm = ref<TreeNodeData[]>([]);

const viewMode = ref<'list' | 'edit' | 'view'>('list');
const currentEditingTestCaseId = ref<number | null>(null);
const currentViewingTestCaseId = ref<number | null>(null);
const testCaseIdsForNavigation = ref<number[]>([]);

const isOptimizationModalVisible = ref(false);
const pendingOptimizationTestCase = ref<TestCase | null>(null);

const suitePanelWidth = ref(180);
const isResizingSuitePanel = ref(false);

const suitePanelShellStyle = computed(() => ({
  width: `${suitePanelWidth.value}px`,
}));

const buildModuleTree = (modules: TestCaseModule[], parentId: number | null = null): TreeNodeData[] =>
  modules
    .filter((module) => module.parent === parentId || module.parent_id === parentId)
    .map((module) => ({
      key: module.id,
      title: module.name,
      id: module.id,
      name: module.name,
      children: buildModuleTree(modules, module.id),
    }));

const fetchModules = async () => {
  if (!currentProjectId.value) {
    allModules.value = [];
    moduleTreeForForm.value = [];
    return;
  }

  const response = await getTestCaseModules(currentProjectId.value, {});
  if (response.success && response.data) {
    allModules.value = response.data;
    moduleTreeForForm.value = buildModuleTree(response.data);
    return;
  }

  allModules.value = [];
  moduleTreeForForm.value = [];
};

const fetchSelectedSuiteDetail = async () => {
  if (!currentProjectId.value || !selectedSuiteId.value) {
    selectedSuiteDetail.value = null;
    return;
  }

  const response = await getTestSuiteDetail(currentProjectId.value, selectedSuiteId.value);
  selectedSuiteDetail.value = response.success && response.data ? response.data : null;
};

const handleSuiteSelected = async (suiteId: number | null) => {
  selectedSuiteId.value = suiteId;
  selectedModuleId.value = null;
  viewMode.value = 'list';
  currentEditingTestCaseId.value = null;
  currentViewingTestCaseId.value = null;
  testCaseIdsForNavigation.value = [];
  await fetchSelectedSuiteDetail();
};

const handleSuiteUpdated = async () => {
  await fetchSelectedSuiteDetail();
  await testCaseListRef.value?.refreshTestCases?.();
};

const handleModuleFilterChange = (moduleId: number | null) => {
  selectedModuleId.value = moduleId;
};

const showEditTestCaseForm = (testCaseOrId: TestCase | number) => {
  const ids = testCaseListRef.value?.getTestCaseIds();
  testCaseIdsForNavigation.value = ids || [];
  currentEditingTestCaseId.value = typeof testCaseOrId === 'number' ? testCaseOrId : testCaseOrId.id;
  viewMode.value = 'edit';
};

const handleNavigateTestCase = (testCaseId: number) => {
  currentEditingTestCaseId.value = testCaseId;
};

const showViewTestCaseDetail = (testCase: TestCase) => {
  const ids = testCaseListRef.value?.getTestCaseIds();
  testCaseIdsForNavigation.value = ids || [];
  currentViewingTestCaseId.value = testCase.id;
  viewMode.value = 'view';
};

const handleNavigateViewTestCase = (testCaseId: number) => {
  currentViewingTestCaseId.value = testCaseId;
};

const handleReviewStatusChanged = async () => {
  const currentId = viewMode.value === 'edit' ? currentEditingTestCaseId.value : currentViewingTestCaseId.value;
  const oldIndex = currentId ? testCaseIdsForNavigation.value.indexOf(currentId) : -1;

  await testCaseListRef.value?.refreshTestCases();

  const newIds = testCaseListRef.value?.getTestCaseIds() || [];
  testCaseIdsForNavigation.value = newIds;

  if (currentId && !newIds.includes(currentId)) {
    if (newIds.length === 0) {
      backToList();
      return;
    }

    const nextIndex = Math.min(oldIndex, newIds.length - 1);
    const nextId = newIds[Math.max(0, nextIndex)];
    if (viewMode.value === 'edit') {
      currentEditingTestCaseId.value = nextId;
    } else {
      currentViewingTestCaseId.value = nextId;
    }
  }
};

const backToList = () => {
  viewMode.value = 'list';
  currentEditingTestCaseId.value = null;
  currentViewingTestCaseId.value = null;
};

const handleFormSubmitSuccess = async () => {
  backToList();
  await testCaseListRef.value?.refreshTestCases?.();
  await suitePanelRef.value?.refreshSuites?.();
  await fetchSelectedSuiteDetail();
};

const handleTestCaseDeleted = async () => {
  await suitePanelRef.value?.refreshSuites?.();
  await fetchSelectedSuiteDetail();
};

const handleTestCaseDeletedFromDetail = async () => {
  backToList();
  await testCaseListRef.value?.refreshTestCases?.();
  await suitePanelRef.value?.refreshSuites?.();
  await fetchSelectedSuiteDetail();
};

const handleRequestOptimization = (testCase: TestCase) => {
  pendingOptimizationTestCase.value = testCase;
  isOptimizationModalVisible.value = true;
};

const handleOptimizationSubmit = async (data: { testCase: TestCase; suggestion: string }) => {
  if (!currentProjectId.value) {
    Message.error('没有有效的项目 ID');
    return;
  }

  try {
    await updateTestCaseReviewStatus(currentProjectId.value, data.testCase.id, 'needs_optimization');
  } catch (error) {
    console.error('更新状态失败:', error);
  }

  let stepsText = '无';
  if (data.testCase.steps && data.testCase.steps.length > 0) {
    stepsText = data.testCase.steps
      .map((step) => `  步骤${step.step_number}: ${step.description} -> 预期结果: ${step.expected_result}`)
      .join('\n');
  }

  const message = `
优化以下测试用例。
【重要约束】
- 调用编辑用例工具时必须带上 is_optimization 参数
- 工具返回成功后即表示任务完成，无需再次编辑
【用例信息】
- 用例ID: ${data.testCase.id}
- 项目ID: ${currentProjectId.value}
- 名称: ${data.testCase.name}
- 优先级: ${data.testCase.level}
- 前置条件: ${data.testCase.precondition || '无'}
- 模块ID: ${data.testCase.module_id || '未分配'}
- 步骤:
${stepsText}
- 备注: ${data.testCase.notes || '无'}

【用户优化建议】
${data.suggestion || '请根据测试最佳实践进行全面优化'}
  `.trim();

  sendChatMessageStream(
    {
      message,
      project_id: String(currentProjectId.value),
      use_knowledge_base: false,
    },
    (sessionId) => {
      localStorage.setItem('langgraph_session_id', sessionId);
      const notificationReturn = Notification.info({
        title: '优化已开始',
        content: '用例优化任务已在后台开始处理。',
        footer: () =>
          h('div', { style: 'text-align: right; margin-top: 12px;' }, [
            h(
              'a',
              {
                href: 'javascript:;',
                onClick: () => {
                  router.push({ name: 'LangGraphChat' });
                  notificationReturn?.close();
                },
              },
              '点击查看优化过程'
            ),
          ]),
        duration: 10000,
        id: `optimize-case-${sessionId}`,
      });
    }
  );

  await testCaseListRef.value?.refreshTestCases();
  pendingOptimizationTestCase.value = null;
};

const handleExecutionSuccess = () => {
  Message.success('测试执行已启动');
  showExecutionList.value = true;
};

const stopSuitePanelResize = () => {
  isResizingSuitePanel.value = false;
  window.removeEventListener('mousemove', handleSuitePanelResize);
  window.removeEventListener('mouseup', stopSuitePanelResize);
};

const handleSuitePanelResize = (event: MouseEvent) => {
  if (!isResizingSuitePanel.value) {
    return;
  }

  const minWidth = 180;
  const maxWidth = Math.max(260, Math.floor(window.innerWidth * 0.45));
  suitePanelWidth.value = Math.min(maxWidth, Math.max(minWidth, event.clientX - 8));
};

const startSuitePanelResize = (event: MouseEvent) => {
  if (window.innerWidth <= 768) {
    return;
  }

  event.preventDefault();
  isResizingSuitePanel.value = true;
  window.addEventListener('mousemove', handleSuitePanelResize);
  window.addEventListener('mouseup', stopSuitePanelResize);
};

watch(currentProjectId, async (projectId) => {
  selectedSuiteId.value = null;
  selectedSuiteDetail.value = null;
  selectedModuleId.value = null;
  testCaseIdsForNavigation.value = [];
  backToList();

  if (!projectId) {
    allModules.value = [];
    moduleTreeForForm.value = [];
    return;
  }

  await fetchModules();
});

onMounted(async () => {
  if (currentProjectId.value) {
    await fetchModules();
  }
});

onUnmounted(() => {
  stopSuitePanelResize();
});
</script>

<style scoped>
.testsuite-management-container {
  display: flex;
  height: 100%;
  background-color: var(--color-bg-1);
  overflow: hidden;
}

.empty-state {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #fff;
  border-radius: 8px;
}

.list-view-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
}

.suite-panel-resizable-shell {
  flex: 0 0 auto;
  min-width: 180px;
  max-width: 45vw;
  height: 100%;
  overflow: hidden;
}

.suite-panel-resizer {
  width: 6px;
  flex: 0 0 6px;
  cursor: col-resize;
  border-radius: 999px;
  background: linear-gradient(to bottom, rgba(22, 93, 255, 0.08), rgba(22, 93, 255, 0.22));
  opacity: 0.7;
}

.suite-panel-resizer:hover {
  background: linear-gradient(to bottom, rgba(22, 93, 255, 0.18), rgba(22, 93, 255, 0.36));
  opacity: 1;
}

.right-content-area {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.suite-list-stack {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.suite-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
  padding: 16px 18px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

.suite-toolbar-info {
  min-width: 0;
}

.suite-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-1);
}

.suite-subtitle {
  margin-top: 6px;
  color: var(--color-text-3);
  word-break: break-word;
}

.suite-toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.suite-empty {
  display: flex;
  flex: 1;
  justify-content: center;
  align-items: center;
  background: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

@media (max-width: 768px) {
  .list-view-layout {
    flex-direction: column;
  }

  .suite-panel-resizable-shell {
    width: 100% !important;
    min-width: 100%;
    max-width: 100%;
    height: 220px;
  }

  .suite-panel-resizer {
    display: none;
  }

  .suite-toolbar {
    flex-direction: column;
  }

  .suite-toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>

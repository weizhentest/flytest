<template>
  <div class="testcase-management-container">

    <!-- 始终显示模块管理面板 -->
    <div class="list-view-layout">
      <ModuleManagementPanel
        :current-project-id="currentProjectId"
        @module-selected="handleModuleSelected"
        @module-updated="handleModuleUpdated"
        ref="modulePanelRef"
      />

      <!-- 右侧内容区域 - 根据视图模式动态切换 -->
      <div class="right-content-area">
        <!-- 列表视图 - 使用 v-show 保持组件状态（筛选条件等） -->
        <TestCaseList
          v-show="viewMode === 'list'"
          :current-project-id="currentProjectId"
          :selected-module-id="selectedModuleId"
          :module-tree="moduleTreeForForm"
          @add-test-case="showAddCaseModeModal"
          @generate-test-cases="showGenerateCasesModal"
          @edit-test-case="showEditTestCaseForm"
          @view-test-case="showViewTestCaseDetail"
          @execute-test-case="handleExecuteTestCase"
          @test-case-deleted="handleTestCaseDeleted"
          @module-filter-change="handleModuleSelected"
          @request-optimization="handleRequestOptimization"
          ref="testCaseListRef"
        />

        <!-- 添加/编辑测试用例表单 -->
        <TestCaseForm
          v-if="viewMode === 'add' || viewMode === 'edit'"
          :is-editing="viewMode === 'edit'"
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

        <!-- 查看测试用例详情 -->
        <TestCaseDetail
          v-if="viewMode === 'view'"
          :test-case-id="currentViewingTestCaseId"
          :current-project-id="currentProjectId"
          :modules="allModules"
          :test-case-ids="testCaseIdsForNavigation"
          @close="backToList"
          @edit-test-case="showEditTestCaseForm"
          @test-case-deleted="handleViewDetailTestCaseDeleted"
          @navigate="handleNavigateViewTestCase"
          @review-status-changed="handleReviewStatusChanged"
        />
      </div>
    </div>

    <GenerateCasesModal
      v-if="isGenerateCasesModalVisible"
      v-model:visible="isGenerateCasesModalVisible"
      :generating="isGeneratingCases"
      :test-case-module-tree="moduleTreeForForm"
      @submit="handleGenerateCasesSubmit"
    />

    <AddCaseModeModal
      v-model:visible="isAddCaseModeModalVisible"
      @manual="handleManualAddSelected"
      @ai="handleAiAddSelected"
    />

    <AppendGenerateCasesModal
      v-if="isAppendGenerateModalVisible"
      v-model:visible="isAppendGenerateModalVisible"
      :generating="isGeneratingCases"
      :module-name="selectedModuleName"
      @submit="handleAppendGenerateSubmit"
    />
    
    <ExecuteTestCaseModal
      v-if="isExecuteModalVisible"
      v-model:visible="isExecuteModalVisible"
      :test-case="pendingExecuteTestCase"
      @confirm="handleExecuteConfirm"
    />

    <OptimizationSuggestionModal
      v-if="isOptimizationModalVisible"
      v-model="isOptimizationModalVisible"
      :test-case="pendingOptimizationTestCase"
      @submit="handleOptimizationSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, h, ref, computed, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectStore } from '@/store/projectStore';
import { useAiActivityStore } from '@/store/aiActivityStore';
import { generateTestCasesFromRequirement, type TestCase } from '@/services/testcaseService';
import type { TestCaseModule } from '@/services/testcaseModuleService';
import type { TreeNodeData } from '@arco-design/web-vue';
import { getTestCaseModules } from '@/services/testcaseModuleService';
import { Message, Notification } from '@arco-design/web-vue';

import ModuleManagementPanel from '@/components/testcase/ModuleManagementPanel.vue';
import TestCaseList from '@/components/testcase/TestCaseList.vue';
import AddCaseModeModal from '@/components/testcase/AddCaseModeModal.vue';
import AppendGenerateCasesModal from '@/components/testcase/AppendGenerateCasesModal.vue';
const TestCaseForm = defineAsyncComponent(() => import('@/components/testcase/TestCaseForm.vue'));
const TestCaseDetail = defineAsyncComponent(() => import('@/components/testcase/TestCaseDetail.vue'));
const GenerateCasesModal = defineAsyncComponent(() => import('@/components/testcase/GenerateCasesModal.vue'));
const ExecuteTestCaseModal = defineAsyncComponent(() => import('@/components/testcase/ExecuteTestCaseModal.vue'));
const OptimizationSuggestionModal = defineAsyncComponent(() => import('@/components/testcase/OptimizationSuggestionModal.vue'));
import {
  sendChatMessageStream
} from '@/features/langgraph/services/chatService';
import type { ChatRequest } from '@/features/langgraph/types/chat';
import { updateTestCaseReviewStatus } from '@/services/testcaseService';

// 测试类型提示词映射
const TEST_TYPE_PROMPTS: Record<string, string> = {
  smoke: `【测试类型：冒烟测试】
- 目标：生成最小化用例，仅验证核心主流程可用性
- 要求：每个功能点最多1-2条用例，覆盖最基本的正向场景
- 原则：快速验证系统基本功能是否正常，不深入边界和异常场景`,
  functional: `【测试类型：功能测试】
- 目标：使用等价类划分技术，全面验证功能正确性
- 要求：覆盖有效等价类和无效等价类，每类至少1条用例
- 原则：确保正向场景完整，主要功能路径全覆盖`,
  boundary: `【测试类型：边界测试】
- 目标：使用边界值分析技术，测试临界条件
- 要求：测试边界值、边界值±1、典型值，每个边界至少3条用例
- 原则：重点关注数值范围、长度限制、日期边界等`,
  exception: `【测试类型：异常测试】
- 目标：使用错误推测法，验证系统容错能力
- 要求：覆盖异常输入、网络异常、数据异常、并发冲突等场景
- 原则：验证错误提示友好性和系统稳定性`,
  permission: `【测试类型：权限测试】
- 目标：验证角色权限控制的正确性
- 要求：识别角色矩阵，验证有权限/无权限/越权场景
- 原则：确保数据隔离和操作权限符合设计`,
  security: `【测试类型：安全测试】
- 目标：关注OWASP Top 10安全风险
- 要求：验证XSS/SQL注入防护、敏感数据保护、认证授权安全
- 原则：确保系统安全性符合行业标准`,
  compatibility: `【测试类型：兼容性测试】
- 目标：验证多设备、多浏览器、多环境的兼容性
- 要求：从需求中提取目标设备/浏览器列表，为每个环境生成独立用例
- 原则：确保用户在不同环境下的体验一致性`
};

// 根据测试类型列表生成提示词片段
const getTestTypePrompt = (testTypes: string[]): string => {
  if (!testTypes || testTypes.length === 0) {
    return TEST_TYPE_PROMPTS['functional'];
  }
  const prompts = testTypes
    .filter(type => type in TEST_TYPE_PROMPTS)
    .map(type => TEST_TYPE_PROMPTS[type]);
  return prompts.length > 0 ? prompts.join('\n\n') : TEST_TYPE_PROMPTS['functional'];
};

const router = useRouter();
const projectStore = useProjectStore();
const aiActivityStore = useAiActivityStore();
const currentProjectId = computed(() => projectStore.currentProjectId || null);

const viewMode = ref<'list' | 'add' | 'edit' | 'view'>('list');
const selectedModuleId = ref<number | null>(null);
const currentEditingTestCaseId = ref<number | null>(null);
const currentViewingTestCaseId = ref<number | null>(null);
const isGenerateCasesModalVisible = ref(false);
const isAddCaseModeModalVisible = ref(false);
const isAppendGenerateModalVisible = ref(false);
const isGeneratingCases = ref(false);
const isExecuteModalVisible = ref(false);
const isOptimizationModalVisible = ref(false);
const pendingExecuteTestCase = ref<TestCase | null>(null);
const pendingOptimizationTestCase = ref<TestCase | null>(null);
const testCaseIdsForNavigation = ref<number[]>([]); // 用于编辑页面导航的用例ID列表

const modulePanelRef = ref<InstanceType<typeof ModuleManagementPanel> | null>(null);
const testCaseListRef = ref<InstanceType<typeof TestCaseList> | null>(null);

// 存储所有模块数据，用于传递给详情页和表单
const allModules = ref<TestCaseModule[]>([]);
const selectedModuleName = computed(() => {
  const target = allModules.value.find((module) => module.id === selectedModuleId.value);
  return target?.name || '';
});
const moduleTreeForForm = ref<TreeNodeData[]>([]); // 用于表单的模块树

const startAutomationTask = (
  requestData: ChatRequest,
  notificationTitle: string,
  notificationContent: string,
  notificationIdPrefix: string,
  footerLinkText: string
) => {
  sendChatMessageStream(
    requestData,
    (sessionId) => {
      localStorage.setItem('langgraph_session_id', sessionId);

      // 保存提示词ID，使LangGraphChatView能恢复选中状态
      if (requestData.prompt_id) {
        localStorage.setItem('flytest_selected_prompt_id', String(requestData.prompt_id));
      }

      // 保存知识库设置，使LangGraphChatView能恢复选中状态
      const knowledgeSettings = {
        useKnowledgeBase: requestData.use_knowledge_base || false,
        selectedKnowledgeBaseId: requestData.knowledge_base_id || null,
        similarityThreshold: 0.3, // 默认值
        topK: 5 // 默认值
      };
      localStorage.setItem('langgraph_knowledge_settings', JSON.stringify(knowledgeSettings));

      const notificationReturn = Notification.info({
        title: notificationTitle,
        content: notificationContent,
        footer: () => h(
          'div',
          {
            style: 'text-align: right; margin-top: 12px;',
          },
          [
            h(
              'a',
              {
                href: 'javascript:;',
                onClick: () => {
                  router.push({ name: 'LangGraphChat' });
                  if (notificationReturn) {
                    notificationReturn.close();
                  }
                },
              },
              footerLinkText
            ),
          ]
        ),
        duration: 10000,
        id: `${notificationIdPrefix}-${sessionId}`,
      });
    }
  );
};

const fetchAllModulesForForm = async () => {
  if (!currentProjectId.value) {
    allModules.value = [];
    moduleTreeForForm.value = [];
    return;
  }
  try {
    const response = await getTestCaseModules(currentProjectId.value, {}); // 获取所有模块
    if (response.success && response.data) {
      allModules.value = response.data;
      moduleTreeForForm.value = buildModuleTree(response.data);
    } else {
      allModules.value = [];
      moduleTreeForForm.value = [];
      console.warn('加载表单模块数据失败:', response.error || '未知错误');
    }
  } catch (error) {
    console.error('加载表单模块数据时发生错误:', error);
    allModules.value = [];
    moduleTreeForForm.value = [];
  }
};

// 构建模块树 (扁平列表转树形) - 这个函数也可以放到 utils 中
const buildModuleTree = (modules: TestCaseModule[], parentId: number | null = null): TreeNodeData[] => {
  return modules
    .filter(module => module.parent === parentId || module.parent_id === parentId)
    .map(module => ({
      key: module.id, // ArcoDesign tree-select 使用 key 作为选中值
      title: module.name, // ArcoDesign tree-select 使用 title 作为显示文本
      id: module.id, // 保留原始id用于兼容
      name: module.name, // 保留原始name用于兼容
      children: buildModuleTree(modules, module.id),
      // selectable: true, // 根据需要设置
    }));
};


const handleModuleSelected = (moduleId: number | null) => {
  selectedModuleId.value = moduleId;
  // 列表组件会自动 watch selectedModuleId 并刷新
};

const handleModuleUpdated = () => {
  // 模块更新后，可能需要刷新模块面板自身（如果它没有自动刷新的话）
  // modulePanelRef.value?.refreshModules(); // 假设 ModuleManagementPanel 有此方法
  // 同时刷新模块数据给表单用
  fetchAllModulesForForm();
  // 如果用例列表依赖模块信息（比如显示模块名），也可能需要刷新用例列表
  // 如需强制刷新用例列表，可在此调用列表刷新方法。
};

const showAddCaseModeModal = () => {
  isAddCaseModeModalVisible.value = true;
};

const handleManualAddSelected = () => {
  isAddCaseModeModalVisible.value = false;
  currentEditingTestCaseId.value = null;
  viewMode.value = 'add';
};

const handleAiAddSelected = () => {
  if (!selectedModuleId.value) {
    Message.warning('请先在左侧选择一个用例模块，再使用 AI 追加生成');
    return;
  }
  isAddCaseModeModalVisible.value = false;
  isAppendGenerateModalVisible.value = true;
};

const showAddTestCaseForm = () => {
  currentEditingTestCaseId.value = null;
  viewMode.value = 'add';
};

const showEditTestCaseForm = (testCaseOrId: TestCase | number) => {
  // 先获取当前筛选后的用例ID列表用于导航（在切换视图之前获取）
  const ids = testCaseListRef.value?.getTestCaseIds();
  testCaseIdsForNavigation.value = ids || [];
  console.log('获取到的用例ID列表:', testCaseIdsForNavigation.value);

  currentEditingTestCaseId.value = typeof testCaseOrId === 'number' ? testCaseOrId : testCaseOrId.id;
  viewMode.value = 'edit';
};

// 处理编辑页面的用例导航
const handleNavigateTestCase = (testCaseId: number) => {
  currentEditingTestCaseId.value = testCaseId;
};

const showViewTestCaseDetail = (testCase: TestCase) => {
  // 获取当前筛选后的用例ID列表用于导航
  const ids = testCaseListRef.value?.getTestCaseIds();
  testCaseIdsForNavigation.value = ids || [];

  currentViewingTestCaseId.value = testCase.id;
  viewMode.value = 'view';
};

// 处理详情页面的用例导航
const handleNavigateViewTestCase = (testCaseId: number) => {
  currentViewingTestCaseId.value = testCaseId;
};

// 处理审核状态变更后刷新导航ID列表并自动跳转
const handleReviewStatusChanged = async () => {
  // 获取当前用例ID（编辑模式或查看模式）
  const currentId = viewMode.value === 'edit'
    ? currentEditingTestCaseId.value
    : currentViewingTestCaseId.value;

  // 获取当前用例在旧列表中的索引
  const oldIndex = currentId ? testCaseIdsForNavigation.value.indexOf(currentId) : -1;

  // 刷新列表数据
  await testCaseListRef.value?.refreshTestCases();

  // 重新获取筛选后的用例ID列表
  const newIds = testCaseListRef.value?.getTestCaseIds() || [];
  testCaseIdsForNavigation.value = newIds;

  // 检查当前用例是否还在新列表中
  if (currentId && !newIds.includes(currentId)) {
    // 当前用例不再符合筛选条件，需要自动跳转
    if (newIds.length === 0) {
      // 没有符合条件的用例了，返回列表
      backToList();
      return;
    }

    // 尝试跳转到原索引位置的用例，如果超出范围则跳到最后一条
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

const handleFormSubmitSuccess = () => {
  backToList();
  testCaseListRef.value?.refreshTestCases(); // 刷新列表
  // 如果用例创建/更新影响了模块的用例数量，需要通知模块面板刷新
  modulePanelRef.value?.refreshModules();
};

const handleTestCaseDeleted = () => {
  // 用例在列表组件内部删除并刷新列表，这里可能需要刷新模块面板的用例计数
  modulePanelRef.value?.refreshModules();
};

const handleViewDetailTestCaseDeleted = () => {
    // 从详情页删除后，返回列表并刷新
    backToList();
    testCaseListRef.value?.refreshTestCases();
    modulePanelRef.value?.refreshModules();
};

const showGenerateCasesModal = () => {
  isGenerateCasesModalVisible.value = true;
};

const startRequirementCaseGenerationJob = async (
  payload: Parameters<typeof generateTestCasesFromRequirement>[1],
  options?: {
    submittingModal?: 'generate' | 'append';
    startLabel?: string;
    startNotification?: {
      title: string;
      content: string;
      duration?: number;
    };
    activityMeta?: {
      mode: 'standard' | 'append';
      targetModuleId: number | null;
    };
  }
) => {
  const restoreSubmitModal = () => {
    if (options?.submittingModal === 'generate') {
      isGenerateCasesModalVisible.value = true;
    }
    if (options?.submittingModal === 'append') {
      isAppendGenerateModalVisible.value = true;
    }
  };

  if (!currentProjectId.value) {
    Message.error('没有有效的项目ID');
    return null;
  }

  if (options?.submittingModal === 'generate') {
    isGenerateCasesModalVisible.value = false;
  }
  if (options?.submittingModal === 'append') {
    isAppendGenerateModalVisible.value = false;
  }

  isGeneratingCases.value = true;
  try {
    try {
      const result = await generateTestCasesFromRequirement(currentProjectId.value, payload);
      if (!result.success) {
        restoreSubmitModal();
        Message.error(result.error || '生成测试用例失败');
        return null;
      }

      if (!result.jobId) {
        restoreSubmitModal();
        Message.error('生成任务创建失败，请稍后重试');
        return null;
      }

      if (options?.startNotification) {
        Notification.info({
          title: options.startNotification.title,
          content: options.startNotification.content,
          duration: options.startNotification.duration ?? 5000,
        });
      }

      aiActivityStore.startGenerationJob(
        currentProjectId.value,
        result.jobId,
        options?.startLabel || 'AI正在生成用例',
        options?.activityMeta
      );

      return result.jobId;
    } catch (error) {
      restoreSubmitModal();
      Message.error(error instanceof Error ? error.message : '生成测试用例失败，请稍后重试');
      return null;
    }
  } finally {
    isGeneratingCases.value = false;
  }
};

const handleAppendGenerateSubmit = async (payload: { extraPrompt: string }) => {
  if (!currentProjectId.value) {
    Message.error('缺少有效的项目ID');
    return;
  }

  if (!selectedModuleId.value) {
    Message.warning('请先选择一个用例模块');
    return;
  }

  await startRequirementCaseGenerationJob(
    {
      test_case_module_id: selectedModuleId.value,
      generate_mode: 'full',
      test_types: ['functional'],
      extra_prompt: payload.extraPrompt,
      append_to_existing: true,
      auto_infer_requirement: true,
    },
    {
      submittingModal: 'append',
      startLabel: 'AI正在生成用例',
      startNotification: {
        title: '正在追加生成测试用例',
        content: '任务已提交到后台，系统会自动带入当前模块需求和已有用例继续生成。',
      },
      activityMeta: {
        mode: 'append',
        targetModuleId: selectedModuleId.value,
      },
    }
  );
};

const resolveGeneratedCount = (payload?: {
  generated_count?: number;
  generatedCount?: number;
  data?: unknown[];
  review_history?: Array<{ generated_count?: number }>;
} | null, fallbackCount?: number) => {
  if (typeof payload?.generated_count === 'number') {
    return payload.generated_count;
  }
  if (typeof payload?.generatedCount === 'number') {
    return payload.generatedCount;
  }
  if (Array.isArray(payload?.data)) {
    return payload.data.length;
  }
  if (Array.isArray(payload?.review_history) && payload.review_history.length > 0) {
    return payload.review_history.reduce((total, item) => total + (item?.generated_count || 0), 0);
  }
  if (typeof fallbackCount === 'number') {
    return fallbackCount;
  }
  return 0;
};

const resolveGeneratedCaseIds = (payload?: { data?: Array<{ id?: number }> } | null) => {
  if (!Array.isArray(payload?.data)) {
    return [];
  }
  return payload.data
    .map((item) => item?.id)
    .filter((id): id is number => typeof id === 'number' && id > 0);
};

const buildGenerationSuccessSummary = (
  payload: {
    message?: string;
    coverage_complete?: boolean;
    review_rounds?: number;
    missing_coverage_points?: string[];
    gaps?: string[];
    skipped_duplicate_names?: string[];
    skipped_duplicate_count?: number;
  } | null | undefined,
  generatedCount: number
) => {
  const summaryParts = [
    generatedCount > 0 ? `???? ${generatedCount} ???` : '?????????',
  ];

  if (typeof payload?.coverage_complete === 'boolean') {
    summaryParts.push(payload.coverage_complete ? 'AI???????' : 'AI???????');
  }

  if (typeof payload?.review_rounds === 'number' && payload.review_rounds > 0) {
    summaryParts.push(`?? ${payload.review_rounds} ?`);
  }

  const missingItems = payload?.missing_coverage_points?.length
    ? payload.missing_coverage_points
    : (payload?.gaps || []);

  if (missingItems && missingItems.length > 0) {
    const preview = missingItems.slice(0, 2).join('?');
    summaryParts.push(`???${preview}${missingItems.length > 2 ? ' ?' : ''}`);
  }

  const skippedDuplicateCount =
    typeof payload?.skipped_duplicate_count === 'number'
      ? payload.skipped_duplicate_count
      : (payload?.skipped_duplicate_names?.length || 0);
  if (skippedDuplicateCount > 0) {
    summaryParts.push(`???? ${skippedDuplicateCount} ?`);
  }

  if (generatedCount === 0 && payload?.message) {
    summaryParts.unshift(payload.message);
  }

  return summaryParts.join('?');
};

const handleGenerateCasesSubmit = async (formData: {
  generateMode: 'full' | 'title_only' | 'kb_complete' | 'kb_generate',
  requirementDocumentId: string,
  requirementModuleId: string,
  promptId: number,
  useKnowledgeBase: boolean,
  knowledgeBaseId?: string | null,
  testCaseModuleId: number,
  selectedDocument?: { id: string, title: string } | null,
  selectedModule: { title: string, content: string },
  selectedTestCaseIds: number[],
  selectedTestCases: TestCase[],
  testTypes: string[],
}) => {
  if (!currentProjectId.value) {
    Message.error('没有有效的项目ID');
    return;
  }

  if (['full', 'title_only'].includes(formData.generateMode)) {
    await startRequirementCaseGenerationJob(
      {
        requirement_document_id: formData.requirementDocumentId,
        requirement_module_id: formData.requirementModuleId,
        test_case_module_id: formData.testCaseModuleId,
        prompt_id: formData.promptId,
        generate_mode: formData.generateMode as 'full' | 'title_only',
        test_types: formData.testTypes,
      },
      {
        submittingModal: 'generate',
        startLabel: 'AI正在生成用例',
        startNotification: {
          title: '正在生成测试用例',
          content: '任务已提交到后台，提示将在 10 秒后自动关闭。生成进度请看页面顶部 AI 在线旁边。',
          duration: 10000,
        },
        activityMeta: {
          mode: 'standard',
          targetModuleId: null,
        },
      }
    );
    return;
  }

  isGenerateCasesModalVisible.value = false;

  let message = '';
  let notificationTitle = '';
  let notificationContent = '';
  let notificationIdPrefix = '';

  // 获取测试类型提示词
  const testTypePrompt = getTestTypePrompt(formData.testTypes);
  const requirementContextBlock = `
【已选需求上下文】
- 需求文档ID: ${formData.requirementDocumentId}
- 需求文档标题: ${formData.selectedDocument?.title || '未命名需求文档'}
- 需求模块ID: ${formData.requirementModuleId}
- 需求模块标题: ${formData.selectedModule?.title || '未命名需求模块'}

[需求模块内容]
${formData.selectedModule?.content || '无'}

【执行要求】
- 上述需求文档和模块内容就是本次生成的唯一需求输入，禁止再次向用户索要需求文档、功能描述、项目背景或模块说明。
- 直接基于已提供内容开始分析和生成。
- 如果发现需求信息存在缺失，只能基于当前内容指出缺口并继续给出可生成的结果，不要先反问用户再继续。
  `.trim();

  switch (formData.generateMode) {
    case 'full':
      // 完整生成模式（原有逻辑）
      message = `
请根据以下需求模块信息，为我生成测试用例。

${testTypePrompt}

${requirementContextBlock}

请注意：生成的测试用例最终需要被保存在 **项目ID "${currentProjectId.value}"** 下的 **测试用例模块ID "${formData.testCaseModuleId}"** 中。
(此需求模块来源于需求文档ID: ${formData.requirementDocumentId})
      `.trim();
      notificationTitle = '生成已开始';
      notificationContent = '用例生成任务已在后台开始处理。';
      notificationIdPrefix = 'gen-case';
      break;

    case 'title_only':
      // 标题生成模式
      message = `
请根据以下需求模块信息，只保存测试用例的标题，禁止生成测试步骤。

${testTypePrompt}

${requirementContextBlock}

请注意：
- 只需要生成用例标题，不需要生成详细的测试步骤和预期结果
- 生成的测试用例最终需要被保存在 **项目ID "${currentProjectId.value}"** 下的 **测试用例模块ID "${formData.testCaseModuleId}"** 中
(此需求模块来源于需求文档ID: ${formData.requirementDocumentId})
      `.trim();
      notificationTitle = '标题生成已开始';
      notificationContent = '用例标题生成任务已在后台开始处理。';
      notificationIdPrefix = 'gen-title';
      break;

    case 'kb_complete':
      // 知识库补全模式（禁止生成，只能从知识库检索）
      message = `
请根据知识库中的相似测试用例，为以下用例补全测试步骤。

【重要约束】
- 只能从知识库中检索相似用例，直接复用其测试步骤
- 严禁自行生成或创造任何步骤内容
- 如果知识库中没有相似用例，请明确告知无法补全，不要自行编造步骤
- 根据用例名称在知识库中检索最相似的用例

[待补全用例列表]
${formData.selectedTestCases.map(tc => `- 用例ID: ${tc.id}, 名称: ${tc.name}, 优先级: ${tc.level}, 模块ID: ${tc.module_id ?? '未分配'}, 模块: ${tc.module_detail || '未分配'}`).join('\n')}

项目ID: ${currentProjectId.value}
      `.trim();
      notificationTitle = '补全已开始';
      notificationContent = '用例补全任务已在后台开始处理。';
      notificationIdPrefix = 'kb-complete';
      break;

    case 'kb_generate':
      // 知识生成模式（基于知识库+需求文档，禁止猜测）
      message = `
请根据知识库和需求文档的知识，为以下用例生成测试步骤并保存对应用例中。

${testTypePrompt}

【重要约束】
- 必须基于知识库和需求文档中的实际内容
- 严禁猜测或假设任何功能行为
- 生成的步骤必须有知识库或需求文档作为依据
- 如果无法从知识库和需求文档中找到相关信息，请明确告知

[待生成步骤的用例列表]
${formData.selectedTestCases.map(tc => `- 用例ID: ${tc.id}, 名称: ${tc.name}, 优先级: ${tc.level}, 模块ID: ${tc.module_id ?? '未分配'}, 模块: ${tc.module_detail || '未分配'}`).join('\n')}

${requirementContextBlock}

项目ID: ${currentProjectId.value}
      `.trim();
      notificationTitle = '知识生成已开始';
      notificationContent = '用例知识生成任务已在后台开始处理。';
      notificationIdPrefix = 'kb-generate';
      break;
  }

  const requestData: ChatRequest = {
    message,
    project_id: String(currentProjectId.value),
    prompt_id: formData.promptId,
    use_knowledge_base: ['full', 'title_only'].includes(formData.generateMode)
      ? formData.useKnowledgeBase
      : ['kb_complete', 'kb_generate'].includes(formData.generateMode),
  };

  // 如果需要知识库，添加知识库ID
  if ((['full', 'title_only'].includes(formData.generateMode) && formData.useKnowledgeBase && formData.knowledgeBaseId) ||
      (['kb_complete', 'kb_generate'].includes(formData.generateMode) && formData.knowledgeBaseId)) {
    requestData.knowledge_base_id = formData.knowledgeBaseId;
  }

  startAutomationTask(
    requestData,
    notificationTitle,
    notificationContent,
    notificationIdPrefix,
    '点此查看生成过程'
  );
};

const handleExecuteTestCase = (testCase: TestCase) => {
  if (!currentProjectId.value) {
    Message.error('缺少有效的项目ID');
    return;
  }
  
  // 保存待执行的用例并显示确认弹窗
  pendingExecuteTestCase.value = testCase;
  isExecuteModalVisible.value = true;
};

const handleExecuteConfirm = (options: { generatePlaywrightScript: boolean }) => {
  const testCase = pendingExecuteTestCase.value;
  if (!testCase || !currentProjectId.value) {
    return;
  }

  const moduleInfo = testCase.module_detail
    ? testCase.module_detail
    : `ID: ${testCase.module_id ?? '未分配'}`;

  const message = `
执行ID为 ${testCase.id} 的测试用例。
你是一名UI自动化测试人员，需要按照用户的指令执行和验证用例。
请调用工具完成以下任务：
1. 读取该测试用例所属项目（ID：${currentProjectId.value}）及模块，定位完整的测试用例定义。
2. 调用工具执行测试用例，并验证相应的断言。
3. 每一步执行后截图，可以单张上传，也可以批量上传。
4. 必须上传截图以供查看。
5. 执行结束后告知用户本次测试是否通过，并总结。

附加信息：
- 测试用例名称：${testCase.name}
- 测试用例等级：${testCase.level}
- 前置条件：${testCase.precondition || '无'}
- 测试用例模块信息：${moduleInfo}
  `.trim();

  const requestData: ChatRequest = {
    message,
    project_id: String(currentProjectId.value),
    use_knowledge_base: false,
    // Playwright 脚本生成参数
    generate_playwright_script: options.generatePlaywrightScript,
    test_case_id: testCase.id,  // 始终传递，用于截图目录隔离
  };

  const notificationContent = options.generatePlaywrightScript
    ? '测试用例执行任务已在后台开始处理，完成后将自动生成 UI 自动化用例。'
    : '测试用例执行任务已在后台开始处理。';

  startAutomationTask(
    requestData,
    '执行已开始',
    notificationContent,
    'exec-case',
    '点此查看执行进度'
  );
  
  pendingExecuteTestCase.value = null;
};

const handleRequestOptimization = (testCase: TestCase) => {
  pendingOptimizationTestCase.value = testCase;
  isOptimizationModalVisible.value = true;
};

const handleOptimizationSubmit = async (data: { testCase: TestCase; suggestion: string }) => {
  if (!currentProjectId.value) {
    Message.error('没有有效的项目ID');
    return;
  }

  // 先更新用例状态为 needs_optimization
  try {
    await updateTestCaseReviewStatus(
      currentProjectId.value,
      data.testCase.id,
      'needs_optimization'
    );
  } catch (error) {
    console.error('更新状态失败:', error);
  }

  // 构建步骤信息
  let stepsText = '无';
  if (data.testCase.steps && data.testCase.steps.length > 0) {
    stepsText = data.testCase.steps.map(step =>
      `  步骤${step.step_number}: ${step.description} → 预期结果: ${step.expected_result}`
    ).join('\n');
  }

  // 构建优化消息
  const message = `
优化以下测试用例。

【重要约束】
- 调用编辑用例工具时必须带上 is_optimization 参数
- 工具返回成功后即表示任务完成，无需再次编辑。

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

  const requestData: ChatRequest = {
    message,
    project_id: String(currentProjectId.value),
    use_knowledge_base: false,
  };

  startAutomationTask(
    requestData,
    '优化已开始',
    '用例优化任务已在后台开始处理。',
    'optimize-case',
    '点此查看优化过程'
  );

  // 刷新列表以显示状态变化
  testCaseListRef.value?.refreshTestCases();
  pendingOptimizationTestCase.value = null;
};

watch(currentProjectId, (newVal) => {
  selectedModuleId.value = null; // 项目切换时清空已选模块
  // 列表和模块面板会各自 watch projectId 并刷新
  if (newVal) {
    fetchAllModulesForForm(); // 项目切换时，重新加载模块给表单
  } else {
    allModules.value = [];
    moduleTreeForForm.value = [];
  }
});

watch(
  () => ({
    jobId: aiActivityStore.generationJob?.job_id || '',
    status: aiActivityStore.generationJob?.status || '',
    projectId: aiActivityStore.generationJobProjectId,
  }),
  async ({ jobId, status, projectId }) => {
    const stateKey = `${jobId}:${status}`;
    if (!jobId || !status || stateKey === aiActivityStore.generationJobHandledStateKey) {
      return;
    }

    if (!currentProjectId.value || !projectId || projectId !== currentProjectId.value) {
      return;
    }

    if (status === 'success') {
      aiActivityStore.markGenerationJobHandled(stateKey);
      viewMode.value = 'list';
      const result = aiActivityStore.generationJob?.result_payload;
      const generatedCaseIds = resolveGeneratedCaseIds(result);
      if (aiActivityStore.generationJobMeta.mode === 'append' && aiActivityStore.generationJobMeta.targetModuleId) {
        await testCaseListRef.value?.resetToFirstPageAndRefresh?.(generatedCaseIds);
      } else {
        await testCaseListRef.value?.showLatestGeneratedCases?.(generatedCaseIds);
      }
      modulePanelRef.value?.refreshModules();

      const generatedCount = resolveGeneratedCount(result, aiActivityStore.generationJob?.generated_count);
      const baseMessage = result?.message || `??? ${generatedCount} ??????`;
      if (result && !result.message) {
        result.message = baseMessage;
      }
      const summaryContent = buildGenerationSuccessSummary(result, generatedCount);
      if (generatedCount === 0) {
        Notification.warning({
          title: '?????????',
          content: summaryContent,
          duration: 7000,
        });
      } else if (result?.coverage_complete === false) {
        Notification.warning({
          title: '???????????????',
          content: summaryContent,
          duration: 7000,
        });
      } else {
        Notification.success({
          title: '????????',
          content: summaryContent,
          duration: 6000,
        });
      }
      return;
    }

    if (status === 'failed') {
      aiActivityStore.markGenerationJobHandled(stateKey);
      Message.error(aiActivityStore.generationJob?.error_message || '测试用例生成失败');
    }
  },
  { deep: true, immediate: true }
);

onMounted(() => {
  if (currentProjectId.value) {
    fetchAllModulesForForm();
  }
});

</script>

<style scoped>
.testcase-management-container {
  display: flex;
  height: 100%;
  background-color: var(--color-bg-1);
  overflow: hidden;
}

.list-view-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
}

@media (max-width: 768px) {
  .list-view-layout {
    flex-direction: column;
  }
}

/* 右侧内容区域样式 */
.right-content-area {
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  padding: 20px; /* 添加内边距，与其他卡片保持一致 */
}

/* 确保右侧内容区域中的所有组件都能正确显示 */
.right-content-area > * {
  flex: 1;
  height: 100%;
  /* 移除子组件自身的阴影、边框和内边距，因为它们现在在右侧内容区域内 */
  box-shadow: none !important;
  border-radius: 0 !important;
  /* 不要用 !important 覆盖 overflow 和 padding，让子组件自行控制滚动 */
}
</style>


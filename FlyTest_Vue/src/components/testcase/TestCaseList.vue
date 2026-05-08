<template>
  <div ref="testcaseContentRef" class="testcase-content">
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          placeholder="搜索用例名称/前置条件"
          allow-clear
          class="search-input"
          @search="onSearch"
          :style="{ width: isSmallScreen ? '70px' : '130px' }"
          v-model="localSearchKeyword"
        />
        <a-select
          v-model="selectedLevel"
          placeholder="优先级"
          allow-clear
          class="level-filter"
          :style="{ width: isSmallScreen ? '90px' : '130px' }"
          @change="onLevelChange"
        >
          <a-option value="P0">{{ isSmallScreen ? 'P0' : 'P0 - 最高' }}</a-option>
          <a-option value="P1">{{ isSmallScreen ? 'P1' : 'P1 - 高' }}</a-option>
          <a-option value="P2">{{ isSmallScreen ? 'P2' : 'P2 - 中' }}</a-option>
          <a-option value="P3">{{ isSmallScreen ? 'P3' : 'P3 - 低' }}</a-option>
        </a-select>
        <a-select
          v-if="showReviewStatus"
          v-model="selectedReviewStatuses"
          placeholder="审核状态"
          multiple
          allow-clear
          :max-tag-count="1"
          tag-nowrap
          class="review-status-filter"
          :style="{ width: '190px' }"
          @change="onReviewStatusChange"
        >
          <a-option v-for="option in REVIEW_STATUS_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </a-option>
        </a-select>
        <a-select
          v-model="selectedTestType"
          placeholder="测试类型"
          allow-clear
          class="test-type-filter"
          :style="{ width: isSmallScreen ? '90px' : '130px' }"
          @change="onTestTypeChange"
        >
          <a-option v-for="option in TEST_TYPE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </a-option>
        </a-select>
        <a-select
          v-model="selectedAssigneeIds"
          placeholder="执行人"
          multiple
          allow-clear
          :max-tag-count="1"
          tag-nowrap
          class="assignee-filter"
          :style="{ width: '220px' }"
          @change="onAssigneeChange"
        >
          <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
            {{ getUserDisplayName(member.user_detail) }}
          </a-option>
        </a-select>
        <a-button type="outline" class="io-btn" @click="handleExport">
          <template #icon>
            <icon-download />
          </template>
          <span class="io-btn-text">导出</span>
        </a-button>
      </div>
      <div class="action-buttons">
        <template v-if="hasSelection">
          <a-button type="primary" status="danger" @click="handleBatchDelete">批量删除</a-button>
          <a-dropdown trigger="click" @select="(value: string) => handleBatchExecutionStatusChange(value as ExecutionStatus)">
            <a-button type="primary">执行状态</a-button>
            <template #content>
              <a-doption v-for="option in EXECUTION_STATUS_OPTIONS" :key="option.value" :value="option.value">
                <a-tag :color="option.color" size="small">{{ option.label }}</a-tag>
              </a-doption>
            </template>
          </a-dropdown>
          <a-button v-if="!isSuiteActionMode" type="primary" @click="openAssignModal(selectedTestCaseIds)">批量分配</a-button>
        </template>
        <template v-else-if="showCreateActions">
          <a-button type="primary" @click="handleGenerateTestCases">生成用例</a-button>
          <a-button type="primary" @click="handleAddTestCase">添加用例</a-button>
        </template>
      </div>
    </div>

    <div v-if="!currentProjectId" class="no-project-selected">
      <a-empty description="请在顶部选择一个项目">
        <template #image>
          <icon-folder style="font-size: 48px; color: #c2c7d0;" />
        </template>
      </a-empty>
    </div>

    <a-table
      v-else
      :columns="columns"
      :data="testCaseData"
      :pagination="paginationConfig"
      column-resizable
      :loading="loading"
      :scroll="tableScroll"
      :row-class="getRowClassName"
      :bordered="{ cell: true }"
      class="test-case-table"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"


    >
      <template #selection="{ record }">
        <div data-checkbox>
          <a-checkbox
            :model-value="record?.id ? selectedTestCaseIds.includes(record.id) : false"
            @change="(checked: boolean) => record?.id && handleCheckboxChange(record.id, checked)"
            @click.stop
          />
        </div>
      </template>
      <template #selectAll>
        <div data-checkbox>
          <a-checkbox
            :model-value="isCurrentPageAllSelected"
            :indeterminate="isCurrentPageIndeterminate"
            @change="handleSelectCurrentPage"
            @click.stop
          />
        </div>
      </template>
      <template #name="{ record }">
        <a-tooltip :content="record.name">
          <span class="testcase-name-link" @click.stop="handleViewTestCase(record)">
            <span v-if="isHighlightedGeneratedCase(record.id)" class="generated-case-badge">新生成</span>
            {{ record.name }}
          </span>
        </a-tooltip>
      </template>
      <template #level="{ record }">
        <a-dropdown v-if="record" trigger="click" @select="(value: string) => handlePriorityChange(record, value)">
          <a-tag :color="getLevelColor(record.level)" style="cursor: pointer;">
            {{ record.level }}
            <icon-down style="margin-left: 4px; font-size: 10px;" />
          </a-tag>
          <template #content>
            <a-doption value="P0">P0</a-doption>
            <a-doption value="P1">P1</a-doption>
            <a-doption value="P2">P2</a-doption>
            <a-doption value="P3">P3</a-doption>
          </template>
        </a-dropdown>
      </template>
      <template #executionStatus="{ record }">
        <a-dropdown v-if="record" trigger="click" @select="(value: string) => handleExecutionStatusChange(record, value as ExecutionStatus)">
          <a-tag :color="getExecutionStatusColor(record.execution_status)" style="cursor: pointer;">
            {{ getExecutionStatusLabel(record.execution_status) }}
            <icon-down style="margin-left: 4px; font-size: 10px;" />
          </a-tag>
          <template #content>
            <a-doption v-for="option in EXECUTION_STATUS_OPTIONS" :key="option.value" :value="option.value">
              <a-tag :color="option.color" size="small">{{ option.label }}</a-tag>
            </a-doption>
          </template>
        </a-dropdown>
      </template>
      <template #testType="{ record }">
        <a-tag v-if="record">{{ getTestTypeLabel(record.test_type) }}</a-tag>
      </template>
      <template #relatedBug="{ record }">
        <span v-if="(record?.related_bug_count || 0) > 0">{{ record.related_bug_count }}</span>
        <span v-else>-</span>
      </template>
      <template v-if="showReviewStatus" #reviewStatus="{ record }">
        <a-dropdown v-if="record" trigger="click" @select="(value: string) => handleReviewStatusChange(record, value)">
          <a-tag
            :color="getReviewStatusColor(record.review_status)"
            style="cursor: pointer;"
          >
            {{ getReviewStatusLabel(record.review_status) }}
            <icon-down style="margin-left: 4px; font-size: 10px;" />
          </a-tag>
          <template #content>
            <a-doption v-for="option in REVIEW_STATUS_OPTIONS" :key="option.value" :value="option.value">
              <a-tag :color="option.color" size="small">{{ option.label }}</a-tag>
            </a-doption>
          </template>
        </a-dropdown>
      </template>
      <template #module="{ record }">
        <span v-if="record?.module_detail">{{ record.module_detail }}</span>
        <span v-else class="text-gray">未分配</span>
      </template>
      <template #operations="{ record }">
        <a-space v-if="record" :size="4">
          <a-button type="primary" size="mini" @click.stop="handleViewTestCase(record)">查看</a-button>
          <a-button type="primary" size="mini" @click.stop="handleEditTestCase(record)">编辑</a-button>
          <a-dropdown
            v-if="isSuiteActionMode"
            trigger="click"
            @select="(value: string) => handleExecutionStatusChange(record, value as ExecutionStatus)"
          >
            <a-button type="outline" size="mini" @click.stop>执行</a-button>
            <template #content>
              <a-doption
                v-for="option in suiteExecuteOptions"
                :key="option.value"
                :value="option.value"
              >
                <a-tag :color="option.color" size="small">{{ option.label }}</a-tag>
              </a-doption>
            </template>
          </a-dropdown>
          <a-button v-else type="outline" size="mini" @click.stop="openAssignModal([record.id])">分配</a-button>
          <a-button type="primary" status="danger" size="mini" @click.stop="handleDeleteTestCase(record)">删除</a-button>
        </a-space>
      </template>
    </a-table>

    <ExportModal
      v-if="currentProjectId"
      ref="exportModalRef"
      :project-id="currentProjectId"
      :selected-ids="selectedTestCaseIds"
      :module-tree="moduleTree"
    />

    <a-modal
      v-model:visible="assignmentModalVisible"
      title="分配测试用例"
      :confirm-loading="assignmentSubmitting"
      @ok="submitAssignment"
      @cancel="closeAssignModal"
    >
      <a-form :model="assignmentForm" layout="vertical">
        <a-form-item field="suiteId" label="测试套件" required>
          <a-select v-model="assignmentForm.suiteId" :loading="assignmentLoading" placeholder="请选择测试套件" allow-search>
            <a-option v-for="suite in testSuites" :key="suite.id" :value="suite.id">
              {{ suite.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="assigneeId" label="执行人" required>
          <a-select v-model="assignmentForm.assigneeId" :loading="assignmentLoading" placeholder="请选择执行人" allow-search>
            <a-option v-for="member in projectMembers" :key="member.id" :value="member.user">
              {{ getUserDisplayName(member.user_detail) }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, watch, toRefs, nextTick } from 'vue';
import axios from 'axios';
import { Message, Modal } from '@arco-design/web-vue';
import { IconFolder, IconDownload, IconDown } from '@arco-design/web-vue/es/icon';
import { useAuthStore } from '@/store/authStore';
import { getUserDisplayName } from '@/utils/userDisplay';
import { API_BASE_URL } from '@/config/api';
import ExportModal from '@/features/testcase-templates/components/ExportModal.vue';
import {
  getTestCaseList,
  deleteTestCase as deleteTestCaseService,
  batchDeleteTestCases,
  updateTestCase,
  updateTestCaseReviewStatus,
  updateTestCaseExecutionStatus,
  batchUpdateTestCaseExecutionStatus,
  type TestCase,
  type ReviewStatus,
  type ExecutionStatus,
} from '@/services/testcaseService';
import { getProjectMembers, type ProjectMember } from '@/services/projectService';
import { getTestSuiteList, type TestSuite } from '@/services/testSuiteService';
import { formatDate, getLevelColor, getReviewStatusLabel, getReviewStatusColor, getTestTypeLabel, getExecutionStatusLabel, getExecutionStatusColor, REVIEW_STATUS_OPTIONS, EXECUTION_STATUS_OPTIONS, TEST_TYPE_OPTIONS } from '@/utils/formatters';
import type { TreeNodeData } from '@arco-design/web-vue';

type TestCaseListItem = TestCase & {
  assignee_detail?: {
    id: number;
    username: string;
  } | null;
};

const props = defineProps<{
  currentProjectId: number | null;
  selectedModuleId?: number | null; // 鍙€夌殑妯″潡ID锛岀敤浜庣瓫閫?
  selectedSuiteId?: number | null;
  moduleTree?: TreeNodeData[]; // 妯″潡鏍戞暟鎹?
  showCreateActions?: boolean;
  showReviewStatus?: boolean;
  actionMode?: 'default' | 'suite';
  timeColumnMode?: 'created' | 'assigned';
}>();

const emit = defineEmits<{
  (e: 'addTestCase'): void;
  (e: 'generate-test-cases'): void;
  (e: 'editTestCase', testCase: TestCase): void;
  (e: 'viewTestCase', testCase: TestCase): void;
  (e: 'testCaseDeleted'): void;
  (e: 'executeTestCase', testCase: TestCase): void;
  (e: 'module-filter-change', moduleId: number | null): void;
  (e: 'requestOptimization', testCase: TestCase): void;
}>();

const { currentProjectId, selectedModuleId, selectedSuiteId } = toRefs(props);
const showCreateActions = computed(() => props.showCreateActions !== false);
const showReviewStatus = computed(() => props.showReviewStatus !== false);
const isSuiteActionMode = computed(() => props.actionMode === 'suite');
const timeColumnMode = computed(() => props.timeColumnMode || 'created');
const suiteExecuteOptions = computed(() =>
  EXECUTION_STATUS_OPTIONS.filter((option) =>
    ['passed', 'failed', 'not_applicable'].includes(option.value)
  )
);

// 鏈湴妯″潡閫夋嫨锛堜笌澶栭儴 selectedModuleId 鍚屾锛?
const localSelectedModuleId = ref<number | null>(props.selectedModuleId || null);
const testcaseContentRef = ref<HTMLElement | null>(null);

const loading = ref(false);
const localSearchKeyword = ref('');
const selectedLevel = ref<string>('');
const selectedTestType = ref<string>('');
const highlightedGeneratedCaseIds = ref<number[]>([]);
const selectedReviewStatuses = ref<ReviewStatus[]>([]);
const selectedAssigneeIds = ref<number[]>([]);
const testCaseData = ref<TestCaseListItem[]>([]);
const selectedTestCaseIds = ref<number[]>([]);
const exportModalRef = ref<InstanceType<typeof ExportModal> | null>(null);
const assignmentModalVisible = ref(false);
const assignmentLoading = ref(false);
const assignmentSubmitting = ref(false);
const assignmentTargetIds = ref<number[]>([]);
const projectMembers = ref<ProjectMember[]>([]);
const testSuites = ref<TestSuite[]>([]);
const assignmentForm = reactive({
  suiteId: undefined as number | undefined,
  assigneeId: undefined as number | undefined,
});
const hasSelection = computed(() => selectedTestCaseIds.value.length > 0);

// 鍝嶅簲寮忓睆骞曞搴︽娴?
const isSmallScreen = ref(window.innerWidth < 1222);
const tableContainerHeight = ref(400); // 榛樿楂樺害
const handleResize = () => {
  isSmallScreen.value = window.innerWidth < 1222;
  // 璁＄畻琛ㄦ牸瀹瑰櫒楂樺害锛氳鍙ｉ珮搴?- 澶撮儴(56) - 杈硅窛(86) - 鎼滅储鏍?60) - 鍒嗛〉(50) - 鍏朵粬闂磋窛(40)
  tableContainerHeight.value = Math.max(300, window.innerHeight - 56 - 86 - 60 - 50 - 40);
};

// 琛ㄦ牸婊氬姩閰嶇疆
const tableScroll = computed(() => ({
  x: 900,
  y: tableContainerHeight.value,
}));

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 50,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
});

// 澶嶉€夋閫夋嫨鐩稿叧鐨勮绠楀睘鎬у拰鏂规硶
// 鑾峰彇褰撳墠椤靛疄闄呮樉绀虹殑鏁版嵁
const getCurrentPageData = () => {
  const startIndex = (paginationConfig.current - 1) * paginationConfig.pageSize;
  const endIndex = startIndex + paginationConfig.pageSize;
  return testCaseData.value.slice(startIndex, endIndex);
};

// 褰撳墠椤垫槸鍚﹀叏閫?
const isCurrentPageAllSelected = computed(() => {
  const currentPageData = getCurrentPageData();
  if (currentPageData.length === 0) return false;
  return currentPageData.every(item => selectedTestCaseIds.value.includes(item.id));
});

// 褰撳墠椤垫槸鍚﹀崐閫夌姸鎬?
const isCurrentPageIndeterminate = computed(() => {
  const currentPageData = getCurrentPageData();
  const currentPageSelectedCount = currentPageData.filter(item =>
    selectedTestCaseIds.value.includes(item.id)
  ).length;
  return currentPageSelectedCount > 0 && currentPageSelectedCount < currentPageData.length;
});

let highlightedCaseTimer: ReturnType<typeof setTimeout> | null = null;

const clearHighlightedGeneratedCases = () => {
  if (highlightedCaseTimer) {
    clearTimeout(highlightedCaseTimer);
    highlightedCaseTimer = null;
  }
  highlightedGeneratedCaseIds.value = [];
};

const highlightGeneratedCases = (ids?: number[]) => {
  clearHighlightedGeneratedCases();
  const normalizedIds = Array.from(
    new Set((ids || []).filter((id): id is number => typeof id === 'number' && id > 0))
  );
  if (normalizedIds.length === 0) {
    return;
  }
  highlightedGeneratedCaseIds.value = normalizedIds;
  void nextTick(() => {
    const firstHighlightedRow = testcaseContentRef.value?.querySelector('.generated-case-row');
    if (firstHighlightedRow instanceof HTMLElement) {
      firstHighlightedRow.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  });
  highlightedCaseTimer = setTimeout(() => {
    highlightedGeneratedCaseIds.value = [];
    highlightedCaseTimer = null;
  }, 12000);
};

const isHighlightedGeneratedCase = (id?: number | null) =>
  typeof id === 'number' && highlightedGeneratedCaseIds.value.includes(id);

const getRowClassName = ({ record }: { record?: TestCase }) =>
  isHighlightedGeneratedCase(record?.id) ? 'generated-case-row' : '';

// 澶勭悊鍗曚釜澶嶉€夋鍙樺寲
const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!selectedTestCaseIds.value.includes(id)) {
      selectedTestCaseIds.value.push(id);
    }
  } else {
    const index = selectedTestCaseIds.value.indexOf(id);
    if (index > -1) {
      selectedTestCaseIds.value.splice(index, 1);
    }
  }
};

// 澶勭悊褰撳墠椤靛叏閫?鍙栨秷鍏ㄩ€?
const handleSelectCurrentPage = (checked: boolean) => {
  // 鑾峰彇褰撳墠琛ㄦ牸瀹為檯鏄剧ず鐨勬暟鎹?
  // Arco Table 浼氭牴鎹?pagination 閰嶇疆鑷姩鍒囧垎鏁版嵁鏄剧ず
  const startIndex = (paginationConfig.current - 1) * paginationConfig.pageSize;
  const endIndex = startIndex + paginationConfig.pageSize;
  const currentPageData = testCaseData.value.slice(startIndex, endIndex);
  
  if (checked) {
    // 閫変腑褰撳墠椤垫墍鏈夐」鐩?
    const currentPageIds = currentPageData.map(item => item.id);
    currentPageIds.forEach(id => {
      if (!selectedTestCaseIds.value.includes(id)) {
        selectedTestCaseIds.value.push(id);
      }
    });
  } else {
    // 鍙栨秷閫変腑褰撳墠椤垫墍鏈夐」鐩?
    const currentPageIds = currentPageData.map(item => item.id);
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id =>
      !currentPageIds.includes(id)
    );
  }
};

const columns = computed(() => {
  const baseColumns = [
  {
    title: '选择',
    slotName: 'selection',
    width: 48,
    dataIndex: 'selection',
    titleSlotName: 'selectAll',
    align: 'center'
  },
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' },
  { title: '用例名称', dataIndex: 'name', slotName: 'name', width: 220, ellipsis: true, tooltip: false, align: 'center' },
  { title: '前置条件', dataIndex: 'precondition', width: 180, ellipsis: true, tooltip: true, align: 'center' },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 100, align: 'center' },
  { title: '执行状态', dataIndex: 'execution_status', slotName: 'executionStatus', width: 130, align: 'center' },
  { title: '测试类型', dataIndex: 'test_type', slotName: 'testType', width: 120, align: 'center' },
  { title: '关联BUG', dataIndex: 'related_bug_count', slotName: 'relatedBug', width: 110, align: 'center' },
  { title: '审核状态', dataIndex: 'review_status', slotName: 'reviewStatus', width: 140, align: 'center' },
  { title: '所属模块', dataIndex: 'module_detail', slotName: 'module', width: 180, ellipsis: true, tooltip: true, align: 'center' },
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestCase }) => getUserDisplayName(record.creator_detail),
    width: 120,
    align: 'center',
  },
  {
    title: '执行人',
    dataIndex: 'assignee_detail',
    render: ({ record }: { record: TestCaseListItem }) => getUserDisplayName(record.assignee_detail, '未分配'),
    width: 120,
    align: 'center',
  },
  {
    title: timeColumnMode.value === 'assigned' ? '分配时间' : '创建时间',
    dataIndex: timeColumnMode.value === 'assigned' ? 'assignment_created_at' : 'created_at',
    render: ({ record }: { record: TestCase }) =>
      formatDate(
        timeColumnMode.value === 'assigned'
          ? (record.assignment_created_at || record.created_at)
          : record.created_at
      ),
    width: 180,
    align: 'center',
  },
  ...(timeColumnMode.value === 'assigned'
    ? [{
        title: '执行时间',
        dataIndex: 'executed_at',
        render: ({ record }: { record: TestCase }) =>
          record.executed_at ? formatDate(record.executed_at) : '-',
        width: 180,
        align: 'center',
      }]
    : []),
  {
    title: '操作',
    dataIndex: 'operations',
    slotName: 'operations',
    width: isSuiteActionMode.value ? 200 : 180,
    fixed: 'right',
    align: 'center'
  },
  {
    title: '',
    dataIndex: '__tail__',
    width: 8,
    fixed: 'right',
    align: 'center',
    render: () => '',
    headerCellClass: 'resize-tail-column',
    cellClass: 'resize-tail-column',
  },
  ];

  if (!showReviewStatus.value) {
    return baseColumns.filter((column) => column.dataIndex !== 'review_status' && column.slotName !== 'reviewStatus');
  }

  return baseColumns;
});

const hasUnapprovedSelection = (ids: number[]) => {
  const selectedCases = testCaseData.value.filter((item) => ids.includes(item.id));
  return selectedCases.some((item) => item.review_status !== 'approved');
};

const loadAssignmentOptions = async () => {
  if (!currentProjectId.value) {
    return;
  }
  assignmentLoading.value = true;
  try {
    const [membersResponse, suitesResponse] = await Promise.all([
      getProjectMembers(currentProjectId.value),
      getTestSuiteList(currentProjectId.value),
    ]);

    if (!membersResponse.success || !membersResponse.data) {
      throw new Error(membersResponse.error || '获取项目成员失败');
    }
    if (!suitesResponse.success || !suitesResponse.data) {
      throw new Error(suitesResponse.error || '获取测试套件失败');
    }

    projectMembers.value = membersResponse.data;
    testSuites.value = suitesResponse.data;
  } finally {
    assignmentLoading.value = false;
  }
};

const loadProjectMembersForFilter = async () => {
  if (!currentProjectId.value) {
    projectMembers.value = [];
    return;
  }

  const response = await getProjectMembers(currentProjectId.value);
  if (!response.success || !response.data) {
    throw new Error(response.error || '获取项目成员失败');
  }

  projectMembers.value = response.data;
};

const assignTestCasesRequest = async (projectId: number, payload: { ids: number[]; suite_id: number; assignee_id: number }) => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;
  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/projects/${projectId}/testcases/batch-assign/`,
      payload,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
      }
    );

    if (response.data && (response.data.success || response.data.status === 'success')) {
      return {
        success: true,
        message: response.data.message || '测试用例分配成功',
      };
    }

    return {
      success: false,
      error: response.data?.error || response.data?.message || '测试用例分配失败',
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.response?.data?.error || error.response?.data?.message || error.message || '测试用例分配失败',
    };
  }
};

const openAssignModal = async (ids: number[]) => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  const normalizedIds = Array.from(new Set(ids.filter((id) => typeof id === 'number' && id > 0)));
  if (normalizedIds.length === 0) {
    Message.warning('请先选择要分配的测试用例');
    return;
  }
  if (hasUnapprovedSelection(normalizedIds)) {
    Message.warning('只有审核状态为“通过”的测试用例才能分配');
    return;
  }
  assignmentTargetIds.value = normalizedIds;
  assignmentForm.suiteId = undefined;
  assignmentForm.assigneeId = undefined;
  assignmentModalVisible.value = true;
  try {
    await loadAssignmentOptions();
  } catch (error) {
    assignmentModalVisible.value = false;
    Message.error(error instanceof Error ? error.message : '加载分配选项失败');
  }
};

const closeAssignModal = () => {
  assignmentModalVisible.value = false;
  assignmentTargetIds.value = [];
};

const submitAssignment = async () => {
  if (!currentProjectId.value) {
    return;
  }
  if (!assignmentForm.suiteId) {
    Message.warning('请选择测试套件');
    return;
  }
  if (!assignmentForm.assigneeId) {
    Message.warning('请选择执行人');
    return;
  }
  if (hasUnapprovedSelection(assignmentTargetIds.value)) {
    Message.warning('只有审核状态为“通过”的测试用例才能分配');
    return;
  }

  assignmentSubmitting.value = true;
  try {
    const response = await assignTestCasesRequest(currentProjectId.value, {
      ids: assignmentTargetIds.value,
      suite_id: assignmentForm.suiteId,
      assignee_id: assignmentForm.assigneeId,
    });
    if (!response.success) {
      Message.error(response.error || '测试用例分配失败');
      return;
    }
    Message.success(response.message || '测试用例分配成功');
    selectedTestCaseIds.value = [];
    closeAssignModal();
    await fetchTestCases();
  } finally {
    assignmentSubmitting.value = false;
  }
};

const handlePriorityChange = async (record: TestCase, newLevel: string) => {
  if (!currentProjectId.value || !newLevel || newLevel === record.level) {
    return;
  }
  const response = await updateTestCase(currentProjectId.value, record.id, { level: newLevel });
  if (!response.success || !response.data) {
    Message.error(response.error || '更新优先级失败');
    return;
  }
  const index = testCaseData.value.findIndex((item) => item.id === record.id);
  if (index !== -1) {
    testCaseData.value[index].level = response.data.level;
  }
  Message.success('优先级更新成功');
};

const handleExecutionStatusChange = async (record: TestCase, newStatus: ExecutionStatus) => {
  if (!currentProjectId.value || !newStatus || newStatus === record.execution_status) {
    return;
  }
  const response = await updateTestCaseExecutionStatus(currentProjectId.value, record.id, newStatus);
  if (!response.success || !response.data) {
    Message.error(response.error || '更新执行状态失败');
    return;
  }
  const index = testCaseData.value.findIndex((item) => item.id === record.id);
  if (index !== -1) {
    testCaseData.value[index].execution_status = response.data.execution_status;
    testCaseData.value[index].executed_at = response.data.executed_at ?? testCaseData.value[index].executed_at ?? null;
  }
  Message.success('执行状态更新成功');
};

const handleBatchExecutionStatusChange = async (newStatus: ExecutionStatus) => {
  if (!currentProjectId.value) {
    return;
  }
  if (!selectedTestCaseIds.value.length) {
    Message.warning('请先选择测试用例');
    return;
  }

  const response = await batchUpdateTestCaseExecutionStatus(
    currentProjectId.value,
    selectedTestCaseIds.value,
    newStatus,
  );
  if (!response.success) {
    Message.error(response.error || '批量更新执行状态失败');
    return;
  }

  await fetchTestCases();
  Message.success(response.message || '批量更新执行状态成功');
};

const fetchTestCases = async () => {
  if (!currentProjectId.value) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    selectedTestCaseIds.value = []; // 娓呯┖閫変腑鐘舵€?
    return;
  }
  loading.value = true;
  try {
    const response = await getTestCaseList(currentProjectId.value, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: localSearchKeyword.value,
      module_id: localSelectedModuleId.value || undefined, // 浣跨敤鏈湴妯″潡绛涢€?
      suite_id: selectedSuiteId?.value || undefined,
      level: selectedLevel.value || undefined, // 娣诲姞浼樺厛绾х瓫閫?
      test_type: selectedTestType.value || undefined, // 娣诲姞娴嬭瘯绫诲瀷绛涢€?
      // 澶氶€夊鏍哥姸鎬佺瓫閫夛細鏈夐€変腑椤瑰垯浼犻€掞紝鍚﹀垯涓嶉檺鍒讹紙鏄剧ず鍏ㄩ儴锛?
      review_status_in: selectedReviewStatuses.value.length > 0 ? selectedReviewStatuses.value : undefined,
      assignee_id_in: selectedAssigneeIds.value.length > 0 ? selectedAssigneeIds.value : undefined,
    });
    if (response.success && response.data) {
      testCaseData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
      // 娓呯┖涔嬪墠椤甸潰鐨勯€変腑鐘舵€?
      selectedTestCaseIds.value = [];
    } else {
      Message.error(response.error || '鑾峰彇娴嬭瘯鐢ㄤ緥鍒楄〃澶辫触');
      testCaseData.value = [];
      paginationConfig.total = 0;
      selectedTestCaseIds.value = [];
    }
  } catch (error) {
    console.error('鑾峰彇娴嬭瘯鐢ㄤ緥鍒楄〃鍑洪敊:', error);
    Message.error('获取测试用例列表时发生错误');
    testCaseData.value = [];
    paginationConfig.total = 0;
    selectedTestCaseIds.value = [];
  } finally {
    loading.value = false;
  }
};

const onSearch = (value: string) => {
  clearHighlightedGeneratedCases();
  localSearchKeyword.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onLevelChange = (value: string) => {
  clearHighlightedGeneratedCases();
  selectedLevel.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onReviewStatusChange = (value: ReviewStatus[]) => {
  clearHighlightedGeneratedCases();
  selectedReviewStatuses.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onTestTypeChange = (value: string) => {
  clearHighlightedGeneratedCases();
  selectedTestType.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onAssigneeChange = (value: number[]) => {
  clearHighlightedGeneratedCases();
  selectedAssigneeIds.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleReviewStatusChange = async (record: TestCase, newStatus: string) => {
  if (!currentProjectId.value) return;

  // 濡傛灉閫夋嫨"浼樺寲"锛岃Е鍙戜紭鍖栧脊绐?
  if (newStatus === 'needs_optimization') {
    emit('requestOptimization', record);
    return;
  }

  // 鍏朵粬鐘舵€佺洿鎺ユ洿鏂?
  try {
    const response = await updateTestCaseReviewStatus(
      currentProjectId.value,
      record.id,
      newStatus as ReviewStatus
    );
    if (response.success) {
      Message.success('状态更新成功');
      // 鏇存柊鏈湴鏁版嵁
      const index = testCaseData.value.findIndex(tc => tc.id === record.id);
      if (index !== -1) {
        testCaseData.value[index].review_status = newStatus as ReviewStatus;
      }
    } else {
      Message.error(response.error || '状态更新失败');
    }
  } catch (error) {
    Message.error('状态更新时发生错误');
  }
};

const onPageChange = (page: number) => {
  clearHighlightedGeneratedCases();
  paginationConfig.current = page;
  fetchTestCases();
};

const onPageSizeChange = (pageSize: number) => {
  clearHighlightedGeneratedCases();
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleAddTestCase = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  emit('addTestCase');
};

const handleGenerateTestCases = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  emit('generate-test-cases');
};

const handleViewTestCase = (testCase: TestCase) => {
  emit('viewTestCase', testCase);
};

const handleEditTestCase = (testCase: TestCase) => {
  emit('editTestCase', testCase);
};

const handleDeleteTestCase = (testCase: TestCase) => {
  if (!currentProjectId.value) return;
  Modal.warning({
    title: '确认删除',
    content: `确定要删除测试用例“${testCase.name}”吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteTestCaseService(currentProjectId.value!, testCase.id);
        if (response.success) {
          Message.success('测试用例删除成功');
          fetchTestCases(); // 閲嶆柊鍔犺浇鍒楄〃
          emit('testCaseDeleted');
        } else {
          Message.error(response.error || '删除测试用例失败');
        }
      } catch (error) {
        Message.error('删除测试用例时发生错误');
      }
    },
  });
};

// 鎵归噺鍒犻櫎澶勭悊鍑芥暟
const handleBatchDelete = () => {
  if (!currentProjectId.value || selectedTestCaseIds.value.length === 0) return;

  // 鑾峰彇閫変腑鐨勬祴璇曠敤渚嬩俊鎭敤浜庢樉绀?
  const selectedTestCases = testCaseData.value.filter(testCase =>
    selectedTestCaseIds.value.includes(testCase.id)
  );

  const testCaseNames = selectedTestCases.map(tc => tc.name).join('、');
  const displayNames = testCaseNames.length > 100 ?
    testCaseNames.substring(0, 100) + '...' : testCaseNames;

  Modal.warning({
    title: '确认批量删除',
    content: `确定要删除以下 ${selectedTestCaseIds.value.length} 个测试用例吗？此操作不可恢复。\n\n${displayNames}`,
    okText: '确认删除',
    cancelText: '取消',
    width: 500,
    onOk: async () => {
      try {
        const response = await batchDeleteTestCases(currentProjectId.value!, selectedTestCaseIds.value);
        if (response.success && response.data) {
          // 鏄剧ず璇︾粏鐨勫垹闄ょ粨鏋?
          const { deleted_count, deletion_details } = response.data;

          let detailMessage = `成功删除 ${deleted_count} 个测试用例`;
          if (deletion_details) {
            const details = Object.entries(deletion_details)
              .map(([key, count]) => `${key}: ${count}`)
              .join(', ');
            detailMessage += `\n删除详情: ${details}`;
          }

          Message.success(detailMessage);

          // 娓呯┖閫変腑鐘舵€佸苟閲嶆柊鍔犺浇鍒楄〃
          selectedTestCaseIds.value = [];
          fetchTestCases();
          emit('testCaseDeleted');
        } else {
          Message.error(response.error || '批量删除测试用例失败');
        }
      } catch (error) {
        console.error('鎵归噺鍒犻櫎娴嬭瘯鐢ㄤ緥鍑洪敊:', error);
        Message.error('批量删除测试用例时发生错误');
      }
    },
  });
};



// 瀵煎嚭澶勭悊鍑芥暟
const handleExport = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  exportModalRef.value?.open();
};

onMounted(() => {
  handleResize(); // 鍒濆鍖栬〃鏍奸珮搴?
  fetchTestCases();
  void loadProjectMembersForFilter();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  clearHighlightedGeneratedCases();
});

watch(currentProjectId, () => {
  clearHighlightedGeneratedCases();
  paginationConfig.current = 1;
  localSearchKeyword.value = '';
  selectedLevel.value = ''; // 椤圭洰鍒囨崲鏃舵竻绌轰紭鍏堢骇绛涢€?
  selectedTestType.value = ''; // 椤圭洰鍒囨崲鏃舵竻绌烘祴璇曠被鍨嬬瓫閫?
  selectedReviewStatuses.value = [];
  selectedAssigneeIds.value = [];
  void loadProjectMembersForFilter();
  fetchTestCases();
});

// 鐩戝惉澶栭儴妯″潡閫夋嫨鍙樺寲锛堟潵鑷乏渚фā鍧楃鐞嗛潰鏉匡級
watch(selectedModuleId, (newVal) => {
  if (newVal !== localSelectedModuleId.value) {
    clearHighlightedGeneratedCases();
    localSelectedModuleId.value = newVal || null;
    paginationConfig.current = 1;
    fetchTestCases();
  }
});

watch(selectedSuiteId, () => {
  clearHighlightedGeneratedCases();
  paginationConfig.current = 1;
  fetchTestCases();
});

// 鏆撮湶缁欑埗缁勪欢鐨勬柟娉?
defineExpose({
  refreshTestCases: async (generatedIds?: number[]) => {
    await fetchTestCases();
    highlightGeneratedCases(generatedIds);
  },
  resetToFirstPageAndRefresh: async (generatedIds?: number[]) => {
    paginationConfig.current = 1;
    await fetchTestCases();
    highlightGeneratedCases(generatedIds);
  },
  showLatestGeneratedCases: async (generatedIds?: number[]) => {
    paginationConfig.current = 1;
    localSearchKeyword.value = '';
    selectedLevel.value = '';
    selectedTestType.value = '';
    selectedReviewStatuses.value = [];
    selectedAssigneeIds.value = [];
    localSelectedModuleId.value = null;
    await fetchTestCases();
    highlightGeneratedCases(generatedIds);
  },
  // 鑾峰彇褰撳墠绛涢€夊悗鐨勭敤渚婭D鍒楄〃锛堢敤浜庣紪杈戦〉闈㈠鑸級
  getTestCaseIds: () => testCaseData.value.map(tc => tc.id),
});

</script>

<style scoped>
.testcase-content {
  flex: 1;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(var(--arcoblue-1), 0.08));
  border: 1px solid var(--ui-panel-border, var(--color-neutral-3));
  border-radius: var(--ui-radius-lg, 12px);
  padding: 18px;
  box-shadow: var(--ui-panel-shadow, 0 10px 24px rgba(15, 23, 42, 0.08));
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--ui-toolbar-border, var(--color-neutral-3));
  border-radius: var(--ui-radius-md, 10px);
  background: var(--ui-toolbar-bg, var(--color-fill-1));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.search-box {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
  overflow: hidden;
}

.search-box > * {
  margin-left: 0 !important;
  flex-shrink: 1;
}

.action-buttons {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  flex-shrink: 0;
}

.action-buttons > * {
  margin-right: 0 !important;
}

.search-input {
  width: 200px;
  min-width: 120px;
  flex-shrink: 1;
}

.level-filter {
  flex-shrink: 1;
}

.review-status-filter {
  width: 10px;
  flex-shrink: 0;
}

.test-type-filter {
  flex-shrink: 1;
}

.assignee-filter {
  flex-shrink: 0;
}

.review-status-filter :deep(.arco-select-view-multiple) {
  flex-wrap: nowrap;
  overflow: hidden;
}

/* 瀵煎叆瀵煎嚭鎸夐挳鍝嶅簲寮?*/
.io-btn {
  flex-shrink: 0;
}

@media (max-width: 1200px) {
  .io-btn-text {
    display: none;
  }
  .io-btn {
    width: 32px;
    padding: 0;
  }
  .io-btn :deep(.arco-btn-icon) {
    margin-right: 0;
  }
}

.no-project-selected {
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100% - 60px); /* 鍑忓幓澶撮儴楂樺害 */
  flex-grow: 1;
}

.test-case-table {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
}

:deep(.test-case-table .arco-table) {
  width: 100%;
  border-radius: 14px;
  overflow: hidden;
}

:deep(.test-case-table .arco-table-content-scroll) {
  overflow-x: auto !important;
}

:deep(.test-case-table .resize-tail-column) {
  padding: 0 !important;
  border-left: none !important;
  border-right: none !important;
  background: transparent !important;
}

.text-gray {
  color: #86909c;
}

:deep(.test-case-table .arco-table-td) {
  white-space: nowrap;
}

:deep(.test-case-table .arco-table-container) {
  height: 100% !important;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

/* 寮哄埗鏄剧ず鍗曞厓鏍间笅杈规 */
:deep(.test-case-table .arco-table-td) {
  border-bottom: 1px solid var(--color-neutral-3) !important;
}

:deep(.test-case-table .arco-table-header) {
  flex-shrink: 0;
  background: #f8fafc;
}

:deep(.test-case-table .arco-table-body) {
  flex: 1;
  min-height: 0;
  padding-bottom: 16px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.45) transparent;
}

:deep(.test-case-table .arco-table-body::-webkit-scrollbar) {
  width: 8px;
  height: 8px;
}

:deep(.test-case-table .arco-table-body::-webkit-scrollbar-thumb) {
  background: rgba(148, 163, 184, 0.45);
  border-radius: 999px;
}

:deep(.test-case-table .arco-pagination) {
  flex-shrink: 0;
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  position: sticky;
  bottom: 16px;
  background-color: rgba(255, 255, 255, 0.96);
  z-index: 1;
  padding: 10px 0 2px;
  box-shadow: 0 -6px 14px rgba(15, 23, 42, 0.04);
}

:deep(.test-case-table .arco-table-cell-fixed-right) {
  padding: 6px 4px;
}

:deep(.test-case-table .arco-space-compact) {
  display: flex;
  flex-wrap: nowrap;
}

:deep(.test-case-table .arco-btn-size-mini) {
  padding: 0 6px;
  font-size: 12px;
  min-width: 36px;
}

/* 鍕鹃€夋灞呬腑鏄剧ず */
:deep(.test-case-table [data-checkbox]) {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

.testcase-name-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  color: rgb(var(--arcoblue-6));
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.testcase-name-link:hover {
  color: rgb(var(--arcoblue-5));
  text-decoration: underline;
}

.generated-case-badge {
  display: inline-flex;
  align-items: center;
  padding: 0 6px;
  min-height: 20px;
  border-radius: 999px;
  border: 1px solid #b7e4c7;
  background: #e8f7e9;
  color: #1f8f46;
  font-size: 12px;
  line-height: 20px;
  font-weight: 600;
  flex-shrink: 0;
}

:deep(.test-case-table .generated-case-row td) {
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.92), rgba(236, 253, 245, 0.92));
}

:deep(.test-case-table .arco-table-th) {
  color: #475569;
  font-weight: 600;
}

:deep(.test-case-table .arco-select-view),
:deep(.test-case-table .arco-input-wrapper),
:deep(.test-case-table .arco-btn) {
  border-radius: 10px;
}

/* 绉婚櫎閲嶅鐨勬牱寮忓畾涔?*/
</style>

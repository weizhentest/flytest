<template>
  <div class="bug-panel">
    <div class="bug-panel-header">
      <div class="bug-panel-heading">
        <div class="bug-panel-title">BUG管理</div>
        <div class="bug-panel-subtitle">按禅道式流转管理当前套件中的缺陷，优先处理激活状态与高优先级问题。</div>
      </div>

      <div class="bug-panel-actions">
        <a-button @click="fetchBugs">刷新</a-button>
        <a-button type="primary" @click="openCreateModal">提 Bug</a-button>
      </div>
    </div>

    <div class="bug-status-grid">
      <button
        v-for="item in statusCards"
        :key="item.key"
        type="button"
        class="status-card"
        :class="{ 'status-card--active': activeStatusView === item.key }"
        @click="activeStatusView = item.key"
      >
        <span class="status-card-label">{{ item.label }}</span>
        <span class="status-card-value">{{ item.count }}</span>
      </button>
    </div>

    <div class="bug-toolbar">
      <div class="quick-view-list">
        <button
          v-for="item in quickViews"
          :key="item.key"
          type="button"
          class="quick-view-item"
          :class="{ 'quick-view-item--active': activeQuickView === item.key }"
          @click="activeQuickView = item.key"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="bug-filter-grid">
        <a-input-search
          v-model="filters.search"
          placeholder="搜索标题、重现步骤、实际结果"
          allow-clear
          class="bug-filter-search"
          @search="fetchBugs"
          @clear="fetchBugs"
        />

        <a-select
          v-model="filters.bug_type"
          placeholder="类型"
          allow-clear
          @change="handleFilterChange"
          @clear="handleFilterChange"
        >
          <a-option v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
            {{ item.label }}
          </a-option>
        </a-select>

        <a-select
          v-model="filters.severity"
          placeholder="严重程度"
          allow-clear
          @change="handleFilterChange"
          @clear="handleFilterChange"
        >
          <a-option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</a-option>
        </a-select>

        <a-select
          v-model="filters.priority"
          placeholder="优先级"
          allow-clear
          @change="handleFilterChange"
          @clear="handleFilterChange"
        >
          <a-option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</a-option>
        </a-select>

        <a-select
          v-model="filters.assigned_to"
          placeholder="指派给"
          allow-clear
          @change="handleFilterChange"
          @clear="handleFilterChange"
        >
          <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
            {{ member.user_detail.username }}
          </a-option>
        </a-select>

        <a-button type="outline" @click="resetFilters">重置筛选</a-button>
      </div>
    </div>

    <div class="bug-summary-bar">
      <span>当前视图共 {{ filteredBugList.length }} 条 BUG</span>
      <span v-if="activeStatusView !== 'all'">状态：{{ getStatusViewLabel(activeStatusView) }}</span>
      <span v-if="activeQuickView !== 'all'">视图：{{ getQuickViewLabel(activeQuickView) }}</span>
    </div>

    <a-table
      :data="pagedBugList"
      :loading="loading"
      :pagination="false"
      row-key="id"
      class="bug-table"
      :scroll="{ x: 1560, y: 420 }"
      :bordered="{ cell: true }"
      column-resizable
    >
      <a-table-column title="ID" data-index="id" :width="72" align="center" />

      <a-table-column title="Bug标题" :width="280">
        <template #cell="{ record }">
          <a-link @click="openDetail(record)">{{ record.title }}</a-link>
        </template>
      </a-table-column>

      <a-table-column title="关联用例" data-index="testcase_name" :width="180" ellipsis tooltip />

      <a-table-column title="类型" :width="120" align="center">
        <template #cell="{ record }">{{ record.bug_type_display || '-' }}</template>
      </a-table-column>

      <a-table-column title="严重程度" :width="96" align="center">
        <template #cell="{ record }">
          <a-tag :color="getSeverityColor(record.severity)">S{{ record.severity }}</a-tag>
        </template>
      </a-table-column>

      <a-table-column title="优先级" :width="96" align="center">
        <template #cell="{ record }">
          <a-tag :color="getPriorityColor(record.priority)">P{{ record.priority }}</a-tag>
        </template>
      </a-table-column>

      <a-table-column title="状态" :width="110" align="center">
        <template #cell="{ record }">
          <a-tag :color="getStatusColor(record.status)">{{ record.status_display || record.status }}</a-tag>
        </template>
      </a-table-column>

      <a-table-column title="解决方案" :width="120" align="center">
        <template #cell="{ record }">{{ record.resolution_display || '-' }}</template>
      </a-table-column>

      <a-table-column title="指派给" :width="120" align="center">
        <template #cell="{ record }">{{ getAssignedUserName(record) }}</template>
      </a-table-column>

      <a-table-column title="创建人" :width="120" align="center">
        <template #cell="{ record }">{{ getCreatorName(record) }}</template>
      </a-table-column>

      <a-table-column title="创建时间" :width="166" align="center">
        <template #cell="{ record }">{{ formatDate(record.opened_at) }}</template>
      </a-table-column>

      <a-table-column title="解决时间" :width="166" align="center">
        <template #cell="{ record }">{{ record.resolved_at ? formatDate(record.resolved_at) : '-' }}</template>
      </a-table-column>

      <a-table-column title="操作" :width="260" fixed="right" align="center">
        <template #cell="{ record }">
          <a-space :size="4">
            <a-button size="mini" @click="openDetail(record)">查看</a-button>
            <a-button size="mini" type="primary" @click="openEditModal(record)">编辑</a-button>
            <a-dropdown trigger="click" @select="(value) => handleActionSelect(record, String(value))">
              <a-button size="mini" type="outline">更多</a-button>
              <template #content>
                <a-doption value="assign">指派</a-doption>
                <a-doption v-if="record.status === 'active'" value="resolve">解决</a-doption>
                <a-doption v-if="record.status !== 'active'" value="activate">激活</a-doption>
                <a-doption value="close" :disabled="record.status === 'closed'">关闭</a-doption>
                <a-doption value="delete">删除</a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table-column>
    </a-table>

    <div class="bug-pagination">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :total="filteredBugList.length"
        :page-size-options="[10, 20, 50, 100]"
        show-total
        show-page-size
      />
    </div>

    <a-modal
      v-model:visible="formVisible"
      :title="editingBug ? '编辑 Bug' : '提 Bug'"
      :confirm-loading="submitting"
      width="920px"
      @ok="submitBug"
    >
      <a-form :model="formState" layout="vertical">
        <div class="bug-form-section">
          <div class="bug-form-section-title">基本信息</div>
          <div class="bug-form-grid">
            <a-form-item field="title" label="Bug标题" required class="bug-form-full">
              <a-input v-model="formState.title" />
            </a-form-item>

            <a-form-item field="testcase" label="关联测试用例">
              <a-select v-model="formState.testcase" allow-clear placeholder="请选择当前套件中的测试用例">
                <a-option v-for="item in suiteTestCases" :key="item.id" :value="item.id">{{ item.name }}</a-option>
              </a-select>
            </a-form-item>

            <a-form-item field="assigned_to" label="指派给">
              <a-select v-model="formState.assigned_to" allow-clear placeholder="请选择处理人">
                <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
                  {{ member.user_detail.username }}
                </a-option>
              </a-select>
            </a-form-item>

            <a-form-item field="bug_type" label="Bug类型" required>
              <a-select v-model="formState.bug_type">
                <a-option v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-option>
              </a-select>
            </a-form-item>

            <a-form-item field="severity" label="严重程度" required>
              <a-select v-model="formState.severity">
                <a-option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</a-option>
              </a-select>
            </a-form-item>

            <a-form-item field="priority" label="优先级" required>
              <a-select v-model="formState.priority">
                <a-option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</a-option>
              </a-select>
            </a-form-item>

            <a-form-item field="deadline" label="截止日期">
              <a-date-picker v-model="formState.deadline" value-format="YYYY-MM-DD" style="width: 100%;" />
            </a-form-item>

            <a-form-item field="keywords" label="关键词" class="bug-form-full">
              <a-input v-model="formState.keywords" placeholder="多个关键词可用空格分隔" />
            </a-form-item>
          </div>
        </div>

        <div class="bug-form-section">
          <div class="bug-form-section-title">重现与结果</div>
          <div class="bug-form-grid">
            <a-form-item field="steps" label="重现步骤" class="bug-form-full">
              <a-textarea v-model="formState.steps" :auto-size="{ minRows: 4, maxRows: 8 }" />
            </a-form-item>

            <a-form-item field="expected_result" label="期望结果" class="bug-form-full">
              <a-textarea v-model="formState.expected_result" :auto-size="{ minRows: 3, maxRows: 6 }" />
            </a-form-item>

            <a-form-item field="actual_result" label="实际结果" class="bug-form-full">
              <a-textarea v-model="formState.actual_result" :auto-size="{ minRows: 3, maxRows: 6 }" />
            </a-form-item>
          </div>
        </div>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="actionVisible"
      :title="actionModalTitle"
      :confirm-loading="actionSubmitting"
      width="560px"
      @ok="submitAction"
      @cancel="resetActionState"
    >
      <a-form :model="actionForm" layout="vertical">
        <template v-if="actionType === 'assign'">
          <a-form-item field="assigned_to" label="指派给" required>
            <a-select v-model="actionForm.assigned_to" placeholder="请选择项目成员">
              <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
                {{ member.user_detail.username }}
              </a-option>
            </a-select>
          </a-form-item>
        </template>

        <template v-else-if="actionType === 'resolve'">
          <a-form-item field="resolution" label="解决方案" required>
            <a-select v-model="actionForm.resolution">
              <a-option v-for="item in TEST_BUG_RESOLUTION_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="solution" label="解决备注">
            <a-textarea v-model="actionForm.solution" :auto-size="{ minRows: 4, maxRows: 8 }" />
          </a-form-item>
        </template>

        <template v-else-if="actionType === 'close'">
          <a-form-item field="solution" label="关闭备注">
            <a-textarea
              v-model="actionForm.solution"
              placeholder="请填写关闭原因或说明"
              :auto-size="{ minRows: 4, maxRows: 8 }"
            />
          </a-form-item>
        </template>

        <template v-else-if="actionType === 'activate'">
          <div class="action-confirm-tip">将重新激活当前 BUG，并保留已有解决记录供后续追踪。</div>
        </template>
      </a-form>
    </a-modal>

    <a-drawer v-model:visible="detailVisible" width="680px" :footer="false" title="Bug详情">
      <a-spin :loading="detailLoading" style="width: 100%;">
        <template v-if="detailBug">
          <div class="bug-detail">
            <div class="bug-detail-header">
              <div class="bug-detail-title">{{ detailBug.title }}</div>
              <div class="bug-detail-tags">
                <a-tag :color="getStatusColor(detailBug.status)">{{ detailBug.status_display || detailBug.status }}</a-tag>
                <a-tag :color="getSeverityColor(detailBug.severity)">S{{ detailBug.severity }}</a-tag>
                <a-tag :color="getPriorityColor(detailBug.priority)">P{{ detailBug.priority }}</a-tag>
                <a-tag color="blue">{{ detailBug.bug_type_display || '-' }}</a-tag>
              </div>
            </div>

            <div class="bug-detail-section">
              <div class="bug-detail-section-title">基本信息</div>
              <div class="bug-detail-grid">
                <div><strong>所属套件：</strong>{{ detailBug.suite_name || '-' }}</div>
                <div><strong>关联用例：</strong>{{ detailBug.testcase_name || '-' }}</div>
                <div><strong>指派给：</strong>{{ getAssignedUserName(detailBug) }}</div>
                <div><strong>创建人：</strong>{{ getCreatorName(detailBug) }}</div>
                <div><strong>创建时间：</strong>{{ formatDate(detailBug.opened_at) }}</div>
                <div><strong>指派时间：</strong>{{ detailBug.assigned_at ? formatDate(detailBug.assigned_at) : '-' }}</div>
                <div><strong>解决时间：</strong>{{ detailBug.resolved_at ? formatDate(detailBug.resolved_at) : '-' }}</div>
                <div><strong>关闭时间：</strong>{{ detailBug.closed_at ? formatDate(detailBug.closed_at) : '-' }}</div>
                <div><strong>解决方案：</strong>{{ detailBug.resolution_display || '-' }}</div>
                <div><strong>激活次数：</strong>{{ detailBug.activated_count ?? 0 }}</div>
                <div><strong>截止日期：</strong>{{ detailBug.deadline || '-' }}</div>
                <div><strong>关键词：</strong>{{ detailBug.keywords || '-' }}</div>
              </div>
            </div>

            <div class="bug-detail-section">
              <div class="bug-detail-section-title">重现步骤</div>
              <div class="bug-detail-content">{{ detailBug.steps || '-' }}</div>
            </div>

            <div class="bug-detail-section">
              <div class="bug-detail-section-title">期望结果</div>
              <div class="bug-detail-content">{{ detailBug.expected_result || '-' }}</div>
            </div>

            <div class="bug-detail-section">
              <div class="bug-detail-section-title">实际结果</div>
              <div class="bug-detail-content">{{ detailBug.actual_result || '-' }}</div>
            </div>

            <div class="bug-detail-section">
              <div class="bug-detail-section-title">处理备注</div>
              <div class="bug-detail-content">{{ detailBug.solution || '-' }}</div>
            </div>
          </div>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { useAuthStore } from '@/store/authStore';
import { formatDate } from '@/utils/formatters';
import {
  TEST_BUG_RESOLUTION_OPTIONS,
  TEST_BUG_STATUS_OPTIONS,
  TEST_BUG_TYPE_OPTIONS,
  activateTestBug,
  assignTestBug,
  closeTestBug,
  createTestBug,
  deleteTestBug,
  getTestBugDetail,
  getTestBugList,
  resolveTestBug,
  updateTestBug,
  type TestBug,
  type TestBugResolution,
  type TestBugStatus,
  type TestBugType,
} from '@/services/testBugService';
import { getProjectMembers, type ProjectMember } from '@/services/projectService';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';

type ActionType = 'assign' | 'resolve' | 'activate' | 'close' | null;
type StatusView = 'all' | TestBugStatus;
type QuickView = 'all' | 'assigned_to_me' | 'opened_by_me' | 'unassigned' | 'unresolved';

const props = defineProps<{
  currentProjectId: number | null;
  selectedSuiteId: number | null;
}>();

const authStore = useAuthStore();
const currentUserId = computed(() => authStore.user?.id ?? null);

const loading = ref(false);
const detailLoading = ref(false);
const submitting = ref(false);
const actionSubmitting = ref(false);
const formVisible = ref(false);
const actionVisible = ref(false);
const detailVisible = ref(false);
const bugList = ref<TestBug[]>([]);
const projectMembers = ref<ProjectMember[]>([]);
const suiteTestCases = ref<TestCase[]>([]);
const editingBug = ref<TestBug | null>(null);
const detailBug = ref<TestBug | null>(null);
const actionBug = ref<TestBug | null>(null);
const actionType = ref<ActionType>(null);
const activeStatusView = ref<StatusView>('all');
const activeQuickView = ref<QuickView>('all');
const levelOptions = ['1', '2', '3', '4'];

const filters = reactive({
  search: '',
  bug_type: undefined as string | undefined,
  severity: undefined as string | undefined,
  priority: undefined as string | undefined,
  assigned_to: undefined as number | undefined,
});

const pagination = reactive({
  current: 1,
  pageSize: 10,
});

const formState = reactive({
  title: '',
  testcase: undefined as number | undefined,
  assigned_to: undefined as number | undefined,
  bug_type: 'codeerror' as TestBugType,
  severity: '3',
  priority: '3',
  deadline: undefined as string | undefined,
  keywords: '',
  steps: '',
  expected_result: '',
  actual_result: '',
});

const actionForm = reactive({
  assigned_to: undefined as number | undefined,
  resolution: 'fixed' as TestBugResolution,
  solution: '',
});

const statusCards = computed(() => [
  { key: 'all' as const, label: '全部', count: bugList.value.length },
  { key: 'active' as const, label: '激活', count: bugList.value.filter((item) => item.status === 'active').length },
  {
    key: 'resolved' as const,
    label: '已解决',
    count: bugList.value.filter((item) => item.status === 'resolved').length,
  },
  { key: 'closed' as const, label: '已关闭', count: bugList.value.filter((item) => item.status === 'closed').length },
]);

const quickViews = [
  { key: 'all' as const, label: '全部视图' },
  { key: 'assigned_to_me' as const, label: '指派给我' },
  { key: 'opened_by_me' as const, label: '由我创建' },
  { key: 'unassigned' as const, label: '未指派' },
  { key: 'unresolved' as const, label: '未关闭' },
];

const filteredBugList = computed(() =>
  bugList.value.filter((bug) => {
    if (activeStatusView.value !== 'all' && bug.status !== activeStatusView.value) {
      return false;
    }

    if (activeQuickView.value === 'assigned_to_me' && bug.assigned_to !== currentUserId.value) {
      return false;
    }
    if (activeQuickView.value === 'opened_by_me' && bug.opened_by !== currentUserId.value) {
      return false;
    }
    if (activeQuickView.value === 'unassigned' && bug.assigned_to) {
      return false;
    }
    if (activeQuickView.value === 'unresolved' && bug.status === 'closed') {
      return false;
    }

    return true;
  })
);

const pagedBugList = computed(() => {
  const start = (pagination.current - 1) * pagination.pageSize;
  return filteredBugList.value.slice(start, start + pagination.pageSize);
});

const actionModalTitle = computed(() => {
  if (actionType.value === 'assign') return '指派 Bug';
  if (actionType.value === 'resolve') return '解决 Bug';
  if (actionType.value === 'activate') return '激活 Bug';
  if (actionType.value === 'close') return '关闭 Bug';
  return '处理 Bug';
});

const resetForm = () => {
  formState.title = '';
  formState.testcase = undefined;
  formState.assigned_to = undefined;
  formState.bug_type = 'codeerror';
  formState.severity = '3';
  formState.priority = '3';
  formState.deadline = undefined;
  formState.keywords = '';
  formState.steps = '';
  formState.expected_result = '';
  formState.actual_result = '';
};

const resetActionState = () => {
  actionBug.value = null;
  actionType.value = null;
  actionForm.assigned_to = undefined;
  actionForm.resolution = 'fixed';
  actionForm.solution = '';
};

const resetFilters = async () => {
  filters.search = '';
  filters.bug_type = undefined;
  filters.severity = undefined;
  filters.priority = undefined;
  filters.assigned_to = undefined;
  activeStatusView.value = 'all';
  activeQuickView.value = 'all';
  pagination.current = 1;
  await fetchBugs();
};

const getStatusViewLabel = (value: StatusView) => {
  if (value === 'all') return '全部';
  return TEST_BUG_STATUS_OPTIONS.find((item) => item.value === value)?.label || value;
};

const getQuickViewLabel = (value: QuickView) => quickViews.find((item) => item.key === value)?.label || value;

const getAssignedUserName = (bug: TestBug) => bug.assigned_to_detail?.username || bug.assigned_to_name || '-';

const getCreatorName = (bug: TestBug) => bug.creator_detail?.username || bug.opened_by_name || '-';

const fetchMembers = async () => {
  if (!props.currentProjectId) {
    projectMembers.value = [];
    return;
  }

  const response = await getProjectMembers(props.currentProjectId);
  projectMembers.value = response.success && response.data ? response.data : [];
};

const fetchSuiteTestCases = async () => {
  if (!props.currentProjectId || !props.selectedSuiteId) {
    suiteTestCases.value = [];
    return;
  }

  const response = await getTestCaseList(props.currentProjectId, {
    page: 1,
    pageSize: 500,
    suite_id: props.selectedSuiteId,
  });

  suiteTestCases.value = response.success && response.data ? response.data : [];
};

const fetchBugs = async () => {
  if (!props.currentProjectId || !props.selectedSuiteId) {
    bugList.value = [];
    return;
  }

  loading.value = true;
  try {
    const response = await getTestBugList(props.currentProjectId, {
      suite_id: props.selectedSuiteId,
      search: filters.search || undefined,
      bug_type: filters.bug_type,
      severity: filters.severity,
      priority: filters.priority,
      assigned_to: filters.assigned_to,
    });

    if (!response.success) {
      bugList.value = [];
      Message.error(response.error || '获取 BUG 列表失败');
      return;
    }

    bugList.value = response.data || [];
  } finally {
    loading.value = false;
  }
};

const fetchBugDetail = async (bugId: number) => {
  if (!props.currentProjectId) {
    return null;
  }

  const response = await getTestBugDetail(props.currentProjectId, bugId);
  if (!response.success || !response.data) {
    Message.error(response.error || '获取 BUG 详情失败');
    return null;
  }
  return response.data;
};

const openCreateModal = async () => {
  editingBug.value = null;
  resetForm();
  await fetchSuiteTestCases();
  formVisible.value = true;
};

const openEditModal = async (bug: TestBug) => {
  editingBug.value = bug;
  await fetchSuiteTestCases();

  const detail = await fetchBugDetail(bug.id);
  if (!detail) {
    return;
  }

  formState.title = detail.title;
  formState.testcase = detail.testcase || undefined;
  formState.assigned_to = detail.assigned_to || undefined;
  formState.bug_type = detail.bug_type;
  formState.severity = detail.severity;
  formState.priority = detail.priority;
  formState.deadline = detail.deadline || undefined;
  formState.keywords = detail.keywords || '';
  formState.steps = detail.steps || '';
  formState.expected_result = detail.expected_result || '';
  formState.actual_result = detail.actual_result || '';
  formVisible.value = true;
};

const openDetail = async (bug: TestBug) => {
  detailVisible.value = true;
  detailLoading.value = true;
  try {
    detailBug.value = await fetchBugDetail(bug.id);
  } finally {
    detailLoading.value = false;
  }
};

const submitBug = async () => {
  if (!props.currentProjectId || !props.selectedSuiteId) return;
  if (!formState.title.trim()) {
    Message.warning('请填写 Bug 标题');
    return;
  }

  submitting.value = true;
  try {
    const payload = {
      suite: props.selectedSuiteId,
      testcase: formState.testcase,
      assigned_to: formState.assigned_to,
      title: formState.title.trim(),
      bug_type: formState.bug_type,
      severity: formState.severity,
      priority: formState.priority,
      deadline: formState.deadline,
      keywords: formState.keywords.trim(),
      steps: formState.steps.trim(),
      expected_result: formState.expected_result.trim(),
      actual_result: formState.actual_result.trim(),
    };

    const response = editingBug.value
      ? await updateTestBug(props.currentProjectId, editingBug.value.id, payload)
      : await createTestBug(props.currentProjectId, payload);

    if (!response.success) {
      Message.error(response.error || '保存 BUG 失败');
      return;
    }

    formVisible.value = false;
    resetForm();
    Message.success(editingBug.value ? 'BUG 更新成功' : 'BUG 创建成功');
    await fetchBugs();
  } finally {
    submitting.value = false;
  }
};

const openActionModal = (bug: TestBug, type: Exclude<ActionType, null>) => {
  actionBug.value = bug;
  actionType.value = type;
  actionForm.assigned_to = bug.assigned_to || undefined;
  actionForm.resolution = 'fixed';
  actionForm.solution = bug.solution || '';
  actionVisible.value = true;
};

const submitAction = async () => {
  if (!props.currentProjectId || !actionBug.value || !actionType.value) {
    return;
  }

  if (actionType.value === 'assign' && !actionForm.assigned_to) {
    Message.warning('请选择指派人');
    return;
  }

  if (actionType.value === 'resolve' && !actionForm.resolution) {
    Message.warning('请选择解决方案');
    return;
  }

  actionSubmitting.value = true;
  try {
    let response;
    if (actionType.value === 'assign') {
      response = await assignTestBug(props.currentProjectId, actionBug.value.id, actionForm.assigned_to!);
    } else if (actionType.value === 'resolve') {
      response = await resolveTestBug(
        props.currentProjectId,
        actionBug.value.id,
        actionForm.resolution,
        actionForm.solution.trim()
      );
    } else if (actionType.value === 'activate') {
      response = await activateTestBug(props.currentProjectId, actionBug.value.id);
    } else {
      response = await closeTestBug(props.currentProjectId, actionBug.value.id, actionForm.solution.trim());
    }

    if (!response.success) {
      Message.error(response.error || 'BUG 操作失败');
      return;
    }

    Message.success(getActionSuccessMessage(actionType.value));
    actionVisible.value = false;
    await fetchBugs();

    if (detailVisible.value && detailBug.value?.id === actionBug.value.id) {
      detailBug.value = await fetchBugDetail(actionBug.value.id);
    }

    resetActionState();
  } finally {
    actionSubmitting.value = false;
  }
};

const getActionSuccessMessage = (type: Exclude<ActionType, null>) => {
  if (type === 'assign') return 'BUG 指派成功';
  if (type === 'resolve') return 'BUG 已解决';
  if (type === 'activate') return 'BUG 已激活';
  return 'BUG 已关闭';
};

const handleActionSelect = async (bug: TestBug, action: string) => {
  if (!props.currentProjectId) {
    return;
  }

  if (action === 'delete') {
    Modal.warning({
      title: '删除 BUG',
      content: `确定删除 BUG「${bug.title}」吗？`,
      onOk: async () => {
        const response = await deleteTestBug(props.currentProjectId, bug.id);
        if (!response.success) {
          Message.error(response.error || '删除 BUG 失败');
          return false;
        }

        if (detailBug.value?.id === bug.id) {
          detailVisible.value = false;
          detailBug.value = null;
        }

        Message.success('BUG 已删除');
        await fetchBugs();
        return true;
      },
    });
    return;
  }

  if (action === 'assign' || action === 'resolve' || action === 'activate' || action === 'close') {
    openActionModal(bug, action);
  }
};

const handleFilterChange = async () => {
  pagination.current = 1;
  await fetchBugs();
};

const getStatusColor = (status?: string) => {
  if (status === 'resolved') return 'green';
  if (status === 'closed') return 'gray';
  return 'arcoblue';
};

const getSeverityColor = (severity?: string) => {
  if (severity === '1') return 'red';
  if (severity === '2') return 'orangered';
  if (severity === '3') return 'orange';
  return 'gold';
};

const getPriorityColor = (priority?: string) => {
  if (priority === '1') return 'red';
  if (priority === '2') return 'orange';
  if (priority === '3') return 'gold';
  return 'gray';
};

watch([activeStatusView, activeQuickView], () => {
  pagination.current = 1;
});

watch(
  () => [props.currentProjectId, props.selectedSuiteId],
  async ([projectId, suiteId]) => {
    if (!projectId || !suiteId) {
      bugList.value = [];
      suiteTestCases.value = [];
      detailBug.value = null;
      pagination.current = 1;
      activeStatusView.value = 'all';
      activeQuickView.value = 'all';
      return;
    }

    pagination.current = 1;
    activeStatusView.value = 'all';
    activeQuickView.value = 'all';
    await fetchMembers();
    await fetchSuiteTestCases();
    await fetchBugs();
  },
  { immediate: true }
);

watch(
  () => pagination.pageSize,
  () => {
    pagination.current = 1;
  }
);

onMounted(async () => {
  if (props.currentProjectId && props.selectedSuiteId) {
    await fetchMembers();
    await fetchSuiteTestCases();
    await fetchBugs();
  }
});

defineExpose({
  refresh: fetchBugs,
});
</script>

<style scoped>
.bug-panel {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  padding: 16px;
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.bug-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.bug-panel-heading {
  min-width: 0;
}

.bug-panel-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-1);
}

.bug-panel-subtitle {
  margin-top: 6px;
  color: var(--color-text-3);
  line-height: 1.6;
}

.bug-panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.bug-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px 16px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  cursor: pointer;
  transition: 0.2s ease;
}

.status-card:hover,
.status-card--active {
  border-color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.06);
}

.status-card-label {
  font-size: 13px;
  color: var(--color-text-3);
}

.status-card-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-1);
  line-height: 1;
}

.bug-toolbar {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.quick-view-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.quick-view-item {
  height: 32px;
  padding: 0 12px;
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 6px;
  color: var(--color-text-2);
  cursor: pointer;
  transition: 0.2s ease;
}

.quick-view-item:hover,
.quick-view-item--active {
  color: rgb(var(--arcoblue-6));
  border-color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.05);
}

.bug-filter-grid {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(120px, 1fr)) auto;
  gap: 8px;
  align-items: center;
}

.bug-filter-search {
  min-width: 0;
}

.bug-summary-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  color: var(--color-text-3);
  font-size: 13px;
}

.bug-table {
  flex: 1;
}

.bug-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.bug-form-section + .bug-form-section {
  margin-top: 12px;
}

.bug-form-section-title,
.bug-detail-section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
}

.bug-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.bug-form-full {
  grid-column: 1 / -1;
}

.action-confirm-tip {
  padding: 12px;
  line-height: 1.7;
  color: var(--color-text-2);
  background: var(--color-fill-2);
  border-radius: 6px;
}

.bug-detail-header {
  margin-bottom: 16px;
}

.bug-detail-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
}

.bug-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.bug-detail-section + .bug-detail-section {
  margin-top: 18px;
}

.bug-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.bug-detail-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: var(--color-text-2);
}

@media (max-width: 1280px) {
  .bug-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .bug-panel-header,
  .bug-form-grid,
  .bug-detail-grid,
  .bug-status-grid,
  .bug-filter-grid {
    grid-template-columns: 1fr;
  }

  .bug-panel-header {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .bug-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

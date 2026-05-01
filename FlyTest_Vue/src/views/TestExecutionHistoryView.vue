<template>
  <div class="test-report-view">
    <div v-if="!currentProjectId" class="empty-state">
      <a-empty description="请先选择项目" />
    </div>

    <div v-else class="report-layout">
      <section class="report-sidebar">
        <div class="sidebar-header">
          <div>
            <div class="sidebar-title">测试报告</div>
            <div class="sidebar-subtitle">
              勾选一个或多个根套件、子套件，基于测试用例与 BUG 数据生成本轮迭代测试报告。
            </div>
          </div>
          <a-button size="small" @click="fetchSuites">刷新</a-button>
        </div>

        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索套件名称"
          allow-clear
          @search="fetchSuites"
          @clear="fetchSuites"
        />

        <div class="sidebar-toolbar">
          <a-space>
            <a-button size="mini" @click="checkAllSuites">全选</a-button>
            <a-button size="mini" @click="clearCheckedSuites">清空</a-button>
            <a-button size="mini" @click="expandAllSuites">展开</a-button>
          </a-space>
          <span class="checked-summary">已选 {{ checkedSuiteIds.length }} 个</span>
        </div>

        <div class="suite-tree-panel">
          <a-spin :loading="suiteLoading" style="width: 100%">
            <a-tree
              v-if="treeData.length > 0"
              checkable
              block-node
              show-line
              :data="treeData"
              :field-names="{ key: 'id', title: 'name' }"
              v-model:checked-keys="checkedKeys"
              v-model:expanded-keys="expandedKeys"
            >
              <template #title="nodeData">
                <div class="suite-node">
                  <span class="suite-node-name">{{ nodeData.name }}</span>
                  <span class="suite-node-count">{{ nodeData.testcase_count || 0 }}</span>
                </div>
              </template>
            </a-tree>
            <a-empty v-else description="暂无套件数据" />
          </a-spin>
        </div>

        <div class="sidebar-actions">
          <a-button
            type="primary"
            long
            :loading="reportLoading"
            :disabled="checkedSuiteIds.length === 0"
            @click="handleGenerateReport"
          >
            AI生成测试报告
          </a-button>
          <div class="sidebar-note">
            生成时会带入所选套件及其子套件下的测试用例、BUG 列表和执行状态数据。
          </div>
        </div>

        <div class="snapshot-panel">
          <div class="snapshot-header">
            <span class="snapshot-title">报告快照</span>
            <a-space>
              <a-button size="mini" :disabled="!reportData" @click="handleSaveSnapshot">保存</a-button>
              <a-button size="mini" @click="loadReportSnapshots">刷新</a-button>
              <a-button
                size="mini"
                status="danger"
                :disabled="reportSnapshots.length === 0"
                @click="clearReportSnapshots"
              >
                清空
              </a-button>
            </a-space>
          </div>

          <a-input-search
            v-model="snapshotKeyword"
            class="snapshot-search"
            placeholder="搜索快照标题或创建人"
            allow-clear
          />

          <div class="snapshot-summary">
            <span>共 {{ reportSnapshots.length }} 条</span>
            <span v-if="snapshotKeyword.trim()">筛选后 {{ filteredReportSnapshots.length }} 条</span>
          </div>

          <a-empty v-if="filteredReportSnapshots.length === 0" description="暂无报告快照" />
          <div v-else class="snapshot-list">
            <div
              v-for="item in filteredReportSnapshots"
              :key="item.id"
              class="snapshot-item"
              :class="{ active: activeSnapshotId === item.id, pinned: item.isPinned }"
            >
              <div class="snapshot-main" @click="applyReportSnapshot(item)">
                <div class="snapshot-name-row">
                  <template v-if="editingSnapshotId === item.id">
                    <a-input
                      v-model="editingSnapshotTitle"
                      size="small"
                      class="snapshot-title-input"
                      placeholder="请输入快照名称"
                      @click.stop
                      @press-enter="submitRenameSnapshot(item)"
                    />
                  </template>
                  <template v-else>
                    <div class="snapshot-name">{{ item.title }}</div>
                    <a-tag v-if="item.isPinned" size="small" color="gold">置顶</a-tag>
                  </template>
                </div>
                <div class="snapshot-meta">
                  <span>{{ item.generatedAtText }}</span>
                  <span>创建人：{{ item.creatorName }}</span>
                </div>
              </div>

              <div class="snapshot-actions">
                <template v-if="editingSnapshotId === item.id">
                  <a-button size="mini" type="primary" @click.stop="submitRenameSnapshot(item)">保存</a-button>
                  <a-button size="mini" @click.stop="cancelRenameSnapshot">取消</a-button>
                </template>
                <template v-else>
                  <a-button size="mini" @click.stop="startRenameSnapshot(item)">重命名</a-button>
                  <a-button size="mini" @click.stop="handleTogglePinSnapshot(item)">
                    {{ item.isPinned ? '取消置顶' : '置顶' }}
                  </a-button>
                  <a-button size="mini" status="danger" @click.stop="removeReportSnapshot(item.id)">删除</a-button>
                </template>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="report-content">
        <div v-if="reportData" class="report-body">
          <div class="report-header-card">
            <div>
              <div class="report-title">本轮测试报告</div>
              <div class="report-meta">
                生成时间：{{ formatDateTime(reportData.generated_at) }}
                <span v-if="reportData.model_name"> / 模型：{{ reportData.model_name }}</span>
              </div>
            </div>
            <a-space>
              <a-tag color="arcoblue">已选套件 {{ checkedSuiteIds.length }}</a-tag>
              <a-tag :color="reportData.used_ai ? 'arcoblue' : 'gold'">
                {{ reportData.used_ai ? 'AI生成' : '统计生成' }}
              </a-tag>
            </a-space>
          </div>

          <div class="report-toolbar">
            <a-space>
              <a-button size="small" :disabled="!reportData || !activeSnapshotId" @click="handleOverwriteSnapshot">
                覆盖当前快照
              </a-button>
              <a-button size="small" @click="handleCopyReportSummary">复制摘要</a-button>
              <a-button size="small" @click="handleExportReport">导出报告</a-button>
              <a-button size="small" :loading="reportLoading" @click="handleGenerateReport">重新生成</a-button>
            </a-space>
          </div>

          <div class="report-summary-grid">
            <div class="summary-card">
              <div class="summary-label">覆盖套件</div>
              <div class="summary-value">{{ reportData.suite_count }}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">测试用例</div>
              <div class="summary-value">{{ reportData.testcase_count }}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">BUG数量</div>
              <div class="summary-value">{{ reportData.bug_count }}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">本次选择</div>
              <div class="summary-value">{{ reportData.selected_suite_count }}</div>
            </div>
          </div>

          <div class="report-section">
            <div class="section-title">总体结论</div>
            <p class="section-text">{{ reportData.summary }}</p>
            <p class="section-note">{{ reportData.note }}</p>
          </div>

          <div class="report-two-column">
            <div class="report-section">
              <div class="section-title">质量概览</div>
              <p class="section-text">{{ reportData.quality_overview }}</p>
            </div>
            <div class="report-section">
              <div class="section-title">风险概览</div>
              <p class="section-text">{{ reportData.risk_overview }}</p>
            </div>
          </div>

          <div class="report-two-column">
            <div class="report-section">
              <div class="section-title">执行状态分布</div>
              <div class="tag-flow">
                <a-tag v-for="item in executionStatusList" :key="item.key" :color="item.color">
                  {{ item.label }} {{ item.value }}
                </a-tag>
              </div>
            </div>
            <div class="report-section">
              <div class="section-title">BUG状态分布</div>
              <div class="tag-flow">
                <a-tag v-for="item in bugStatusList" :key="item.key" :color="item.color">
                  {{ item.label }} {{ item.value }}
                </a-tag>
              </div>
            </div>
          </div>

          <div class="report-section">
            <div class="section-title">关键发现</div>
            <a-empty v-if="reportData.findings.length === 0" description="暂无关键发现" />
            <div v-else class="item-list">
              <div
                v-for="item in reportData.findings"
                :key="`${item.title}-${item.detail}`"
                class="item-card"
              >
                <div class="item-header">
                  <span class="item-title">{{ item.title }}</span>
                  <a-tag :color="getSeverityColor(item.severity)">{{ getSeverityLabel(item.severity) }}</a-tag>
                </div>
                <div class="item-detail">{{ item.detail }}</div>
              </div>
            </div>
          </div>

          <div class="report-section">
            <div class="section-title">改进建议</div>
            <a-empty v-if="reportData.recommendations.length === 0" description="暂无改进建议" />
            <div v-else class="item-list">
              <div
                v-for="item in reportData.recommendations"
                :key="`${item.title}-${item.detail}`"
                class="item-card"
              >
                <div class="item-header">
                  <span class="item-title">{{ item.title }}</span>
                  <a-tag :color="getPriorityColor(item.priority)">{{ getPriorityLabel(item.priority) }}</a-tag>
                </div>
                <div class="item-detail">{{ item.detail }}</div>
              </div>
            </div>
          </div>

          <div class="report-section">
            <div class="section-title">套件明细</div>
            <a-table
              :columns="suiteColumns"
              :data="reportData.suite_breakdown"
              :pagination="false"
              row-key="id"
              :bordered="{ cell: true }"
            />
          </div>

          <div class="report-section">
            <div class="section-title">支撑证据</div>
            <a-empty v-if="reportData.evidence.length === 0" description="暂无支撑证据" />
            <div v-else class="item-list">
              <div
                v-for="item in reportData.evidence"
                :key="`${item.label}-${item.detail}`"
                class="item-card"
              >
                <div class="item-title">{{ item.label }}</div>
                <div class="item-detail">{{ item.detail }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="report-placeholder">
          <a-empty description="请选择套件后生成测试报告" />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Message, Modal, type TableColumnData, type TreeNodeData } from '@arco-design/web-vue';
import { useRoute } from 'vue-router';
import {
  createTestReportSnapshot,
  deleteTestReportSnapshot,
  generateAiIterationTestReport,
  getTestReportSnapshots,
  updateTestReportSnapshot,
  type AiIterationTestReport,
} from '@/services/testExecutionService';
import { getTestSuiteList, type TestSuite } from '@/services/testSuiteService';
import { useProjectStore } from '@/store/projectStore';

type SuiteTreeNode = TreeNodeData & {
  id: number;
  name: string;
  testcase_count: number;
  children?: SuiteTreeNode[];
};

type ReportSnapshot = {
  id: number;
  title: string;
  projectId: number;
  suiteIds: number[];
  creatorName: string;
  isPinned: boolean;
  generatedAt: string;
  generatedAtText: string;
  report: AiIterationTestReport;
};

const projectStore = useProjectStore();
const route = useRoute();
const currentProjectId = computed(() => projectStore.currentProjectId || null);

const suiteLoading = ref(false);
const reportLoading = ref(false);
const searchKeyword = ref('');
const snapshotKeyword = ref('');
const suites = ref<TestSuite[]>([]);
const checkedKeys = ref<(number | string)[]>([]);
const expandedKeys = ref<(number | string)[]>([]);
const reportData = ref<AiIterationTestReport | null>(null);
const reportSnapshots = ref<ReportSnapshot[]>([]);
const activeSnapshotId = ref<number | null>(null);
const editingSnapshotId = ref<number | null>(null);
const editingSnapshotTitle = ref('');

const checkedSuiteIds = computed(() =>
  checkedKeys.value.map((item) => Number(item)).filter((item) => Number.isFinite(item))
);

const filteredReportSnapshots = computed(() => {
  const keyword = snapshotKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return reportSnapshots.value;
  }
  return reportSnapshots.value.filter((item) => {
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.generatedAtText.toLowerCase().includes(keyword) ||
      item.creatorName.toLowerCase().includes(keyword)
    );
  });
});

const normalizeSnapshots = (items: ReportSnapshot[]) =>
  [...items].sort((left, right) => {
    if (left.isPinned !== right.isPinned) {
      return left.isPinned ? -1 : 1;
    }
    return new Date(right.generatedAt).getTime() - new Date(left.generatedAt).getTime();
  });

const toSnapshot = (item: {
  id: number;
  title: string;
  project: number;
  suite_ids?: number[];
  creator_name?: string;
  is_pinned?: boolean;
  report_data: AiIterationTestReport;
  created_at: string;
}) => ({
  id: item.id,
  title: item.title,
  projectId: item.project,
  suiteIds: item.suite_ids || [],
  creatorName: item.creator_name || '-',
  isPinned: Boolean(item.is_pinned),
  generatedAt: item.report_data?.generated_at || item.created_at,
  generatedAtText: formatDateTime(item.report_data?.generated_at || item.created_at),
  report: item.report_data,
});

const buildTree = (parentId: number | null = null): SuiteTreeNode[] =>
  suites.value
    .filter((suite) => (suite.parent ?? suite.parent_id ?? null) === parentId)
    .map((suite) => ({
      id: suite.id,
      key: suite.id,
      name: suite.name,
      testcase_count: suite.testcase_count || 0,
      children: buildTree(suite.id),
    }));

const treeData = computed(() => buildTree());

const suiteColumns: TableColumnData[] = [
  { title: '套件', dataIndex: 'path', ellipsis: true, tooltip: true },
  { title: '测试用例', dataIndex: 'testcase_count', width: 96, align: 'center' },
  { title: '已审核', dataIndex: 'approved_testcase_count', width: 96, align: 'center' },
  { title: '失败用例', dataIndex: 'failed_testcase_count', width: 96, align: 'center' },
  { title: '未执行', dataIndex: 'not_executed_testcase_count', width: 96, align: 'center' },
  { title: 'BUG数', dataIndex: 'bug_count', width: 88, align: 'center' },
  { title: '待复测', dataIndex: 'pending_retest_bug_count', width: 96, align: 'center' },
  { title: '未关闭BUG', dataIndex: 'open_bug_count', width: 112, align: 'center' },
];

const executionStatusLabelMap: Record<string, string> = {
  not_executed: '未执行',
  passed: '通过',
  failed: '失败',
  not_applicable: '无需执行',
};

const bugStatusLabelMap: Record<string, string> = {
  unassigned: '未指派',
  assigned: '未确认',
  confirmed: '已确认',
  fixed: '已修复',
  pending_retest: '待复测',
  closed: '已关闭',
  expired: '已过期',
};

const executionStatusList = computed(() => {
  const distribution = reportData.value?.execution_status_distribution || {};
  return Object.entries(distribution).map(([key, value]) => ({
    key,
    value,
    label: executionStatusLabelMap[key] || key,
    color: key === 'passed' ? 'green' : key === 'failed' ? 'red' : key === 'not_executed' ? 'gray' : 'arcoblue',
  }));
});

const bugStatusList = computed(() => {
  const distribution = reportData.value?.bug_status_distribution || {};
  return Object.entries(distribution).map(([key, value]) => ({
    key,
    value,
    label: bugStatusLabelMap[key] || key,
    color: key === 'closed' ? 'green' : key === 'pending_retest' ? 'orange' : key === 'expired' ? 'red' : 'arcoblue',
  }));
});

function formatDateTime(value?: string | null) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

async function loadReportSnapshots() {
  if (!currentProjectId.value) {
    reportSnapshots.value = [];
    activeSnapshotId.value = null;
    return;
  }

  const response = await getTestReportSnapshots(currentProjectId.value);
  if (!response.success) {
    Message.error(response.error || '加载报告快照失败');
    reportSnapshots.value = [];
    return;
  }

  reportSnapshots.value = normalizeSnapshots((response.data || []).map((item) => toSnapshot(item)));

  if (activeSnapshotId.value) {
    const matched = reportSnapshots.value.find((item) => item.id === activeSnapshotId.value);
    if (matched) {
      reportData.value = matched.report;
      return;
    }
    activeSnapshotId.value = null;
  }

  if (!reportData.value && reportSnapshots.value.length > 0) {
    applyReportSnapshot(reportSnapshots.value[0], false);
  }
}

async function createReportSnapshot(report: AiIterationTestReport, useCurrentTitle = true) {
  if (!currentProjectId.value) {
    return null;
  }

  const timestamp = new Date();
  const title = useCurrentTitle
    ? `测试报告 ${timestamp.toLocaleString('zh-CN', { hour12: false })}`
    : `手动保存 ${timestamp.toLocaleString('zh-CN', { hour12: false })}`;

  const response = await createTestReportSnapshot(currentProjectId.value, {
    title,
    suite_ids: [...checkedSuiteIds.value],
    report_data: JSON.parse(JSON.stringify(report)),
  });

  if (!response.success || !response.data) {
    Message.error(response.error || '保存报告快照失败');
    return null;
  }

  const snapshot = toSnapshot(response.data);
  reportSnapshots.value = normalizeSnapshots(
    [snapshot, ...reportSnapshots.value.filter((item) => item.id !== snapshot.id)].slice(0, 20)
  );
  activeSnapshotId.value = snapshot.id;
  return snapshot;
}

function applyReportSnapshot(snapshot: ReportSnapshot, showMessage = true) {
  cancelRenameSnapshot();
  reportData.value = snapshot.report;
  checkedKeys.value = [...snapshot.suiteIds];
  expandedKeys.value = Array.from(new Set([...expandedKeys.value, ...snapshot.suiteIds]));
  activeSnapshotId.value = snapshot.id;
  if (showMessage) {
    Message.success('报告快照已加载');
  }
}

async function patchSnapshot(
  snapshotId: number,
  payload: {
    title?: string;
    is_pinned?: boolean;
    suite_ids?: number[];
    report_data?: AiIterationTestReport;
  }
) {
  if (!currentProjectId.value) {
    return null;
  }

  const response = await updateTestReportSnapshot(currentProjectId.value, snapshotId, payload);
  if (!response.success || !response.data) {
    Message.error(response.error || '更新报告快照失败');
    return null;
  }

  const nextItem = toSnapshot(response.data);
  reportSnapshots.value = normalizeSnapshots(
    reportSnapshots.value.map((item) => (item.id === snapshotId ? nextItem : item))
  );

  if (activeSnapshotId.value === snapshotId) {
    reportData.value = nextItem.report;
  }

  return nextItem;
}

function startRenameSnapshot(snapshot: ReportSnapshot) {
  editingSnapshotId.value = snapshot.id;
  editingSnapshotTitle.value = snapshot.title;
}

function cancelRenameSnapshot() {
  editingSnapshotId.value = null;
  editingSnapshotTitle.value = '';
}

async function submitRenameSnapshot(snapshot: ReportSnapshot) {
  const nextTitle = editingSnapshotTitle.value.trim();
  if (!nextTitle) {
    Message.warning('快照标题不能为空');
    return;
  }

  const updated = await patchSnapshot(snapshot.id, { title: nextTitle });
  if (!updated) {
    return;
  }

  cancelRenameSnapshot();
  Message.success('快照名称已更新');
}

async function handleTogglePinSnapshot(snapshot: ReportSnapshot) {
  const updated = await patchSnapshot(snapshot.id, { is_pinned: !snapshot.isPinned });
  if (updated) {
    Message.success(updated.isPinned ? '快照已置顶' : '快照已取消置顶');
  }
}

async function removeReportSnapshot(snapshotId: number) {
  if (!currentProjectId.value) {
    return;
  }

  Modal.confirm({
    title: '确认删除',
    content: '删除后不可恢复，确定删除这条报告快照吗？',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      const response = await deleteTestReportSnapshot(currentProjectId.value!, snapshotId);
      if (!response.success) {
        Message.error(response.error || '删除报告快照失败');
        return;
      }

      reportSnapshots.value = reportSnapshots.value.filter((item) => item.id !== snapshotId);
      if (activeSnapshotId.value === snapshotId) {
        activeSnapshotId.value = null;
        reportData.value = null;
        if (reportSnapshots.value.length > 0) {
          applyReportSnapshot(reportSnapshots.value[0], false);
        }
      }
      Message.success('报告快照已删除');
    },
  });
}

async function clearReportSnapshots() {
  if (!currentProjectId.value || reportSnapshots.value.length === 0) {
    return;
  }

  Modal.confirm({
    title: '确认清空',
    content: '将清空当前项目下最近保存的报告快照，确定继续吗？',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      const snapshotIds = reportSnapshots.value.map((item) => item.id);
      for (const snapshotId of snapshotIds) {
        const response = await deleteTestReportSnapshot(currentProjectId.value!, snapshotId);
        if (!response.success) {
          Message.error(response.error || '清空报告快照失败');
          return;
        }
      }

      reportSnapshots.value = [];
      reportData.value = null;
      activeSnapshotId.value = null;
      cancelRenameSnapshot();
      Message.success('报告快照已清空');
    },
  });
}

async function handleSaveSnapshot() {
  if (!reportData.value) {
    Message.warning('当前没有可保存的测试报告');
    return;
  }

  const snapshot = await createReportSnapshot(reportData.value, false);
  if (snapshot) {
    Message.success('报告快照已保存');
  }
}

async function handleOverwriteSnapshot() {
  if (!reportData.value || !activeSnapshotId.value) {
    Message.warning('请先加载一个可覆盖的报告快照');
    return;
  }

  Modal.confirm({
    title: '确认覆盖',
    content: '将用当前报告内容覆盖这条快照，原内容会被更新，确定继续吗？',
    onOk: async () => {
      const updated = await patchSnapshot(activeSnapshotId.value!, {
        suite_ids: [...checkedSuiteIds.value],
        report_data: JSON.parse(JSON.stringify(reportData.value)),
      });
      if (!updated) {
        return;
      }
      activeSnapshotId.value = updated.id;
      reportData.value = updated.report;
      Message.success('当前快照已覆盖保存');
    },
  });
}

function applySuiteSelectionFromRoute() {
  const suiteId = Number(route.query.suiteId);
  if (!suiteId || !Number.isFinite(suiteId)) {
    return;
  }
  if (!suites.value.some((suite) => suite.id === suiteId)) {
    return;
  }
  checkedKeys.value = Array.from(new Set([suiteId, ...checkedSuiteIds.value]));
  expandedKeys.value = Array.from(new Set([suiteId, ...expandedKeys.value.map((item) => Number(item))]));
}

async function fetchSuites() {
  if (!currentProjectId.value) {
    suites.value = [];
    checkedKeys.value = [];
    expandedKeys.value = [];
    return;
  }

  suiteLoading.value = true;
  try {
    const response = await getTestSuiteList(currentProjectId.value, {
      search: searchKeyword.value.trim() || undefined,
    });
    if (response.success && response.data) {
      suites.value = response.data;
      expandedKeys.value = response.data.map((item) => item.id);
      checkedKeys.value = checkedKeys.value.filter((item) => response.data?.some((suite) => suite.id === Number(item)));
      applySuiteSelectionFromRoute();
      return;
    }
    Message.error(response.error || '获取套件列表失败');
    suites.value = [];
  } catch (error) {
    console.error('获取套件列表失败:', error);
    Message.error('获取套件列表失败');
    suites.value = [];
  } finally {
    suiteLoading.value = false;
  }
}

function checkAllSuites() {
  checkedKeys.value = suites.value.map((item) => item.id);
}

function clearCheckedSuites() {
  checkedKeys.value = [];
}

function expandAllSuites() {
  expandedKeys.value = suites.value.map((item) => item.id);
}

async function handleGenerateReport() {
  if (!currentProjectId.value) {
    Message.warning('请先选择项目');
    return;
  }

  if (checkedSuiteIds.value.length === 0) {
    Message.warning('请至少选择一个测试套件');
    return;
  }

  reportLoading.value = true;
  try {
    const response = await generateAiIterationTestReport(currentProjectId.value, checkedSuiteIds.value);
    if (response.success && response.data) {
      reportData.value = response.data;
      await createReportSnapshot(response.data);
      Message.success(response.data.used_ai ? '测试报告生成完成' : '测试报告已生成（统计版）');
      return;
    }
    Message.error(response.error || '生成测试报告失败');
  } catch (error) {
    console.error('生成测试报告失败:', error);
    Message.error('生成测试报告失败');
  } finally {
    reportLoading.value = false;
  }
}

function getSeverityColor(value: string) {
  if (value === 'high') return 'red';
  if (value === 'low') return 'green';
  return 'orange';
}

function getSeverityLabel(value: string) {
  if (value === 'high') return '高';
  if (value === 'low') return '低';
  return '中';
}

function getPriorityColor(value: string) {
  if (value === 'high') return 'red';
  if (value === 'low') return 'green';
  return 'orange';
}

function getPriorityLabel(value: string) {
  if (value === 'high') return '高优先级';
  if (value === 'low') return '低优先级';
  return '中优先级';
}

function buildReportMarkdown(report: AiIterationTestReport) {
  const lines: string[] = [
    '# 测试报告',
    '',
    `- 生成时间：${formatDateTime(report.generated_at)}`,
    `- 生成方式：${report.used_ai ? 'AI生成' : '统计生成'}`,
    `- 覆盖套件：${report.suite_count}`,
    `- 测试用例：${report.testcase_count}`,
    `- BUG数量：${report.bug_count}`,
    `- 本次选择：${report.selected_suite_count}`,
    '',
    '## 总体结论',
    report.summary,
    '',
    '## 质量概览',
    report.quality_overview,
    '',
    '## 风险概览',
    report.risk_overview,
    '',
    '## 关键发现',
  ];

  if (report.findings.length === 0) {
    lines.push('- 暂无');
  } else {
    report.findings.forEach((item) => {
      lines.push(`- [${getSeverityLabel(item.severity)}] ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 改进建议');
  if (report.recommendations.length === 0) {
    lines.push('- 暂无');
  } else {
    report.recommendations.forEach((item) => {
      lines.push(`- [${getPriorityLabel(item.priority)}] ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 套件明细');
  report.suite_breakdown.forEach((item) => {
    lines.push(
      `- ${item.path}：测试用例 ${item.testcase_count}，已审核 ${item.approved_testcase_count}，失败 ${item.failed_testcase_count}，未执行 ${item.not_executed_testcase_count}，BUG ${item.bug_count}，待复测 ${item.pending_retest_bug_count}`
    );
  });

  lines.push('', '## 支撑证据');
  if (report.evidence.length === 0) {
    lines.push('- 暂无');
  } else {
    report.evidence.forEach((item) => {
      lines.push(`- ${item.label}：${item.detail}`);
    });
  }

  return lines.join('\n');
}

async function handleCopyReportSummary() {
  if (!reportData.value) {
    Message.warning('当前没有可复制的测试报告');
    return;
  }

  const summaryText = buildReportMarkdown(reportData.value);
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(summaryText);
    } else {
      const textArea = document.createElement('textarea');
      textArea.value = summaryText;
      textArea.style.position = 'fixed';
      textArea.style.opacity = '0';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
    Message.success('测试报告摘要已复制');
  } catch (error) {
    console.error('复制测试报告失败:', error);
    Message.error('复制测试报告失败');
  }
}

function handleExportReport() {
  if (!reportData.value) {
    Message.warning('当前没有可导出的测试报告');
    return;
  }

  const blob = new Blob([buildReportMarkdown(reportData.value)], {
    type: 'text/markdown;charset=utf-8',
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  const date = new Date();
  const fileName = `测试报告_${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(
    date.getDate()
  ).padStart(2, '0')}_${String(date.getHours()).padStart(2, '0')}${String(date.getMinutes()).padStart(2, '0')}.md`;
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
  Message.success('测试报告已导出');
}

onMounted(() => {
  fetchSuites();
  void loadReportSnapshots();
});

watch(
  () => currentProjectId.value,
  (projectId) => {
    if (!projectId) {
      suites.value = [];
      checkedKeys.value = [];
      expandedKeys.value = [];
      reportData.value = null;
      reportSnapshots.value = [];
      activeSnapshotId.value = null;
      cancelRenameSnapshot();
      return;
    }
    fetchSuites();
    void loadReportSnapshots();
  }
);

watch(
  () => route.query.suiteId,
  () => {
    applySuiteSelectionFromRoute();
  }
);
</script>

<style scoped>
.test-report-view {
  height: 100%;
}

.empty-state,
.report-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 420px;
  background: #fff;
  border-radius: 8px;
}

.report-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  min-height: calc(100vh - 180px);
}

.report-sidebar,
.report-content {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.report-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-header,
.report-header-card,
.item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-toolbar {
  display: flex;
  justify-content: flex-end;
}

.sidebar-title,
.report-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
}

.sidebar-subtitle,
.report-meta,
.sidebar-note,
.section-note,
.checked-summary {
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
}

.sidebar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.suite-tree-panel {
  flex: 1;
  min-height: 260px;
  overflow: auto;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px;
}

.suite-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.suite-node-name,
.item-title {
  color: #1d2129;
  font-weight: 500;
}

.suite-node-count {
  min-width: 28px;
  text-align: center;
  padding: 0 8px;
  border-radius: 999px;
  background: #f2f3f5;
  color: #4e5969;
  font-size: 12px;
  line-height: 22px;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snapshot-panel {
  margin-top: 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.snapshot-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.snapshot-search {
  margin-bottom: 8px;
}

.snapshot-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #86909c;
  font-size: 12px;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}

.snapshot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #f2f3f5;
  background: #f7f8fa;
}

.snapshot-item.active {
  border-color: #165dff;
  background: #eff4ff;
}

.snapshot-item.pinned {
  border-color: #f7c244;
}

.snapshot-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.snapshot-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.snapshot-name {
  color: #1d2129;
  font-size: 13px;
  font-weight: 500;
}

.snapshot-title-input {
  width: 220px;
}

.snapshot-meta {
  margin-top: 4px;
  color: #86909c;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.snapshot-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.report-content {
  overflow: auto;
}

.report-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card,
.report-section,
.item-card,
.report-header-card {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
}

.summary-card {
  padding: 16px;
}

.summary-label {
  font-size: 13px;
  color: #86909c;
}

.summary-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 600;
  color: #1d2129;
  line-height: 1;
}

.report-header-card,
.report-section,
.item-card {
  padding: 16px;
}

.report-two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}

.section-text,
.item-detail {
  margin: 0;
  color: #4e5969;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  text-align: left;
}

.tag-flow,
.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tag-flow {
  flex-direction: row;
  flex-wrap: wrap;
}

@media (max-width: 1200px) {
  .report-layout {
    grid-template-columns: 1fr;
  }

  .report-summary-grid,
  .report-two-column {
    grid-template-columns: 1fr;
  }

  .snapshot-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .snapshot-actions {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .snapshot-title-input {
    width: 100%;
  }
}
</style>

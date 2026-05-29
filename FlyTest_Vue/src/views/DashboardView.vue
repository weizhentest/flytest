<template>
  <div class="dashboard-view">
    <div v-if="!isApproved" class="approval-pending-card">
      <div class="approval-shell">
        <div class="approval-kicker">Workspace Access</div>
        <a-result
          status="warning"
          title="账号等待管理员审核"
          :subtitle="approvalSubtitle"
        />
      </div>
    </div>

    <div v-else-if="!currentProjectId" class="no-project-selected">
      <div class="empty-project-shell">
        <div class="empty-project-icon">
          <icon-bar-chart />
        </div>
        <div class="empty-project-copy">
          <h2>当前还没有可用项目</h2>
          <p>请先创建项目，或联系管理员将你加入项目后，再查看管理首页。</p>
          <div class="empty-project-actions">
            <a-button type="primary" @click="goToProjectManagement">去创建项目</a-button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="dashboard-content">
      <a-spin :loading="loading" tip="正在加载首页数据..." class="dashboard-spin">
        <section class="hero-section">
          <div class="hero-main">
            <div class="hero-kicker-row">
              <span class="hero-eyebrow">Control Center</span>
              <span class="hero-project-chip">当前项目</span>
            </div>
            <div class="hero-title-row">
              <h1 class="hero-title">{{ currentProjectName }}</h1>
              <span class="hero-inline-status" :class="passRateTone">{{ passRateStatusText }}</span>
            </div>

            <div class="hero-highlights">
              <div v-for="item in heroHighlights" :key="item.label" class="hero-highlight-card">
                <span class="hero-highlight-label">{{ item.label }}</span>
                <strong class="hero-highlight-value">{{ item.value }}</strong>
              </div>
            </div>

            <div class="hero-kpi-strip">
              <article v-for="card in overviewCards" :key="card.title" class="hero-kpi-card">
                <div class="hero-kpi-head">
                  <component :is="card.icon" class="hero-kpi-icon" />
                  <span class="hero-kpi-title">{{ card.title }}</span>
                </div>
                <div class="hero-kpi-value-row">
                  <strong class="hero-kpi-value">{{ card.value }}</strong>
                  <span class="hero-kpi-unit">{{ card.unit }}</span>
                </div>
              </article>
            </div>
          </div>

          <div class="hero-aside">
            <div class="hero-aside-panel">
              <div class="hero-aside-head">
                <span class="hero-aside-kicker">Quality Signal</span>
                <span class="hero-aside-badge" :class="passRateTone">{{ passRateStatusText }}</span>
              </div>
              <div class="hero-score-row">
                <div class="hero-score-ring">
                  <svg viewBox="0 0 120 120" class="hero-score-svg">
                    <circle cx="60" cy="60" r="48" class="hero-score-track" />
                    <circle
                      cx="60"
                      cy="60"
                      r="48"
                      class="hero-score-progress"
                      :style="{ strokeDasharray: `${passRate * 3.02} 302`, stroke: rateColor }"
                    />
                  </svg>
                  <div class="hero-score-text">
                    <strong>{{ passRate }}</strong>
                    <span>%</span>
                  </div>
                </div>
                <div class="hero-score-meta">
                  <div class="hero-score-stat">
                    <span>通过</span>
                    <strong>{{ statistics?.executions?.case_results?.passed || 0 }}</strong>
                  </div>
                  <div class="hero-score-stat">
                    <span>失败</span>
                    <strong>{{ statistics?.executions?.case_results?.failed || 0 }}</strong>
                  </div>
                  <div class="hero-score-stat">
                    <span>跳过</span>
                    <strong>{{ statistics?.executions?.case_results?.skipped || 0 }}</strong>
                  </div>
                </div>
              </div>
            </div>

            <div class="hero-aside-panel compact">
              <div class="hero-aside-head">
                <span class="hero-aside-kicker">Governance Snapshot</span>
              </div>
              <div class="governance-list">
                <div v-for="item in governanceSnapshot" :key="item.label" class="governance-item">
                  <span class="governance-label">{{ item.label }}</span>
                  <strong class="governance-value">{{ item.value }}</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="insight-grid">
          <article class="surface-card backlog-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">Actionable Queue</span>
                <h3 class="section-title">待处理事项</h3>
              </div>
              <span class="section-badge">{{ backlogTotal }} 项</span>
            </div>
            <div class="backlog-list">
              <div v-for="item in backlogCards" :key="item.label" class="backlog-item">
                <div class="backlog-main">
                  <div class="backlog-copy">
                    <span class="backlog-label">{{ item.label }}</span>
                    <p class="backlog-desc">{{ item.description }}</p>
                  </div>
                  <div class="backlog-value-block">
                    <strong class="backlog-value">{{ item.value }}</strong>
                    <span class="backlog-share">{{ item.share }}</span>
                  </div>
                </div>
                <div class="review-track">
                  <div class="review-fill" :style="{ width: `${item.percent}%`, background: item.color }"></div>
                </div>
              </div>
            </div>
          </article>

          <article class="surface-card bug-risk-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">Defect Signal</span>
                <h3 class="section-title">缺陷风险</h3>
              </div>
              <span class="section-badge">{{ statistics?.bugs?.total || 0 }} 个</span>
            </div>
            <div class="bug-hero">
              <div class="bug-hero-value">
                <strong>{{ statistics?.bugs?.open || 0 }}</strong>
                <span>未关闭缺陷</span>
              </div>
              <div class="bug-hero-tags">
                <span class="bug-tag danger">高优先级 {{ statistics?.bugs?.high_severity || 0 }}</span>
                <span class="bug-tag warning">待回归 {{ statistics?.bugs?.pending_retest || 0 }}</span>
              </div>
            </div>
            <div class="bug-risk-list">
              <div v-for="item in bugRiskCards" :key="item.label" class="bug-risk-item">
                <div class="bug-risk-head">
                  <span class="bug-risk-label">{{ item.label }}</span>
                  <strong class="bug-risk-value">{{ item.value }}</strong>
                </div>
                <p class="bug-risk-desc">{{ item.description }}</p>
                <div class="review-track compact">
                  <div class="review-fill" :style="{ width: `${item.percent}%`, background: item.color }"></div>
                </div>
              </div>
            </div>
          </article>

          <article class="surface-card automation-matrix-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">Automation Coverage</span>
                <h3 class="section-title">自动化矩阵</h3>
              </div>
              <span class="section-badge">{{ automationFootnote }}</span>
            </div>
            <div class="automation-matrix">
              <div v-for="item in automationMatrixCards" :key="item.label" class="automation-row">
                <div class="automation-row-main">
                  <div>
                    <div class="automation-label-row">
                      <span class="automation-label">{{ item.label }}</span>
                      <span :class="['automation-status', item.tone]">{{ item.status }}</span>
                    </div>
                    <p class="automation-desc">{{ item.description }}</p>
                  </div>
                  <strong class="automation-total">{{ item.total }}</strong>
                </div>
                <div class="automation-metrics">
                  <span>{{ item.metricA }}</span>
                  <span>{{ item.metricB }}</span>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="secondary-insight-grid">
          <article class="surface-card review-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">Review Status</span>
                <h3 class="section-title">测试用例审核分布</h3>
              </div>
              <span class="section-badge">{{ statistics?.testcases?.total || 0 }} 条</span>
            </div>
            <div class="review-list">
              <div v-for="item in reviewStatusData" :key="item.key" class="review-item">
                <div class="review-item-head">
                  <span class="review-label">{{ item.label }}</span>
                  <span class="review-value">{{ item.value }} / {{ item.percent }}%</span>
                </div>
                <div class="review-track">
                  <div class="review-fill" :style="{ width: `${item.percent}%`, background: item.color }"></div>
                </div>
              </div>
            </div>
          </article>

          <article class="surface-card token-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">AI Resource</span>
                <h3 class="section-title">Token 使用概况</h3>
              </div>
              <div class="token-period-selector">
                <span
                  v-for="opt in periodOptions"
                  :key="opt.value"
                  :class="['period-tag', { active: tokenPeriod === opt.value }]"
                  @click="changeTokenPeriod(opt.value)"
                >{{ opt.label }}</span>
              </div>
            </div>
            <div class="token-total-panel">
              <span class="token-total-label">总消耗</span>
              <strong class="token-total-value">{{ formatTokenCount(tokenStats?.total?.total_tokens || 0) }}</strong>
              <div class="token-total-meta">
                <span>输入 {{ formatTokenCount(tokenStats?.total?.input_tokens || 0) }}</span>
                <span>输出 {{ formatTokenCount(tokenStats?.total?.output_tokens || 0) }}</span>
              </div>
            </div>
            <div class="token-stats-grid">
              <div class="token-mini-card">
                <span>请求次数</span>
                <strong>{{ tokenStats?.total?.request_count || 0 }}</strong>
              </div>
              <div class="token-mini-card">
                <span>会话数</span>
                <strong>{{ tokenStats?.total?.session_count || 0 }}</strong>
              </div>
              <div class="token-mini-card accent">
                <span>平均每次请求</span>
                <strong>{{ avgTokensPerRequest }}</strong>
              </div>
            </div>
            <div v-if="tokenStats?.by_user?.length" class="token-ranking">
              <div class="token-ranking-title">高使用用户</div>
              <div class="token-ranking-list">
                <div v-for="(user, index) in tokenStats.by_user.slice(0, 3)" :key="user.user_id" class="token-ranking-item">
                  <span>{{ index + 1 }}. {{ getUserDisplayName(user) }}</span>
                  <strong>{{ formatTokenCount(user.total_tokens) }}</strong>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="trend-grid">
          <article class="surface-card trend-panel">
            <div class="section-head">
              <div>
                <span class="section-kicker">Execution Trend</span>
                <h3 class="section-title">近 7 天执行趋势</h3>
              </div>
              <div class="trend-summary">
                <span class="summary-item">近 30 天 {{ statistics?.execution_trend?.summary_30d?.execution_count || 0 }} 次</span>
                <span class="summary-item passed">通过 {{ statistics?.execution_trend?.summary_30d?.passed || 0 }}</span>
                <span class="summary-item failed">失败 {{ statistics?.execution_trend?.summary_30d?.failed || 0 }}</span>
              </div>
            </div>
            <div class="trend-chart">
              <div
                v-for="(day, index) in statistics?.execution_trend?.daily_7d || []"
                :key="index"
                class="trend-column"
              >
                <div class="trend-bar-shell">
                  <div
                    class="trend-bar passed"
                    :style="{ height: getBarHeight(day.passed) }"
                    :title="`通过：${day.passed}`"
                  ></div>
                  <div
                    class="trend-bar failed"
                    :style="{ height: getBarHeight(day.failed) }"
                    :title="`失败：${day.failed}`"
                  ></div>
                </div>
                <div class="trend-column-meta">
                  <span class="trend-date">{{ formatDate(day.date) }}</span>
                  <span class="trend-total">{{ day.passed + day.failed }}</span>
                </div>
              </div>
            </div>
            <div class="trend-legend">
              <span class="legend-tag passed">通过</span>
              <span class="legend-tag failed">失败</span>
            </div>
          </article>

          <article class="surface-card operations-panel">
            <div class="section-head">
              <div>
                <span class="section-kicker">Operations</span>
                <h3 class="section-title">项目运营看板</h3>
              </div>
            </div>
            <div class="operations-list">
              <div v-for="item in operationalCards" :key="item.label" class="operations-item">
                <div class="operations-item-copy">
                  <span class="operations-item-label">{{ item.label }}</span>
                  <p class="operations-item-desc">{{ item.description }}</p>
                </div>
                <strong class="operations-item-value">{{ item.value }}</strong>
              </div>
            </div>
          </article>
        </section>

      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import {
  IconBarChart, IconFile, IconThunderbolt, IconApps, IconDesktop
} from '@arco-design/web-vue/es/icon'
import { getProjectStatistics, getTokenUsageStats, type ProjectStatistics, type TokenUsageStats } from '@/services/projectService'
import { useProjectStore } from '@/store/projectStore'
import { useAuthStore } from '@/store/authStore'
import { getUserDisplayName } from '@/utils/userDisplay'
import { fetchTokenUsageStats } from '@/features/langgraph/services/llmConfigService'
import type { TokenUsageStats as LlmTokenUsageStats } from '@/features/langgraph/types/llmConfig'

const projectStore = useProjectStore()
const authStore = useAuthStore()
const router = useRouter()
const loading = ref(false)
const statistics = ref<ProjectStatistics | null>(null)
const tokenStats = ref<TokenUsageStats | null>(null)
const tokenPeriod = ref<'day' | 'week' | 'month'>('day')
const tokenUsageStats = ref<LlmTokenUsageStats | null>(null)
const tokenUsageLoading = ref(false)
const usagePreset = ref<'today' | '7d' | '30d' | 'custom'>('today')
const usageSource = ref('')
const currentProjectName = computed(() => projectStore.currentProject?.name || 'FlyTest Project')
const DASHBOARD_REFRESH_INTERVAL_MS = 120000
const DASHBOARD_FOCUS_REFRESH_COOLDOWN_MS = 15000
let dashboardRefreshTimer: ReturnType<typeof setTimeout> | null = null
let isDashboardRefreshing = false
let isSecondaryLoading = false
let lastRefreshStartedAt = 0
let lastLoadedProjectId: number | null = null

const periodOptions = [
  { label: '日', value: 'day' as const },
  { label: '周', value: 'week' as const },
  { label: '月', value: 'month' as const },
]

const currentProjectId = computed(() => projectStore.currentProjectId)
const currentUser = computed(() => authStore.currentUser)
const isApproved = computed(() => authStore.isApproved)
const approvalSubtitle = computed(() => {
  if (currentUser.value?.approval_status === 'rejected') {
    return currentUser.value.approval_review_note || '当前账号已被驳回，请联系管理员处理。'
  }
  return '新注册用户默认没有后台权限，请等待管理员审核并分配权限后再使用管理后台。'
})

const goToProjectManagement = () => {
  void router.push({ name: 'ProjectManagement' })
}

const formatDashboardDate = (date: Date): string => {
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const usageStartDate = ref(formatDashboardDate(new Date()))
const usageEndDate = ref(formatDashboardDate(new Date()))

const passRate = computed(() => {
  const total = statistics.value?.executions?.case_results?.total || 0
  const passed = statistics.value?.executions?.case_results?.passed || 0
  if (total === 0) return 0
  return Math.round((passed / total) * 100)
})

const rateColor = computed(() => {
  if (passRate.value >= 80) return '#22c55e'
  if (passRate.value >= 60) return '#f59e0b'
  return '#ef4444'
})

const passRateTone = computed(() => {
  if (passRate.value >= 80) return 'good'
  if (passRate.value >= 60) return 'warning'
  return 'risk'
})

const passRateStatusText = computed(() => {
  if (passRate.value >= 80) return '质量稳定'
  if (passRate.value >= 60) return '需要关注'
  return '存在风险'
})

const reviewStatusData = computed(() => {
  const total = statistics.value?.testcases?.total || 0
  const getPercent = (val: number) => total === 0 ? 0 : Math.round((val / total) * 100)
  const statuses = statistics.value?.testcases?.by_review_status

  return [
    { key: 'approved', label: '已通过', value: statuses?.approved || 0, percent: getPercent(statuses?.approved || 0), color: '#22c55e' },
    { key: 'pending', label: '待审核', value: statuses?.pending_review || 0, percent: getPercent(statuses?.pending_review || 0), color: '#f59e0b' },
    { key: 'optimization', label: '待优化', value: statuses?.needs_optimization || 0, percent: getPercent(statuses?.needs_optimization || 0), color: '#3b82f6' },
    { key: 'opt_pending', label: '优化待审', value: statuses?.optimization_pending_review || 0, percent: getPercent(statuses?.optimization_pending_review || 0), color: '#8b5cf6' },
    { key: 'unavailable', label: '不可用', value: statuses?.unavailable || 0, percent: getPercent(statuses?.unavailable || 0), color: '#ef4444' },
  ]
})

const executionLegend = computed(() => [
  { label: '通过', value: statistics.value?.executions?.case_results?.passed || 0, color: '#22c55e' },
  { label: '失败', value: statistics.value?.executions?.case_results?.failed || 0, color: '#ef4444' },
  { label: '跳过', value: statistics.value?.executions?.case_results?.skipped || 0, color: '#f59e0b' },
  { label: '错误', value: statistics.value?.executions?.case_results?.error || 0, color: '#fb7185' },
])

const heroHighlights = computed(() => [
  {
    label: '测试用例总量',
    value: statistics.value?.testcases?.total || 0,
  },
  {
    label: '近 30 天执行次数',
    value: statistics.value?.execution_trend?.summary_30d?.execution_count || 0,
  },
  {
    label: '自动化用例规模',
    value: statistics.value?.ui_automation?.total_cases || 0,
  },
])

const governanceSnapshot = computed(() => [
  { label: 'MCP 已启用', value: `${statistics.value?.mcp?.active || 0}/${statistics.value?.mcp?.total || 0}` },
  { label: 'Skills 已启用', value: `${statistics.value?.skills?.active || 0}/${statistics.value?.skills?.total || 0}` },
  { label: 'AI 会话数', value: tokenStats.value?.total?.session_count || 0 },
])

const overviewCards = computed(() => [
  {
    title: '测试用例库',
    caption: '需求与回归资产沉淀',
    value: statistics.value?.testcases?.total || 0,
    unit: '条',
    icon: IconFile,
    tags: [
      { label: '通过', value: statistics.value?.testcases?.by_review_status?.approved || 0, tone: 'positive' },
      { label: '待审核', value: statistics.value?.testcases?.by_review_status?.pending_review || 0, tone: 'warning' },
      { label: '待优化', value: statistics.value?.testcases?.by_review_status?.needs_optimization || 0, tone: 'info' },
    ],
  },
  {
    title: 'UI 自动化',
    caption: '执行覆盖与自动化产出',
    value: statistics.value?.ui_automation?.total_cases || 0,
    unit: '条',
    icon: IconDesktop,
    tags: [
      { label: '执行', value: statistics.value?.ui_automation?.total_executions || 0, tone: 'neutral' },
      { label: '成功', value: statistics.value?.ui_automation?.by_status?.success || 0, tone: 'positive' },
      { label: '失败', value: statistics.value?.ui_automation?.by_status?.failed || 0, tone: 'danger' },
    ],
  },
  {
    title: '执行结果',
    caption: '质量稳定性核心指标',
    value: statistics.value?.executions?.total_executions || 0,
    unit: '次',
    icon: IconThunderbolt,
    tags: [
      { label: '通过', value: statistics.value?.executions?.case_results?.passed || 0, tone: 'positive' },
      { label: '失败', value: statistics.value?.executions?.case_results?.failed || 0, tone: 'danger' },
      { label: '跳过', value: statistics.value?.executions?.case_results?.skipped || 0, tone: 'warning' },
    ],
  },
  {
    title: 'MCP / Skills',
    caption: '扩展能力与智能工具底座',
    value: (statistics.value?.mcp?.total || 0) + (statistics.value?.skills?.total || 0),
    unit: '项',
    icon: IconApps,
    tags: [
      { label: 'MCP', value: `${statistics.value?.mcp?.active || 0}/${statistics.value?.mcp?.total || 0}`, tone: 'neutral' },
      { label: 'Skills', value: `${statistics.value?.skills?.active || 0}/${statistics.value?.skills?.total || 0}`, tone: 'info' },
      { label: 'Token', value: formatTokenCount(tokenStats.value?.total?.total_tokens || 0), tone: 'accent' },
    ],
  },
])

const operationalCards = computed(() => [
  {
    label: '审核积压',
    value: statistics.value?.testcases?.by_review_status?.pending_review || 0,
    description: '仍待进入正式可执行状态的测试用例数量。',
  },
  {
    label: '优化中用例',
    value: statistics.value?.testcases?.by_review_status?.needs_optimization || 0,
    description: '建议优先梳理高频失败或描述不完整的用例。',
  },
  {
    label: '自动化失败记录',
    value: statistics.value?.ui_automation?.by_status?.failed || 0,
    description: '持续失败的自动化任务需要尽快回看设备、脚本与环境。',
  },
  {
    label: '资源请求量',
    value: tokenStats.value?.total?.request_count || 0,
    description: '反映当前项目 AI 调用强度与近期分析活跃度。',
  },
])

const backlogCards = computed(() => {
  const caseTotal = statistics.value?.testcases?.total || 0
  const executionTotal = statistics.value?.executions?.total_executions || 0
  const pendingReview = statistics.value?.testcases?.by_review_status?.pending_review || 0
  const needsOptimization = statistics.value?.testcases?.by_review_status?.needs_optimization || 0
  const pendingRetest = statistics.value?.bugs?.pending_retest || 0
  const uiFailed = statistics.value?.ui_automation?.by_status?.failed || 0
  const getPercent = (value: number, base: number) => base === 0 ? 0 : Math.min(100, Math.round((value / base) * 100))

  return [
    {
      label: '待审核用例',
      description: '还未进入正式可执行状态，影响新增需求流转。',
      value: pendingReview,
      share: `${getPercent(pendingReview, caseTotal)}%`,
      percent: getPercent(pendingReview, caseTotal),
      color: '#f59e0b',
    },
    {
      label: '待优化用例',
      description: '建议优先回看描述不完整或频繁波动的用例。',
      value: needsOptimization,
      share: `${getPercent(needsOptimization, caseTotal)}%`,
      percent: getPercent(needsOptimization, caseTotal),
      color: '#3b82f6',
    },
    {
      label: '待回归缺陷',
      description: '修复已提交，当前仍等待验证闭环。',
      value: pendingRetest,
      share: `${getPercent(pendingRetest, Math.max(statistics.value?.bugs?.total || 0, 1))}%`,
      percent: getPercent(pendingRetest, Math.max(statistics.value?.bugs?.total || 0, 1)),
      color: '#8b5cf6',
    },
    {
      label: 'UI 失败记录',
      description: '优先排查环境、脚本和元素定位稳定性。',
      value: uiFailed,
      share: `${getPercent(uiFailed, executionTotal)}%`,
      percent: getPercent(uiFailed, executionTotal),
      color: '#ef4444',
    },
  ]
})

const backlogTotal = computed(() => backlogCards.value.reduce((sum, item) => sum + item.value, 0))

const bugRiskCards = computed(() => {
  const bugTotal = Math.max(statistics.value?.bugs?.total || 0, 1)
  const getPercent = (value: number) => Math.min(100, Math.round((value / bugTotal) * 100))

  return [
    {
      label: '高优先级缺陷',
      value: statistics.value?.bugs?.high_severity || 0,
      description: '直接影响核心流程，建议持续追踪修复时效。',
      percent: getPercent(statistics.value?.bugs?.high_severity || 0),
      color: '#ef4444',
    },
    {
      label: '已确认待修复',
      value: statistics.value?.bugs?.by_status?.confirmed || 0,
      description: '问题已定位，需要明确版本与负责人。',
      percent: getPercent(statistics.value?.bugs?.by_status?.confirmed || 0),
      color: '#f97316',
    },
    {
      label: '处理中',
      value: statistics.value?.bugs?.by_status?.assigned || 0,
      description: '开发处理中，适合和迭代节奏一起看。',
      percent: getPercent(statistics.value?.bugs?.by_status?.assigned || 0),
      color: '#3b82f6',
    },
    {
      label: '已关闭',
      value: statistics.value?.bugs?.closed || 0,
      description: '已完成修复闭环，可作为当前消化进度参考。',
      percent: getPercent(statistics.value?.bugs?.closed || 0),
      color: '#22c55e',
    },
  ]
})

const automationMatrixCards = computed(() => {
  const uiTotal = statistics.value?.ui_automation?.total_cases || 0
  const uiSuccess = statistics.value?.ui_automation?.by_status?.success || 0
  const uiFailed = statistics.value?.ui_automation?.by_status?.failed || 0
  const apiRequests = statistics.value?.api_automation?.requests || 0
  const apiCases = statistics.value?.api_automation?.test_cases || 0
  const apiExecutions = statistics.value?.api_automation?.executions || 0
  const appTotal = 0
  const appStatus = '待接入'

  return [
    {
      label: 'API 自动化',
      status: apiCases > 0 ? '已接入' : '待补齐',
      tone: apiCases > 0 ? 'good' : 'warning',
      description: '接口侧数据结构已预留，适合补执行覆盖与成功率。',
      total: apiCases,
      metricA: `请求 ${apiRequests}`,
      metricB: `执行 ${apiExecutions}`,
    },
    {
      label: 'UI 自动化',
      status: uiTotal > 0 ? '运行中' : '待建设',
      tone: uiTotal > 0 ? 'good' : 'warning',
      description: '更适合盯稳定性、失败数和回归覆盖面。',
      total: uiTotal,
      metricA: `成功 ${uiSuccess}`,
      metricB: `失败 ${uiFailed}`,
    },
    {
      label: 'APP 自动化',
      status: appStatus,
      tone: 'muted',
      description: '首页先保留入口位，后续接入真机与移动回归数据。',
      total: appTotal,
      metricA: '设备 0',
      metricB: '执行 0',
    },
  ]
})

const automationFootnote = computed(() => {
  const activeLines = automationMatrixCards.value.filter(item => item.total > 0).length
  return `${activeLines}/3 已形成数据`
})

const getBarHeight = (value: number): string => {
  const maxValue = Math.max(
    ...(statistics.value?.execution_trend?.daily_7d?.map(d => Math.max(d.passed, d.failed)) || [1])
  )
  if (maxValue === 0) return '6px'
  const height = Math.max(6, (value / maxValue) * 110)
  return `${height}px`
}

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const formatTokenCount = (count: number): string => {
  return count.toLocaleString('zh-CN')
}

const avgTokensPerRequest = computed(() => {
  const total = tokenStats.value?.total?.total_tokens || 0
  const requests = tokenStats.value?.total?.request_count || 0
  if (requests === 0) return '0'
  return formatTokenCount(Math.round(total / requests))
})

const canTriggerRefresh = () => {
  const now = Date.now()
  return !isDashboardRefreshing && now - lastRefreshStartedAt >= DASHBOARD_FOCUS_REFRESH_COOLDOWN_MS
}

const clearDashboardRefreshTimer = () => {
  if (dashboardRefreshTimer !== null) {
    clearTimeout(dashboardRefreshTimer)
    dashboardRefreshTimer = null
  }
}

const scheduleDashboardRefresh = (delay = DASHBOARD_REFRESH_INTERVAL_MS) => {
  clearDashboardRefreshTimer()
  if (!isApproved.value || !currentProjectId.value) {
    return
  }
  dashboardRefreshTimer = setTimeout(() => {
    void refreshDashboardData({ silent: true })
  }, delay)
}

const fetchTokenStats = async () => {
  try {
    const response = await getTokenUsageStats({ group_by: tokenPeriod.value })
    if (response.success && response.data) {
      tokenStats.value = response.data
    }
  } catch (error) {
    console.error('获取 Token 统计数据出错:', error)
  }
}

const changeTokenPeriod = (period: 'day' | 'week' | 'month') => {
  tokenPeriod.value = period
  void fetchTokenStats()
}

const fetchTokenUsage = async () => {
  tokenUsageLoading.value = true
  try {
    const response = await fetchTokenUsageStats({
      preset: usagePreset.value === 'custom' ? undefined : usagePreset.value,
      start_date: usagePreset.value === 'custom' ? usageStartDate.value : undefined,
      end_date: usagePreset.value === 'custom' ? usageEndDate.value : undefined,
      source: usageSource.value || undefined,
    })
    if (response.status === 'success') {
      tokenUsageStats.value = response.data
    }
  } catch (error) {
    console.error('获取 Token 仪表盘数据出错:', error)
  } finally {
    tokenUsageLoading.value = false
  }
}

const handleUsagePresetChange = (preset: string) => {
  usagePreset.value = preset as typeof usagePreset.value
  const end = new Date()
  const start = new Date()
  if (preset === 'today') {
    usageStartDate.value = formatDashboardDate(end)
    usageEndDate.value = formatDashboardDate(end)
  } else if (preset === '7d') {
    start.setDate(end.getDate() - 6)
    usageStartDate.value = formatDashboardDate(start)
    usageEndDate.value = formatDashboardDate(end)
  } else if (preset === '30d') {
    start.setDate(end.getDate() - 29)
    usageStartDate.value = formatDashboardDate(start)
    usageEndDate.value = formatDashboardDate(end)
  }
  void fetchTokenUsage()
}

const handleUsageSourceChange = (source: string) => {
  usageSource.value = source
  void fetchTokenUsage()
}

const handleUsageDateRangeChange = (payload: { startDate: string; endDate: string }) => {
  usageStartDate.value = payload.startDate
  usageEndDate.value = payload.endDate
  usagePreset.value = 'custom'
  void fetchTokenUsage()
}

const fetchStatistics = async ({ controlLoading = true }: { controlLoading?: boolean } = {}) => {
  if (!currentProjectId.value) return
  if (!isApproved.value) return

  if (controlLoading) {
    loading.value = true
  }
  try {
    const response = await getProjectStatistics(currentProjectId.value)
    if (response.success && response.data) {
      statistics.value = response.data
    } else {
      Message.error(response.error || '获取统计数据失败')
    }
  } catch (error) {
    console.error('获取统计数据出错:', error)
    Message.error('获取统计数据时发生错误')
  } finally {
    if (controlLoading) {
      loading.value = false
    }
  }
}

const fetchDashboardSecondaryData = async () => {
  if (isSecondaryLoading || !isApproved.value || !currentProjectId.value) {
    return
  }

  isSecondaryLoading = true
  try {
    await Promise.allSettled([
      fetchTokenStats(),
      fetchTokenUsage(),
    ])
  } finally {
    isSecondaryLoading = false
  }
}

const refreshDashboardData = async ({
  silent = false,
  projectChanged = false,
}: {
  silent?: boolean
  projectChanged?: boolean
} = {}) => {
  if (!isApproved.value || !currentProjectId.value) {
    clearDashboardRefreshTimer()
    return
  }
  if (isDashboardRefreshing) {
    return
  }

  isDashboardRefreshing = true
  lastRefreshStartedAt = Date.now()
  if (!silent) {
    loading.value = true
  }

  try {
    await fetchStatistics({ controlLoading: false })
    if (projectChanged) {
      tokenStats.value = null
      tokenUsageStats.value = null
    }
    void fetchDashboardSecondaryData()
  } finally {
    isDashboardRefreshing = false
    if (!silent) {
      loading.value = false
    }
    scheduleDashboardRefresh()
  }
}

const handleWindowFocus = () => {
  if (!isApproved.value || !currentProjectId.value) {
    return
  }
  if (!canTriggerRefresh()) {
    return
  }
  void refreshDashboardData({ silent: true })
}

const handleVisibilityChange = () => {
  if (document.visibilityState !== 'visible') {
    clearDashboardRefreshTimer()
    return
  }
  if (!isApproved.value || !currentProjectId.value) {
    return
  }
  if (!canTriggerRefresh()) {
    return
  }
  void refreshDashboardData({ silent: true })
}

watch(currentProjectId, (newProjectId) => {
  if (!isApproved.value) {
    statistics.value = null
    tokenStats.value = null
    tokenUsageStats.value = null
    clearDashboardRefreshTimer()
    lastLoadedProjectId = null
  } else if (newProjectId) {
    const projectChanged = newProjectId !== lastLoadedProjectId
    lastLoadedProjectId = newProjectId
    void refreshDashboardData({ projectChanged })
  } else {
    statistics.value = null
    tokenStats.value = null
    tokenUsageStats.value = null
    clearDashboardRefreshTimer()
    lastLoadedProjectId = null
  }
}, { immediate: true })

onMounted(() => {
  window.addEventListener('focus', handleWindowFocus)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  clearDashboardRefreshTimer()
  window.removeEventListener('focus', handleWindowFocus)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.dashboard-view {
  min-height: 100%;
  padding: 16px;
  background:
    radial-gradient(circle at top left, rgba(var(--theme-accent-rgb), 0.16), transparent 24%),
    radial-gradient(circle at top right, rgba(var(--theme-accent-secondary-rgb), 0.12), transparent 20%),
    radial-gradient(circle at bottom right, rgba(var(--theme-accent-tertiary-rgb), 0.11), transparent 22%),
    linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(240, 245, 252, 0.92));
  box-sizing: border-box;
  overflow-y: auto;
}

.dashboard-content {
  display: flex;
  flex-direction: column;
}

.dashboard-spin {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:deep(.arco-spin-children) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.approval-pending-card,
.no-project-selected {
  min-height: calc(100vh - 180px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.approval-shell,
.empty-project-shell {
  width: min(760px, 100%);
  padding: 32px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 28px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
}

.approval-kicker {
  margin-bottom: 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-accent);
}

.empty-project-shell {
  display: flex;
  align-items: center;
  gap: 20px;
}

.empty-project-icon {
  width: 80px;
  height: 80px;
  border-radius: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--theme-accent-rgb), 0.1);
  color: var(--theme-accent);
  font-size: 34px;
}

.empty-project-copy h2 {
  margin: 0 0 10px;
  font-size: 26px;
  color: var(--theme-text);
}

.empty-project-copy p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--theme-text-secondary);
}

.empty-project-actions {
  margin-top: 18px;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
  gap: 12px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.24), transparent 28%),
    radial-gradient(circle at bottom left, rgba(var(--theme-accent-secondary-rgb), 0.16), transparent 24%),
    linear-gradient(140deg, rgba(255, 255, 255, 0.99), rgba(243, 248, 255, 0.96));
  box-shadow: 0 30px 72px rgba(15, 23, 42, 0.1);
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hero-kicker-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.hero-eyebrow,
.hero-project-chip,
.section-kicker,
.hero-aside-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-eyebrow,
.section-kicker,
.hero-aside-kicker {
  color: var(--theme-accent);
}

.hero-project-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--theme-text-secondary);
  letter-spacing: 0;
  text-transform: none;
}

.hero-title {
  margin: 0;
  font-family: var(--theme-display-font);
  font-size: 28px;
  line-height: 1.1;
  color: var(--theme-text);
}

.hero-highlights {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.hero-kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.hero-highlight-card,
.hero-aside-panel,
.hero-kpi-card,
.surface-card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(249, 251, 255, 0.88));
  box-shadow: 0 20px 46px rgba(15, 23, 42, 0.06);
}

.hero-highlight-card:nth-child(1) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(255, 255, 255, 0.94));
}

.hero-highlight-card:nth-child(2) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-secondary-rgb), 0.08), rgba(255, 255, 255, 0.94));
}

.hero-highlight-card:nth-child(3) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-tertiary-rgb), 0.08), rgba(255, 255, 255, 0.94));
}

.hero-highlight-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 72px;
  padding: 10px 12px;
  border-radius: 12px;
}

.hero-highlight-label,
.kpi-caption,
.hero-highlight-foot,
.governance-label,
.section-badge,
.review-label,
.trend-date,
.operations-item-desc,
.token-total-label {
  color: var(--theme-text-secondary);
}

.hero-highlight-label {
  font-size: 12px;
  font-weight: 600;
}

.hero-highlight-value {
  font-size: 22px;
  line-height: 1;
  color: var(--theme-text);
}

.hero-kpi-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 82px;
  padding: 10px 12px;
  border-radius: 12px;
}

.hero-kpi-card:nth-child(1) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.09), rgba(255, 255, 255, 0.95));
}

.hero-kpi-card:nth-child(2) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-secondary-rgb), 0.09), rgba(255, 255, 255, 0.95));
}

.hero-kpi-card:nth-child(3) {
  background: linear-gradient(180deg, rgba(var(--theme-accent-tertiary-rgb), 0.09), rgba(255, 255, 255, 0.95));
}

.hero-kpi-card:nth-child(4) {
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.08), rgba(255, 255, 255, 0.95));
}

.hero-kpi-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hero-kpi-icon {
  font-size: 15px;
  color: var(--theme-accent);
}

.hero-kpi-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--theme-text-secondary);
}

.hero-kpi-value-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
}

.hero-kpi-value {
  font-size: 22px;
  line-height: 1;
  color: var(--theme-text);
}

.hero-kpi-unit {
  font-size: 10px;
  color: var(--theme-text-tertiary);
  margin-bottom: 2px;
}

.hero-aside {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hero-aside-panel {
  padding: 12px;
  border-radius: 14px;
}

.hero-aside-panel.compact {
  padding-top: 12px;
}

.hero-inline-status {
  flex-shrink: 0;
  padding: 5px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.hero-inline-status.good {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.hero-inline-status.warning {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.hero-inline-status.risk {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.hero-aside-head,
.section-head,
.kpi-head,
.review-item-head,
.trend-column-meta,
.token-ranking-item,
.operations-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hero-aside-badge,
.section-badge,
.kpi-tag,
.period-tag {
  border-radius: 999px;
}

.hero-aside-badge {
  padding: 5px 8px;
  font-size: 11px;
  font-weight: 700;
}

.hero-aside-badge.good {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.hero-aside-badge.warning {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.hero-aside-badge.risk {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.hero-score-row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  margin-top: 8px;
}

.hero-score-ring {
  position: relative;
  width: 96px;
  height: 96px;
}

.hero-score-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.hero-score-track,
.hero-score-progress,
.execution-ring-track,
.execution-ring-progress {
  fill: none;
  stroke-linecap: round;
}

.hero-score-track {
  stroke: rgba(148, 163, 184, 0.2);
  stroke-width: 10;
}

.hero-score-progress {
  stroke-width: 10;
  transition: stroke-dasharray 0.4s ease;
}

.hero-score-text,
.execution-ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.hero-score-text strong {
  font-size: 22px;
  color: var(--theme-text);
  line-height: 1;
}

.hero-score-text span {
  margin-top: 4px;
  font-size: 11px;
  color: var(--theme-text-secondary);
}

.hero-score-meta {
  display: grid;
  gap: 6px;
}

.hero-score-stat {
  display: flex;
  justify-content: space-between;
  padding: 7px 9px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.88);
}

.hero-score-stat span {
  font-size: 11px;
  color: var(--theme-text-secondary);
}

.hero-score-stat strong,
.governance-value,
.section-title,
.kpi-value,
.review-value,
.execution-legend-value,
.trend-total,
.operations-item-value,
.token-ranking-item strong {
  color: var(--theme-text);
}

.hero-score-stat strong {
  font-size: 13px;
}

.governance-list {
  display: grid;
  gap: 6px;
  margin-top: 6px;
}

.governance-item {
  display: flex;
  justify-content: space-between;
  padding: 7px 9px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.9);
}

.governance-label {
  font-size: 11px;
}

.governance-value {
  font-size: 13px;
  font-weight: 700;
}

.hero-kpi-card:hover,
.surface-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.08);
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.9fr) minmax(0, 1fr);
  gap: 12px;
}

.secondary-insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(340px, 0.9fr);
  gap: 12px;
  margin-top: 12px;
}

.surface-card {
  --card-accent-rgb: var(--theme-accent-rgb);
  position: relative;
  overflow: hidden;
  padding: 14px;
  border-radius: 16px;
  border-color: rgba(var(--card-accent-rgb), 0.14);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

.surface-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 4px;
  border-radius: 0 0 999px 999px;
  background: rgba(var(--card-accent-rgb), 0.78);
}

.backlog-card {
  --card-accent-rgb: var(--theme-accent-rgb);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.14), rgba(255, 255, 255, 0.95));
}

.bug-risk-card {
  --card-accent-rgb: 239, 68, 68;
  background:
    linear-gradient(180deg, rgba(239, 68, 68, 0.12), rgba(255, 255, 255, 0.95));
}

.automation-matrix-card {
  --card-accent-rgb: var(--theme-accent-secondary-rgb);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-secondary-rgb), 0.14), rgba(255, 255, 255, 0.95));
}

.review-card {
  --card-accent-rgb: var(--theme-accent-tertiary-rgb);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-tertiary-rgb), 0.12), rgba(255, 255, 255, 0.95));
}

.token-card {
  --card-accent-rgb: 245, 158, 11;
  background:
    linear-gradient(180deg, rgba(245, 158, 11, 0.12), rgba(255, 255, 255, 0.95));
}

.trend-panel {
  --card-accent-rgb: var(--theme-accent-rgb);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.11), rgba(255, 255, 255, 0.96));
}

.operations-panel {
  --card-accent-rgb: var(--theme-accent-secondary-rgb);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-secondary-rgb), 0.11), rgba(255, 255, 255, 0.96));
}

.section-head {
  gap: 10px;
  margin-bottom: 12px;
}

.section-title {
  margin: 4px 0 0;
  font-size: 16px;
  line-height: 1.2;
}

.section-badge {
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(var(--card-accent-rgb), 0.92);
  background: rgba(var(--card-accent-rgb), 0.1);
}

.review-list {
  display: grid;
  gap: 10px;
}

.backlog-list,
.bug-risk-list,
.automation-matrix {
  display: grid;
  gap: 10px;
}

.backlog-item,
.bug-risk-item,
.automation-row {
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.backlog-main,
.automation-row-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.backlog-copy,
.bug-risk-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.backlog-label,
.bug-risk-label,
.automation-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--theme-text);
}

.backlog-desc,
.bug-risk-desc,
.automation-desc {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--theme-text-secondary);
}

.backlog-value-block {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 72px;
}

.backlog-value,
.bug-risk-value,
.automation-total {
  font-size: 22px;
  line-height: 1;
  color: var(--theme-text);
}

.backlog-share {
  font-size: 11px;
  font-weight: 600;
  color: var(--theme-text-secondary);
}

.review-track.compact {
  margin-top: 8px;
  height: 6px;
}

.bug-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  margin-bottom: 10px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(255, 255, 255, 0.92));
}

.bug-hero-value {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bug-hero-value strong {
  font-size: 28px;
  line-height: 1;
  color: #b91c1c;
}

.bug-hero-value span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.bug-hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.bug-tag,
.automation-status {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.bug-tag.danger {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.12);
}

.bug-tag.warning {
  color: #7c3aed;
  background: rgba(139, 92, 246, 0.12);
}

.bug-risk-head {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.automation-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.automation-status.good {
  color: #166534;
  background: rgba(34, 197, 94, 0.12);
}

.automation-status.warning {
  color: #b45309;
  background: rgba(245, 158, 11, 0.14);
}

.automation-status.muted {
  color: #475569;
  background: rgba(148, 163, 184, 0.16);
}

.automation-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.automation-metrics span {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: var(--theme-text-secondary);
  background: rgba(15, 23, 42, 0.06);
}

.review-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.9);
}

.review-label,
.review-value {
  font-size: 12px;
}

.review-value {
  font-weight: 700;
}

.review-track {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.15);
}

.review-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.3s ease;
}

.execution-summary {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
}

.execution-ring {
  position: relative;
  width: 132px;
  height: 132px;
}

.execution-ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.execution-ring-track {
  stroke: rgba(148, 163, 184, 0.18);
  stroke-width: 8;
}

.execution-ring-progress {
  stroke-width: 8;
  transition: stroke-dasharray 0.4s ease;
}

.execution-ring-text strong {
  font-size: 28px;
  line-height: 1;
}

.execution-ring-text span {
  margin-top: 6px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.execution-legend {
  display: grid;
  gap: 8px;
}

.execution-legend-item {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.92);
}

.execution-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.execution-legend-label {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.execution-legend-value {
  font-size: 14px;
}

.token-total-panel {
  padding: 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(255, 255, 255, 0.82));
}

.token-total-label {
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.token-total-value {
  display: block;
  font-size: 26px;
  line-height: 1.1;
  color: var(--theme-accent);
}

.token-total-meta {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--theme-text-secondary);
}

.token-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.token-mini-card {
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.92);
}

.token-mini-card span {
  display: block;
  font-size: 11px;
  color: var(--theme-text-secondary);
}

.token-mini-card strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  color: var(--theme-text);
}

.token-mini-card.accent {
  background: rgba(var(--theme-accent-rgb), 0.08);
}

.token-mini-card.accent strong {
  color: var(--theme-accent);
}

.token-ranking {
  margin-top: 12px;
}

.token-ranking-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--theme-text);
}

.token-ranking-list {
  display: grid;
  gap: 8px;
}

.token-ranking-item {
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.92);
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.token-period-selector {
  display: flex;
  gap: 6px;
}

.period-tag {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--theme-text-secondary);
  background: rgba(15, 23, 42, 0.06);
  transition: all 0.2s ease;
}

.period-tag:hover {
  color: var(--theme-accent);
}

.period-tag.active {
  color: #fff;
  background: var(--theme-accent);
}

.trend-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.85fr);
  gap: 12px;
}

.trend-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-item {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: var(--theme-text-secondary);
  background: rgba(15, 23, 42, 0.06);
}

.summary-item.passed {
  color: #15803d;
  background: rgba(34, 197, 94, 0.12);
}

.summary-item.failed {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.12);
}

.trend-chart {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  align-items: end;
  min-height: 176px;
}

.trend-column {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 8px;
}

.trend-bar-shell {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 5px;
  min-height: 124px;
  padding: 8px 0;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.86), rgba(241, 245, 249, 0.98));
}

.trend-bar {
  width: 12px;
  border-radius: 999px;
  transition: height 0.3s ease;
}

.trend-bar.passed {
  background: linear-gradient(180deg, #4ade80, #16a34a);
}

.trend-bar.failed {
  background: linear-gradient(180deg, #fb7185, #ef4444);
}

.trend-column-meta {
  gap: 6px;
}

.trend-date,
.trend-total {
  font-size: 11px;
}

.trend-total {
  font-weight: 700;
}

.trend-legend {
  display: flex;
  gap: 14px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.legend-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--theme-text-secondary);
}

.legend-tag::before {
  content: '';
  width: 14px;
  height: 10px;
  border-radius: 999px;
}

.legend-tag.passed::before {
  background: linear-gradient(180deg, #4ade80, #16a34a);
}

.legend-tag.failed::before {
  background: linear-gradient(180deg, #fb7185, #ef4444);
}

.operations-list {
  display: grid;
  gap: 8px;
}

.operations-item {
  gap: 12px;
  align-items: flex-start;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(252, 253, 255, 0.92);
}

.operations-item-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.operations-item-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--theme-text);
}

.operations-item-desc {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.operations-item-value {
  font-size: 22px;
  line-height: 1;
}

@media (max-width: 1400px) {
  .hero-section,
  .insight-grid,
  .secondary-insight-grid,
  .trend-grid {
    grid-template-columns: 1fr;
  }

  .hero-kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .dashboard-view {
    padding: 12px;
  }

  .hero-section,
  .surface-card,
  .approval-shell,
  .empty-project-shell {
    padding: 18px;
    border-radius: 20px;
  }

  .hero-title {
    font-size: 28px;
  }

  .hero-highlights,
  .hero-kpi-strip,
  .token-stats-grid {
    grid-template-columns: 1fr;
  }

  .backlog-main,
  .automation-row-main,
  .bug-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .backlog-value-block {
    align-items: flex-start;
  }

  .hero-score-row,
  .execution-summary {
    grid-template-columns: 1fr;
  }

  .trend-chart {
    gap: 8px;
  }

  .empty-project-shell {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>


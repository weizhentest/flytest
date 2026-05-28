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
          <h2>请选择项目后查看管理首页</h2>
          <p>首页会集中展示当前项目的测试用例、执行结果、自动化能力与 AI 资源使用情况。</p>
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
            <h1 class="hero-title">{{ currentProjectName }}</h1>
            <p class="hero-description">
              面向测试管理、质量治理与 AI 能力协同的统一工作台，帮助团队快速掌握用例规模、执行质量、自动化产出与资源消耗。
            </p>

            <div class="hero-highlights">
              <div v-for="item in heroHighlights" :key="item.label" class="hero-highlight-card">
                <span class="hero-highlight-label">{{ item.label }}</span>
                <strong class="hero-highlight-value">{{ item.value }}</strong>
                <span class="hero-highlight-foot">{{ item.foot }}</span>
              </div>
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

        <section class="kpi-grid">
          <article v-for="card in overviewCards" :key="card.title" class="kpi-card">
            <div class="kpi-head">
              <div class="kpi-icon-wrap">
                <component :is="card.icon" class="kpi-icon" />
              </div>
              <div class="kpi-head-copy">
                <span class="kpi-title">{{ card.title }}</span>
                <span class="kpi-caption">{{ card.caption }}</span>
              </div>
            </div>
            <div class="kpi-value-row">
              <strong class="kpi-value">{{ card.value }}</strong>
              <span class="kpi-value-unit">{{ card.unit }}</span>
            </div>
            <div class="kpi-tags">
              <span
                v-for="tag in card.tags"
                :key="`${card.title}-${tag.label}`"
                class="kpi-tag"
                :class="tag.tone"
              >
                {{ tag.label }} {{ tag.value }}
              </span>
            </div>
          </article>
        </section>

        <section class="insight-grid">
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

          <article class="surface-card execution-card">
            <div class="section-head">
              <div>
                <span class="section-kicker">Execution Quality</span>
                <h3 class="section-title">执行结果结构</h3>
              </div>
              <span class="section-badge">{{ statistics?.executions?.total_executions || 0 }} 次</span>
            </div>
            <div class="execution-summary">
              <div class="execution-ring">
                <svg viewBox="0 0 100 100" class="execution-ring-svg">
                  <circle cx="50" cy="50" r="42" class="execution-ring-track" />
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    class="execution-ring-progress"
                    :style="{ strokeDasharray: `${passRate * 2.64} 264`, stroke: rateColor }"
                  />
                </svg>
                <div class="execution-ring-text">
                  <strong>{{ passRate }}</strong>
                  <span>通过率</span>
                </div>
              </div>
              <div class="execution-legend">
                <div v-for="item in executionLegend" :key="item.label" class="execution-legend-item">
                  <span class="execution-legend-dot" :style="{ background: item.color }"></span>
                  <span class="execution-legend-label">{{ item.label }}</span>
                  <strong class="execution-legend-value">{{ item.value }}</strong>
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
                <h3 class="section-title">近 7 天执行走势</h3>
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
    foot: '覆盖当前项目的业务验证基础',
  },
  {
    label: '近 30 天执行次数',
    value: statistics.value?.execution_trend?.summary_30d?.execution_count || 0,
    foot: '反映近期回归与验证活跃度',
  },
  {
    label: '自动化用例规模',
    value: statistics.value?.ui_automation?.total_cases || 0,
    foot: '用于支撑高频回归与持续验证',
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
    radial-gradient(circle at top left, rgba(var(--theme-accent-rgb), 0.06), transparent 22%),
    linear-gradient(180deg, rgba(247, 250, 253, 0.92), rgba(241, 245, 249, 0.88));
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
  gap: 18px;
}

:deep(.arco-spin-children) {
  display: flex;
  flex-direction: column;
  gap: 18px;
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

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
  gap: 18px;
  padding: 24px;
  border-radius: 28px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.16), transparent 26%),
    linear-gradient(140deg, rgba(255, 255, 255, 0.97), rgba(244, 248, 252, 0.92));
  box-shadow: 0 28px 64px rgba(15, 23, 42, 0.08);
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-kicker-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-eyebrow,
.hero-project-chip,
.section-kicker,
.hero-aside-kicker {
  font-size: 12px;
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
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--theme-text-secondary);
  letter-spacing: 0;
  text-transform: none;
}

.hero-title {
  margin: 0;
  font-family: var(--theme-display-font);
  font-size: 34px;
  line-height: 1.1;
  color: var(--theme-text);
}

.hero-description {
  margin: 0;
  max-width: 760px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--theme-text-secondary);
}

.hero-highlights {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.hero-highlight-card,
.hero-aside-panel,
.kpi-card,
.surface-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.05);
}

.hero-highlight-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 124px;
  padding: 18px;
  border-radius: 20px;
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
  font-size: 13px;
  font-weight: 600;
}

.hero-highlight-value {
  font-size: 30px;
  line-height: 1;
  color: var(--theme-text);
}

.hero-highlight-foot {
  font-size: 12px;
  line-height: 1.6;
}

.hero-aside {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-aside-panel {
  padding: 18px;
  border-radius: 22px;
}

.hero-aside-panel.compact {
  padding-top: 16px;
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
  padding: 6px 10px;
  font-size: 12px;
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
  grid-template-columns: 138px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
  margin-top: 12px;
}

.hero-score-ring {
  position: relative;
  width: 138px;
  height: 138px;
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
  font-size: 34px;
  color: var(--theme-text);
  line-height: 1;
}

.hero-score-text span {
  margin-top: 6px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.hero-score-meta {
  display: grid;
  gap: 10px;
}

.hero-score-stat {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.88);
}

.hero-score-stat span {
  font-size: 13px;
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
  font-size: 16px;
}

.governance-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.governance-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
}

.governance-label {
  font-size: 13px;
}

.governance-value {
  font-size: 16px;
  font-weight: 700;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 220px;
  padding: 20px;
  border-radius: 22px;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.kpi-card:hover,
.surface-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.08);
}

.kpi-head {
  gap: 12px;
  justify-content: flex-start;
}

.kpi-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--theme-accent-rgb), 0.1);
}

.kpi-icon {
  font-size: 22px;
  color: var(--theme-accent);
}

.kpi-head-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kpi-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--theme-text);
}

.kpi-caption {
  font-size: 12px;
  line-height: 1.5;
}

.kpi-value-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.kpi-value {
  font-size: 38px;
  line-height: 1;
}

.kpi-value-unit {
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--theme-text-tertiary);
}

.kpi-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}

.kpi-tag {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
}

.kpi-tag.positive {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.kpi-tag.warning {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.kpi-tag.info {
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
}

.kpi-tag.danger {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.kpi-tag.neutral {
  background: rgba(15, 23, 42, 0.06);
  color: var(--theme-text-secondary);
}

.kpi-tag.accent {
  background: rgba(var(--theme-accent-rgb), 0.12);
  color: var(--theme-accent);
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.9fr) minmax(0, 1fr);
  gap: 16px;
}

.surface-card {
  padding: 20px;
  border-radius: 22px;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.section-head {
  gap: 12px;
  margin-bottom: 18px;
}

.section-title {
  margin: 6px 0 0;
  font-size: 22px;
  line-height: 1.2;
}

.section-badge {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(15, 23, 42, 0.06);
}

.review-list {
  display: grid;
  gap: 14px;
}

.review-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-label,
.review-value {
  font-size: 13px;
}

.review-value {
  font-weight: 700;
}

.review-track {
  height: 10px;
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
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 20px;
  align-items: center;
}

.execution-ring {
  position: relative;
  width: 160px;
  height: 160px;
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
  font-size: 34px;
  line-height: 1;
}

.execution-ring-text span {
  margin-top: 6px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.execution-legend {
  display: grid;
  gap: 12px;
}

.execution-legend-item {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
}

.execution-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.execution-legend-label {
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.execution-legend-value {
  font-size: 16px;
}

.token-total-panel {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(255, 255, 255, 0.82));
}

.token-total-label {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}

.token-total-value {
  display: block;
  font-size: 32px;
  line-height: 1.1;
  color: var(--theme-accent);
}

.token-total-meta {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.token-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.token-mini-card {
  padding: 14px 12px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.92);
}

.token-mini-card span {
  display: block;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.token-mini-card strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
  color: var(--theme-text);
}

.token-mini-card.accent {
  background: rgba(var(--theme-accent-rgb), 0.08);
}

.token-mini-card.accent strong {
  color: var(--theme-accent);
}

.token-ranking {
  margin-top: 18px;
}

.token-ranking-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--theme-text);
}

.token-ranking-list {
  display: grid;
  gap: 10px;
}

.token-ranking-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
  font-size: 13px;
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
  gap: 16px;
}

.trend-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-item {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
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
  gap: 10px;
  align-items: end;
  min-height: 220px;
}

.trend-column {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 10px;
}

.trend-bar-shell {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 6px;
  min-height: 150px;
  padding: 12px 0;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.86), rgba(241, 245, 249, 0.98));
}

.trend-bar {
  width: 16px;
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
  gap: 8px;
}

.trend-date,
.trend-total {
  font-size: 12px;
}

.trend-total {
  font-weight: 700;
}

.trend-legend {
  display: flex;
  gap: 18px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.legend-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
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
  gap: 12px;
}

.operations-item {
  gap: 18px;
  align-items: flex-start;
  padding: 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.9);
}

.operations-item-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.operations-item-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--theme-text);
}

.operations-item-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
}

.operations-item-value {
  font-size: 28px;
  line-height: 1;
}

@media (max-width: 1400px) {
  .hero-section,
  .insight-grid,
  .trend-grid {
    grid-template-columns: 1fr;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .dashboard-view {
    padding: 12px;
  }

  .hero-section,
  .surface-card,
  .kpi-card,
  .approval-shell,
  .empty-project-shell {
    padding: 18px;
    border-radius: 20px;
  }

  .hero-title {
    font-size: 28px;
  }

  .hero-highlights,
  .kpi-grid,
  .token-stats-grid {
    grid-template-columns: 1fr;
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

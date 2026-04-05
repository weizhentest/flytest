<template>
  <div class="dashboard-view">
    <div v-if="!currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后查看 APP 自动化概览" />
    </div>
    <template v-else>
      <div class="stats-grid">
        <a-card class="stat-card">
          <div class="stat-label">设备在线</div>
          <div class="stat-value">{{ statistics.devices.online }}</div>
          <div class="stat-meta">总设备 {{ statistics.devices.total }} / 锁定 {{ statistics.devices.locked }}</div>
        </a-card>
        <a-card class="stat-card">
          <div class="stat-label">应用包</div>
          <div class="stat-value">{{ statistics.packages.total }}</div>
          <div class="stat-meta">当前项目已登记应用</div>
        </a-card>
        <a-card class="stat-card">
          <div class="stat-label">元素资产</div>
          <div class="stat-value">{{ statistics.elements.total }}</div>
          <div class="stat-meta">用于定位与页面编排</div>
        </a-card>
        <a-card class="stat-card">
          <div class="stat-label">测试用例</div>
          <div class="stat-value">{{ statistics.test_cases.total }}</div>
          <div class="stat-meta">通过率 {{ statistics.executions.pass_rate }}%</div>
        </a-card>
      </div>

      <div class="content-grid">
        <a-card class="panel-card" title="执行态势">
          <div class="summary-grid">
            <div class="summary-item">
              <span>总执行</span>
              <strong>{{ statistics.executions.total }}</strong>
            </div>
            <div class="summary-item">
              <span>运行中</span>
              <strong>{{ statistics.executions.running }}</strong>
            </div>
            <div class="summary-item">
              <span>通过</span>
              <strong class="success">{{ statistics.executions.passed }}</strong>
            </div>
            <div class="summary-item">
              <span>失败</span>
              <strong class="danger">{{ statistics.executions.failed }}</strong>
            </div>
          </div>
        </a-card>

        <a-card class="panel-card" title="最近执行">
          <a-table :data="statistics.recent_executions" :pagination="false" size="small" :bordered="false">
            <template #columns>
              <a-table-column title="用例" data-index="case_name" />
              <a-table-column title="设备" data-index="device_name" />
              <a-table-column title="状态">
                <template #cell="{ record }">
                  <a-tag :color="record.status === 'completed' ? 'green' : record.status === 'running' ? 'arcoblue' : 'orange'">
                    {{ record.status }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column title="进度">
                <template #cell="{ record }">{{ record.progress }}%</template>
              </a-table-column>
            </template>
          </a-table>
        </a-card>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppDashboardStatistics } from '../types'

const projectStore = useProjectStore()
const currentProjectId = projectStore.currentProjectId

const statistics = reactive<AppDashboardStatistics>({
  devices: { total: 0, online: 0, locked: 0 },
  packages: { total: 0 },
  elements: { total: 0 },
  test_cases: { total: 0 },
  executions: { total: 0, running: 0, passed: 0, failed: 0, pass_rate: 0 },
  recent_executions: [],
})

const loadStatistics = async () => {
  if (!projectStore.currentProjectId) {
    return
  }

  try {
    const data = await AppAutomationService.getDashboardStatistics(projectStore.currentProjectId)
    Object.assign(statistics, data)
  } catch (error: any) {
    Message.error(error.message || '加载 APP 自动化概览失败')
  }
}

let timer: number | null = null

watch(
  () => projectStore.currentProjectId,
  () => {
    void loadStatistics()
  },
  { immediate: true }
)

onMounted(() => {
  timer = window.setInterval(() => {
    void loadStatistics()
  }, 15000)
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})
</script>

<style scoped>
.dashboard-view {
  min-height: 100%;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.stat-card,
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 16px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 700;
  color: var(--theme-text);
}

.stat-meta {
  margin-top: 8px;
  color: var(--theme-text-tertiary);
  font-size: 12px;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr;
  gap: 16px;
  margin-top: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.summary-item {
  padding: 16px;
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-item span {
  color: var(--theme-text-secondary);
}

.summary-item strong {
  font-size: 28px;
  color: var(--theme-text);
}

.summary-item .success {
  color: var(--theme-success);
}

.summary-item .danger {
  color: var(--theme-danger);
}

@media (max-width: 900px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>

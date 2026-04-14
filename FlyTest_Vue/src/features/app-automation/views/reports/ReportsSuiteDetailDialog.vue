<template>
  <a-modal
    v-model:visible="visibleModel"
    title="套件详情"
    width="880px"
    :footer="false"
  >
    <div v-if="selectedSuite" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">最近状态</span>
          <strong>{{ getSuiteStatus(selectedSuite).label }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">套件用例数</span>
          <strong>{{ selectedSuite.test_case_count || 0 }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">平均健康度</span>
          <strong>{{ getSuiteHealthRate(selectedSuite) }}%</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">最近执行</span>
          <strong>{{ formatDateTime(selectedSuite.last_run_at) }}</strong>
        </div>
      </div>

      <a-card class="detail-panel" title="套件说明">
        <div class="summary-text">{{ selectedSuite.description || '暂无套件说明。' }}</div>
        <div class="meta-row">
          <span>创建人：{{ selectedSuite.created_by || '-' }}</span>
          <span>创建时间：{{ formatDateTime(selectedSuite.created_at) }}</span>
          <span>更新时间：{{ formatDateTime(selectedSuite.updated_at) }}</span>
        </div>
      </a-card>

      <a-card class="detail-panel" title="套件用例清单">
        <div v-if="selectedSuite.suite_cases?.length" class="case-list">
          <div v-for="item in selectedSuite.suite_cases" :key="item.id" class="case-item">
            <strong>#{{ item.order }} {{ item.test_case.name }}</strong>
            <span>{{ item.test_case.description || '暂无用例描述' }}</span>
            <small>应用包：{{ item.test_case.package_name || '-' }}</small>
          </div>
        </div>
        <div v-else class="empty-note">该套件暂未配置用例</div>
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { ReportsSuiteDetailDialogProps } from './reportViewModels'

defineProps<ReportsSuiteDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.detail-shell,
.case-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-card strong,
.case-item strong {
  color: var(--theme-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-card,
.case-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  margin-bottom: 14px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.case-item span,
.case-item small {
  color: var(--theme-text-secondary);
}

.empty-note {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
}

.case-list {
  gap: 10px;
}

@media (max-width: 1280px) {
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>

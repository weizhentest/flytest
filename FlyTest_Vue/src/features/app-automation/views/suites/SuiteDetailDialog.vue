<template>
  <a-modal v-model:visible="visibleModel" title="套件详情" width="920px" :footer="false">
    <div v-if="selectedSuite" class="detail-shell">
      <div class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">最近状态</span>
          <strong>{{ getSuiteStatusMeta(selectedSuite).label }}</strong>
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

      <a-card class="detail-panel" title="执行统计">
        <div class="metric-row">
          <div class="metric-chip success-chip">通过 {{ selectedSuite.passed_count || 0 }}</div>
          <div class="metric-chip danger-chip">失败 {{ selectedSuite.failed_count || 0 }}</div>
          <div class="metric-chip warning-chip">停止 {{ selectedSuite.stopped_count || 0 }}</div>
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
import type { SuiteDetailDialogProps } from './suiteViewModels'

defineProps<SuiteDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.detail-shell,
.case-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.detail-card,
.detail-panel {
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.detail-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 124px;
  padding: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015)),
    var(--theme-card-bg);
}

.detail-label,
.meta-row,
.case-item span,
.case-item small {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.detail-label {
  letter-spacing: 0.2px;
}

.detail-card strong,
.detail-panel strong,
.case-item strong {
  color: var(--theme-text);
}

.detail-card strong {
  font-size: 28px;
  line-height: 1.15;
}

.detail-panel :deep(.arco-card-header) {
  min-height: 60px;
  padding: 0 22px;
  border-bottom-color: rgba(var(--theme-accent-rgb), 0.12);
}

.detail-panel :deep(.arco-card-header-title) {
  color: var(--theme-text);
  font-size: 15px;
  font-weight: 700;
}

.detail-panel :deep(.arco-card-body) {
  padding: 22px;
}

.summary-text {
  color: var(--theme-text);
  line-height: 1.7;
  white-space: pre-wrap;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.metric-chip {
  padding: 10px 16px;
  border-radius: 999px;
  font-weight: 700;
  border: 1px solid transparent;
}

.success-chip {
  background: rgba(0, 180, 42, 0.1);
  border-color: rgba(0, 180, 42, 0.18);
  color: #00b42a;
}

.danger-chip {
  background: rgba(245, 63, 63, 0.1);
  border-color: rgba(245, 63, 63, 0.18);
  color: #f53f3f;
}

.warning-chip {
  background: rgba(255, 125, 0, 0.1);
  border-color: rgba(255, 125, 0, 0.18);
  color: #ff7d00;
}

.case-list {
  gap: 14px;
}

.case-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.06), rgba(var(--theme-accent-rgb), 0.025)),
    rgba(255, 255, 255, 0.03);
}

.empty-note {
  color: var(--theme-text-secondary);
  min-height: 132px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

:deep(.arco-modal-header) {
  min-height: 68px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(var(--theme-accent-rgb), 0.12);
}

:deep(.arco-modal-title) {
  color: var(--theme-text);
  font-size: 18px;
  font-weight: 700;
}

:deep(.arco-modal-body) {
  padding: 22px 24px 24px;
}

@media (max-width: 1200px) {
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .detail-panel :deep(.arco-card-body),
  :deep(.arco-modal-body) {
    padding: 18px;
  }
}
</style>

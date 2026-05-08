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
  gap: 18px;
}

.detail-panel {
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
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

.detail-card strong,
.case-item strong {
  color: var(--theme-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.detail-card,
.case-item {
  padding: 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.06), rgba(var(--theme-accent-rgb), 0.025)),
    rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.2px;
}

.detail-card strong {
  font-size: 28px;
  line-height: 1.15;
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
  font-size: 13px;
  color: var(--theme-text-secondary);
  border-top: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
}

.case-item span,
.case-item small {
  color: var(--theme-text-secondary);
  line-height: 1.6;
}

.empty-note {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
  border-radius: 16px;
  border: 1px dashed rgba(var(--theme-accent-rgb), 0.14);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.case-list {
  gap: 14px;
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

@media (max-width: 1280px) {
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .detail-panel :deep(.arco-card-body),
  :deep(.arco-modal-body) {
    padding: 18px;
  }
}
</style>

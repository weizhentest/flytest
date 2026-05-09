<template>
  <div class="app-automation-shell">
    <div class="app-automation-layout">
      <component :is="activeDefinition.component" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { appAutomationTabDefinitions, normalizeAppAutomationTab } from './appAutomationTabs'

const route = useRoute()

const tabDefinitions = appAutomationTabDefinitions
const activeDefinition = computed(
  () => tabDefinitions.find(tab => tab.key === normalizeAppAutomationTab(route.query.tab)) ?? tabDefinitions[0],
)
</script>

<style scoped>
.app-automation-shell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.app-automation-layout {
  min-height: 0;
  padding: 0;
}

:deep(.page-shell),
:deep(.dashboard-view) {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
  padding: 12px 10px 16px;
}

:deep(.empty-shell) {
  min-height: 360px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.1), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(246, 249, 253, 0.92));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

:deep(.page-header) {
  position: relative;
  align-items: flex-start;
  gap: 18px;
  padding: 22px 24px;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.09), rgba(var(--theme-accent-rgb), 0.025)),
    rgba(255, 255, 255, 0.92);
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

:deep(.page-header::after) {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  border-radius: 22px 0 0 22px;
  background: linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.78), rgba(var(--theme-accent-rgb), 0.2));
}

:deep(.page-header > div:first-child) {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

:deep(.page-header h3) {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: var(--theme-text);
}

:deep(.page-header p) {
  max-width: 860px;
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--theme-text-secondary);
}

:deep(.page-header .arco-space) {
  row-gap: 10px !important;
  column-gap: 10px !important;
}

:deep(.page-header .header-tip) {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.06);
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

:deep(.page-header .auto-refresh-toggle) {
  min-height: 36px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(255, 255, 255, 0.76);
}

:deep(.page-header .arco-btn),
:deep(.page-header .arco-input-wrapper),
:deep(.page-header .arco-select-view) {
  border-radius: 12px;
}

:deep(.page-header .arco-input-wrapper),
:deep(.page-header .arco-select-view) {
  min-height: 40px;
  background: rgba(255, 255, 255, 0.88);
}

:deep(.page-header .arco-btn) {
  min-height: 40px;
  padding-inline: 16px;
}

:deep(.arco-card),
:deep(.dashboard-card),
:deep(.device-card),
:deep(.stats-card),
:deep(.suite-card),
:deep(.case-card),
:deep(.report-panel-card),
:deep(.scene-builder-card) {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.045);
  background: rgba(255, 255, 255, 0.92);
}

:deep(.arco-card-header) {
  min-height: 60px;
  padding: 0 22px;
  border-bottom-color: rgba(var(--theme-accent-rgb), 0.12);
}

:deep(.arco-card-header-title) {
  color: var(--theme-text);
  font-size: 15px;
  font-weight: 700;
}

:deep(.arco-card-body) {
  padding: 20px 22px;
}

:deep(.filter-card),
:deep(.table-card),
:deep(.stat-card),
:deep(.batch-bar),
:deep(.library-panel),
:deep(.canvas-panel),
:deep(.config-panel) {
  position: relative;
  overflow: hidden;
}

:deep(.filter-card::before),
:deep(.table-card::before),
:deep(.stat-card::before),
:deep(.library-panel::before),
:deep(.canvas-panel::before),
:deep(.config-panel::before) {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(var(--theme-accent-rgb), 0), rgba(var(--theme-accent-rgb), 0.22), rgba(var(--theme-accent-rgb), 0));
}

:deep(.filter-grid) {
  align-items: end;
}

:deep(.filter-actions) {
  align-items: center;
  flex-wrap: wrap;
}

:deep(.stats-grid) {
  align-items: stretch;
}

:deep(.stat-card .arco-card-body) {
  justify-content: space-between;
}

:deep(.arco-table-container) {
  border-radius: 16px;
}

:deep(.arco-table-th) {
  height: 48px;
  background: rgba(248, 250, 252, 0.92);
}

:deep(.arco-table-td) {
  padding-top: 14px;
  padding-bottom: 14px;
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background: rgba(var(--theme-accent-rgb), 0.035);
}

:deep(.pagination-row) {
  align-items: center;
  flex-wrap: wrap;
}

:deep(.builder-grid) {
  align-items: start;
  grid-template-columns: 0.94fr 1.26fr 1.02fr;
  gap: 20px;
  min-height: 620px;
}

:deep(.report-tabs .arco-tabs-nav) {
  margin-bottom: 16px;
}

:deep(.report-tabs .arco-tabs-nav::before) {
  border-bottom-color: rgba(149, 161, 187, 0.14);
}

:deep(.report-tabs .arco-tabs-tab) {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 14px 14px 0 0;
}

:deep(.report-tabs .arco-tabs-tab-active) {
  background: rgba(var(--theme-accent-rgb), 0.08);
}

@media (max-width: 768px) {
  :deep(.page-shell),
  :deep(.dashboard-view) {
    gap: 16px;
    padding: 4px;
  }

  :deep(.page-header) {
    padding: 16px 16px 16px 18px;
  }

  :deep(.arco-card-body) {
    padding: 18px;
  }
}
</style>

<template>
  <div class="app-automation-shell">
    <section class="app-automation-hero">
      <div class="app-automation-hero__copy">
        <div class="app-automation-hero__eyebrow">APP Automation Workspace</div>
        <div class="app-automation-hero__title">APP 自动化</div>
        <div class="app-automation-hero__desc">
          覆盖设备、应用包、元素、场景编排、测试用例、测试套件、执行记录与报告的完整移动端自动化工作台。
        </div>
      </div>

      <div class="app-automation-hero__meta">
        <div class="hero-metric-card">
          <span>能力范围</span>
          <strong>12</strong>
          <em>核心子模块</em>
        </div>
        <div class="hero-metric-card">
          <span>工作模式</span>
          <strong>端到端</strong>
          <em>编排到回溯</em>
        </div>
      </div>
    </section>

    <div class="app-automation-layout">
      <a-tabs v-model:active-key="activeTab" type="card-gutter" lazy-load class="app-tabs">
        <a-tab-pane
          v-for="tab in tabDefinitions"
          :key="tab.key"
          :title="tab.title"
        >
          <component :is="tab.component" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { AppAutomationTab } from '../types'
import {
  buildAppAutomationTabChangePatch,
  replaceAppAutomationQuery,
} from './appAutomationNavigation'
import {
  appAutomationTabDefinitions,
  normalizeAppAutomationTab,
} from './appAutomationTabs'

const route = useRoute()
const router = useRouter()

const activeTab = computed<AppAutomationTab>({
  get: () => normalizeAppAutomationTab(route.query.tab),
  set: value => {
    if (value === normalizeAppAutomationTab(route.query.tab)) {
      return
    }
    void replaceAppAutomationQuery(route, router, buildAppAutomationTabChangePatch(value))
  },
})

const tabDefinitions = appAutomationTabDefinitions
</script>

<style scoped>
.app-automation-shell {
  height: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 4px 0 0;
}

.app-automation-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  position: relative;
  overflow: hidden;
  padding: 24px 26px;
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.18), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 252, 0.94));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.app-automation-hero__copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 780px;
}

.app-automation-hero__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--theme-accent);
}

.app-automation-hero__title {
  font-size: 30px;
  font-weight: 800;
  line-height: 1.06;
  color: var(--theme-text);
}

.app-automation-hero__desc {
  max-width: 860px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--theme-text-secondary);
}

.app-automation-hero__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  gap: 12px;
  min-width: 320px;
}

.hero-metric-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(255, 255, 255, 0.74);
}

.hero-metric-card span,
.hero-metric-card em {
  font-size: 12px;
  color: var(--theme-text-secondary);
  font-style: normal;
}

.hero-metric-card strong {
  font-size: 24px;
  line-height: 1.1;
  color: var(--theme-text);
}

.app-automation-layout {
  min-height: 0;
  height: auto;
  padding: 2px;
}

.app-tabs {
  height: auto;
  border-radius: 26px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(255, 255, 255, 0.74);
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.04);
  overflow: visible;
}

:deep(.arco-tabs-nav) {
  margin: 0;
  padding: 16px 20px 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.82));
}

:deep(.arco-tabs-nav::before) {
  left: 20px;
  right: 20px;
  border-bottom-color: rgba(148, 163, 184, 0.14);
}

:deep(.arco-tabs-tab) {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 14px 14px 0 0;
  color: var(--theme-text-secondary);
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

:deep(.arco-tabs-tab:hover) {
  color: var(--theme-text);
}

:deep(.arco-tabs-tab-active) {
  background: rgba(var(--theme-accent-rgb), 0.1);
  color: var(--theme-text);
}

:deep(.arco-tabs-content) {
  height: auto;
  overflow: visible;
  padding: 18px;
}

@media (max-width: 980px) {
  .app-automation-hero {
    flex-direction: column;
  }

  .app-automation-hero__meta {
    min-width: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .app-automation-shell {
    gap: 14px;
  }

  .app-automation-hero {
    padding: 20px;
    border-radius: 22px;
  }

  .app-automation-hero__title {
    font-size: 26px;
  }

  .app-tabs {
    border-radius: 22px;
  }

  :deep(.arco-tabs-content) {
    padding: 12px;
  }
}
</style>

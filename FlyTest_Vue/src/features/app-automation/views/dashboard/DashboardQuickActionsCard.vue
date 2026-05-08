<template>
  <a-card class="panel-card quick-card" title="快速操作">
    <div class="quick-grid">
      <button class="quick-item" type="button" @click="emit('open-tab', 'devices')">
        <strong>设备管理</strong>
        <span>连接设备并查看在线状态</span>
      </button>
      <button class="quick-item" type="button" @click="emit('open-tab', 'elements')">
        <strong>元素管理</strong>
        <span>维护图片、OCR 与定位资源</span>
      </button>
      <button class="quick-item" type="button" @click="emit('open-tab', 'test-cases')">
        <strong>测试用例</strong>
        <span>快速进入用例列表，单条执行或转到测试套件编排</span>
      </button>
      <button class="quick-item" type="button" @click="emit('open-tab', 'scene-builder')">
        <strong>场景编排</strong>
        <span>通过 AI 和组件库搭建测试步骤</span>
      </button>
      <button class="quick-item" type="button" @click="emit('open-tab', 'suites')">
        <strong>测试套件</strong>
        <span>组合回归套件并触发批量执行</span>
      </button>
      <button class="quick-item" type="button" @click="emit('open-tab', 'executions')">
        <strong>执行记录</strong>
        <span>跟踪运行进度、日志和证据</span>
      </button>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { DashboardQuickActionsCardEmits } from './dashboardEventModels'

const emit = defineEmits<DashboardQuickActionsCardEmits>()
</script>

<style scoped>
.panel-card {
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  box-shadow: var(--theme-card-shadow);
  border-radius: 18px;
}

.quick-card {
  overflow: hidden;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.quick-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.03)),
    rgba(var(--theme-accent-rgb), 0.06);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.quick-item:hover {
  transform: translateY(-2px);
  border-color: rgba(var(--theme-accent-rgb), 0.34);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.11), rgba(var(--theme-accent-rgb), 0.05)),
    rgba(var(--theme-accent-rgb), 0.1);
  box-shadow: 0 16px 28px rgba(var(--theme-accent-rgb), 0.12);
}

.quick-item strong {
  color: var(--theme-text);
  font-size: 15px;
}

.quick-item span {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>

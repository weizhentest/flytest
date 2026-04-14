<template>
  <a-card class="settings-card diagnostics-card">
    <template #title>运行能力诊断</template>

    <div class="diagnostics-header">
      <div class="diagnostics-status">
        <a-tag :color="runtimeReady ? 'green' : 'orange'">{{ runtimeReady ? '能力已就绪' : '部分能力待安装' }}</a-tag>
        <span v-if="runtimeCapabilities.checked_at" class="checked-at">
          最近检测：{{ formatTime(runtimeCapabilities.checked_at) }}
        </span>
      </div>
      <p class="diagnostics-hint">这里会展示 OCR、循环点击断言、全屏模板找图等能力在当前机器上的依赖状态。</p>
    </div>

    <div class="actions">
      <a-space wrap>
        <a-button :loading="runtimeLoading" @click="emit('refresh-runtime')">刷新运行能力</a-button>
      </a-space>
    </div>

    <div class="diagnostics-grid runtime-grid">
      <div class="diagnostic-item">
        <span>Python 版本</span>
        <strong>{{ runtimeCapabilities.python_version || '-' }}</strong>
      </div>
      <div class="diagnostic-item">
        <span>已安装依赖</span>
        <strong>{{ installedDependencyCount }}/{{ runtimeCapabilities.dependencies.length }}</strong>
      </div>
    </div>

    <div class="runtime-section">
      <div class="section-title">依赖组件</div>
      <div class="dependency-grid">
        <div
          v-for="dependency in runtimeCapabilities.dependencies"
          :key="dependency.module_name"
          class="diagnostic-item dependency-item"
        >
          <span>{{ dependency.name }}</span>
          <strong>{{ dependency.installed ? `已安装${dependency.version ? ` · ${dependency.version}` : ''}` : '未安装' }}</strong>
        </div>
      </div>
    </div>

    <div class="runtime-section">
      <div class="section-title">能力状态</div>
      <div class="capability-list">
        <div v-for="capability in runtimeCapabilities.capabilities" :key="capability.key" class="capability-item">
          <div class="capability-main">
            <strong>{{ capability.label }}</strong>
            <a-tag :color="capability.ready ? 'green' : 'orange'">
              {{ capability.ready ? '可用' : '待安装' }}
            </a-tag>
          </div>
          <div class="capability-message">{{ capability.message }}</div>
        </div>
      </div>
    </div>

    <div v-if="!runtimeReady" class="runtime-install">
      <div class="section-title">建议安装命令</div>
      <a-typography-paragraph copyable class="install-command">
        {{ runtimeCapabilities.install_command }}
      </a-typography-paragraph>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { AppRuntimeCapabilities } from '../../types'

interface Props {
  runtimeCapabilities: AppRuntimeCapabilities
  runtimeReady: boolean
  installedDependencyCount: number
  runtimeLoading: boolean
  formatTime: (value: string) => string
}

defineProps<Props>()

const emit = defineEmits<{
  'refresh-runtime': []
}>()
</script>

<style scoped>
.settings-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.diagnostics-card {
  overflow: hidden;
}

.diagnostics-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.diagnostics-status {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.checked-at,
.diagnostics-hint {
  color: var(--color-text-2);
}

.diagnostics-hint {
  margin: 0;
}

.actions {
  margin-top: 8px;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.runtime-grid {
  margin-top: 16px;
}

.diagnostic-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-2);
}

.diagnostic-item span,
.section-title {
  font-size: 12px;
  color: var(--color-text-3);
}

.diagnostic-item strong {
  color: var(--color-text-1);
  line-break: anywhere;
}

.runtime-section,
.runtime-install {
  margin-top: 18px;
}

.section-title {
  margin-bottom: 10px;
}

.dependency-grid,
.capability-list {
  display: grid;
  gap: 12px;
}

.dependency-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.dependency-item strong {
  font-size: 13px;
}

.capability-item {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-2);
}

.capability-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.capability-message {
  margin-top: 8px;
  color: var(--color-text-2);
  line-height: 1.6;
}

.install-command {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(var(--primary-6), 0.08);
  border: 1px solid rgba(var(--primary-6), 0.2);
}
</style>

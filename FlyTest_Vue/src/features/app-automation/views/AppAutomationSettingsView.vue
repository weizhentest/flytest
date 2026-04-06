<template>
  <div class="settings-shell">
    <a-card class="settings-card">
      <template #title>APP 自动化环境设置</template>
      <a-form :model="form" layout="vertical">
        <a-form-item field="adb_path" label="ADB 路径">
          <a-input v-model="form.adb_path" placeholder="默认使用 adb，也可以填写绝对路径" />
        </a-form-item>
        <a-form-item field="workspace_root" label="工作目录">
          <a-input v-model="form.workspace_root" placeholder="可选，用于保存截图、日志和执行报告" />
        </a-form-item>
        <a-form-item field="default_timeout" label="默认超时时间（秒）">
          <a-input-number v-model="form.default_timeout" :min="1" :max="7200" />
        </a-form-item>
        <a-form-item field="auto_discover_on_open" label="进入页面时自动同步设备">
          <a-switch v-model="form.auto_discover_on_open" />
        </a-form-item>
        <a-form-item field="notes" label="备注说明">
          <a-textarea v-model="form.notes" :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
      </a-form>

      <div class="actions">
        <a-space wrap>
          <a-button @click="reloadAll">重新加载</a-button>
          <a-button :loading="diagnosticsLoading" @click="loadDiagnostics(true)">刷新诊断</a-button>
          <a-button :loading="detecting" @click="detectAdb">自动检测 ADB</a-button>
          <a-button type="primary" :loading="saving" @click="save">保存设置</a-button>
        </a-space>
      </div>
    </a-card>

    <a-card class="settings-card diagnostics-card">
      <template #title>ADB 环境诊断</template>

      <div class="diagnostics-header">
        <div class="diagnostics-status">
          <a-tag :color="statusColor">{{ statusLabel }}</a-tag>
          <span v-if="diagnostics.checked_at" class="checked-at">最近检测：{{ formatTime(diagnostics.checked_at) }}</span>
        </div>
        <p class="diagnostics-hint">这里会展示当前配置路径、实际解析到的 ADB、版本信息以及已发现的设备数量。</p>
      </div>

      <div class="diagnostics-grid">
        <div class="diagnostic-item">
          <span>配置路径</span>
          <strong>{{ diagnostics.configured_path || '-' }}</strong>
        </div>
        <div class="diagnostic-item">
          <span>解析路径</span>
          <strong>{{ diagnostics.resolved_path || '-' }}</strong>
        </div>
        <div class="diagnostic-item">
          <span>ADB 状态</span>
          <strong>{{ diagnostics.executable_found ? '已找到' : '未找到' }}</strong>
        </div>
        <div class="diagnostic-item">
          <span>版本信息</span>
          <strong>{{ diagnostics.version || '-' }}</strong>
        </div>
        <div class="diagnostic-item">
          <span>已发现设备</span>
          <strong>{{ diagnostics.device_count }}</strong>
        </div>
      </div>

      <div v-if="diagnostics.devices.length" class="device-section">
        <div class="section-title">在线设备</div>
        <a-space wrap>
          <a-tag v-for="device in diagnostics.devices" :key="device.device_id" color="blue">
            {{ device.name || device.device_id }} · {{ device.device_id }}
          </a-tag>
        </a-space>
      </div>

      <div v-else class="empty-text">当前没有发现在线设备。</div>

      <div v-if="diagnostics.error" class="diagnostic-error">
        {{ diagnostics.error }}
      </div>
    </a-card>

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
          <a-button :loading="runtimeLoading" @click="loadRuntimeCapabilities(true)">刷新运行能力</a-button>
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
          <div v-for="dependency in runtimeCapabilities.dependencies" :key="dependency.module_name" class="diagnostic-item dependency-item">
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppAdbDiagnostics, AppRuntimeCapabilities } from '../types'

const saving = ref(false)
const detecting = ref(false)
const diagnosticsLoading = ref(false)
const runtimeLoading = ref(false)

const form = reactive({
  adb_path: 'adb',
  default_timeout: 300,
  workspace_root: '',
  auto_discover_on_open: true,
  notes: '',
})

const diagnostics = reactive<AppAdbDiagnostics>({
  configured_path: '',
  resolved_path: '',
  executable_found: false,
  version: '',
  device_count: 0,
  devices: [],
  error: '',
  checked_at: '',
})

const runtimeCapabilities = reactive<AppRuntimeCapabilities>({
  checked_at: '',
  python_version: '',
  install_command: '',
  dependencies: [],
  capabilities: [],
})

const statusLabel = computed(() => {
  if (diagnostics.executable_found && !diagnostics.error) {
    return 'ADB 可用'
  }
  if (diagnostics.executable_found) {
    return 'ADB 已找到'
  }
  return 'ADB 未就绪'
})

const statusColor = computed(() => {
  if (diagnostics.executable_found && !diagnostics.error) {
    return 'green'
  }
  if (diagnostics.executable_found) {
    return 'orange'
  }
  return 'red'
})

const installedDependencyCount = computed(() => runtimeCapabilities.dependencies.filter(item => item.installed).length)

const runtimeReady = computed(
  () => runtimeCapabilities.capabilities.length > 0 && runtimeCapabilities.capabilities.every(item => item.ready),
)

const formatTime = (value: string) => {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

const getErrorMessage = (error: any, fallback: string) => {
  return error?.error || error?.message || fallback
}

const loadSettings = async () => {
  try {
    Object.assign(form, await AppAutomationService.getSettings())
  } catch (error: any) {
    Message.error(getErrorMessage(error, '加载环境设置失败'))
  }
}

const loadDiagnostics = async (showMessage = false) => {
  diagnosticsLoading.value = true
  try {
    Object.assign(diagnostics, await AppAutomationService.getAdbDiagnostics())
    if (showMessage) {
      Message.success('ADB 诊断已刷新')
    }
  } catch (error: any) {
    Message.error(getErrorMessage(error, '获取 ADB 诊断失败'))
  } finally {
    diagnosticsLoading.value = false
  }
}

const loadRuntimeCapabilities = async (showMessage = false) => {
  runtimeLoading.value = true
  try {
    Object.assign(runtimeCapabilities, await AppAutomationService.getRuntimeCapabilities())
    if (showMessage) {
      Message.success('运行能力诊断已刷新')
    }
  } catch (error: any) {
    Message.error(getErrorMessage(error, '获取运行能力诊断失败'))
  } finally {
    runtimeLoading.value = false
  }
}

const detectAdb = async () => {
  detecting.value = true
  try {
    const result = await AppAutomationService.detectAdb()
    Object.assign(form, result.settings)
    Object.assign(diagnostics, result.diagnostics)
    if (result.diagnostics.executable_found) {
      Message.success('已检测到可用 ADB，并同步到当前配置')
    } else {
      Message.warning(result.diagnostics.error || '未检测到可用 ADB')
    }
  } catch (error: any) {
    Message.error(getErrorMessage(error, '自动检测 ADB 失败'))
  } finally {
    detecting.value = false
  }
}

const reloadAll = async () => {
  await Promise.all([loadSettings(), loadDiagnostics(), loadRuntimeCapabilities()])
}

const save = async () => {
  saving.value = true
  try {
    await AppAutomationService.saveSettings(form)
    Message.success('环境设置已保存')
    await loadDiagnostics()
  } catch (error: any) {
    Message.error(getErrorMessage(error, '保存环境设置失败'))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void reloadAll()
})
</script>

<style scoped>
.settings-shell {
  display: grid;
  gap: 16px;
  max-width: 920px;
}

.settings-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.actions {
  margin-top: 8px;
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
.diagnostics-hint,
.empty-text {
  color: var(--color-text-2);
}

.diagnostics-hint,
.empty-text {
  margin: 0;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
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

.device-section {
  margin-top: 16px;
}

.runtime-section,
.runtime-install {
  margin-top: 18px;
}

.runtime-grid {
  margin-top: 16px;
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

.section-title {
  margin-bottom: 10px;
}

.diagnostic-error {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--warning-6), 0.35);
  background: rgba(var(--warning-6), 0.08);
  color: rgb(var(--warning-6));
  line-height: 1.6;
}

@media (max-width: 768px) {
  .settings-shell {
    max-width: 100%;
  }
}
</style>

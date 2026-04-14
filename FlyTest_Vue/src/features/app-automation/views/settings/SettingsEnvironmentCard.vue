<template>
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
        <a-button @click="emit('reload-all')">重新加载</a-button>
        <a-button :loading="diagnosticsLoading" @click="emit('refresh-diagnostics')">刷新诊断</a-button>
        <a-button :loading="detecting" @click="emit('detect-adb')">自动检测 ADB</a-button>
        <a-button type="primary" :loading="saving" @click="emit('save')">保存设置</a-button>
      </a-space>
    </div>
  </a-card>
</template>

<script setup lang="ts">
interface SettingsForm {
  adb_path: string
  default_timeout: number
  workspace_root: string
  auto_discover_on_open: boolean
  notes: string
}

interface Props {
  form: SettingsForm
  saving: boolean
  detecting: boolean
  diagnosticsLoading: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'reload-all': []
  'refresh-diagnostics': []
  'detect-adb': []
  save: []
}>()
</script>

<style scoped>
.settings-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.actions {
  margin-top: 8px;
}
</style>

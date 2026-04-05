<template>
  <div class="settings-shell">
    <a-card class="settings-card">
      <template #title>APP 自动化环境设置</template>
      <a-form :model="form" layout="vertical">
        <a-form-item field="adb_path" label="ADB 路径">
          <a-input v-model="form.adb_path" placeholder="默认 adb" />
        </a-form-item>
        <a-form-item field="workspace_root" label="工作目录">
          <a-input v-model="form.workspace_root" placeholder="可选，保存截图与报告的目录" />
        </a-form-item>
        <a-form-item field="default_timeout" label="默认超时时间（秒）">
          <a-input-number v-model="form.default_timeout" :min="1" :max="7200" />
        </a-form-item>
        <a-form-item field="auto_discover_on_open" label="自动同步设备">
          <a-switch v-model="form.auto_discover_on_open" />
        </a-form-item>
        <a-form-item field="notes" label="说明">
          <a-textarea v-model="form.notes" :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
      </a-form>
      <a-space>
        <a-button @click="loadSettings">重新加载</a-button>
        <a-button type="primary" :loading="saving" @click="save">保存设置</a-button>
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { AppAutomationService } from '../services/appAutomationService'

const saving = ref(false)
const form = reactive({
  adb_path: 'adb',
  default_timeout: 300,
  workspace_root: '',
  auto_discover_on_open: true,
  notes: '',
})

const loadSettings = async () => {
  try {
    Object.assign(form, await AppAutomationService.getSettings())
  } catch (error: any) {
    Message.error(error.message || '加载设置失败')
  }
}

const save = async () => {
  saving.value = true
  try {
    await AppAutomationService.saveSettings(form)
    Message.success('环境设置已保存')
  } catch (error: any) {
    Message.error(error.message || '保存设置失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<style scoped>
.settings-shell {
  display: flex;
  flex-direction: column;
}

.settings-card {
  max-width: 760px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}
</style>

<template>
  <a-modal v-model:visible="visibleModel" width="560px">
    <template #title>保存并执行当前用例</template>

    <div class="dialog-shell">
      <a-alert class="custom-dialog-alert">
        会先保存当前场景草稿，再立即创建执行任务，并跳转到执行记录页跟踪执行进度。
      </a-alert>

      <a-form layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item label="当前用例">
            <a-input :model-value="executionCaseName" readonly />
          </a-form-item>
        </div>

        <div class="field-card">
          <a-form-item label="执行设备">
            <a-select v-model="form.device_id" placeholder="请选择执行设备">
              <a-option v-for="device in availableDevices" :key="device.id" :value="device.id">
                {{ device.name || device.device_id }}
              </a-option>
            </a-select>
          </a-form-item>

          <div class="execute-device-meta">
            <span>可用设备 {{ availableDevices.length }} 台</span>
            <a-button type="text" size="mini" @click="emit('reload-devices')">刷新设备</a-button>
          </div>
        </div>
      </a-form>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="primary" :loading="saving || executing" @click="emit('submit')">开始执行</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import type {
  SceneBuilderExecuteDeviceOption,
  SceneBuilderExecuteFormModel,
} from './sceneBuilderDialogModels'

interface Props {
  executionCaseName: string
  availableDevices: SceneBuilderExecuteDeviceOption[]
  form: SceneBuilderExecuteFormModel
  saving: boolean
  executing: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  'reload-devices': []
  submit: []
}>()
</script>

<style scoped>
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.custom-dialog-alert {
  margin-bottom: 0;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.field-card :deep(.arco-form-item) {
  margin-bottom: 0;
}

.field-card :deep(.arco-input-wrapper),
.field-card :deep(.arco-select-view) {
  border-radius: 12px;
}

.execute-device-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

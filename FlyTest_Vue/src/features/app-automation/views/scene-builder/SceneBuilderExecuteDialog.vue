<template>
  <a-modal v-model:visible="visibleModel" width="560px">
    <template #title>保存并执行当前用例</template>

    <a-form layout="vertical">
      <a-alert class="custom-dialog-alert">
        会先保存当前场景草稿，再立即创建执行任务，并跳转到执行记录页跟踪执行进度。
      </a-alert>

      <a-form-item label="当前用例">
        <a-input :model-value="executionCaseName" readonly />
      </a-form-item>

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
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="primary" :loading="saving || executing" @click="emit('submit')">开始执行</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
interface ExecuteDeviceOption {
  id: number | string
  name?: string | null
  device_id?: string | null
}

interface ExecuteFormModel {
  device_id?: number | string
}

interface Props {
  executionCaseName: string
  availableDevices: ExecuteDeviceOption[]
  form: ExecuteFormModel
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
.custom-dialog-alert {
  margin-bottom: 14px;
}

.execute-device-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}
</style>

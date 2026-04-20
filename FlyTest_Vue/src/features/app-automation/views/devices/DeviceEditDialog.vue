<template>
  <a-modal
    v-model:visible="visibleModel"
    title="编辑设备信息"
    :confirm-loading="editSaving"
    @ok="emit('submit')"
  >
    <a-form :model="editForm" layout="vertical">
      <a-form-item field="name" label="设备名称">
        <a-input v-model="editForm.name" placeholder="输入设备名称" />
      </a-form-item>
      <a-form-item field="status" label="设备状态">
        <a-select
          v-model="editForm.status"
          placeholder="选择设备状态"
          :disabled="['locked', 'stopping'].includes(editForm.status)"
        >
          <a-option value="available">可用</a-option>
          <a-option value="online">在线</a-option>
          <a-option value="offline">离线</a-option>
          <a-option v-if="editForm.status === 'locked'" value="locked" disabled>锁定</a-option>
          <a-option v-if="editForm.status === 'stopping'" value="stopping" disabled>正在停止</a-option>
        </a-select>
        <div class="status-hint">锁定和正在停止状态由系统或执行流程自动维护。</div>
      </a-form-item>
      <a-form-item field="location" label="位置">
        <a-input v-model="editForm.location" placeholder="例如 QA 机房 / 本地模拟器" />
      </a-form-item>
      <a-form-item field="description" label="备注">
        <a-textarea v-model="editForm.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type { DeviceEditDialogEmits } from './deviceEventModels'
import type { DeviceEditDialogProps } from './deviceViewModels'

defineProps<DeviceEditDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<DeviceEditDialogEmits>()
</script>

<style scoped>
.status-hint {
  margin-top: 8px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
</style>

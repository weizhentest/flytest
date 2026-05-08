<template>
  <a-modal
    v-model:visible="visibleModel"
    title="编辑设备信息"
    :confirm-loading="editSaving"
    @ok="emit('submit')"
  >
    <div class="dialog-shell">
      <div class="dialog-intro">
        <span class="dialog-kicker">Device Settings</span>
        <strong>维护设备基础信息与状态展示</strong>
        <p>这里保留人工可维护的信息项，执行链路中的锁定与停止状态仍由系统自动回写。</p>
      </div>
      <a-form :model="editForm" layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item field="name" label="设备名称">
            <a-input v-model="editForm.name" placeholder="输入设备名称" />
          </a-form-item>
        </div>
        <div class="field-card">
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
              <a-option v-if="editForm.status === 'stopping'" value="stopping" disabled>停止中</a-option>
            </a-select>
            <div class="status-hint">锁定和停止中状态由系统或执行流程自动维护。</div>
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item field="location" label="位置">
            <a-input v-model="editForm.location" placeholder="例如 QA 机房 / 本地模拟器" />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item field="description" label="备注">
            <a-textarea v-model="editForm.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
          </a-form-item>
        </div>
      </a-form>
    </div>
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
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dialog-intro {
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(var(--theme-accent-rgb), 0.04));
}

.dialog-kicker {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dialog-intro strong {
  display: block;
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.dialog-intro p {
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
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
.field-card :deep(.arco-select-view),
.field-card :deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}

.status-hint {
  margin-top: 8px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

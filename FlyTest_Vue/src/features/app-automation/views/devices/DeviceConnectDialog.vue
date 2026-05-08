<template>
  <a-modal v-model:visible="visibleModel" title="添加远程设备" @ok="emit('connect')">
    <div class="dialog-shell">
      <div class="dialog-intro">
        <span class="dialog-kicker">Remote Device</span>
        <strong>接入局域网或远程 Android 设备</strong>
        <p>填写设备网络地址后即可纳入统一设备池，后续可直接分配给用例或套件执行。</p>
      </div>
      <a-form :model="connectForm" layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item field="ip_address" label="IP 地址">
            <a-input v-model="connectForm.ip_address" placeholder="例如 192.168.1.15" />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item field="port" label="端口">
            <a-input-number v-model="connectForm.port" :min="1" :max="65535" />
          </a-form-item>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { DeviceConnectDialogEmits } from './deviceEventModels'
import type { DeviceConnectDialogProps } from './deviceViewModels'

defineProps<DeviceConnectDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<DeviceConnectDialogEmits>()
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
.field-card :deep(.arco-input-number),
.field-card :deep(.arco-input-number-input-wrap) {
  border-radius: 12px;
}

:deep(.arco-modal-header) {
  margin-bottom: 0;
  padding-bottom: 14px;
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-body) {
  padding-top: 4px;
}

:deep(.arco-modal-footer) {
  padding-top: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

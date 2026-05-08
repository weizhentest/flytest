<template>
  <a-modal v-model:visible="visibleModel" title="执行测试套件" @ok="emit('run')">
    <a-form :model="runForm" layout="vertical">
      <a-form-item field="device_id" label="执行设备">
        <a-select v-model="runForm.device_id" placeholder="请选择可用设备">
          <a-option v-for="item in availableDevices" :key="item.id" :value="item.id">
            {{ item.name || item.device_id }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="package_name" label="应用包覆盖">
        <a-select
          v-model="runForm.package_name"
          allow-clear
          placeholder="可选：覆盖套件内用例默认应用包"
        >
          <a-option v-for="item in packages" :key="item.id" :value="item.package_name">
            {{ item.name }}（{{ item.package_name }}）
          </a-option>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type { SuiteRunDialogEmits } from './suiteEventModels'
import type { SuiteRunDialogProps } from './suiteViewModels'

defineProps<SuiteRunDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<SuiteRunDialogEmits>()
</script>

<style scoped>
:deep(.arco-modal-header) {
  min-height: 68px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(var(--theme-accent-rgb), 0.12);
}

:deep(.arco-modal-title) {
  color: var(--theme-text);
  font-size: 18px;
  font-weight: 700;
}

:deep(.arco-modal-body) {
  padding: 22px 24px 10px;
}

:deep(.arco-modal-footer) {
  padding: 16px 24px 22px;
  border-top: 1px solid rgba(var(--theme-accent-rgb), 0.1);
}

:deep(.arco-form-item-label-col > label) {
  color: var(--theme-text);
  font-weight: 600;
}

:deep(.arco-select-view) {
  min-height: 42px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

@media (max-width: 900px) {
  :deep(.arco-modal-body),
  :deep(.arco-modal-footer) {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>

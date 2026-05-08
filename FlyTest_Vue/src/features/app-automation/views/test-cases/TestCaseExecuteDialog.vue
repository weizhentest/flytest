<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="mode === 'batch' ? '批量执行测试用例' : '执行测试用例'"
    @ok="emit('execute')"
  >
    <a-form :model="executeForm" layout="vertical">
      <a-form-item field="device_id" label="执行设备">
        <a-select v-model="executeForm.device_id" placeholder="请选择设备">
          <a-option v-for="device in availableDevices" :key="device.id" :value="device.id">
            {{ device.name || device.device_id }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="package_id" label="应用包">
        <a-select v-model="executeForm.package_id" allow-clear placeholder="使用用例绑定的应用包">
          <a-option v-for="pkg in packages" :key="pkg.id" :value="pkg.id">
            {{ pkg.name }}
          </a-option>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type { TestCaseExecuteDialogEmits } from './testCaseEventModels'
import type { TestCaseExecuteDialogProps } from './testCaseViewModels'

defineProps<TestCaseExecuteDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<TestCaseExecuteDialogEmits>()
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

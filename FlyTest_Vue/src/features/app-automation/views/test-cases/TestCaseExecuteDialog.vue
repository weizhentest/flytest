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

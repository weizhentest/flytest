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

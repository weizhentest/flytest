<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑测试用例' : '新增测试用例'"
    width="860px"
    @ok="emit('submit')"
  >
    <a-form :model="form" layout="vertical">
      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="name" label="用例名称">
            <a-input v-model="form.name" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="package_id" label="应用包">
            <a-select v-model="form.package_id" allow-clear>
              <a-option v-for="pkg in packages" :key="pkg.id" :value="pkg.id">{{ pkg.name }}</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="timeout" label="超时时间">
            <a-input-number v-model="form.timeout" :min="1" :max="7200" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="retry_count" label="失败重试">
            <a-input-number v-model="form.retry_count" :min="0" :max="10" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item field="description" label="描述">
        <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" />
      </a-form-item>
      <a-form-item field="variablesText" label="变量 JSON">
        <a-textarea v-model="form.variablesText" :auto-size="{ minRows: 4, maxRows: 8 }" />
      </a-form-item>
      <a-form-item field="uiFlowText" label="UI Flow JSON">
        <a-textarea v-model="form.uiFlowText" :auto-size="{ minRows: 8, maxRows: 14 }" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type { AppPackage } from '../../types'

interface TestCaseForm {
  id: number
  name: string
  description: string
  package_id: number | undefined
  timeout: number
  retry_count: number
  variablesText: string
  uiFlowText: string
}

interface Props {
  form: TestCaseForm
  packages: AppPackage[]
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

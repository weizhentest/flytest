<template>
  <a-modal v-model:visible="visibleModel" width="560px">
    <template #title>导出组件包</template>

    <a-form layout="vertical">
      <a-form-item label="组件包名称">
        <a-input v-model="form.name" placeholder="例如：app-component-pack" />
      </a-form-item>
      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item label="版本">
            <a-input v-model="form.version" placeholder="例如：2026.04.07" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="作者">
            <a-input v-model="form.author" placeholder="可选" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="描述">
        <a-textarea
          v-model="form.description"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          placeholder="可选"
        />
      </a-form-item>
      <a-form-item label="导出禁用组件">
        <a-switch v-model="includeDisabledModel" />
      </a-form-item>
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="outline" :loading="exporting" @click="emit('submit-json')">导出 JSON</a-button>
        <a-button type="primary" :loading="exporting" @click="emit('submit-yaml')">导出 YAML</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import type { SceneBuilderComponentPackageExportFormModel } from './sceneBuilderDialogModels'

interface Props {
  exporting: boolean
  form: SceneBuilderComponentPackageExportFormModel
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const includeDisabledModel = defineModel<boolean>('includeDisabled', { required: true })

const emit = defineEmits<{
  'submit-json': []
  'submit-yaml': []
}>()
</script>

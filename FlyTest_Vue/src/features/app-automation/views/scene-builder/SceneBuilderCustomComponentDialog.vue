<template>
  <a-modal v-model:visible="visibleModel" width="760px">
    <template #title>
      {{ mode === 'create' ? '保存为自定义组件' : '编辑自定义组件' }}
    </template>

    <a-form layout="vertical">
      <a-alert class="custom-dialog-alert">
        {{
          mode === 'create'
            ? '当前会将场景中的基础步骤和流程步骤保存为新的自定义组件，暂不支持嵌套自定义组件。'
            : '这里可以维护组件名称、类型与步骤 JSON，保存后会同步到组件库。'
        }}
      </a-alert>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="name" label="组件名称">
            <a-input v-model="form.name" placeholder="请输入组件名称" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="type" label="组件类型">
            <a-input v-model="form.type" placeholder="例如：login_flow_component" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item field="description" label="组件描述">
        <a-textarea
          v-model="form.description"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          placeholder="说明该组件的用途"
        />
      </a-form-item>

      <a-form-item field="stepsText" label="步骤 JSON">
        <a-textarea
          v-model="form.stepsText"
          :auto-size="{ minRows: 12, maxRows: 20 }"
          placeholder="请填写组件步骤 JSON 数组"
        />
      </a-form-item>
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="primary" :loading="saving" @click="emit('submit')">保存组件</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import type {
  SceneBuilderCustomComponentDialogMode,
  SceneBuilderCustomComponentFormModel,
} from './sceneBuilderDialogModels'

interface Props {
  mode: SceneBuilderCustomComponentDialogMode
  form: SceneBuilderCustomComponentFormModel
  saving: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

<style scoped>
.custom-dialog-alert {
  margin-bottom: 14px;
}
</style>

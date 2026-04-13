<template>
  <div class="page-header">
    <div>
      <h3>场景编排</h3>
      <p>支持基础步骤、自定义组件和流程控制分支的可视化编排。</p>
    </div>
    <a-space class="header-actions" wrap>
      <a-button type="outline" :loading="aiGenerating" @click="emit('open-ai-plan')">AI 生成场景</a-button>
      <a-button :loading="loading" @click="emit('reload-data')">刷新</a-button>
      <a-button type="outline" @click="emit('open-testcase-workspace')">测试用例</a-button>
      <a-button type="outline" @click="emit('open-execution-workspace')">执行记录</a-button>
      <a-button @click="emit('create-draft')">新建草稿</a-button>
      <a-button :disabled="!hasSteps" @click="emit('open-create-custom-component')">另存为自定义组件</a-button>
      <a-button type="primary" :loading="saving" @click="emit('save-draft')">保存用例</a-button>
      <a-button type="primary" status="success" :loading="saving || executing" @click="emit('open-execute-dialog')">
        保存并执行
      </a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
interface Props {
  aiGenerating: boolean
  loading: boolean
  saving: boolean
  executing: boolean
  hasSteps: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'open-ai-plan': []
  'reload-data': []
  'open-testcase-workspace': []
  'open-execution-workspace': []
  'create-draft': []
  'open-create-custom-component': []
  'save-draft': []
  'open-execute-dialog': []
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-actions {
  justify-content: flex-end;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

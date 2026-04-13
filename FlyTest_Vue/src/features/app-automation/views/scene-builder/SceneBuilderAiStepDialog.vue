<template>
  <a-modal v-model:visible="visibleModel" width="640px">
    <template #title>AI 补全当前步骤</template>

    <a-form layout="vertical">
      <a-alert class="custom-dialog-alert">
        这里会基于当前已选步骤、场景上下文和激活的 LLM 配置补全当前步骤；如果模型不可用，会自动回退到规则补全。
      </a-alert>

      <div class="ai-dialog-meta">
        <div class="ai-dialog-item">
          <span>当前引擎</span>
          <strong>{{ aiDialogEngineName }}</strong>
        </div>
        <div class="ai-dialog-item">
          <span>执行模式</span>
          <strong>{{ aiDialogModeText }}</strong>
        </div>
        <div class="ai-dialog-item">
          <span>最近检测</span>
          <strong>{{ checkedAtDisplay }}</strong>
        </div>
      </div>

      <a-form-item field="prompt" label="补全说明">
        <a-textarea
          v-model="promptModel"
          :auto-size="{ minRows: 5, maxRows: 8 }"
          placeholder="例如：补全为输入登录账号，优先复用已有元素，缺少值时自动生成变量。"
        />
      </a-form-item>
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="primary" :loading="loading" @click="emit('submit')">补全并应用</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
interface Props {
  aiDialogEngineName: string
  aiDialogModeText: string
  checkedAtDisplay: string
  loading: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const promptModel = defineModel<string>('prompt', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

<style scoped>
.custom-dialog-alert {
  margin-bottom: 14px;
}

.ai-dialog-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.ai-dialog-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.ai-dialog-item span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.ai-dialog-item strong {
  color: var(--theme-text);
  word-break: break-word;
  overflow-wrap: anywhere;
}

@media (max-width: 1480px) {
  .ai-dialog-meta {
    grid-template-columns: 1fr;
  }
}
</style>

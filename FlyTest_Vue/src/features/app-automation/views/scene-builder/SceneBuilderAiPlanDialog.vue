<template>
  <a-modal v-model:visible="visibleModel" width="720px">
    <template #title>AI 生成 APP 场景</template>

    <div class="dialog-shell">
      <a-alert class="custom-dialog-alert">
        优先使用当前激活的 LLM 配置生成步骤；如果模型不可用或网络失败，会自动回退到规则规划，保证场景草稿仍然可编辑可保存。
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

      <a-form layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item field="prompt" label="场景描述">
            <a-textarea
              v-model="promptModel"
              :auto-size="{ minRows: 6, maxRows: 10 }"
              placeholder="例如：启动企业微信，输入账号密码登录，进入工作台后校验消息入口存在并截图。"
            />
          </a-form-item>
        </div>

        <div class="field-card">
          <a-form-item field="applyMode" label="应用方式">
            <a-radio-group v-model="applyModeModel" type="button">
              <a-radio value="replace">替换当前草稿</a-radio>
              <a-radio value="append">追加到当前步骤</a-radio>
            </a-radio-group>
          </a-form-item>
        </div>
      </a-form>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">取消</a-button>
        <a-button type="primary" :loading="loading" @click="emit('submit')">生成并应用</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
type AiApplyMode = 'replace' | 'append'

interface Props {
  aiDialogEngineName: string
  aiDialogModeText: string
  checkedAtDisplay: string
  loading: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const promptModel = defineModel<string>('prompt', { required: true })
const applyModeModel = defineModel<AiApplyMode>('applyMode', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

<style scoped>
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.custom-dialog-alert {
  margin-bottom: 0;
}

.ai-dialog-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.ai-dialog-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.04)),
    rgba(var(--theme-surface-rgb), 0.72);
}

.ai-dialog-item span {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ai-dialog-item strong {
  color: var(--theme-text);
  word-break: break-word;
  overflow-wrap: anywhere;
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

.field-card :deep(.arco-textarea-wrapper),
.field-card :deep(.arco-radio-group) {
  border-radius: 12px;
}

@media (max-width: 1480px) {
  .ai-dialog-meta {
    grid-template-columns: 1fr;
  }
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

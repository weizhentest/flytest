<template>
  <a-modal v-model:visible="visibleModel" width="720px">
    <template #title>AI 生成 APP 场景</template>

    <a-form layout="vertical">
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

      <a-form-item field="prompt" label="场景描述">
        <a-textarea
          v-model="promptModel"
          :auto-size="{ minRows: 6, maxRows: 10 }"
          placeholder="例如：启动企业微信，输入账号密码登录，进入工作台后校验消息入口存在并截图。"
        />
      </a-form-item>

      <a-form-item field="applyMode" label="应用方式">
        <a-radio-group v-model="applyModeModel" type="button">
          <a-radio value="replace">替换当前草稿</a-radio>
          <a-radio value="append">追加到当前步骤</a-radio>
        </a-radio-group>
      </a-form-item>
    </a-form>

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

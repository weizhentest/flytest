<template>
  <a-form-item label="配置字段">
    <div class="config-keys">
      <a-tag v-for="item in configKeys" :key="item" size="small">{{ item }}</a-tag>
      <span v-if="!configKeys.length" class="config-empty-text">当前步骤还没有配置字段</span>
    </div>
  </a-form-item>
  <a-form-item label="配置 JSON">
    <a-textarea
      v-model="stepConfigTextModel"
      :auto-size="{ minRows: 10, maxRows: 18 }"
      placeholder="请输入步骤配置 JSON"
    />
  </a-form-item>

  <div class="config-actions">
    <a-button @click="emit('reset-selected-step-config')">恢复默认配置</a-button>
    <a-button type="primary" @click="emit('apply-step-config')">应用到当前步骤</a-button>
  </div>
</template>

<script setup lang="ts">
interface Props {
  configKeys: string[]
}

defineProps<Props>()

const stepConfigTextModel = defineModel<string>('stepConfigText', { required: true })

const emit = defineEmits<{
  'reset-selected-step-config': []
  'apply-step-config': []
}>()
</script>

<style scoped>
.config-empty-text {
  color: var(--theme-text-secondary);
}

.config-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

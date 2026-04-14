<template>
  <div class="page-header">
    <div>
      <h3>执行报告</h3>
      <p>从套件报告和执行明细两个维度查看 APP 自动化结果，支持快速定位报告、日志和执行证据。</p>
    </div>
    <a-space>
      <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { ReportsHeaderBarEmits } from './reportEventModels'
import type { ReportsHeaderBarProps } from './reportViewModels'

defineProps<ReportsHeaderBarProps>()

const emit = defineEmits<ReportsHeaderBarEmits>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p,
.header-tip {
  color: var(--theme-text-secondary);
}

.page-header p {
  margin: 6px 0 0;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

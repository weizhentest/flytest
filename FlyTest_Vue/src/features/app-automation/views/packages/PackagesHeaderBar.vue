<template>
  <div class="page-header">
    <div>
      <h3>应用包</h3>
      <p>集中维护 APP 包名、启动 Activity、平台信息与更新时间，方便设备执行与场景复用。</p>
    </div>
    <a-space wrap class="page-actions">
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
      <a-button type="primary" @click="emit('create')">新增应用包</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { PackagesHeaderBarEmits } from './packageEventModels'
import type { PackagesHeaderBarProps } from './packageViewModels'

defineProps<PackagesHeaderBarProps>()

const emit = defineEmits<PackagesHeaderBarEmits>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid var(--theme-card-border);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.02)),
    var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
  font-size: 22px;
  line-height: 1.2;
}

.page-header p {
  max-width: 760px;
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.page-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.page-header :deep(.arco-btn) {
  min-width: 92px;
  border-radius: 12px;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
  }

  .page-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>

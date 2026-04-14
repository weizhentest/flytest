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
interface Props {
  loading: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  refresh: []
  create: []
}>()
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

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.page-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>

<template>
  <div class="page-header">
    <div>
      <h3>测试用例</h3>
      <p>维护 APP 自动化场景、最近执行结果与快速执行入口，让日常回归更高效。</p>
    </div>
    <a-space wrap>
      <a-input-search
        v-model="searchModel"
        allow-clear
        placeholder="搜索测试用例"
        @search="emit('search')"
      />
      <a-select v-model="packageFilterModel" allow-clear placeholder="全部应用包" style="width: 220px">
        <a-option value="">全部应用包</a-option>
        <a-option v-for="pkg in packages" :key="pkg.id" :value="pkg.id">{{ pkg.name }}</a-option>
      </a-select>
      <a-button @click="emit('reset')">重置</a-button>
      <a-button @click="emit('quick-create')">快速新建</a-button>
      <a-button type="primary" @click="emit('open-scene-builder-draft')">新增测试用例</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { TestCasesHeaderBarEmits } from './testCaseEventModels'
import type { TestCasesHeaderBarProps } from './testCaseViewModels'

defineProps<TestCasesHeaderBarProps>()

const searchModel = defineModel<string>('search', { required: true })
const packageFilterModel = defineModel<number | ''>('packageFilter', { required: true })

const emit = defineEmits<TestCasesHeaderBarEmits>()
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

.page-header :deep(.arco-input-wrapper),
.page-header :deep(.arco-select-view),
.page-header :deep(.arco-btn) {
  border-radius: 12px;
}

.page-header :deep(.arco-btn) {
  min-width: 92px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
  }
}
</style>

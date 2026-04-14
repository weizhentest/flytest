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
import type { AppPackage } from '../../types'

interface Props {
  packages: AppPackage[]
}

defineProps<Props>()

const searchModel = defineModel<string>('search', { required: true })
const packageFilterModel = defineModel<number | ''>('packageFilter', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
  'quick-create': []
  'open-scene-builder-draft': []
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

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<template>
  <div class="page-header">
    <div>
      <h3>测试套件</h3>
      <p>组合多个 APP 用例形成可批量执行的回归套件，支持查看状态、历史、报告和套件详情。</p>
    </div>
    <a-space wrap>
      <a-input-search
        v-model="searchModel"
        allow-clear
        placeholder="搜索测试套件"
        @search="emit('search')"
      />
      <a-select v-model="statusModel" allow-clear placeholder="全部状态" style="width: 180px">
        <a-option value="">全部状态</a-option>
        <a-option value="not_run">未执行</a-option>
        <a-option value="running">执行中</a-option>
        <a-option value="passed">执行通过</a-option>
        <a-option value="failed">执行失败</a-option>
        <a-option value="stopped">已停止</a-option>
      </a-select>
      <a-button @click="emit('reset')">重置</a-button>
      <a-button @click="emit('refresh')">刷新</a-button>
      <a-button type="primary" @click="emit('create')">新建套件</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import type { SuitesHeaderBarEmits } from './suiteEventModels'

const searchModel = defineModel<string>('search', { required: true })
const statusModel = defineModel<string>('status', { required: true })

const emit = defineEmits<SuitesHeaderBarEmits>()
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

<template>
  <a-card class="table-card">
    <a-table :data="suites" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="套件 / 描述" :width="260">
          <template #cell="{ record }">
            <div class="stack">
              <strong>{{ record.name }}</strong>
              <span>{{ record.description || '暂无套件描述' }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="状态 / 健康度" :width="200">
          <template #cell="{ record }">
            <div class="stack">
              <a-tag :color="getSuiteStatusMeta(record).color">{{ getSuiteStatusMeta(record).label }}</a-tag>
              <small>健康度 {{ getSuiteHealthRate(record) }}%</small>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="用例 / 结果" :width="240">
          <template #cell="{ record }">
            <div class="stack">
              <span>用例数 {{ record.test_case_count || 0 }}</span>
              <small>
                通过 {{ record.passed_count || 0 }} / 失败 {{ record.failed_count || 0 }} / 停止
                {{ record.stopped_count || 0 }}
              </small>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="最近执行" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.last_run_at) }}</template>
        </a-table-column>
        <a-table-column title="操作" :width="380" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-run', record)">执行</a-button>
              <a-button type="text" @click="emit('open-detail', record)">详情</a-button>
              <a-button type="text" @click="emit('open-history', record)">历史</a-button>
              <a-button type="text" @click="emit('duplicate-suite', record)">复制</a-button>
              <a-button type="text" @click="emit('open-edit', record)">编辑</a-button>
              <a-button type="text" status="danger" @click="emit('remove', record.id)">删除</a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import type { SuitesTableCardEmits } from './suiteEventModels'
import type { SuitesTableCardProps } from './suiteViewModels'

defineProps<SuitesTableCardProps>()

const emit = defineEmits<SuitesTableCardEmits>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stack strong {
  color: var(--theme-text);
}

.stack span,
.stack small {
  color: var(--theme-text-secondary);
}
</style>

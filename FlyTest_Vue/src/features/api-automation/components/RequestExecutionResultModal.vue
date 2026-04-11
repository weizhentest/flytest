<template>
  <a-modal
    :visible="visible"
    class="detail-modal detail-modal--wide"
    :title="result?.id ? '执行结果详情' : '接口详情'"
    width="1120px"
    :footer="false"
    :mask-closable="true"
    :body-style="{ maxHeight: '78vh', overflowY: 'auto' }"
    @update:visible="value => emit('update:visible', value)"
  >
    <div v-if="result" class="result-drawer">
      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="接口名称">{{ result.request_name }}</a-descriptions-item>
        <a-descriptions-item label="执行状态">
          <a-tag :color="result.passed ? 'green' : result.status === 'error' ? 'red' : 'orange'">
            {{ result.status }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态码">{{ result.status_code ?? '-' }}</a-descriptions-item>
        <a-descriptions-item label="响应时间">{{ formatDuration(result.response_time) }}</a-descriptions-item>
        <a-descriptions-item label="最终地址" :span="2">{{ result.url }}</a-descriptions-item>
        <a-descriptions-item label="错误信息" :span="2">
          {{ result.error_message || '-' }}
        </a-descriptions-item>
      </a-descriptions>

      <a-divider>断言结果</a-divider>
      <a-table :data="result.assertions_results || []" :pagination="false" row-key="index">
        <template #columns>
          <a-table-column title="#" data-index="index" :width="60" />
          <a-table-column title="类型" data-index="type" :width="120" />
          <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
          <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
          <a-table-column title="结果" :width="90">
            <template #cell="{ record }">
              <a-tag :color="record.passed ? 'green' : 'red'">{{ record.passed ? '通过' : '失败' }}</a-tag>
            </template>
          </a-table-column>
        </template>
      </a-table>

      <a-divider>请求快照</a-divider>
      <pre class="json-block">{{ stringifyBlock(result.request_snapshot) }}</pre>

      <template v-if="result.request_snapshot?.generated_script">
        <a-divider>接口脚本</a-divider>
        <pre class="json-block">{{ stringifyBlock(result.request_snapshot.generated_script) }}</pre>
      </template>

      <a-divider>响应快照</a-divider>
      <pre class="json-block">{{ stringifyBlock(result.response_snapshot) }}</pre>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { ApiExecutionRecord } from '../types'

defineProps<{
  visible: boolean
  result: ApiExecutionRecord | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const stringifyBlock = (value: unknown) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}
</script>

<style scoped>
.result-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.json-block {
  margin: 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.95);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

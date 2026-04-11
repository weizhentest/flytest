<template>
  <a-drawer
    :visible="visible"
    width="920px"
    title="文档导入结果"
    :footer="false"
    @update:visible="value => emit('update:visible', value)"
  >
    <div v-if="result" class="import-result-drawer">
      <a-alert
        :type="result.ai_requested ? (result.ai_used ? 'success' : 'warning') : 'info'"
        class="import-result-alert"
      >
        <template #title>
          {{ alertTitle }}
        </template>
        <div>{{ alertMessage }}</div>
        <div v-if="alertActionHint" class="import-result-alert__hint">{{ alertActionHint }}</div>
      </a-alert>

      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="导入来源">{{ result.source_type || '-' }}</a-descriptions-item>
        <a-descriptions-item label="使用 Marker">
          <a-tag :color="result.marker_used ? 'arcoblue' : 'gray'">
            {{ result.marker_used ? '是' : '否' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="AI增强解析">
          <a-tag :color="result.ai_requested ? (result.ai_used ? 'green' : 'orange') : 'gray'">
            {{
              result.ai_requested
                ? result.ai_used
                  ? '已启用'
                  : '已回退'
                : '未开启'
            }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="AI模型">{{ result.ai_model_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="生成接口">{{ result.created_count || 0 }}</a-descriptions-item>
        <a-descriptions-item label="生成脚本">{{ result.generated_script_count || 0 }}</a-descriptions-item>
        <a-descriptions-item label="生成测试用例">{{ result.created_testcase_count || 0 }}</a-descriptions-item>
        <a-descriptions-item label="AI缓存">
          <a-tag :color="result.ai_cache_hit ? 'green' : 'gray'">
            {{ result.ai_cache_hit ? '命中缓存' : '未命中' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="AI耗时">
          {{ result.ai_duration_ms ? `${Math.round(result.ai_duration_ms)} ms` : '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="提示词来源">
          {{ result.ai_prompt_name || result.ai_prompt_source || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="解析说明" :span="2">{{ result.note || '-' }}</a-descriptions-item>
      </a-descriptions>

      <a-tabs type="rounded">
        <a-tab-pane key="scripts" title="接口脚本">
          <a-empty v-if="!result.generated_scripts?.length" description="暂无生成脚本" />
          <a-collapse v-else>
            <a-collapse-item
              v-for="item in result.generated_scripts"
              :key="item.request_id"
              :header="`${item.request_name}${item.collection_name ? ` · ${item.collection_name}` : ''}`"
            >
              <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
            </a-collapse-item>
          </a-collapse>
        </a-tab-pane>
        <a-tab-pane key="test-cases" title="测试用例">
          <a-empty v-if="!result.test_cases?.length" description="本次未生成测试用例" />
          <a-collapse v-else>
            <a-collapse-item
              v-for="item in result.test_cases"
              :key="item.id"
              :header="`${item.name}${item.request_name ? ` · ${item.request_name}` : ''}`"
            >
              <a-space wrap class="import-tags">
                <a-tag v-for="tag in item.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
              </a-space>
              <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
              <a-divider>断言规则</a-divider>
              <pre class="json-block">{{ stringifyBlock(item.assertions) }}</pre>
            </a-collapse-item>
          </a-collapse>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import type { ApiImportResult } from '../types'

const props = defineProps<{
  visible: boolean
  result: ApiImportResult | null
  alertTitle: string
  alertMessage: string
  alertActionHint: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const stringifyBlock = (value: unknown) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
</script>

<style scoped>
.import-result-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-result-alert {
  margin-bottom: 4px;
}

.import-result-alert__hint {
  margin-top: 8px;
  color: #7c2d12;
  font-size: 12px;
  line-height: 1.7;
}

.import-tags {
  margin-bottom: 12px;
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

<template>
  <a-modal
    :visible="modelValue"
    :title="title"
    width="980px"
    :footer="false"
    @cancel="emit('update:modelValue', false)"
  >
    <div class="reference-picker">
      <div class="reference-picker__toolbar">
        <a-input-search
          v-model="keyword"
          allow-clear
          placeholder="搜索标签、记录或预览内容"
          style="max-width: 320px"
        />
        <div class="reference-picker__hint">
          选中后会插入 {{ referenceExample }}
        </div>
      </div>

      <a-spin :loading="loading">
        <a-tabs v-model:active-key="activeTab" type="rounded">
          <a-tab-pane key="tags" title="标签引用">
            <a-table :data="filteredTags" :pagination="false" row-key="code">
              <template #columns>
                <a-table-column title="标签名称" data-index="name" />
                <a-table-column title="引用编码" :width="160">
                  <template #cell="{ record }">
                    <a-tag :color="record.color || 'arcoblue'">{{ record.code }}</a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="预览" data-index="preview" ellipsis tooltip />
                <a-table-column title="占位符" :width="220">
                  <template #cell="{ record }">
                    <code class="reference-code">{{ record.placeholder }}</code>
                  </template>
                </a-table-column>
                <a-table-column title="操作" :width="90" align="center">
                  <template #cell="{ record }">
                    <a-button size="mini" type="primary" @click="handleSelect(record.placeholder)">
                      选择
                    </a-button>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane key="records" title="记录引用">
            <a-table :data="filteredRecords" :pagination="false" row-key="id">
              <template #columns>
                <a-table-column title="记录ID" data-index="id" :width="90" />
                <a-table-column title="工具" data-index="tool_name" :width="170" />
                <a-table-column title="创建时间" :width="170">
                  <template #cell="{ record }">
                    {{ formatDate(record.created_at) }}
                  </template>
                </a-table-column>
                <a-table-column title="关联标签" :width="180">
                  <template #cell="{ record }">
                    <a-space wrap size="mini">
                      <a-tag v-for="tag in record.tag_codes" :key="tag" color="blue">{{ tag }}</a-tag>
                    </a-space>
                  </template>
                </a-table-column>
                <a-table-column title="预览" data-index="preview" ellipsis tooltip />
                <a-table-column title="占位符" :width="220">
                  <template #cell="{ record }">
                    <code class="reference-code">{{ record.placeholder }}</code>
                  </template>
                </a-table-column>
                <a-table-column title="操作" :width="90" align="center">
                  <template #cell="{ record }">
                    <a-button size="mini" type="primary" @click="handleSelect(record.placeholder)">
                      选择
                    </a-button>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </a-tab-pane>
        </a-tabs>
      </a-spin>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { dataFactoryApi } from '../api'
import type { DataFactoryReferencePayload } from '../types'
import { extractDataFactoryData } from '../types'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    projectId?: number | null
    mode?: 'api' | 'ui'
    title?: string
  }>(),
  {
    mode: 'api',
    title: '插入数据工厂引用',
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'select', value: string): void
}>()

const loading = ref(false)
const keyword = ref('')
const activeTab = ref('tags')
const payload = ref<DataFactoryReferencePayload>({
  mode: props.mode,
  tree: {},
  tags: [],
  records: [],
})

const referenceExample = computed(() =>
  props.mode === 'api' ? '`{{df.tag.demo}}` / `{{df.record.123}}`' : '`${{df.tag.demo}}` / `${{df.record.123}}`'
)

const filteredTags = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  if (!search) return payload.value.tags
  return payload.value.tags.filter(item =>
    [item.name, item.code, item.preview].some(value => String(value || '').toLowerCase().includes(search))
  )
})

const filteredRecords = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  if (!search) return payload.value.records
  return payload.value.records.filter(item =>
    [item.id, item.tool_name, item.preview, ...(item.tag_codes || [])]
      .map(value => String(value || '').toLowerCase())
      .some(value => value.includes(search))
  )
})

const loadReferences = async () => {
  if (!props.projectId) {
    payload.value = { mode: props.mode, tree: {}, tags: [], records: [] }
    return
  }

  loading.value = true
  try {
    const response = await dataFactoryApi.getReferences({ project: props.projectId, mode: props.mode })
    payload.value = extractDataFactoryData<DataFactoryReferencePayload>(response)
  } catch (error: any) {
    Message.error(error?.error || '加载数据工厂引用失败')
  } finally {
    loading.value = false
  }
}

const handleSelect = (placeholder: string) => {
  emit('select', placeholder)
  emit('update:modelValue', false)
}

const formatDate = (value: string) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN')
}

watch(
  () => [props.modelValue, props.projectId, props.mode] as const,
  ([visible]) => {
    if (visible) {
      void loadReferences()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.reference-picker {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reference-picker__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.reference-picker__hint {
  color: var(--color-text-3);
  font-size: 12px;
  text-align: right;
}

.reference-code {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
  font-size: 12px;
}

@media (max-width: 900px) {
  .reference-picker__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .reference-picker__hint {
    text-align: left;
  }
}
</style>

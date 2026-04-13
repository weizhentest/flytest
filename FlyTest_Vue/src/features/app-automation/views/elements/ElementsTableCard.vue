<template>
  <a-card class="table-card">
    <div v-if="selectedElementIdsModel.length" class="batch-bar">
      <span>已选择 <strong>{{ selectedElementIdsModel.length }}</strong> 个元素</span>
      <a-space wrap>
        <a-button type="primary" status="danger" size="small" :loading="batchDeleting" @click="emit('remove-selected')">
          批量删除
        </a-button>
        <a-button size="small" @click="emit('clear-selection')">取消选择</a-button>
      </a-space>
    </div>

    <a-table
      v-model:selectedKeys="selectedElementIdsModel"
      :data="elements"
      :loading="loading"
      :pagination="false"
      :row-selection="rowSelection"
      row-key="id"
    >
      <template #columns>
        <a-table-column title="名称" :width="180">
          <template #cell="{ record }">
            <a-button type="text" class="name-button" @click="emit('open-detail', record)">
              {{ record.name }}
            </a-button>
          </template>
        </a-table-column>

        <a-table-column title="类型" :width="100">
          <template #cell="{ record }">
            <a-tag :color="getTypeColor(record.element_type)">{{ getTypeLabel(record.element_type) }}</a-tag>
          </template>
        </a-table-column>

        <a-table-column title="预览" :width="220">
          <template #cell="{ record }">
            <div v-if="record.element_type === 'image' && record.image_path" class="table-preview">
              <img :src="getPreviewUrl(record.image_path)" alt="element preview" class="preview-image" />
            </div>
            <div v-else-if="record.element_type === 'pos'" class="coordinate-preview">
              {{ renderPos(record) }}
            </div>
            <div v-else-if="record.element_type === 'region'" class="coordinate-preview">
              {{ renderRegion(record) }}
            </div>
            <span v-else class="muted-text">-</span>
          </template>
        </a-table-column>

        <a-table-column title="图片分类" :width="140">
          <template #cell="{ record }">{{ getImageCategory(record) || '-' }}</template>
        </a-table-column>

        <a-table-column title="定位方式" data-index="selector_type" :width="120" />

        <a-table-column title="定位值">
          <template #cell="{ record }">
            <span class="mono">{{ record.selector_value || '-' }}</span>
          </template>
        </a-table-column>

        <a-table-column title="状态" :width="120">
          <template #cell="{ record }">
            <a-switch
              :model-value="record.is_active"
              size="small"
              @change="value => emit('toggle-active', record, Boolean(value))"
            />
          </template>
        </a-table-column>

        <a-table-column title="更新时间" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.updated_at) }}</template>
        </a-table-column>

        <a-table-column title="操作" :width="240" fixed="right">
          <template #cell="{ record }">
            <a-space>
              <a-button type="text" @click="emit('open-detail', record)">详情</a-button>
              <a-button type="text" @click="emit('duplicate-element', record)">复制</a-button>
              <a-button type="text" @click="emit('open-edit', record)">编辑</a-button>
              <a-button type="text" status="danger" @click="emit('remove', record.id)">删除</a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>

    <div class="pagination-row">
      <a-pagination
        v-model:current="currentModel"
        v-model:page-size="pageSizeModel"
        :total="total"
        :show-total="true"
        :show-jumper="true"
        :show-page-size="true"
        :page-size-options="['10', '20', '50', '100']"
      />
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { AppElement } from '../../types'

interface Props {
  loading: boolean
  batchDeleting: boolean
  elements: AppElement[]
  total: number
  formatDateTime: (value?: string) => string
  getTypeLabel: (value: string) => string
  getTypeColor: (value: string) => string
  getPreviewUrl: (imagePath?: string) => string
  renderPos: (record: AppElement) => string
  renderRegion: (record: AppElement) => string
  getImageCategory: (record: AppElement) => string
}

defineProps<Props>()

const selectedElementIdsModel = defineModel<number[]>('selectedElementIds', { required: true })
const currentModel = defineModel<number>('current', { required: true })
const pageSizeModel = defineModel<number>('pageSize', { required: true })

const rowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
}

const emit = defineEmits<{
  'open-detail': [record: AppElement]
  'duplicate-element': [record: AppElement]
  'open-edit': [record: AppElement]
  remove: [id: number]
  'toggle-active': [record: AppElement, value: boolean]
  'remove-selected': []
  'clear-selection': []
}>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.05);
  color: var(--theme-text);
}

.name-button {
  padding: 0;
}

.table-preview {
  display: flex;
  align-items: center;
}

.preview-image {
  width: 160px;
  height: 90px;
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.04);
}

.coordinate-preview,
.muted-text {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 960px) {
  .batch-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .pagination-row {
    justify-content: flex-start;
  }
}
</style>

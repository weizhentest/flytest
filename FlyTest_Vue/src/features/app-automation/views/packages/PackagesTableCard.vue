<template>
  <a-card class="table-card">
    <a-table :data="packages" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="应用名称" :width="260">
          <template #cell="{ record }">
            <div class="meta-stack">
              <strong>{{ record.name }}</strong>
              <span>{{ record.description || '未填写描述' }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="包名" :width="240">
          <template #cell="{ record }">
            <div class="meta-stack">
              <strong>{{ record.package_name }}</strong>
              <span>ID: {{ record.id }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="启动 Activity" :width="240">
          <template #cell="{ record }">
            <span>{{ record.activity_name || '未配置' }}</span>
          </template>
        </a-table-column>
        <a-table-column title="平台" :width="120">
          <template #cell="{ record }">
            <a-tag :color="getPlatformColor(record.platform)">{{ getPlatformLabel(record.platform) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="创建时间" :width="180">
          <template #cell="{ record }">
            <span>{{ formatDateTime(record.created_at) }}</span>
          </template>
        </a-table-column>
        <a-table-column title="更新时间" :width="180">
          <template #cell="{ record }">
            <span>{{ formatDateTime(record.updated_at) }}</span>
          </template>
        </a-table-column>
        <a-table-column title="操作" :width="180" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-edit', record)">编辑</a-button>
              <a-button type="text" status="danger" @click="emit('remove', record)">删除</a-button>
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
        :page-size-options="['10', '20', '50']"
      />
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { AppPackage } from '../../types'

interface Props {
  packages: AppPackage[]
  loading: boolean
  total: number
  formatDateTime: (value?: string | null) => string
  getPlatformLabel: (platform: string) => string
  getPlatformColor: (platform: string) => string
}

defineProps<Props>()

const currentModel = defineModel<number>('current', { required: true })
const pageSizeModel = defineModel<number>('pageSize', { required: true })

const emit = defineEmits<{
  'open-edit': [record: AppPackage]
  remove: [record: AppPackage]
}>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.meta-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-stack strong {
  color: var(--theme-text);
}

.meta-stack span {
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.pagination-row {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .pagination-row {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>

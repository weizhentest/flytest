<template>
  <div>
    <a-table
      :columns="columns"
      :data="configs"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      @page-change="(page: number) => emit('page-change', page)"
      @page-size-change="(pageSize: number) => emit('page-size-change', pageSize)"
    >
      <template #systemPrompt="{ record }">
        <span v-if="record.system_prompt" :title="record.system_prompt">
          {{ record.system_prompt.length > 50 ? record.system_prompt.substring(0, 50) + '...' : record.system_prompt }}
        </span>
        <span v-else class="text-gray-400">未设置</span>
      </template>
      <template #isActive="{ record }">
        <a-switch
          :model-value="record.is_active"
          :disabled="loading"
          @change="(value) => emit('toggle-active', record.id, !!value)"
        >
          <template #checked>已激活</template>
          <template #unchecked>未激活</template>
        </a-switch>
      </template>
      <template #actions="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="emit('edit', record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm
            content="确定要删除此配置吗？此操作不可撤销。"
            type="warning"
            @ok="emit('delete', record.id)"
          >
            <a-button type="primary" status="danger" size="small">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
      <template #createdAt="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>
      <template #updatedAt="{ record }">
        {{ formatDateTime(record.updated_at) }}
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import {
  Table as ATable,
  Button as AButton,
  Space as ASpace,
  Popconfirm as APopconfirm,
  Switch as ASwitch,
  type TableColumnData,
  type PaginationProps,
} from '@arco-design/web-vue';
import { IconEdit, IconDelete } from '@arco-design/web-vue/es/icon';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import { formatDateTime } from '@/utils/formatters';

interface Props {
  configs: LlmConfig[];
  loading: boolean;
  pagination?: PaginationProps; // 可选的分页配置
}

withDefaults(defineProps<Props>(), {
  configs: () => [],
  loading: false,
  pagination: () => ({
    current: 1,
    pageSize: 10,
    total: 0,
    showTotal: true,
    showPageSize: true,
  }),
});

const emit = defineEmits<{
  (e: 'edit', config: LlmConfig): void;
  (e: 'delete', configId: number): void;
  (e: 'toggle-active', configId: number, isActive: boolean): void;
  (e: 'page-change', page: number): void;
  (e: 'page-size-change', pageSize: number): void;
}>();

const columns: TableColumnData[] = [
  { title: 'ID', dataIndex: 'id', width: 80, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '配置名称', dataIndex: 'config_name', width: 150, ellipsis: true, tooltip: true },
  { title: '模型名称', dataIndex: 'name', width: 150, ellipsis: true, tooltip: true },
  { title: 'API URL', dataIndex: 'api_url', width: 200, ellipsis: true, tooltip: true },
  { title: '系统提示词', dataIndex: 'system_prompt', slotName: 'systemPrompt', width: 200, ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'is_active', slotName: 'isActive', width: 100, align: 'center' },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 150, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '更新时间', dataIndex: 'updated_at', slotName: 'updatedAt', width: 150, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'actions', width: 220, align: 'center', fixed: 'right' },
];

</script>

<style scoped>
/* 可以在这里添加特定于此组件的样式 */
</style>
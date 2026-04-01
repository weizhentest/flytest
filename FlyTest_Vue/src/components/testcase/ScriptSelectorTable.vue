<template>
  <div class="script-selector">
    <div class="selector-header">
      <a-input-search
        v-model="searchKeyword"
        placeholder="搜索脚本名称"
        allow-clear
        style="width: 300px;"
        @search="handleSearch"
      />
      <a-select
        v-model="selectedStatus"
        placeholder="筛选状态"
        allow-clear
        style="width: 150px; margin-left: 12px;"
        @change="handleStatusChange"
      >
        <a-option value="draft">草稿</a-option>
        <a-option value="active">可用</a-option>
        <a-option value="deprecated">已弃用</a-option>
      </a-select>
      <a-select
        v-model="selectedSource"
        placeholder="筛选来源"
        allow-clear
        style="width: 150px; margin-left: 12px;"
        @change="handleSourceChange"
      >
        <a-option value="ai_generated">AI生成</a-option>
        <a-option value="manual">手动编写</a-option>
        <a-option value="imported">导入</a-option>
      </a-select>
    </div>

    <a-table
      :columns="columns"
      :data="scriptData"
      :pagination="paginationConfig"
      :loading="loading"
      :scroll="{ y: 400 }"
      :bordered="{ cell: true }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #selection="{ record }">
        <a-checkbox
          :model-value="localSelectedIds.includes(record.id)"
          @change="(checked: boolean) => handleCheckboxChange(record.id, checked)"
        />
      </template>
      <template #selectAll>
        <a-checkbox
          :model-value="isCurrentPageAllSelected"
          :indeterminate="isCurrentPageIndeterminate"
          @change="handleSelectCurrentPage"
        />
      </template>
      <template #status="{ record }">
        <a-tag :color="getStatusColor(record.status)">{{ getStatusText(record.status) }}</a-tag>
      </template>
      <template #source="{ record }">
        <a-tag :color="getSourceColor(record.source)">{{ getSourceText(record.source) }}</a-tag>
      </template>
    </a-table>

    <div class="selector-footer">
      <div class="selected-info">
        已选择 <strong>{{ localSelectedIds.length }}</strong> 个自动化脚本
      </div>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          type="primary"
          :disabled="localSelectedIds.length === 0"
          @click="handleConfirm"
        >
          确认选择
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { listAutomationScripts } from '@/services/automationScriptService';
import { formatDate } from '@/utils/formatters';

interface AutomationScript {
  id: number;
  name: string;
  test_case: number;
  test_case_name?: string;
  script_type: string;
  source: string;
  status: string;
  version: number;
  description?: string;
  created_at: string;
}

interface Props {
  currentProjectId: number | null;
  initialSelectedIds?: number[];
}

const props = withDefaults(defineProps<Props>(), {
  initialSelectedIds: () => [],
});

const emit = defineEmits<{
  (e: 'confirm', selectedIds: number[]): void;
  (e: 'cancel'): void;
}>();

const loading = ref(false);
const searchKeyword = ref('');
const selectedStatus = ref<string>('');
const selectedSource = ref<string>('');
const scriptData = ref<AutomationScript[]>([]);
const localSelectedIds = ref<number[]>([...props.initialSelectedIds]);

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
});

const columns = [
  {
    title: '选择',
    slotName: 'selection',
    width: 50,
    titleSlotName: 'selectAll',
    align: 'center' as const,
  },
  { title: 'ID', dataIndex: 'id', width: 60, align: 'center' as const },
  { title: '脚本名称', dataIndex: 'name', width: 200, ellipsis: true, tooltip: true },
  { title: '关联用例', dataIndex: 'test_case_name', width: 150, ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 80, align: 'center' as const },
  { title: '来源', dataIndex: 'source', slotName: 'source', width: 100, align: 'center' as const },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    render: ({ record }: { record: AutomationScript }) => formatDate(record.created_at),
    width: 150,
    align: 'center' as const,
  },
];

const getStatusColor = (status: string) => {
  const map: Record<string, string> = {
    draft: 'gray',
    active: 'green',
    deprecated: 'red',
  };
  return map[status] || 'gray';
};

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    draft: '草稿',
    active: '可用',
    deprecated: '已弃用',
  };
  return map[status] || status;
};

const getSourceColor = (source: string) => {
  const map: Record<string, string> = {
    ai_generated: 'arcoblue',
    manual: 'purple',
    imported: 'orange',
  };
  return map[source] || 'gray';
};

const getSourceText = (source: string) => {
  const map: Record<string, string> = {
    ai_generated: 'AI生成',
    manual: '手动编写',
    imported: '导入',
  };
  return map[source] || source;
};

const isCurrentPageAllSelected = computed(() => {
  if (scriptData.value.length === 0) return false;
  return scriptData.value.every((item) => localSelectedIds.value.includes(item.id));
});

const isCurrentPageIndeterminate = computed(() => {
  const currentPageSelectedCount = scriptData.value.filter((item) =>
    localSelectedIds.value.includes(item.id)
  ).length;
  return currentPageSelectedCount > 0 && currentPageSelectedCount < scriptData.value.length;
});

const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!localSelectedIds.value.includes(id)) {
      localSelectedIds.value.push(id);
    }
  } else {
    const index = localSelectedIds.value.indexOf(id);
    if (index > -1) {
      localSelectedIds.value.splice(index, 1);
    }
  }
};

const handleSelectCurrentPage = (checked: boolean) => {
  if (checked) {
    const currentPageIds = scriptData.value.map((item) => item.id);
    currentPageIds.forEach((id) => {
      if (!localSelectedIds.value.includes(id)) {
        localSelectedIds.value.push(id);
      }
    });
  } else {
    const currentPageIds = scriptData.value.map((item) => item.id);
    localSelectedIds.value = localSelectedIds.value.filter((id) => !currentPageIds.includes(id));
  }
};

const fetchScripts = async () => {
  if (!props.currentProjectId) {
    scriptData.value = [];
    paginationConfig.total = 0;
    return;
  }

  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      page: paginationConfig.current,
      page_size: paginationConfig.pageSize,
      project_id: props.currentProjectId,
    };
    if (searchKeyword.value) params.search = searchKeyword.value;
    if (selectedStatus.value) params.status = selectedStatus.value;
    if (selectedSource.value) params.source = selectedSource.value;

    const response = await listAutomationScripts(params as any);

    if (response.data?.success) {
      // 处理分页响应格式: { data: { count, next, previous, results } }
      // 或者直接数组格式: { data: [...] }
      const responseData = response.data.data;
      if (responseData && Array.isArray(responseData.results)) {
        scriptData.value = responseData.results;
        paginationConfig.total = responseData.count || 0;
      } else if (Array.isArray(responseData)) {
        scriptData.value = responseData;
        paginationConfig.total = response.data.total || responseData.length;
      } else {
        scriptData.value = [];
        paginationConfig.total = 0;
      }
    } else {
      Message.error(response.data?.message || '获取脚本列表失败');
      scriptData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    console.error('获取脚本列表出错:', error);
    Message.error('获取脚本列表时发生错误');
    scriptData.value = [];
    paginationConfig.total = 0;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  paginationConfig.current = 1;
  fetchScripts();
};

const handleStatusChange = () => {
  paginationConfig.current = 1;
  fetchScripts();
};

const handleSourceChange = () => {
  paginationConfig.current = 1;
  fetchScripts();
};

const onPageChange = (page: number) => {
  paginationConfig.current = page;
  fetchScripts();
};

const onPageSizeChange = (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  fetchScripts();
};

const handleConfirm = () => {
  emit('confirm', [...localSelectedIds.value]);
};

const handleCancel = () => {
  emit('cancel');
};

onMounted(() => {
  fetchScripts();
});

watch(
  () => props.currentProjectId,
  () => {
    paginationConfig.current = 1;
    searchKeyword.value = '';
    selectedStatus.value = '';
    selectedSource.value = '';
    fetchScripts();
  }
);
</script>

<style scoped>
.script-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selector-header {
  display: flex;
  align-items: center;
}

.selector-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.selected-info {
  font-size: 14px;
  color: var(--color-text-2);
}
</style>

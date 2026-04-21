<template>
  <div class="project-deletion-log-page">
    <div class="page-header">
      <div>
        <h2>项目删除记录</h2>
        <p>管理员可在这里审核项目删除申请，并对已删除项目执行恢复。</p>
      </div>
      <a-button type="primary" :loading="loading" @click="fetchRecords">刷新</a-button>
    </div>

    <a-table :columns="columns" :data="records" :loading="loading" row-key="id" :pagination="false">
      <template #status="{ record }">
        <a-tag :color="statusColorMap[record.status] || 'gray'">{{ statusLabelMap[record.status] || record.status }}</a-tag>
      </template>
      <template #requested_at="{ record }">
        {{ formatDate(record.requested_at) }}
      </template>
      <template #deleted_at="{ record }">
        {{ formatDate(record.deleted_at) }}
      </template>
      <template #restored_at="{ record }">
        {{ formatDate(record.restored_at) }}
      </template>
      <template #operations="{ record }">
        <a-space>
          <a-button
            v-if="record.status === 'pending'"
            type="primary"
            size="mini"
            @click="approve(record)"
          >
            审核通过
          </a-button>
          <a-button
            v-if="record.status === 'pending'"
            status="warning"
            size="mini"
            @click="reject(record)"
          >
            驳回
          </a-button>
          <a-button
            v-if="record.can_restore"
            status="success"
            size="mini"
            @click="restore(record)"
          >
            恢复
          </a-button>
        </a-space>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';

import {
  approveProjectDeletionRequest,
  getProjectDeletionRequests,
  rejectProjectDeletionRequest,
  restoreProjectDeletionRequest,
  type ProjectDeletionRequest,
} from '@/services/projectDeletionService';

const loading = ref(false);
const records = ref<ProjectDeletionRequest[]>([]);

const statusLabelMap: Record<string, string> = {
  pending: '待审核',
  approved: '已删除',
  rejected: '已驳回',
  restored: '已恢复',
};

const statusColorMap: Record<string, string> = {
  pending: 'orange',
  approved: 'red',
  rejected: 'gray',
  restored: 'green',
};

const columns = [
  { title: '项目ID', dataIndex: 'project_display_id', width: 100 },
  { title: '项目名称', dataIndex: 'project_name', ellipsis: true, tooltip: true },
  { title: '删除人员', dataIndex: 'requested_by_name', width: 140 },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 110 },
  { title: '申请时间', dataIndex: 'requested_at', slotName: 'requested_at', width: 180 },
  { title: '删除时间', dataIndex: 'deleted_at', slotName: 'deleted_at', width: 180 },
  { title: '恢复时间', dataIndex: 'restored_at', slotName: 'restored_at', width: 180 },
  { title: '操作', slotName: 'operations', width: 220, fixed: 'right' },
];

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const fetchRecords = async () => {
  loading.value = true;
  try {
    const response = await getProjectDeletionRequests();
    if (response.success && response.data) {
      records.value = response.data;
      return;
    }
    Message.error(response.error || '获取项目删除记录失败');
  } finally {
    loading.value = false;
  }
};

const approve = (record: ProjectDeletionRequest) => {
  Modal.warning({
    title: '确认审核通过',
    content: `确认删除项目「${record.project_name}」并同步隐藏其测试用例和自动化脚本吗？`,
    onOk: async () => {
      const response = await approveProjectDeletionRequest(record.id);
      if (response.success) {
        Message.success(response.message || '项目删除已审核通过');
        await fetchRecords();
      } else {
        Message.error(response.error || '审核失败');
      }
    },
  });
};

const reject = (record: ProjectDeletionRequest) => {
  Modal.warning({
    title: '确认驳回',
    content: `确认驳回项目「${record.project_name}」的删除申请吗？`,
    onOk: async () => {
      const response = await rejectProjectDeletionRequest(record.id);
      if (response.success) {
        Message.success(response.message || '删除申请已驳回');
        await fetchRecords();
      } else {
        Message.error(response.error || '驳回失败');
      }
    },
  });
};

const restore = (record: ProjectDeletionRequest) => {
  Modal.warning({
    title: '确认恢复',
    content: `确认恢复项目「${record.project_name}」吗？恢复后其关联测试数据会重新可见。`,
    onOk: async () => {
      const response = await restoreProjectDeletionRequest(record.id);
      if (response.success) {
        Message.success(response.message || '项目已恢复');
        await fetchRecords();
      } else {
        Message.error(response.error || '恢复失败');
      }
    },
  });
};

onMounted(() => {
  void fetchRecords();
});
</script>

<style scoped>
.project-deletion-log-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}

.page-header h2 {
  margin: 0 0 8px;
}

.page-header p {
  margin: 0;
  color: #666;
}
</style>

<template>
  <div class="user-operation-log-view">
    <div class="operation-log-header">
      <div class="operation-log-title">
        <a-button class="back-button" size="small" @click="goBack">
          <template #icon><icon-left /></template>
        </a-button>
        <div>
          <h2>用户操作记录</h2>
          <p>{{ userTitle }}</p>
        </div>
      </div>
      <a-button :loading="loading" @click="fetchLogs">
        <template #icon><icon-refresh /></template>
        刷新
      </a-button>
    </div>

    <div class="operation-log-table">
      <a-table
        row-key="id"
        :columns="columns"
        :data="logs"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 980 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #action="{ record }">
          <a-tag :color="actionColor(record.action)">
            {{ record.action_display || record.action || '-' }}
          </a-tag>
        </template>
        <template #label="{ record }">
          <span class="log-label">{{ record.label || '-' }}</span>
        </template>
        <template #path="{ record }">
          <span class="log-path" :title="record.path || '-'">{{ record.path || '-' }}</span>
        </template>
        <template #ip="{ record }">
          <span class="log-ip">{{ record.ip_address || '-' }}</span>
        </template>
        <template #userAgent="{ record }">
          <span class="log-user-agent" :title="record.user_agent || '-'">{{ record.user_agent || '-' }}</span>
        </template>
        <template #createdAt="{ record }">
          <span class="log-time">{{ formatDateTime(record.created_at) }}</span>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import { IconLeft, IconRefresh } from '@arco-design/web-vue/es/icon';
import {
  getUserDetail,
  getUserOperationLogs,
  type User,
  type UserOperationLog,
} from '@/services/userService';
import { getUserDisplayName } from '@/utils/userDisplay';

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const logs = ref<UserOperationLog[]>([]);
const selectedUser = ref<User | null>(null);

const userId = computed(() => {
  const rawId = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id;
  return Number(rawId) || 0;
});

const userTitle = computed(() => {
  if (selectedUser.value) {
    return `${getUserDisplayName(selectedUser.value)} / ID ${selectedUser.value.id}`;
  }
  return userId.value ? `用户 ID ${userId.value}` : '未选择用户';
});

const columns = [
  {
    title: '操作时间',
    dataIndex: 'created_at',
    slotName: 'createdAt',
    width: 180,
  },
  {
    title: '操作',
    dataIndex: 'action',
    slotName: 'action',
    width: 110,
    align: 'center',
  },
  {
    title: '操作内容',
    dataIndex: 'label',
    slotName: 'label',
    width: 160,
  },
  {
    title: 'IP地址',
    dataIndex: 'ip_address',
    slotName: 'ip',
    width: 150,
  },
  {
    title: '页面路径',
    dataIndex: 'path',
    slotName: 'path',
    width: 240,
  },
  {
    title: '请求方式',
    dataIndex: 'method',
    width: 100,
    align: 'center',
  },
  {
    title: '浏览器',
    dataIndex: 'user_agent',
    slotName: 'userAgent',
    width: 260,
  },
];

const pagination = reactive({
  total: 0,
  current: 1,
  pageSize: 20,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
});

const actionColor = (action: string) => {
  if (action === 'login') return 'green';
  if (action === 'logout') return 'red';
  return 'blue';
};

const formatDateTime = (value: string) => {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('zh-CN', { hour12: false });
};

const fetchUser = async () => {
  if (!userId.value) {
    return;
  }

  const response = await getUserDetail(userId.value);
  if (response.success && response.data) {
    selectedUser.value = response.data;
  }
};

const fetchLogs = async () => {
  if (!userId.value) {
    Message.error('用户ID无效');
    return;
  }

  loading.value = true;
  try {
    const response = await getUserOperationLogs(userId.value, {
      page: pagination.current,
      pageSize: pagination.pageSize,
    });

    if (response.success) {
      logs.value = response.data || [];
      pagination.total = response.total || 0;
      return;
    }

    Message.error(response.error || '获取用户操作记录失败');
    logs.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

const handlePageChange = (page: number) => {
  pagination.current = page;
  fetchLogs();
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
  fetchLogs();
};

const goBack = () => {
  router.push({ name: 'UserManagement' });
};

onMounted(() => {
  fetchUser();
  fetchLogs();
});
</script>

<style scoped>
.user-operation-log-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.operation-log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--ui-toolbar-border, var(--color-border-2));
  border-radius: 8px;
  background: var(--ui-toolbar-bg, var(--color-bg-2));
}

.operation-log-title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
}

.operation-log-title h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
  color: var(--color-text-1);
}

.operation-log-title p {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--color-text-3);
}

.back-button {
  flex: 0 0 auto;
}

.operation-log-table {
  overflow: hidden;
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  background: var(--color-bg-2);
}

.log-label,
.log-path,
.log-user-agent {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

.log-ip,
.log-time {
  white-space: nowrap;
}

:deep(.arco-table-th) {
  background: var(--color-fill-2);
  color: var(--color-text-2);
  font-weight: 600;
}

:deep(.arco-table-td) {
  background: var(--color-bg-2);
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background: rgba(var(--primary-6), 0.06);
}

:deep(.arco-pagination) {
  margin: 0;
  padding: 10px 12px;
  border-top: 1px solid var(--color-border-2);
}
</style>

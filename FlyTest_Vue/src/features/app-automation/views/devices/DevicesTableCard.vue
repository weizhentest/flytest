<template>
  <a-card class="table-card">
    <a-table :data="devices" :loading="loading" :pagination="false" row-key="id">
      <template #columns>
        <a-table-column title="设备信息" :width="260">
          <template #cell="{ record }">
            <div class="device-copy">
              <strong>{{ record.name || record.device_id }}</strong>
              <span>{{ record.device_id }}</span>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="状态" :width="120">
          <template #cell="{ record }">
            <a-tag :color="getStatusColor(record.status)">{{ getStatusLabel(record.status) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="连接类型" :width="180">
          <template #cell="{ record }">
            <div class="device-copy">
              <span>{{ getConnectionLabel(record.connection_type) }}</span>
              <small>{{ formatEndpoint(record) }}</small>
            </div>
          </template>
        </a-table-column>
        <a-table-column title="Android" data-index="android_version" :width="110" />
        <a-table-column title="锁定用户" :width="140">
          <template #cell="{ record }">{{ record.locked_by || '-' }}</template>
        </a-table-column>
        <a-table-column title="最近更新时间" :width="180">
          <template #cell="{ record }">{{ formatDateTime(record.updated_at) }}</template>
        </a-table-column>
        <a-table-column title="操作" :width="380" fixed="right">
          <template #cell="{ record }">
            <a-space wrap>
              <a-button type="text" @click="emit('open-detail', record)">详情</a-button>
              <a-button type="text" @click="emit('open-edit', record)">编辑</a-button>
              <a-button
                type="text"
                :loading="screenshotLoadingId === record.id"
                @click="emit('preview-screenshot', record.id)"
              >
                截图
              </a-button>
              <a-button
                v-if="canLock(record)"
                type="text"
                @click="emit('lock', record.id)"
              >
                锁定
              </a-button>
              <a-button
                v-else-if="canUnlock(record)"
                type="text"
                @click="emit('unlock', record.id)"
              >
                释放
              </a-button>
              <a-button
                v-if="canReconnect(record)"
                type="text"
                @click="emit('reconnect', record)"
              >
                重连
              </a-button>
              <a-button
                v-if="canDisconnect(record)"
                type="text"
                @click="emit('disconnect', record.id)"
              >
                断开
              </a-button>
              <a-button
                type="text"
                status="danger"
                :disabled="record.can_delete === false"
                :title="record.delete_block_reason || ''"
                @click="emit('remove', record.id)"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import type { DevicesTableCardEmits } from './deviceEventModels'
import type { DevicesTableCardProps } from './deviceViewModels'

defineProps<DevicesTableCardProps>()

const emit = defineEmits<DevicesTableCardEmits>()
</script>

<style scoped>
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.device-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.device-copy strong {
  color: var(--theme-text);
}

.device-copy span,
.device-copy small {
  color: var(--theme-text-secondary);
}
</style>

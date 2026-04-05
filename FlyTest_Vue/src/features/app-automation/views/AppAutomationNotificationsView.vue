<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <h3>通知日志</h3>
        <p>补齐 APP 自动化通知日志能力，支持筛选、统计、分页、详情查看和失败重试。</p>
      </div>
      <a-space>
        <a-button @click="loadData" :loading="loading">刷新</a-button>
      </a-space>
    </div>

    <a-card class="filter-card">
      <div class="filter-grid">
        <a-input-search
          v-model="filters.search"
          allow-clear
          placeholder="搜索任务名称或通知内容"
          @search="handleSearch"
        />
        <a-select v-model="filters.status" allow-clear placeholder="发送状态">
          <a-option value="success">success</a-option>
          <a-option value="failed">failed</a-option>
          <a-option value="pending">pending</a-option>
        </a-select>
        <a-select v-model="filters.notification_type" allow-clear placeholder="通知类型">
          <a-option value="email">email</a-option>
          <a-option value="webhook">webhook</a-option>
          <a-option value="both">both</a-option>
        </a-select>
        <div class="filter-actions">
          <a-button @click="resetFilters">重置</a-button>
          <a-button type="primary" @click="handleSearch">查询</a-button>
        </div>
      </div>
    </a-card>

    <div class="stats-grid">
      <a-card class="stat-card">
        <span class="stat-label">日志总数</span>
        <strong>{{ statistics.total }}</strong>
        <span class="stat-desc">当前筛选条件下的通知日志数量</span>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">发送成功</span>
        <strong>{{ statistics.success }}</strong>
        <span class="stat-desc">成功投递到邮箱或 Webhook 的记录</span>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">发送失败</span>
        <strong>{{ statistics.failed }}</strong>
        <span class="stat-desc">失败日志可进入详情查看错误并重试</span>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">已重试</span>
        <strong>{{ statistics.retried }}</strong>
        <span class="stat-desc">已经触发过重试的通知条目</span>
      </a-card>
    </div>

    <a-card class="table-card">
      <a-table :data="pagedLogs" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="任务" :width="220">
            <template #cell="{ record }">
              <div class="meta-stack">
                <strong>{{ record.task_name || '-' }}</strong>
                <span>{{ getTaskTypeLabel(record.task_type) }}</span>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="通知类型" :width="150">
            <template #cell="{ record }">
              <a-tag :color="getNotificationTypeColor(record.actual_notification_type || record.notification_type)">
                {{ getNotificationTypeLabel(record.actual_notification_type || record.notification_type) }}
              </a-tag>
            </template>
          </a-table-column>

          <a-table-column title="收件对象" :width="240">
            <template #cell="{ record }">
              <div class="meta-stack">
                <span>{{ recipientSummary(record) }}</span>
                <small>发送者：{{ record.sender_name || 'FlyTest' }}</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="状态" :width="140">
            <template #cell="{ record }">
              <div class="meta-stack">
                <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
                <small>重试 {{ record.retry_count || 0 }} 次</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="通知时间" :width="210">
            <template #cell="{ record }">
              <div class="meta-stack">
                <span>创建：{{ formatDateTime(record.created_at) }}</span>
                <small>发送：{{ formatDateTime(record.sent_at) }}</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="操作" :width="220" fixed="right">
            <template #cell="{ record }">
              <a-space>
                <a-button type="text" @click="viewDetail(record)">详情</a-button>
                <a-button
                  v-if="record.status !== 'success'"
                  type="text"
                  :loading="retryingId === record.id"
                  @click="retry(record.id)"
                >
                  重试
                </a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>

      <div class="pagination-row">
        <a-pagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="filteredLogs.length"
          :show-total="true"
          :show-jumper="true"
          :show-page-size="true"
          :page-size-options="['10', '20', '50']"
        />
      </div>
    </a-card>

    <a-modal v-model:visible="detailVisible" title="通知详情" width="860px" :footer="false">
      <div v-if="currentLog" class="detail-shell">
        <div class="detail-grid">
          <div class="detail-card">
            <span class="detail-label">任务名称</span>
            <strong>{{ currentLog.task_name || '-' }}</strong>
          </div>
          <div class="detail-card">
            <span class="detail-label">任务类型</span>
            <strong>{{ getTaskTypeLabel(currentLog.task_type) }}</strong>
          </div>
          <div class="detail-card">
            <span class="detail-label">通知类型</span>
            <strong>{{ getNotificationTypeLabel(currentLog.actual_notification_type || currentLog.notification_type) }}</strong>
          </div>
          <div class="detail-card">
            <span class="detail-label">发送状态</span>
            <strong>{{ currentLog.status }}</strong>
          </div>
        </div>

        <a-card class="detail-panel" title="投递信息">
          <div class="meta-block">
            <div class="meta-row">
              <span>发送者：{{ currentLog.sender_name || '-' }}</span>
              <span>邮箱：{{ currentLog.sender_email || '-' }}</span>
              <span>创建时间：{{ formatDateTime(currentLog.created_at) }}</span>
              <span>发送时间：{{ formatDateTime(currentLog.sent_at) }}</span>
            </div>
            <div class="meta-row">
              <span>接收方：{{ recipientSummary(currentLog) }}</span>
              <span>重试次数：{{ currentLog.retry_count || 0 }}</span>
              <span>已重试：{{ currentLog.is_retried ? '是' : '否' }}</span>
            </div>
          </div>
        </a-card>

        <a-card class="detail-panel" title="通知内容">
          <div v-if="parsedContent.length" class="parsed-content">
            <div v-for="item in parsedContent" :key="`${item.label}-${item.value}`" class="parsed-row">
              <span class="parsed-label">{{ item.label }}</span>
              <span class="parsed-value">{{ item.value }}</span>
            </div>
          </div>
          <a-textarea
            v-else
            :model-value="currentLog.notification_content || '-'"
            readonly
            :auto-size="{ minRows: 8, maxRows: 16 }"
          />
        </a-card>

        <a-card class="detail-panel" title="响应 / 错误信息">
          <a-alert v-if="currentLog.error_message" type="error">{{ currentLog.error_message }}</a-alert>
          <a-textarea
            :model-value="JSON.stringify(currentLog.response_info || {}, null, 2)"
            readonly
            :auto-size="{ minRows: 8, maxRows: 16 }"
          />
        </a-card>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppNotificationLog } from '../types'

const loading = ref(false)
const retryingId = ref<number | null>(null)
const detailVisible = ref(false)
const currentLog = ref<AppNotificationLog | null>(null)
const logs = ref<AppNotificationLog[]>([])

const filters = reactive({
  search: '',
  status: '',
  notification_type: '',
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
})

const filteredLogs = computed(() => {
  const keyword = filters.search.trim().toLowerCase()

  return logs.value.filter(log => {
    if (filters.status && log.status !== filters.status) return false

    const notificationType = String(log.actual_notification_type || log.notification_type || '')
    if (filters.notification_type && notificationType !== filters.notification_type) return false

    if (!keyword) return true

    return [
      log.task_name,
      log.notification_content,
      notificationType,
      recipientSummary(log),
      log.error_message,
    ]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const pagedLogs = computed(() => {
  const start = (pagination.current - 1) * pagination.pageSize
  return filteredLogs.value.slice(start, start + pagination.pageSize)
})

const statistics = computed(() => ({
  total: filteredLogs.value.length,
  success: filteredLogs.value.filter(item => item.status === 'success').length,
  failed: filteredLogs.value.filter(item => item.status === 'failed').length,
  retried: filteredLogs.value.filter(item => item.is_retried).length,
}))

const parsedContent = computed(() => {
  const content = currentLog.value?.notification_content
  if (!content) return []

  try {
    const payload = JSON.parse(content)
    const rawText =
      payload.markdown?.content ||
      payload.markdown?.text ||
      payload.card?.elements?.[0]?.text?.content ||
      ''

    if (!rawText) {
      return []
    }

    return rawText
      .split('\n')
      .map(item => item.trim())
      .filter(item => item && !item.includes('**'))
      .map(item => {
        const index = item.indexOf(':')
        return index > 0
          ? { label: item.slice(0, index).trim(), value: item.slice(index + 1).trim() }
          : null
      })
      .filter(Boolean) as Array<{ label: string; value: string }>
  } catch {
    return content
      .split('\n')
      .map(item => item.trim())
      .filter(Boolean)
      .map(item => {
        const index = item.indexOf(':')
        return index > 0
          ? { label: item.slice(0, index).trim(), value: item.slice(index + 1).trim() }
          : null
      })
      .filter(Boolean) as Array<{ label: string; value: string }>
  }
})

const recipientSummary = (record: AppNotificationLog) =>
  record.recipient_info.map(item => item.email || item.name || '').filter(Boolean).join(', ') || '-'

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const getTaskTypeLabel = (value: string) => {
  if (value === 'TEST_SUITE') return '测试套件'
  if (value === 'TEST_CASE') return '测试用例'
  return value || '-'
}

const getNotificationTypeLabel = (value: string) => {
  if (value === 'email') return '邮件'
  if (value === 'webhook') return 'Webhook'
  if (value === 'both') return '邮件 + Webhook'
  return value || '-'
}

const getNotificationTypeColor = (value: string) => {
  if (value === 'email') return 'arcoblue'
  if (value === 'webhook') return 'green'
  if (value === 'both') return 'orange'
  return 'gray'
}

const getStatusColor = (value: string) => {
  if (value === 'success') return 'green'
  if (value === 'failed') return 'red'
  if (value === 'pending') return 'orange'
  return 'gray'
}

const loadData = async () => {
  loading.value = true
  try {
    logs.value = await AppAutomationService.getNotificationLogs({
      search: filters.search || undefined,
      status: filters.status || undefined,
      notification_type: filters.notification_type || undefined,
    })
  } catch (error: any) {
    Message.error(error.message || '加载通知日志失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  void loadData()
}

const resetFilters = () => {
  filters.search = ''
  filters.status = ''
  filters.notification_type = ''
  pagination.current = 1
  void loadData()
}

const retry = async (id: number) => {
  retryingId.value = id
  try {
    await AppAutomationService.retryNotification(id)
    Message.success('通知已重试')
    await loadData()
  } catch (error: any) {
    Message.error(error.message || '重试通知失败')
  } finally {
    retryingId.value = null
  }
}

const viewDetail = (record: AppNotificationLog) => {
  currentLog.value = record
  detailVisible.value = true
}

watch(
  () => filteredLogs.value.length,
  total => {
    const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
    if (pagination.current > maxPage) {
      pagination.current = maxPage
    }
  },
)

void loadData()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.filter-card,
.table-card,
.stat-card,
.detail-panel {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.4fr 180px 180px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-card strong {
  font-size: 30px;
  color: var(--theme-text);
  line-height: 1;
}

.stat-desc {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.meta-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-stack strong,
.meta-stack span {
  color: var(--theme-text);
}

.meta-stack small {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.detail-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-label {
  display: block;
  margin-bottom: 8px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.detail-card strong {
  color: var(--theme-text);
}

.meta-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.parsed-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.parsed-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(var(--theme-accent-rgb), 0.1);
}

.parsed-row:last-child {
  border-bottom: none;
}

.parsed-label {
  color: var(--theme-text-secondary);
  font-weight: 600;
}

.parsed-value {
  color: var(--theme-text);
  word-break: break-word;
}

@media (max-width: 1260px) {
  .filter-grid,
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-grid,
  .stats-grid,
  .parsed-row {
    grid-template-columns: 1fr;
  }

  .filter-actions,
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>

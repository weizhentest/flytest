<template>
  <div class="page-shell">
    <div class="page-header">
        <div>
          <h3>设备管理</h3>
          <p>统一管理本地模拟器、远程设备和真机，支持快速排查、锁定、截图和重连。</p>
        </div>
        <a-space wrap>
          <span class="header-tip">最近刷新：{{ lastUpdatedText }}</span>
          <label class="auto-refresh-toggle">
            <span>30 秒自动刷新</span>
            <a-switch :model-value="autoRefreshEnabled" size="small" @change="toggleAutoRefresh" />
          </label>
          <a-button @click="showConnectModal = true">添加远程设备</a-button>
          <a-button type="primary" :loading="loading" @click="discover">刷新设备</a-button>
        </a-space>
      </div>

    <div class="stats-grid">
      <a-card class="stat-card">
        <span class="stat-label">设备总数</span>
        <strong>{{ stats.total }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">可用设备</span>
        <strong>{{ stats.available }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">锁定中</span>
        <strong>{{ stats.locked }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">离线设备</span>
        <strong>{{ stats.offline }}</strong>
      </a-card>
    </div>

    <a-card class="filter-card">
      <div class="filter-grid">
          <a-input-search
            v-model="filters.search"
            allow-clear
            placeholder="搜索设备名称或序列号"
            @search="handleSearch"
          />
        <a-select v-model="filters.status" allow-clear placeholder="筛选状态">
          <a-option value="">全部状态</a-option>
          <a-option value="available">可用</a-option>
          <a-option value="online">在线</a-option>
          <a-option value="locked">锁定</a-option>
          <a-option value="offline">离线</a-option>
        </a-select>
        <div class="filter-actions">
          <a-button @click="resetFilters">重置</a-button>
          <a-button type="primary" @click="handleSearch">查询</a-button>
        </div>
      </div>
    </a-card>

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
                <a-button type="text" @click="openDetail(record)">详情</a-button>
                <a-button type="text" @click="openEdit(record)">编辑</a-button>
                <a-button
                  type="text"
                  :loading="screenshotLoadingId === record.id"
                  @click="previewScreenshot(record.id)"
                >
                  截图
                </a-button>
                <a-button v-if="record.status !== 'locked'" type="text" @click="lock(record.id)">锁定</a-button>
                <a-button v-else type="text" @click="unlock(record.id)">释放</a-button>
                <a-button v-if="canReconnect(record)" type="text" @click="reconnect(record)">重连</a-button>
                <a-button v-if="canDisconnect(record)" type="text" @click="disconnect(record.id)">断开</a-button>
                <a-button type="text" status="danger" @click="remove(record.id)">删除</a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <a-modal v-model:visible="showConnectModal" title="添加远程设备" @ok="connect">
      <a-form :model="connectForm" layout="vertical">
        <a-form-item field="ip_address" label="IP 地址">
          <a-input v-model="connectForm.ip_address" placeholder="例如 192.168.1.15" />
        </a-form-item>
        <a-form-item field="port" label="端口">
          <a-input-number v-model="connectForm.port" :min="1" :max="65535" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:visible="editVisible" title="编辑设备信息" :confirm-loading="editSaving" @ok="submitEdit">
      <a-form :model="editForm" layout="vertical">
        <a-form-item field="name" label="设备名称">
          <a-input v-model="editForm.name" placeholder="输入设备名称" />
        </a-form-item>
        <a-form-item field="status" label="设备状态">
          <a-select v-model="editForm.status" placeholder="选择设备状态">
            <a-option value="available">可用</a-option>
            <a-option value="online">在线</a-option>
            <a-option value="locked">锁定</a-option>
            <a-option value="offline">离线</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="location" label="位置">
          <a-input v-model="editForm.location" placeholder="例如 QA 机房 / 本地模拟器" />
        </a-form-item>
        <a-form-item field="description" label="备注">
          <a-textarea v-model="editForm.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:visible="detailVisible" title="设备详情" width="760px" :footer="false">
      <div v-if="currentDevice" class="detail-grid">
        <div class="detail-card">
          <span class="detail-label">设备名称</span>
          <strong>{{ currentDevice.name || currentDevice.device_id }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">当前状态</span>
          <strong>{{ getStatusLabel(currentDevice.status) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">连接方式</span>
          <strong>{{ getConnectionLabel(currentDevice.connection_type) }}</strong>
        </div>
        <div class="detail-card">
          <span class="detail-label">Android 版本</span>
          <strong>{{ currentDevice.android_version || '-' }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">序列号</span>
          <strong>{{ currentDevice.device_id }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">网络地址</span>
          <strong>{{ formatEndpoint(currentDevice) }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">锁定用户</span>
          <strong>{{ currentDevice.locked_by || '-' }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">锁定时间</span>
          <strong>{{ formatDateTime(currentDevice.locked_at) }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">位置</span>
          <strong>{{ currentDevice.location || '-' }}</strong>
        </div>
        <div class="detail-panel">
          <span class="detail-label">最近在线</span>
          <strong>{{ formatDateTime(currentDevice.last_seen_at) }}</strong>
        </div>
        <div class="detail-panel detail-panel-wide">
          <span class="detail-label">备注</span>
          <strong>{{ currentDevice.description || '-' }}</strong>
        </div>
      </div>
    </a-modal>

    <a-modal v-model:visible="screenshotVisible" title="设备截图" width="980px" :footer="false">
      <div v-if="currentScreenshot" class="screenshot-shell">
        <div class="screenshot-meta">
          <span>设备：{{ currentScreenshot.device_id }}</span>
          <span>时间：{{ formatTimestamp(currentScreenshot.timestamp) }}</span>
        </div>
        <div class="screenshot-frame">
          <img :src="currentScreenshot.content" alt="device screenshot" class="screenshot-image" />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAuthStore } from '@/store/authStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppDevice, AppDeviceScreenshot } from '../types'

const authStore = useAuthStore()
const loading = ref(false)
const editSaving = ref(false)
const autoRefreshEnabled = ref(true)
const showConnectModal = ref(false)
const screenshotVisible = ref(false)
const screenshotLoadingId = ref<number | null>(null)
const detailVisible = ref(false)
const editVisible = ref(false)
const currentScreenshot = ref<AppDeviceScreenshot | null>(null)
const currentDevice = ref<AppDevice | null>(null)
const editingDeviceId = ref<number | null>(null)
const devices = ref<AppDevice[]>([])
const lastUpdatedAt = ref<string>('')

let refreshTimer: ReturnType<typeof setInterval> | null = null

const filters = reactive({
  search: '',
  status: '',
})

const connectForm = reactive({
  ip_address: '',
  port: 5555,
})

const editForm = reactive({
  name: '',
  description: '',
  location: '',
  status: 'available',
})

const stats = computed(() => {
  const total = devices.value.length
  const available = devices.value.filter(item => ['available', 'online'].includes(item.status)).length
  const locked = devices.value.filter(item => item.status === 'locked').length
  const offline = devices.value.filter(item => item.status === 'offline').length
  return { total, available, locked, offline }
})

const lastUpdatedText = computed(() => {
  if (!lastUpdatedAt.value) return '未刷新'
  return formatDateTime(lastUpdatedAt.value)
})

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const formatTimestamp = (timestamp?: number) => {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

const getStatusLabel = (status: string) => {
  if (status === 'available') return '可用'
  if (status === 'online') return '在线'
  if (status === 'locked') return '锁定'
  if (status === 'offline') return '离线'
  return status || '-'
}

const getStatusColor = (status: string) => {
  if (status === 'available') return 'green'
  if (status === 'online') return 'arcoblue'
  if (status === 'locked') return 'orange'
  if (status === 'offline') return 'gray'
  return 'gray'
}

const getConnectionLabel = (connectionType: string) => {
  if (connectionType === 'emulator') return '模拟器'
  if (connectionType === 'remote') return '远程设备'
  if (connectionType === 'remote_emulator') return '远程设备'
  if (connectionType === 'usb') return 'USB 真机'
  return connectionType || '-'
}

const formatEndpoint = (record: AppDevice) => {
  if (record.ip_address) {
    return `${record.ip_address}:${record.port || 5555}`
  }
  return '-'
}

const canReconnect = (record: AppDevice) =>
  record.status === 'offline' && Boolean(record.ip_address) && record.connection_type !== 'emulator'

const canDisconnect = (record: AppDevice) =>
  record.status !== 'offline' && Boolean(record.ip_address) && record.connection_type !== 'emulator'

const loadDevices = async (options: { silent?: boolean } = {}) => {
  if (loading.value && options.silent) {
    return
  }

  loading.value = true
  try {
    devices.value = await AppAutomationService.getDevices({
      search: filters.search.trim() || undefined,
      status: filters.status || undefined,
    })
    lastUpdatedAt.value = new Date().toISOString()
  } catch (error: any) {
    if (!options.silent) {
      Message.error(error.message || '加载设备失败')
    }
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  await loadDevices()
}

const resetFilters = async () => {
  filters.search = ''
  filters.status = ''
  await loadDevices()
}

const discover = async () => {
  loading.value = true
  try {
    await AppAutomationService.discoverDevices()
    Message.success('设备列表已刷新')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '刷新设备失败')
  } finally {
    loading.value = false
  }
}

const connect = async () => {
  try {
    await AppAutomationService.connectDevice(connectForm)
    showConnectModal.value = false
    connectForm.ip_address = ''
    connectForm.port = 5555
    Message.success('远程设备连接成功')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '连接设备失败')
  }
}

const openDetail = (record: AppDevice) => {
  currentDevice.value = { ...record }
  detailVisible.value = true
}

const openEdit = (record: AppDevice) => {
  editingDeviceId.value = record.id
  editForm.name = record.name || ''
  editForm.description = record.description || ''
  editForm.location = record.location || ''
  editForm.status = record.status || 'available'
  editVisible.value = true
}

const submitEdit = async () => {
  if (!editingDeviceId.value) return

  editSaving.value = true
  try {
    const updated = await AppAutomationService.updateDevice(editingDeviceId.value, {
      name: editForm.name,
      description: editForm.description,
      location: editForm.location,
      status: editForm.status,
    })
    editVisible.value = false
    currentDevice.value = updated
    Message.success('设备信息已更新')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '更新设备失败')
  } finally {
    editSaving.value = false
  }
}

const lock = async (id: number) => {
  try {
    await AppAutomationService.lockDevice(id, authStore.currentUser?.username || 'FlyTest')
    Message.success('设备已锁定')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '锁定设备失败')
  }
}

const unlock = async (id: number) => {
  try {
    await AppAutomationService.unlockDevice(id)
    Message.success('设备已释放')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '释放设备失败')
  }
}

const disconnect = async (id: number) => {
  try {
    await AppAutomationService.disconnectDevice(id)
    Message.success('设备已断开')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '断开设备失败')
  }
}

const reconnect = async (record: AppDevice) => {
  if (!record.ip_address) {
    Message.warning('当前设备没有远程地址，无法重连')
    return
  }

  try {
    await AppAutomationService.connectDevice({
      ip_address: record.ip_address,
      port: record.port || 5555,
    })
    Message.success('设备重连成功')
    await loadDevices()
  } catch (error: any) {
    Message.error(error.message || '设备重连失败')
  }
}

const previewScreenshot = async (id: number) => {
  screenshotLoadingId.value = id
  try {
    currentScreenshot.value = await AppAutomationService.captureDeviceScreenshot(id)
    screenshotVisible.value = true
  } catch (error: any) {
    Message.error(error.message || '设备截图失败')
  } finally {
    screenshotLoadingId.value = null
  }
}

const remove = (id: number) => {
  Modal.confirm({
    title: '删除设备',
    content: '确认删除这条设备记录吗？',
    onOk: async () => {
      await AppAutomationService.deleteDevice(id)
      Message.success('设备已删除')
      await loadDevices()
    },
  })
}

const stopAutoRefresh = () => {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

const startAutoRefresh = () => {
  stopAutoRefresh()
  refreshTimer = setInterval(() => {
    void loadDevices({ silent: true })
  }, 30000)
}

const toggleAutoRefresh = (value: string | number | boolean) => {
  const enabled = Boolean(value)
  autoRefreshEnabled.value = enabled
  if (enabled) {
    startAutoRefresh()
    void loadDevices({ silent: true })
    return
  }
  stopAutoRefresh()
}

onMounted(() => {
  void loadDevices()
  if (autoRefreshEnabled.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
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

.header-tip {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card,
.filter-card,
.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label,
.detail-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.stat-card strong,
.detail-card strong,
.detail-panel strong {
  color: var(--theme-text);
  font-size: 24px;
  line-height: 1.2;
}

.filter-grid {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) minmax(180px, 1fr) auto;
  gap: 12px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
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

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.detail-card,
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
}

.detail-panel-wide {
  grid-column: 1 / -1;
}

.screenshot-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.screenshot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.screenshot-frame {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
  overflow: auto;
}

.screenshot-image {
  max-width: 100%;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgba(18, 32, 61, 0.18);
}

@media (max-width: 1080px) {
  .stats-grid,
  .detail-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

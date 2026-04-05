<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <h3>设备管理</h3>
        <p>统一管理本地模拟器、远程设备和真机，并支持实时截图预览。</p>
      </div>
      <a-space>
        <a-button @click="showConnectModal = true">添加远程设备</a-button>
        <a-button type="primary" :loading="loading" @click="discover">刷新设备</a-button>
      </a-space>
    </div>

    <a-card class="table-card">
      <a-table :data="devices" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="设备名称">
            <template #cell="{ record }">{{ record.name || record.device_id }}</template>
          </a-table-column>
          <a-table-column title="序列号" data-index="device_id" />
          <a-table-column title="状态">
            <template #cell="{ record }">
              <a-tag :color="record.status === 'available' ? 'green' : record.status === 'locked' ? 'orange' : record.status === 'offline' ? 'gray' : 'arcoblue'">
                {{ record.status }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="Android" data-index="android_version" />
          <a-table-column title="连接类型" data-index="connection_type" />
          <a-table-column title="锁定用户" data-index="locked_by" />
          <a-table-column title="更新时间">
            <template #cell="{ record }">{{ formatDateTime(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="320">
            <template #cell="{ record }">
              <a-space>
                <a-button
                  type="text"
                  :loading="screenshotLoadingId === record.id"
                  @click="previewScreenshot(record.id)"
                >
                  截图
                </a-button>
                <a-button v-if="record.status !== 'locked'" type="text" @click="lock(record.id)">锁定</a-button>
                <a-button v-else type="text" @click="unlock(record.id)">释放</a-button>
                <a-button type="text" @click="disconnect(record.id)">断开</a-button>
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
import { onMounted, reactive, ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAuthStore } from '@/store/authStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppDevice, AppDeviceScreenshot } from '../types'

const authStore = useAuthStore()
const loading = ref(false)
const showConnectModal = ref(false)
const screenshotVisible = ref(false)
const screenshotLoadingId = ref<number | null>(null)
const currentScreenshot = ref<AppDeviceScreenshot | null>(null)
const devices = ref<AppDevice[]>([])
const connectForm = reactive({
  ip_address: '',
  port: 5555,
})

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatTimestamp = (timestamp?: number) => {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const loadDevices = async () => {
  loading.value = true
  try {
    devices.value = await AppAutomationService.getDevices()
  } catch (error: any) {
    Message.error(error.message || '加载设备失败')
  } finally {
    loading.value = false
  }
}

const discover = async () => {
  loading.value = true
  try {
    devices.value = await AppAutomationService.discoverDevices()
    Message.success('设备列表已刷新')
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

onMounted(() => {
  void loadDevices()
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

.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
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
</style>

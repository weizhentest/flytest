import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAuthStore } from '@/store/authStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppDevice, AppDeviceScreenshot } from '../../types'

interface DeviceFilters {
  search: string
  status: string
}

interface ConnectForm {
  ip_address: string
  port: number
}

interface EditForm {
  name: string
  description: string
  location: string
  status: string
}

export function useAppAutomationDevices() {
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

  const filters = reactive<DeviceFilters>({
    search: '',
    status: '',
  })

  const connectForm = reactive<ConnectForm>({
    ip_address: '',
    port: 5555,
  })

  const editForm = reactive<EditForm>({
    name: '',
    description: '',
    location: '',
    status: 'available',
  })

  const stats = computed(() => {
    const total = devices.value.length
    const available = devices.value.filter(item =>
      ['available', 'online'].includes(item.status),
    ).length
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
    record.status === 'offline' &&
    Boolean(record.ip_address) &&
    record.connection_type !== 'emulator'

  const canDisconnect = (record: AppDevice) =>
    record.status !== 'offline' &&
    Boolean(record.ip_address) &&
    record.connection_type !== 'emulator'

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

  return {
    loading,
    editSaving,
    autoRefreshEnabled,
    showConnectModal,
    screenshotVisible,
    screenshotLoadingId,
    detailVisible,
    editVisible,
    currentScreenshot,
    currentDevice,
    devices,
    filters,
    connectForm,
    editForm,
    stats,
    lastUpdatedText,
    formatDateTime,
    formatTimestamp,
    getStatusLabel,
    getStatusColor,
    getConnectionLabel,
    formatEndpoint,
    canReconnect,
    canDisconnect,
    loadData: loadDevices,
    handleSearch,
    resetFilters,
    discover,
    connect,
    openDetail,
    openEdit,
    submitEdit,
    lock,
    unlock,
    disconnect,
    reconnect,
    previewScreenshot,
    remove,
    toggleAutoRefresh,
  }
}

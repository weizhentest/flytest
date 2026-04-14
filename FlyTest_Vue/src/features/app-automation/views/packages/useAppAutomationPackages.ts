import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppPackage } from '../../types'
import type {
  PackageFormModel,
  PackagePaginationState,
  PackageStats,
} from './packageViewModels'

export function useAppAutomationPackages() {
  const projectStore = useProjectStore()
  const route = useRoute()
  const loading = ref(false)
  const submitting = ref(false)
  const visible = ref(false)
  const search = ref('')
  const platformFilter = ref('')
  const packages = ref<AppPackage[]>([])

  const pagination = reactive<PackagePaginationState>({
    current: 1,
    pageSize: 10,
  })

  const form = reactive<PackageFormModel>({
    id: 0,
    project_id: 0,
    name: '',
    package_name: '',
    activity_name: '',
    platform: 'android',
    description: '',
  })

  const filteredPackages = computed(() => {
    const keyword = search.value.trim().toLowerCase()
    return packages.value.filter(item => {
      if (platformFilter.value && item.platform !== platformFilter.value) {
        return false
      }

      if (!keyword) {
        return true
      }

      return [item.name, item.package_name, item.activity_name, item.description]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
  })

  const pagedPackages = computed(() => {
    const start = (pagination.current - 1) * pagination.pageSize
    return filteredPackages.value.slice(start, start + pagination.pageSize)
  })

  const packageStats = computed<PackageStats>(() => ({
    total: filteredPackages.value.length,
    android: filteredPackages.value.filter(item => item.platform === 'android').length,
    ios: filteredPackages.value.filter(item => item.platform === 'ios').length,
    configuredActivity: filteredPackages.value.filter(item =>
      Boolean(item.activity_name?.trim()),
    ).length,
  }))

  const resetForm = () => {
    form.id = 0
    form.project_id = projectStore.currentProjectId || 0
    form.name = ''
    form.package_name = ''
    form.activity_name = ''
    form.platform = 'android'
    form.description = ''
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  }

  const getPlatformLabel = (platform: string) => {
    if (platform === 'android') return 'Android'
    if (platform === 'ios') return 'iOS'
    return platform || '-'
  }

  const getPlatformColor = (platform: string) => {
    if (platform === 'android') return 'green'
    if (platform === 'ios') return 'arcoblue'
    return 'gray'
  }

  const loadPackages = async () => {
    if (!projectStore.currentProjectId) {
      packages.value = []
      return
    }
    loading.value = true
    try {
      packages.value = await AppAutomationService.getPackages(projectStore.currentProjectId)
    } catch (error: any) {
      Message.error(error.message || '加载应用包失败')
    } finally {
      loading.value = false
    }
  }

  const handleSearch = () => {
    pagination.current = 1
  }

  const resetFilters = () => {
    search.value = ''
    platformFilter.value = ''
    pagination.current = 1
  }

  const openCreate = () => {
    resetForm()
    visible.value = true
  }

  const openEdit = (record: AppPackage) => {
    form.id = record.id
    form.project_id = record.project_id
    form.name = record.name
    form.package_name = record.package_name
    form.activity_name = record.activity_name
    form.platform = record.platform || 'android'
    form.description = record.description
    visible.value = true
  }

  const submit = async () => {
    if (!form.name.trim() || !form.package_name.trim()) {
      Message.warning('请先填写应用名称和包名')
      return
    }

    submitting.value = true
    try {
      const payload = {
        project_id: projectStore.currentProjectId || form.project_id,
        name: form.name.trim(),
        package_name: form.package_name.trim(),
        activity_name: form.activity_name.trim(),
        platform: form.platform || 'android',
        description: form.description.trim(),
      }
      if (form.id) {
        await AppAutomationService.updatePackage(form.id, payload)
        Message.success('应用包已更新')
      } else {
        await AppAutomationService.createPackage(payload)
        Message.success('应用包已创建')
      }
      visible.value = false
      await loadPackages()
    } catch (error: any) {
      Message.error(error.message || '保存应用包失败')
    } finally {
      submitting.value = false
    }
  }

  const remove = (record: AppPackage) => {
    Modal.confirm({
      title: '删除应用包',
      content: `确认删除应用包“${record.name}”吗？`,
      onOk: async () => {
        try {
          await AppAutomationService.deletePackage(record.id)
          Message.success('应用包已删除')
          await loadPackages()
        } catch (error: any) {
          Message.error(error.message || '删除应用包失败')
        }
      },
    })
  }

  watch([search, platformFilter, () => pagination.pageSize], () => {
    pagination.current = 1
  })

  watch(
    () => route.query.tab,
    tab => {
      if (tab === 'packages') {
        return
      }
      visible.value = false
    },
  )

  watch(
    () => visible.value,
    value => {
      if (!value) {
        resetForm()
      }
    },
  )

  watch(
    () => filteredPackages.value.length,
    total => {
      const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
      if (pagination.current > maxPage) {
        pagination.current = maxPage
      }
    },
  )

  watch(
    () => projectStore.currentProjectId,
    () => {
      resetForm()
      resetFilters()
      void loadPackages()
    },
    { immediate: true },
  )

  return {
    projectStore,
    loading,
    submitting,
    visible,
    search,
    platformFilter,
    pagination,
    form,
    filteredPackages,
    pagedPackages,
    packageStats,
    formatDateTime,
    getPlatformLabel,
    getPlatformColor,
    loadPackages,
    handleSearch,
    resetFilters,
    openCreate,
    openEdit,
    submit,
    remove,
  }
}

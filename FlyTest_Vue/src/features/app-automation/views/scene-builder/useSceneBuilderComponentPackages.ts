import { Message, Modal } from '@arco-design/web-vue'
import type { FileItem } from '@arco-design/web-vue/es/upload/interfaces'
import { reactive, ref } from 'vue'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppComponentPackage } from '../../types'
import type { SceneBuilderComponentPackageExportFormModel } from './sceneBuilderDialogModels'

interface UseSceneBuilderComponentPackagesOptions {
  reloadData: () => Promise<void>
}

export const useSceneBuilderComponentPackages = ({
  reloadData,
}: UseSceneBuilderComponentPackagesOptions) => {
  const componentPackageLoading = ref(false)
  const componentPackageUploading = ref(false)
  const componentPackageExporting = ref(false)
  const componentPackageVisible = ref(false)
  const componentPackageExportVisible = ref(false)
  const componentPackageRecords = ref<AppComponentPackage[]>([])
  const componentPackageFileList = ref<FileItem[]>([])
  const componentPackageFile = ref<File | null>(null)
  const componentPackageOverwrite = ref(true)
  const componentPackageIncludeDisabled = ref(false)

  const componentPackageExportForm = reactive<SceneBuilderComponentPackageExportFormModel>({
    name: 'app-component-pack',
    version: '',
    author: '',
    description: 'FlyTest APP 自动化组件包',
  })

  const loadComponentPackageRecords = async () => {
    componentPackageLoading.value = true
    try {
      componentPackageRecords.value = await AppAutomationService.getComponentPackages()
    } catch (error: any) {
      Message.error(error.message || '加载组件包记录失败')
      componentPackageRecords.value = []
    } finally {
      componentPackageLoading.value = false
    }
  }

  const handleComponentPackageFileChange = (fileListParam: FileItem[], fileItem: FileItem) => {
    componentPackageFileList.value = fileListParam.slice(-1)
    if (fileItem?.file) {
      componentPackageFile.value = fileItem.file as File
      return
    }

    if (!componentPackageFileList.value.length) {
      componentPackageFile.value = null
    }
  }

  const openComponentPackageDialog = async () => {
    componentPackageVisible.value = true
    await loadComponentPackageRecords()
  }

  const openComponentPackageExportDialog = () => {
    componentPackageExportVisible.value = true
  }

  const submitComponentPackageImport = async () => {
    if (!componentPackageFile.value) {
      Message.warning('请选择组件包文件')
      return
    }

    componentPackageUploading.value = true
    try {
      const result = await AppAutomationService.importComponentPackage(
        componentPackageFile.value,
        componentPackageOverwrite.value,
      )
      componentPackageFile.value = null
      componentPackageFileList.value = []
      await Promise.all([reloadData(), loadComponentPackageRecords()])

      const counts = result.counts
      Message.success(
        `组件包已导入：基础组件新增 ${counts.base_created} 个，更新 ${counts.base_updated} 个；自定义组件新增 ${counts.custom_created} 个，更新 ${counts.custom_updated} 个。`,
      )
    } catch (error: any) {
      Message.error(error.message || '导入组件包失败')
    } finally {
      componentPackageUploading.value = false
    }
  }

  const deleteComponentPackageRecord = (item: AppComponentPackage) => {
    Modal.confirm({
      title: '删除组件包记录',
      content: `确认删除组件包记录“${item.name}”吗？此操作不会删除已经安装的组件，仅删除导入记录。`,
      onOk: async () => {
        await AppAutomationService.deleteComponentPackage(item.id)
        Message.success('组件包记录已删除')
        await loadComponentPackageRecords()
      },
    })
  }

  const downloadTextFile = (content: string, filename: string, contentType: string) => {
    const blob = new Blob([content], { type: contentType || 'application/octet-stream' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const downloadComponentPackage = async (format: 'json' | 'yaml') => {
    componentPackageExporting.value = true
    try {
      const payload = await AppAutomationService.exportComponentPackage({
        export_format: format,
        include_disabled: componentPackageIncludeDisabled.value,
        name: componentPackageExportForm.name.trim() || 'app-component-pack',
        version: componentPackageExportForm.version.trim(),
        author: componentPackageExportForm.author.trim(),
        description: componentPackageExportForm.description.trim(),
      })
      downloadTextFile(payload.content, payload.filename, payload.content_type)
      Message.success(
        `组件包已导出：基础组件 ${payload.component_count} 个，自定义组件 ${payload.custom_component_count} 个。`,
      )
      componentPackageExportVisible.value = false
    } catch (error: any) {
      Message.error(error.message || '导出组件包失败')
    } finally {
      componentPackageExporting.value = false
    }
  }

  return {
    componentPackageLoading,
    componentPackageUploading,
    componentPackageExporting,
    componentPackageVisible,
    componentPackageExportVisible,
    componentPackageRecords,
    componentPackageFileList,
    componentPackageFile,
    componentPackageOverwrite,
    componentPackageIncludeDisabled,
    componentPackageExportForm,
    loadComponentPackageRecords,
    handleComponentPackageFileChange,
    openComponentPackageDialog,
    openComponentPackageExportDialog,
    submitComponentPackageImport,
    deleteComponentPackageRecord,
    downloadComponentPackage,
  }
}

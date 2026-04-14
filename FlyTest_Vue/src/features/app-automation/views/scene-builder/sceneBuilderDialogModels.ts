import type { FileItem } from '@arco-design/web-vue'

import type { AppComponentPackage } from '../../types'
import type { AiApplyMode } from './useSceneBuilderAiPlanning'

export interface SceneBuilderComponentPackageExportFormModel {
  name?: string
  version?: string
  author?: string
  description?: string
}

export interface SceneBuilderExecuteDeviceOption {
  id: number
  name?: string | null
  device_id?: string | null
}

export interface SceneBuilderExecuteFormModel {
  device_id?: number
}

export interface SceneBuilderCustomComponentFormModel {
  name?: string
  type?: string
  description?: string
  stepsText?: string
}

export interface SceneBuilderAiPlanFormModel {
  prompt: string
  applyMode: AiApplyMode
}

export interface SceneBuilderAiStepFormModel {
  prompt: string
}

export type SceneBuilderCustomComponentDialogMode = 'create' | 'edit'

export interface SceneBuilderDialogsHostProps {
  componentPackageLoading: boolean
  componentPackageUploading: boolean
  componentPackageFileList: FileItem[]
  componentPackageRecords: AppComponentPackage[]
  componentPackageExporting: boolean
  componentPackageExportForm: SceneBuilderComponentPackageExportFormModel
  aiDialogEngineName: string
  aiDialogModeText: string
  aiCheckedAtDisplay: string
  aiGenerating: boolean
  aiStepSuggesting: boolean
  executionCaseName: string
  availableDevices: SceneBuilderExecuteDeviceOption[]
  executeForm: SceneBuilderExecuteFormModel
  saving: boolean
  executing: boolean
  customComponentMode: SceneBuilderCustomComponentDialogMode
  customComponentForm: SceneBuilderCustomComponentFormModel
  customComponentSaving: boolean
}

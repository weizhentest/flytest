import type { FileItem } from '@arco-design/web-vue'

import type { AppComponent, AppComponentPackage, AppCustomComponent, AppSceneStep } from '../../types'
import type {
  SceneBuilderAddSubStepPayload,
  SceneBuilderIndexedSubStepPayload,
  SceneBuilderPaletteTab,
  SceneBuilderUpdateStepGroupItemsPayload,
  SceneBuilderUpdateSubStepSelectionPayload,
} from './sceneBuilderViewModels'

export interface SceneBuilderTopSectionEmits {
  'open-ai-plan': []
  'reload-data': []
  'open-testcase-workspace': []
  'open-execution-workspace': []
  'create-draft': []
  'open-create-custom-component': []
  'save-draft': []
  'open-execute-dialog': []
  'refresh-ai-status': []
  'open-llm-config': []
  'update:selected-case-id': [value?: number]
  'case-change': [value?: number]
  'add-variable': []
  'remove-variable': [index: number]
}

export interface SceneBuilderWorkspaceLayoutEmits {
  'update:componentSearch': [value: string]
  'update:paletteTab': [value: SceneBuilderPaletteTab]
  'open-import-dialog': []
  'open-export-dialog': []
  'append-base': [component: AppComponent]
  'append-custom': [component: AppCustomComponent]
  'edit-custom': [component: AppCustomComponent]
  'delete-custom': [component: AppCustomComponent]
  'update:steps': [items: AppSceneStep[]]
  'select-step': [index: number]
  'toggle-expand': [index: number]
  'duplicate-step': [index: number]
  'remove-step': [index: number]
  'clear-steps': []
  'select-sub-step': [payload: SceneBuilderIndexedSubStepPayload]
  'update-sub-step-selection': [payload: SceneBuilderUpdateSubStepSelectionPayload]
  'add-sub-step': [payload: SceneBuilderAddSubStepPayload]
  'duplicate-sub-step': [payload: SceneBuilderIndexedSubStepPayload]
  'remove-sub-step': [payload: SceneBuilderIndexedSubStepPayload]
  'update-step-group-items': [payload: SceneBuilderUpdateStepGroupItemsPayload]
  'update:stepConfigText': [value: string]
  'open-ai-step-dialog': []
  'reset-selected-step-config': []
  'apply-step-config': []
}

export interface SceneBuilderDialogsHostEmits {
  'file-change': [fileListParam: FileItem[], fileItem: FileItem]
  'delete-record': [record: AppComponentPackage]
  'submit-component-package-import': []
  'submit-export-json': []
  'submit-export-yaml': []
  'submit-ai-plan': []
  'submit-ai-step': []
  'reload-devices': []
  'submit-execute': []
  'submit-custom-component': []
}

export interface SceneBuilderConfigPanelEmits {
  'open-ai-step-dialog': []
  'reset-selected-step-config': []
  'apply-step-config': []
}

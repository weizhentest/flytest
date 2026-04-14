import type { AppElement } from '../../types'

export interface ElementsHeaderBarEmits {
  search: []
  'type-change': []
  refresh: []
  'open-capture': []
  'open-create': []
}

export interface ElementsEditorDialogEmits {
  submit: []
  cancel: []
  'file-change': [file: File | null]
  'create-category': []
  'delete-current-category': []
}

export interface ElementsTableCardEmits {
  'open-detail': [record: AppElement]
  'duplicate-element': [record: AppElement]
  'open-edit': [record: AppElement]
  remove: [id: number]
  'toggle-active': [record: AppElement, value: boolean]
  'remove-selected': []
  'clear-selection': []
}

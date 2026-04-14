import type { AppElement, AppImageCategory } from '../../types'

export interface ElementsEditorFormModel {
  id: number
  name: string
  element_type: string
  selector_type: string
  selector_value: string
  description: string
  tagsText: string
  configText: string
  image_path: string
  imageCategory: string
  fileHash: string
  is_active: boolean
  threshold: number
  rgb: boolean
  posX: number
  posY: number
  regionX1: number
  regionY1: number
  regionX2: number
  regionY2: number
}

export interface ElementsPaginationState {
  current: number
  pageSize: number
}

export interface ElementsHeaderBarProps {
  loading: boolean
}

export interface ElementsDetailDialogProps {
  detailRecord: AppElement | null
  getPreviewUrl: (imagePath?: string) => string
  getTypeLabel: (value: string) => string
  renderPos: (record: AppElement) => string
  renderRegion: (record: AppElement) => string
  formatDateTime: (value?: string) => string
  formatConfig: (value: Record<string, unknown>) => string
}

export interface ElementsEditorDialogProps {
  form: ElementsEditorFormModel
  imageCategories: AppImageCategory[]
  imagePreviewUrl: string
  uploading: boolean
  categorySaving: boolean
  categoryDeleting: boolean
}

export interface ElementsTableCardProps {
  loading: boolean
  batchDeleting: boolean
  elements: AppElement[]
  total: number
  formatDateTime: (value?: string) => string
  getTypeLabel: (value: string) => string
  getTypeColor: (value: string) => string
  getPreviewUrl: (imagePath?: string) => string
  renderPos: (record: AppElement) => string
  renderRegion: (record: AppElement) => string
  getImageCategory: (record: AppElement) => string
}

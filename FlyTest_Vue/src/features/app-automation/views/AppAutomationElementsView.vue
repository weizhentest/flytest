<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再管理 APP 自动化元素" />
    </div>
    <template v-else>
      <ElementsHeaderBar
        v-model:search="search"
        v-model:type-filter="typeFilter"
        :loading="loading"
        @search="handleSearch"
        @type-change="handleTypeChange"
        @refresh="loadElements"
        @open-capture="captureVisible = true"
        @open-create="openCreate"
      />

      <ElementsTableCard
        v-model:selected-element-ids="selectedElementIds"
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :loading="loading"
        :batch-deleting="batchDeleting"
        :elements="pagedElements"
        :total="elements.length"
        :format-date-time="formatDateTime"
        :get-type-label="getTypeLabel"
        :get-type-color="getTypeColor"
        :get-preview-url="getPreviewUrl"
        :render-pos="renderPos"
        :render-region="renderRegion"
        :get-image-category="getImageCategory"
        @open-detail="openDetail"
        @duplicate-element="duplicateElement"
        @open-edit="openEdit"
        @remove="remove"
        @toggle-active="toggleActive"
        @remove-selected="removeSelected"
        @clear-selection="clearSelection"
      />

      <ElementsEditorDialog
        v-model:visible="visible"
        v-model:new-category-name="newCategoryName"
        :form="form"
        :image-categories="imageCategories"
        :image-preview-url="imagePreviewUrl"
        :uploading="uploading"
        :category-saving="categorySaving"
        :category-deleting="categoryDeleting"
        @submit="submit"
        @cancel="closeEditor"
        @file-change="handleFileChange"
        @create-category="createCategory"
        @delete-current-category="deleteCurrentCategory"
      />

      <ElementsDetailDialog
        v-model:visible="detailVisible"
        :detail-record="detailRecord"
        :get-preview-url="getPreviewUrl"
        :get-type-label="getTypeLabel"
        :render-pos="renderPos"
        :render-region="renderRegion"
        :format-date-time="formatDateTime"
        :format-config="formatConfig"
      />

      <AppAutomationCaptureElementModal
        v-model:visible="captureVisible"
        :project-id="projectStore.currentProjectId"
        @success="handleCaptureSuccess"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import AppAutomationCaptureElementModal from '../components/AppAutomationCaptureElementModal.vue'
import {
  ElementsDetailDialog,
  ElementsEditorDialog,
  ElementsHeaderBar,
  ElementsTableCard,
  useAppAutomationElements,
} from './elements'

const {
  projectStore,
  loading,
  visible,
  detailVisible,
  captureVisible,
  uploading,
  batchDeleting,
  categorySaving,
  categoryDeleting,
  search,
  typeFilter,
  elements,
  imageCategories,
  newCategoryName,
  detailRecord,
  selectedElementIds,
  pagination,
  form,
  imagePreviewUrl,
  pagedElements,
  formatDateTime,
  formatConfig,
  getTypeLabel,
  getTypeColor,
  getPreviewUrl,
  getImageCategory,
  renderPos,
  renderRegion,
  loadElements,
  handleSearch,
  handleTypeChange,
  openCreate,
  openEdit,
  openDetail,
  handleFileChange,
  createCategory,
  deleteCurrentCategory,
  submit,
  closeEditor,
  duplicateElement,
  toggleActive,
  remove,
  clearSelection,
  removeSelected,
  handleCaptureSuccess,
} = useAppAutomationElements()
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-shell {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 16px;
}
</style>

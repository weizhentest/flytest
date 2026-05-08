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
  gap: 18px;
  min-height: 0;
  padding: 8px 6px 10px;
}

.empty-shell {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.06), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 249, 253, 0.9));
  border: 1px solid var(--theme-card-border);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.page-shell :deep(.arco-card),
.page-shell :deep(.element-card),
.page-shell :deep(.stats-card) {
  border-radius: 20px;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.page-shell :deep(.arco-card-body) {
  padding: 20px;
}

@media (max-width: 900px) {
  .page-shell {
    gap: 16px;
    padding: 4px;
  }

  .page-shell :deep(.arco-card-body) {
    padding: 18px;
  }
}
</style>

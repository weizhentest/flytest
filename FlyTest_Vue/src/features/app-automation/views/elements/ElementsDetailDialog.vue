<template>
  <a-modal
    v-model:visible="visibleModel"
    title="元素详情"
    width="760px"
    hide-cancel
    @ok="visibleModel = false"
  >
    <div v-if="detailRecord" class="detail-layout">
      <div class="detail-preview">
        <img
          v-if="detailRecord.element_type === 'image' && detailRecord.image_path"
          :src="getPreviewUrl(detailRecord.image_path)"
          alt="element preview"
          class="preview-image large"
        />
        <div v-else class="detail-placeholder">
          <strong>{{ getTypeLabel(detailRecord.element_type) }}</strong>
          <span>{{ detailRecord.element_type === 'pos' ? renderPos(detailRecord) : renderRegion(detailRecord) }}</span>
        </div>
      </div>
      <div class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">元素名称</span>
          <strong>{{ detailRecord.name }}</strong>
        </div>
        <div class="detail-item">
          <span class="detail-label">元素类型</span>
          <strong>{{ getTypeLabel(detailRecord.element_type) }}</strong>
        </div>
        <div class="detail-item">
          <span class="detail-label">定位方式</span>
          <strong>{{ detailRecord.selector_type || '-' }}</strong>
        </div>
        <div class="detail-item">
          <span class="detail-label">状态</span>
          <strong>{{ detailRecord.is_active ? '启用' : '停用' }}</strong>
        </div>
        <div class="detail-item detail-item-wide">
          <span class="detail-label">定位值</span>
          <strong class="mono">{{ detailRecord.selector_value || '-' }}</strong>
        </div>
        <div class="detail-item detail-item-wide">
          <span class="detail-label">标签</span>
          <div class="tag-row">
            <a-tag v-for="tag in detailRecord.tags" :key="tag" color="arcoblue">{{ tag }}</a-tag>
            <span v-if="!detailRecord.tags.length" class="muted-text">无</span>
          </div>
        </div>
        <div class="detail-item detail-item-wide">
          <span class="detail-label">描述</span>
          <strong>{{ detailRecord.description || '-' }}</strong>
        </div>
        <div class="detail-item">
          <span class="detail-label">创建时间</span>
          <strong>{{ formatDateTime(detailRecord.created_at || detailRecord.updated_at) }}</strong>
        </div>
        <div class="detail-item">
          <span class="detail-label">更新时间</span>
          <strong>{{ formatDateTime(detailRecord.updated_at) }}</strong>
        </div>
        <div class="detail-item detail-item-wide">
          <span class="detail-label">配置 JSON</span>
          <pre class="detail-json">{{ formatConfig(detailRecord.config) }}</pre>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { ElementsDetailDialogProps } from './elementViewModels'

defineProps<ElementsDetailDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 20px;
}

.detail-preview {
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.preview-image {
  width: 160px;
  height: 90px;
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.04);
}

.preview-image.large {
  width: min(100%, 360px);
  height: auto;
  max-height: 260px;
  padding: 8px;
}

.detail-placeholder {
  width: 100%;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px dashed var(--theme-card-border);
  border-radius: 14px;
  color: var(--theme-text-secondary);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.detail-item-wide {
  grid-column: 1 / -1;
}

.detail-label,
.muted-text {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.mono,
.detail-json {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.detail-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--theme-text);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 960px) {
  .detail-layout,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>

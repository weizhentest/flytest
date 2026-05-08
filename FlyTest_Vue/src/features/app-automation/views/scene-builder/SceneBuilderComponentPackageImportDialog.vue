<template>
  <a-modal v-model:visible="visibleModel" width="760px">
    <template #title>导入组件包</template>

    <div class="dialog-shell">
      <a-alert class="custom-dialog-alert">
        支持导入 `.json`、`.yaml`、`.yml` 组件包。导入时可以选择覆盖已有组件，也会同步安装组件包里的自定义组件。
      </a-alert>

      <a-form layout="vertical" class="dialog-form">
        <div class="field-card">
          <a-form-item label="覆盖已有组件">
            <a-switch v-model="overwriteModel" />
          </a-form-item>
        </div>

        <div class="field-card">
          <a-form-item label="选择文件">
            <a-upload
              :file-list="fileList"
              :auto-upload="false"
              :limit="1"
              accept=".json,.yaml,.yml"
              @change="(fileListParam, fileItem) => emit('file-change', fileListParam, fileItem)"
            />
          </a-form-item>
        </div>

        <div class="field-card">
          <a-form-item label="已导入组件包">
            <div class="component-package-list">
              <div
                v-for="item in records"
                :key="item.id"
                class="component-package-item"
              >
                <div class="component-package-copy">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.description || '暂无描述' }}</span>
                </div>
                <div class="component-package-meta">
                  <span>{{ item.version || '-' }}</span>
                  <a-button type="text" size="mini" status="danger" @click="emit('delete-record', item)">
                    删除
                  </a-button>
                </div>
              </div>
              <a-empty v-if="!loading && !records.length" description="暂无组件包记录" />
              <a-spin v-if="loading" style="width: 100%" />
            </div>
          </a-form-item>
        </div>
      </a-form>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="visibleModel = false">关闭</a-button>
        <a-button type="primary" :loading="uploading" @click="emit('submit')">导入组件包</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import type { FileItem } from '@arco-design/web-vue'
import type { AppComponentPackage } from '../../types'

interface Props {
  loading: boolean
  uploading: boolean
  fileList: FileItem[]
  records: AppComponentPackage[]
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const overwriteModel = defineModel<boolean>('overwrite', { required: true })

const emit = defineEmits<{
  'file-change': [fileListParam: FileItem[], fileItem: FileItem]
  'delete-record': [record: AppComponentPackage]
  submit: []
}>()
</script>

<style scoped>
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.custom-dialog-alert {
  margin-bottom: 0;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.field-card :deep(.arco-form-item) {
  margin-bottom: 0;
}

.component-package-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.component-package-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(var(--theme-accent-rgb), 0.04)),
    rgba(var(--theme-surface-rgb), 0.72);
}

.component-package-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.component-package-copy strong {
  color: var(--theme-text);
}

.component-package-copy span,
.component-package-meta {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.component-package-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

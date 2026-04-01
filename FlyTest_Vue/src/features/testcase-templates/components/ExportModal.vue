<template>
  <a-modal
    v-model:visible="visible"
    title="导出用例"
    :width="400"
    :mask-closable="false"
    :modal-class="'export-modal'"
    :footer-style="{ display: 'flex', justifyContent: 'flex-end' }"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button
          type="primary"
          :loading="exporting"
          @click="handleExport"
        >
          <template #icon><icon-export /></template>
          {{ exporting ? '导出中...' : '开始导出' }}
        </a-button>
      </a-space>
    </template>

    <a-spin :loading="loading">
      <div class="export-form">
        <!-- 导出范围 -->
        <div class="form-section">
          <div class="section-title">
            <icon-select-all class="section-icon" />
            导出范围
          </div>
          <div class="export-options">
            <div
              class="option-card"
              :class="{ active: form.exportMode === 'all' }"
              @click="form.exportMode = 'all'"
            >
              <div class="option-icon">
                <icon-apps />
              </div>
              <div class="option-content">
                <div class="option-title">导出所有用例</div>
                <div class="option-desc">导出当前项目的全部测试用例</div>
              </div>
              <div class="option-check" v-if="form.exportMode === 'all'">
                <icon-check-circle-fill />
              </div>
            </div>
            <div
              class="option-card"
              :class="{ active: form.exportMode === 'selected', disabled: selectedCount === 0 }"
              @click="selectedCount > 0 && (form.exportMode = 'selected')"
            >
              <div class="option-icon">
                <icon-check-square />
              </div>
              <div class="option-content">
                <div class="option-title">
                  导出选中用例
                  <a-badge :count="selectedCount" :max-count="99" />
                </div>
                <div class="option-desc">
                  {{ selectedCount > 0 ? `已选择 ${selectedCount} 条用例` : '请先在列表中选择用例' }}
                </div>
              </div>
              <div class="option-check" v-if="form.exportMode === 'selected'">
                <icon-check-circle-fill />
              </div>
            </div>
            <div
              class="option-card"
              :class="{ active: form.exportMode === 'module', disabled: !hasModules }"
              @click="hasModules && (form.exportMode = 'module')"
            >
              <div class="option-icon">
                <icon-folder />
              </div>
              <div class="option-content">
                <div class="option-title">按模块导出</div>
                <div class="option-desc">
                  {{ hasModules ? '选择模块导出其下所有用例' : '当前项目暂无模块' }}
                </div>
              </div>
              <div class="option-check" v-if="form.exportMode === 'module'">
                <icon-check-circle-fill />
              </div>
            </div>
          </div>
          <!-- 模块选择 -->
          <div v-if="form.exportMode === 'module'" class="module-select-area">
            <a-tree-select
              v-model="form.moduleIds"
              :data="moduleTree"
              placeholder="请选择要导出的模块"
              multiple
              allow-clear
              :max-tag-count="3"
              tree-checkable
              :tree-check-strictly="false"
              size="large"
            />
          </div>
        </div>

        <!-- 选择模版 -->
        <div class="form-section">
          <div class="section-title">
            <icon-file-image class="section-icon" />
            导出模版
            <span class="section-hint">（可选）</span>
          </div>
          <a-select
            v-model="form.templateId"
            placeholder="使用默认格式导出"
            :loading="loadingTemplates"
            allow-clear
            size="large"
          >
            <template #prefix>
              <icon-file />
            </template>
            <a-option
              v-for="template in templates"
              :key="template.id"
              :value="template.id"
            >
              <div class="template-option">
                <span class="template-name">{{ template.name }}</span>
                <span class="template-desc" v-if="template.description">
                  {{ template.description }}
                </span>
              </div>
            </a-option>
          </a-select>
          <div class="section-extra">
            <a-link @click="goToTemplateManagement" class="manage-link">
              <icon-settings /> 管理模版
            </a-link>
          </div>
        </div>

        <!-- 模版预览 -->
        <transition name="slide">
          <div v-if="selectedTemplate" class="template-preview">
            <div class="preview-header">
              <icon-info-circle /> 模版配置
            </div>
            <div class="preview-grid">
              <div class="preview-item" v-if="selectedTemplate.sheet_name">
                <span class="preview-label">工作表</span>
                <span class="preview-value">{{ selectedTemplate.sheet_name }}</span>
              </div>
              <div class="preview-item">
                <span class="preview-label">表头行</span>
                <span class="preview-value">第 {{ selectedTemplate.header_row }} 行</span>
              </div>
              <div class="preview-item">
                <span class="preview-label">数据起始</span>
                <span class="preview-value">第 {{ selectedTemplate.data_start_row }} 行</span>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import {
  IconExport,
  IconSelectAll,
  IconApps,
  IconCheckSquare,
  IconCheckCircleFill,
  IconFileImage,
  IconFile,
  IconSettings,
  IconInfoCircle,
  IconFolder,
} from '@arco-design/web-vue/es/icon';
import type { TreeNodeData } from '@arco-design/web-vue';
import {
  getTemplateList,
  getTemplateDetail,
  exportTestCasesWithTemplate,
  type ImportExportTemplateListItem,
  type ImportExportTemplate,
} from '../services/templateService';

const props = defineProps<{
  projectId: number;
  selectedIds: number[];
  moduleTree?: TreeNodeData[];
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const router = useRouter();

const visible = ref(false);
const loading = ref(false);
const loadingTemplates = ref(false);
const exporting = ref(false);

const templates = ref<ImportExportTemplateListItem[]>([]);
const selectedTemplate = ref<ImportExportTemplate | null>(null);

const form = ref({
  exportMode: 'all' as 'all' | 'selected' | 'module',
  templateId: null as number | null,
  moduleIds: [] as number[],
});

const hasModules = computed(() => (props.moduleTree?.length ?? 0) > 0);

const selectedCount = computed(() => props.selectedIds.length);

watch(() => form.value.templateId, async (newId) => {
  if (newId) {
    loading.value = true;
    try {
      const result = await getTemplateDetail(newId);
      if (result.success && result.data) {
        selectedTemplate.value = result.data;
      }
    } finally {
      loading.value = false;
    }
  } else {
    selectedTemplate.value = null;
  }
});

const loadTemplates = async () => {
  loadingTemplates.value = true;
  try {
    const allTemplates: ImportExportTemplateListItem[] = [];
    const exportResult = await getTemplateList({ template_type: 'export', is_active: true });
    if (exportResult.success && exportResult.data) {
      allTemplates.push(...exportResult.data);
    }
    const bothResult = await getTemplateList({ template_type: 'both', is_active: true });
    if (bothResult.success && bothResult.data) {
      allTemplates.push(...bothResult.data);
    }
    templates.value = allTemplates;
  } finally {
    loadingTemplates.value = false;
  }
};

const handleExport = async () => {
  if (form.value.exportMode === 'module' && form.value.moduleIds.length === 0) {
    Message.warning('请选择至少一个模块');
    return;
  }
  exporting.value = true;
  try {
    const ids = form.value.exportMode === 'selected' ? props.selectedIds : undefined;
    const moduleIds = form.value.exportMode === 'module' ? form.value.moduleIds : undefined;
    const result = await exportTestCasesWithTemplate(
      props.projectId,
      form.value.templateId,
      ids,
      moduleIds
    );

    if (result.success) {
      Message.success(result.message || '导出成功');
      handleClose();
    } else {
      Message.error(result.error || '导出失败');
    }
  } finally {
    exporting.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  form.value = {
    exportMode: 'all',
    templateId: null,
    moduleIds: [],
  };
  selectedTemplate.value = null;
  emit('close');
};

const goToTemplateManagement = () => {
  handleClose();
  router.push({ name: 'TemplateManagement' });
};

const open = () => {
  visible.value = true;
  form.value.exportMode = props.selectedIds.length > 0 ? 'selected' : 'all';
  loadTemplates();
};

defineExpose({ open });
</script>

<style scoped>
.export-form {
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

/* 确保 spin 容器撑满 */
:deep(.arco-spin) {
  width: 100%;
}

/* 表单区块 */
.form-section {
  margin-bottom: 24px;
}

.form-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
  margin-bottom: 12px;
}

.section-icon {
  color: var(--color-text-3);
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-4);
}

.section-extra {
  margin-top: 8px;
}

.manage-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

/* 导出选项卡片 */
.export-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 2px solid var(--color-border-2);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--color-bg-1);
  position: relative;
}

.option-card:hover {
  border-color: #00a0e9;
  background: rgba(0, 160, 233, 0.02);
}

.option-card.active {
  border-color: #00a0e9;
  background: rgba(0, 160, 233, 0.06);
}

.option-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.option-card.disabled:hover {
  border-color: var(--color-border-2);
  background: var(--color-bg-1);
}

.option-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-fill-2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--color-text-3);
  flex-shrink: 0;
}

.option-card.active .option-icon {
  background: rgba(0, 160, 233, 0.15);
  color: #00a0e9;
}

.option-content {
  flex: 1;
  min-width: 0;
  padding-right: 28px;
}

.option-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-1);
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-desc {
  font-size: 12px;
  color: var(--color-text-3);
  margin-top: 2px;
}

.option-check {
  font-size: 18px;
  color: #00a0e9;
  flex-shrink: 0;
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
}

/* 模版选项 */
.template-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-name {
  font-weight: 500;
}

.template-desc {
  font-size: 12px;
  color: var(--color-text-3);
}

/* 模块选择区域 */
.module-select-area {
  margin-top: 12px;
}

/* 模版预览 */
.template-preview {
  margin-top: 16px;
  background: var(--color-fill-1);
  border-radius: 8px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--color-fill-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-2);
}

.preview-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1px;
  background: var(--color-border-1);
}

.preview-item {
  flex: 1 1 calc(33.333% - 1px);
  min-width: 100px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  background: var(--color-bg-1);
  text-align: center;
}

.preview-label {
  font-size: 11px;
  color: var(--color-text-4);
}

.preview-value {
  font-size: 13px;
  color: var(--color-text-1);
  font-weight: 500;
}

/* 过渡动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 选择器样式 */
:deep(.arco-select-view-single) {
  height: 40px;
}

/* Badge 样式 */
:deep(.arco-badge-number) {
  font-size: 10px;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
}

/* 响应式 */
@media (max-width: 576px) {
  .option-card {
    padding: 12px 14px;
    gap: 12px;
  }

  .option-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }

  .option-title {
    font-size: 13px;
  }

  .preview-item {
    flex: 1 1 100%;
  }
}
</style>

<template>
  <a-modal
    v-model:visible="visible"
    :title="isEdit ? '编辑模版' : '新建模版'"
    :width="860"
    :mask-closable="false"
    :modal-class="'template-form-modal'"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button v-if="currentStep > 0" @click="prevStep">上一步</a-button>
        <a-button
          v-if="currentStep < steps.length - 1"
          type="primary"
          :disabled="!canNextStep"
          @click="nextStep"
        >
          下一步
        </a-button>
        <a-button
          v-else
          type="primary"
          :loading="saving"
          @click="handleSave"
        >
          {{ saving ? '保存中...' : '保存' }}
        </a-button>
      </a-space>
    </template>

    <a-spin :loading="loading">
      <!-- 步骤条 -->
      <a-steps :current="currentStep" class="steps-bar">
        <a-step v-for="(step, index) in steps" :key="index" :title="step.title" />
      </a-steps>

      <div class="step-content">
        <!-- Step 1: 上传样例文件并解析表头 -->
        <div v-show="currentStep === 0">
          <a-form :model="form" layout="vertical">
            <a-form-item label="上传样例 Excel 文件（可选）">
              <a-upload
                :file-list="sampleFileList"
                :auto-upload="false"
                accept=".xlsx,.xls"
                :limit="1"
                :show-retry-button="false"
                :show-cancel-button="false"
                :show-preview-button="false"
                @change="handleSampleFileChange"
              >
                <template #upload-button>
                  <a-button type="outline">
                    <template #icon><icon-upload /></template>
                    选择文件
                  </a-button>
                </template>
              </a-upload>
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item label="表头行号">
                  <a-input-number
                    v-model="form.header_row"
                    :min="1"
                    :max="100"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="数据起始行号">
                  <a-input-number
                    v-model="form.data_start_row"
                    :min="1"
                    :max="1000"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="工作表名称">
                  <a-select
                    v-model="form.sheet_name"
                    placeholder="默认第一个"
                    allow-clear
                    :options="sheetOptions"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-button
              v-if="sampleFileList.length > 0"
              type="primary"
              :loading="parsing"
              @click="parseHeaders"
            >
              解析表头
            </a-button>

            <!-- 解析结果预览 -->
            <div v-if="parsedHeaders.length > 0" class="parsed-preview">
              <a-divider>识别到的表头列</a-divider>
              <a-space wrap>
                <a-tag v-for="header in parsedHeaders" :key="header" color="arcoblue">
                  {{ header }}
                </a-tag>
              </a-space>
            </div>
          </a-form>
        </div>

        <!-- Step 2: 字段映射 -->
        <div v-show="currentStep === 1">
          <a-alert type="info" class="mapping-tip">
            将 Excel 列名映射到用例字段。带 * 的字段为必填。
          </a-alert>

          <a-form :model="form.field_mappings" layout="vertical">
            <a-row :gutter="16">
              <a-col :span="12" v-for="field in fieldOptions" :key="field.value">
                <a-form-item>
                  <template #label>
                    {{ field.label }}
                    <span v-if="field.required" class="required-mark">*</span>
                  </template>
                  <a-select
                    v-model="form.field_mappings[field.value]"
                    placeholder="请选择对应的 Excel 列"
                    allow-clear
                    allow-search
                  >
                    <a-option v-for="header in parsedHeaders" :key="header" :value="header">
                      {{ header }}
                    </a-option>
                    <a-option v-if="parsedHeaders.length === 0" disabled>
                      请先在上一步解析表头或手动输入列名
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>

            <!-- 手动输入列名 -->
            <a-collapse v-if="parsedHeaders.length === 0">
              <a-collapse-item header="手动输入 Excel 列名">
                <a-input
                  v-model="manualHeaders"
                  placeholder="输入列名，用逗号分隔，如: 用例名称,模块,前置条件,步骤,预期结果"
                  @blur="parseManualHeaders"
                />
              </a-collapse-item>
            </a-collapse>
          </a-form>
        </div>

        <!-- Step 3: 值转换配置 -->
        <div v-show="currentStep === 2">
          <a-alert type="info" class="mapping-tip">
            配置字段值的转换规则。例如将 Excel 中的 "高" 转换为系统中的 "P0"。
          </a-alert>

          <!-- 等级转换 -->
          <a-card title="用例等级转换" size="small" class="transform-card">
            <a-table
              :columns="transformColumns"
              :data="levelTransformData"
              :pagination="false"
              size="small"
            >
              <template #input_value="{ record }">
                <a-input v-model="record.input" placeholder="Excel中的值" size="small" />
              </template>
              <template #output_value="{ record }">
                <a-select v-model="record.output" placeholder="转换为" size="small" style="width: 120px">
                  <a-option value="P0">P0 - 最高</a-option>
                  <a-option value="P1">P1 - 高</a-option>
                  <a-option value="P2">P2 - 中</a-option>
                  <a-option value="P3">P3 - 低</a-option>
                </a-select>
              </template>
              <template #actions="{ rowIndex }">
                <a-button
                  size="mini"
                  status="danger"
                  @click="removeLevelTransform(rowIndex)"
                >
                  删除
                </a-button>
              </template>
            </a-table>
            <a-button size="small" type="text" @click="addLevelTransform" class="add-btn">
              <template #icon><icon-plus /></template>
              添加规则
            </a-button>
          </a-card>
        </div>

        <!-- Step 4: 步骤解析配置 -->
        <div v-show="currentStep === 3">
          <a-form :model="form" layout="vertical">
            <a-form-item label="步骤解析模式">
              <a-radio-group v-model="form.step_parsing_mode">
                <a-radio value="single_cell">
                  <div>
                    <div>单元格合并模式</div>
                    <div class="radio-desc">所有步骤在一个单元格中，如 [1]步骤1\n[2]步骤2</div>
                  </div>
                </a-radio>
                <a-radio value="multi_row">
                  <div>
                    <div>多行模式</div>
                    <div class="radio-desc">每个步骤占一行，用例信息在第一行</div>
                  </div>
                </a-radio>
              </a-radio-group>
            </a-form-item>

            <a-form-item label="模块路径分隔符">
              <a-input
                v-model="form.module_path_delimiter"
                placeholder="如 / 或 >"
                style="width: 120px"
              />
              <template #extra>
                用于解析模块层级路径，如 "模块A/子模块B"
              </template>
            </a-form-item>
          </a-form>
        </div>

        <!-- Step 5: 基本信息 -->
        <div v-show="currentStep === 4">
          <a-form :model="form" layout="vertical">
            <a-form-item label="模版名称" required>
              <a-input v-model="form.name" placeholder="请输入模版名称" :max-length="255" />
            </a-form-item>

            <a-form-item label="模版类型">
              <a-radio-group v-model="form.template_type">
                <a-radio value="import">导入</a-radio>
                <a-radio value="export">导出</a-radio>
                <a-radio value="both">导入/导出</a-radio>
              </a-radio-group>
            </a-form-item>

            <a-form-item label="描述">
              <a-textarea
                v-model="form.description"
                placeholder="请输入模版描述"
                :max-length="500"
                :auto-size="{ minRows: 2, maxRows: 4 }"
              />
            </a-form-item>

            <a-form-item label="启用状态">
              <a-switch v-model="form.is_active" />
            </a-form-item>
          </a-form>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconUpload, IconPlus } from '@arco-design/web-vue/es/icon';
import type { FileItem } from '@arco-design/web-vue/es/upload/interfaces';
import {
  getTemplateDetail,
  createTemplate,
  updateTemplate,
  parseExcelHeaders,
  getFieldOptions,
  uploadTemplateFile,
  type TemplateFormData,
  type FieldOption,
  type StepParsingMode,
  type TemplateType,
} from '../services/templateService';

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const visible = ref(false);
const loading = ref(false);
const saving = ref(false);
const parsing = ref(false);
const isEdit = ref(false);
const editId = ref<number | null>(null);
const currentStep = ref(0);

const steps = [
  { title: '表头配置' },
  { title: '字段映射' },
  { title: '值转换' },
  { title: '步骤解析' },
  { title: '基本信息' },
];

const form = reactive<TemplateFormData & { field_mappings: Record<string, string> }>({
  name: '',
  template_type: 'import' as TemplateType,
  description: '',
  sheet_name: '',
  header_row: 1,
  data_start_row: 2,
  field_mappings: {},
  value_transformations: {},
  step_parsing_mode: 'single_cell' as StepParsingMode,
  step_config: {},
  module_path_delimiter: '/',
  is_active: true,
});

const sampleFileList = ref<FileItem[]>([]);
const parsedHeaders = ref<string[]>([]);
const sheetOptions = ref<{ value: string; label: string }[]>([]);
const fieldOptions = ref<FieldOption[]>([]);
const manualHeaders = ref('');

// 等级转换数据
const levelTransformData = ref<{ input: string; output: string }[]>([
  { input: '高', output: 'P0' },
  { input: '中', output: 'P1' },
  { input: '低', output: 'P2' },
]);

const transformColumns = [
  { title: 'Excel 中的值', slotName: 'input_value', width: 150 },
  { title: '转换为', slotName: 'output_value', width: 150 },
  { title: '操作', slotName: 'actions', width: 80 },
];

const canNextStep = computed(() => {
  switch (currentStep.value) {
    case 0: // 表头配置
      return form.header_row > 0 && form.data_start_row >= form.header_row;
    case 1: // 字段映射
      return !!form.field_mappings.name && !!form.field_mappings.module;
    case 4: // 基本信息
      return !!form.name;
    default:
      return true;
  }
});

const handleSampleFileChange = (files: FileItem[]) => {
  sampleFileList.value = files;
};

const parseHeaders = async () => {
  if (sampleFileList.value.length === 0) return;

  const file = sampleFileList.value[0].file;
  if (!file) return;

  parsing.value = true;
  try {
    const result = await parseExcelHeaders(file, form.sheet_name || undefined, form.header_row);
    if (result.success && result.data) {
      parsedHeaders.value = result.data.headers.filter((h: string) => h);
      sheetOptions.value = result.data.sheet_names.map((s: string) => ({ value: s, label: s }));
      Message.success(`成功解析 ${parsedHeaders.value.length} 个表头列`);
    } else {
      Message.error(result.error || '解析失败');
    }
  } finally {
    parsing.value = false;
  }
};

const parseManualHeaders = () => {
  if (manualHeaders.value) {
    parsedHeaders.value = manualHeaders.value.split(',').map(h => h.trim()).filter(h => h);
  }
};

const addLevelTransform = () => {
  levelTransformData.value.push({ input: '', output: 'P2' });
};

const removeLevelTransform = (index: number) => {
  levelTransformData.value.splice(index, 1);
};

const nextStep = () => {
  if (currentStep.value < steps.length - 1) {
    currentStep.value++;
  }
};

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

const buildFormData = (): TemplateFormData => {
  // 构建值转换规则
  const valueTransformations: Record<string, Record<string, string>> = {};
  if (levelTransformData.value.some(t => t.input && t.output)) {
    valueTransformations.level = {};
    for (const t of levelTransformData.value) {
      if (t.input && t.output) {
        valueTransformations.level[t.input] = t.output;
      }
    }
  }

  return {
    name: form.name,
    template_type: form.template_type,
    description: form.description || undefined,
    sheet_name: form.sheet_name || undefined,
    template_headers: parsedHeaders.value.length > 0 ? parsedHeaders.value : undefined,
    header_row: form.header_row,
    data_start_row: form.data_start_row,
    field_mappings: form.field_mappings,
    value_transformations: valueTransformations,
    step_parsing_mode: form.step_parsing_mode,
    step_config: form.step_config,
    module_path_delimiter: form.module_path_delimiter,
    is_active: form.is_active,
  };
};

const handleSave = async () => {
  if (!form.name) {
    Message.warning('请输入模版名称');
    return;
  }

  saving.value = true;
  try {
    const sampleFile = sampleFileList.value[0]?.file || null;
    const data = buildFormData();
    const result = isEdit.value && editId.value
      ? await updateTemplate(editId.value, data)
      : await createTemplate(data);

    if (result.success) {
      const templateId = result.data?.id || editId.value;
      if (templateId && sampleFile) {
        const uploadResult = await uploadTemplateFile(templateId, sampleFile);
        if (!uploadResult.success) {
          Message.warning(uploadResult.error || '模版已保存，但模板文件上传失败（导出将无法完全复用原始样式）');
        }
      }
      Message.success(isEdit.value ? '更新成功' : '创建成功');
      emit('success');
      handleClose();
    } else {
      Message.error(result.error || '保存失败');
    }
  } finally {
    saving.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  resetForm();
};

const resetForm = () => {
  currentStep.value = 0;
  form.name = '';
  form.template_type = 'import';
  form.description = '';
  form.sheet_name = '';
  form.header_row = 1;
  form.data_start_row = 2;
  form.field_mappings = {};
  form.value_transformations = {};
  form.step_parsing_mode = 'single_cell';
  form.step_config = {};
  form.module_path_delimiter = '/';
  form.is_active = true;
  sampleFileList.value = [];
  parsedHeaders.value = [];
  sheetOptions.value = [];
  manualHeaders.value = '';
  levelTransformData.value = [
    { input: '高', output: 'P0' },
    { input: '中', output: 'P1' },
    { input: '低', output: 'P2' },
  ];
  isEdit.value = false;
  editId.value = null;
};

const loadFieldOptions = async () => {
  const result = await getFieldOptions();
  if (result.success && result.data) {
    fieldOptions.value = result.data.fields;
  }
};

const open = async (id?: number) => {
  visible.value = true;
  resetForm();
  await loadFieldOptions();

  if (id) {
    isEdit.value = true;
    editId.value = id;
    loading.value = true;
    try {
      const result = await getTemplateDetail(id);
      if (result.success && result.data) {
        const data = result.data;
        form.name = data.name;
        form.template_type = data.template_type;
        form.description = data.description || '';
        form.sheet_name = data.sheet_name || '';
        form.header_row = data.header_row;
        form.data_start_row = data.data_start_row;
        form.field_mappings = Object.fromEntries(
          Object.entries(data.field_mappings || {}).filter(([, v]) => v !== undefined)
        ) as Record<string, string>;
        form.step_parsing_mode = data.step_parsing_mode;
        form.step_config = data.step_config || {};
        form.module_path_delimiter = data.module_path_delimiter;
        form.is_active = data.is_active;

        // 回填模版结构：优先使用后端保存的 template_headers
        parsedHeaders.value = (data.template_headers && data.template_headers.length > 0)
          ? data.template_headers
          : (Object.values(data.field_mappings).filter(v => v) as string[]);

        // 解析等级转换规则
        if (data.value_transformations?.level) {
          levelTransformData.value = Object.entries(data.value_transformations.level).map(
            ([input, output]) => ({ input, output })
          );
        }
      }
    } finally {
      loading.value = false;
    }
  }
};

defineExpose({ open });
</script>

<style scoped>
.steps-bar {
  margin-bottom: 28px;
  padding: 0 8px;
}

.steps-bar :deep(.arco-steps-item-title) {
  font-size: 13px;
}

.step-content {
  min-height: 320px;
  padding: 4px 0;
}

/* 隐藏上传列表中的开始按钮 */
:deep(.arco-upload-progress) {
  display: none !important;
}

.upload-tip {
  margin-top: 8px;
  color: var(--color-text-3);
  font-size: 12px;
}

.parsed-preview {
  margin-top: 20px;
  padding: 16px;
  background: var(--color-fill-1);
  border-radius: 8px;
}

.parsed-preview :deep(.arco-divider) {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--color-text-2);
}

.parsed-preview :deep(.arco-tag) {
  margin: 4px;
  font-size: 12px;
}

.mapping-tip {
  margin-bottom: 20px;
}

.required-mark {
  color: rgb(var(--danger-6));
  margin-left: 2px;
}

.transform-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.transform-card :deep(.arco-card-header) {
  padding: 12px 16px;
  background: var(--color-fill-1);
  border-radius: 8px 8px 0 0;
}

.transform-card :deep(.arco-card-body) {
  padding: 16px;
}

.add-btn {
  margin-top: 12px;
}

.radio-desc {
  color: var(--color-text-3);
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.5;
}

/* 响应式 */
@media (max-width: 768px) {
  .steps-bar {
    margin-bottom: 20px;
  }

  .steps-bar :deep(.arco-steps-item-title) {
    font-size: 12px;
  }

  .step-content {
    min-height: 280px;
  }

  .step-content :deep(.arco-col-8) {
    flex: 0 0 50%;
    max-width: 50%;
  }

  .step-content :deep(.arco-col-12) {
    flex: 0 0 100%;
    max-width: 100%;
  }
}

@media (max-width: 576px) {
  .steps-bar :deep(.arco-steps-item-description) {
    display: none;
  }

  .step-content :deep(.arco-col-8) {
    flex: 0 0 100%;
    max-width: 100%;
  }
}

/* 表单样式优化 */
.step-content :deep(.arco-form-item) {
  margin-bottom: 20px;
}

.step-content :deep(.arco-form-item-label) {
  font-weight: 500;
  color: var(--color-text-1);
}

/* 步骤解析模式卡片样式 */
.step-content :deep(.arco-radio) {
  padding: 12px 16px;
  margin-bottom: 8px;
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  transition: all 0.2s;
}

.step-content :deep(.arco-radio:hover) {
  border-color: rgb(var(--primary-6));
  background: var(--color-fill-1);
}

.step-content :deep(.arco-radio-checked) {
  border-color: rgb(var(--primary-6));
  background: var(--color-primary-light-1);
}
</style>

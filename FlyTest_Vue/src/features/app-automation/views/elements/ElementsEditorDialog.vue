<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑元素' : '新增元素'"
    width="980px"
    @ok="emit('submit')"
    @cancel="emit('cancel')"
  >
    <a-form :model="form" layout="vertical">
      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="name" label="元素名称">
            <a-input v-model="form.name" placeholder="例如：登录按钮、首页搜索框" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="element_type" label="元素类型">
            <a-select v-model="form.element_type">
              <a-option value="image">图片</a-option>
              <a-option value="pos">坐标</a-option>
              <a-option value="region">区域</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <template v-if="form.element_type === 'image'">
        <div class="config-block">
          <div class="config-block-title">图片配置</div>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="图片分类">
                <a-select v-model="form.imageCategory" placeholder="选择分类">
                  <a-option
                    v-for="category in imageCategories"
                    :key="category.name"
                    :value="category.name"
                  >
                    {{ category.name }} ({{ category.count }})
                  </a-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="新增分类">
                <div class="inline-action">
                  <a-input v-model="newCategoryNameModel" placeholder="输入新分类名称" />
                  <a-button :loading="categorySaving" @click="emit('create-category')">创建</a-button>
                  <a-button
                    v-if="form.imageCategory && form.imageCategory !== 'common'"
                    status="danger"
                    :loading="categoryDeleting"
                    @click="emit('delete-current-category')"
                  >
                    删除
                  </a-button>
                </div>
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item label="图片资源">
            <div class="upload-shell">
              <input
                ref="fileInputRef"
                type="file"
                accept="image/*"
                class="hidden-input"
                @change="handleFileInputChange"
              />
              <a-space>
                <a-button :loading="uploading" @click="triggerUpload">选择图片</a-button>
                <span class="muted-text">{{ form.image_path || '未上传图片' }}</span>
              </a-space>
              <div v-if="imagePreviewUrl" class="form-preview">
                <img :src="imagePreviewUrl" alt="uploaded preview" class="preview-image large" />
              </div>
            </div>
          </a-form-item>

          <div class="summary-grid">
            <div class="summary-card">
              <span class="summary-label">匹配阈值</span>
              <a-input-number v-model="form.threshold" :min="0.5" :max="1" :step="0.05" />
            </div>
            <div class="summary-card">
              <span class="summary-label">颜色模式</span>
              <label class="switch-row">
                <a-switch v-model="form.rgb" />
                <span>{{ form.rgb ? 'RGB' : '灰度' }}</span>
              </label>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="form.element_type === 'pos'">
        <div class="config-block">
          <div class="config-block-title">坐标配置</div>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="坐标 X">
                <a-input-number v-model="form.posX" :min="0" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="坐标 Y">
                <a-input-number v-model="form.posY" :min="0" />
              </a-form-item>
            </a-col>
          </a-row>
        </div>
      </template>

      <template v-else>
        <div class="config-block">
          <div class="config-block-title">区域配置</div>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="左上角 X1">
                <a-input-number v-model="form.regionX1" :min="0" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="左上角 Y1">
                <a-input-number v-model="form.regionY1" :min="0" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="右下角 X2">
                <a-input-number v-model="form.regionX2" :min="0" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="右下角 Y2">
                <a-input-number v-model="form.regionY2" :min="0" />
              </a-form-item>
            </a-col>
          </a-row>
        </div>
      </template>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="selector_type" label="定位方式">
            <a-input v-model="form.selector_type" placeholder="image / pos / region / text / xpath" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="selector_value" label="定位值">
            <a-input v-model="form.selector_value" placeholder="不填时会按元素类型自动生成默认值" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="tags" label="标签">
            <a-input v-model="form.tagsText" placeholder="使用逗号分隔，例如：登录, 首页, 支付" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="启用状态">
            <label class="switch-row">
              <a-switch v-model="form.is_active" />
              <span>{{ form.is_active ? '已启用' : '已停用' }}</span>
            </label>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item field="description" label="描述">
        <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" />
      </a-form-item>

      <a-form-item field="config" label="扩展配置 JSON">
        <a-textarea v-model="form.configText" :auto-size="{ minRows: 6, maxRows: 10 }" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AppImageCategory } from '../../types'

interface ElementsEditorForm {
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

interface Props {
  form: ElementsEditorForm
  imageCategories: AppImageCategory[]
  imagePreviewUrl: string
  uploading: boolean
  categorySaving: boolean
  categoryDeleting: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const newCategoryNameModel = defineModel<string>('newCategoryName', { required: true })

const fileInputRef = ref<HTMLInputElement | null>(null)

const emit = defineEmits<{
  submit: []
  cancel: []
  'file-change': [file: File | null]
  'create-category': []
  'delete-current-category': []
}>()

const triggerUpload = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('file-change', target.files?.[0] || null)
  target.value = ''
}
</script>

<style scoped>
.form-preview {
  display: flex;
  align-items: center;
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

.muted-text {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.config-block {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.config-block-title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text);
}

.upload-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hidden-input {
  display: none;
}

.inline-action {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
}

.summary-label {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.switch-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 960px) {
  .inline-action,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>

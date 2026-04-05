<template>
  <div class="page-shell">
    <div v-if="!projectStore.currentProjectId" class="empty-shell">
      <a-empty description="请先选择项目后再管理 APP 自动化元素" />
    </div>
    <template v-else>
      <div class="page-header">
        <div>
          <h3>元素管理</h3>
          <p>沉淀图片、坐标、区域等元素资源，供 APP 自动化场景编排和用例复用。</p>
        </div>
        <a-space>
          <a-input-search v-model="search" placeholder="搜索元素" allow-clear @search="loadElements" />
          <a-select v-model="typeFilter" allow-clear placeholder="元素类型" style="width: 140px" @change="loadElements">
            <a-option value="image">image</a-option>
            <a-option value="pos">pos</a-option>
            <a-option value="region">region</a-option>
          </a-select>
          <a-button @click="loadElements">刷新</a-button>
          <a-button @click="captureVisible = true">从设备截图创建</a-button>
          <a-button type="primary" @click="openCreate">新增元素</a-button>
        </a-space>
      </div>

      <a-card class="table-card">
        <a-table :data="elements" :loading="loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="名称" data-index="name" />
            <a-table-column title="类型" data-index="element_type" />
            <a-table-column title="预览" :width="220">
              <template #cell="{ record }">
                <div v-if="record.element_type === 'image' && record.image_path" class="table-preview">
                  <img :src="getPreviewUrl(record.image_path)" alt="element preview" class="preview-image" />
                </div>
                <div v-else-if="record.element_type === 'pos'" class="coordinate-preview">
                  {{ renderPos(record) }}
                </div>
                <div v-else-if="record.element_type === 'region'" class="coordinate-preview">
                  {{ renderRegion(record) }}
                </div>
                <span v-else class="muted-text">-</span>
              </template>
            </a-table-column>
            <a-table-column title="图片分类">
              <template #cell="{ record }">{{ getImageCategory(record) || '-' }}</template>
            </a-table-column>
            <a-table-column title="定位方式" data-index="selector_type" />
            <a-table-column title="定位值">
              <template #cell="{ record }">
                <span class="mono">{{ record.selector_value || '-' }}</span>
              </template>
            </a-table-column>
            <a-table-column title="状态">
              <template #cell="{ record }">
                <a-tag :color="record.is_active ? 'green' : 'gray'">{{ record.is_active ? '启用' : '停用' }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column title="操作" :width="180">
              <template #cell="{ record }">
                <a-space>
                  <a-button type="text" @click="openEdit(record)">编辑</a-button>
                  <a-button type="text" status="danger" @click="remove(record.id)">删除</a-button>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-card>

      <a-modal
        v-model:visible="visible"
        :title="form.id ? '编辑元素' : '新增元素'"
        width="860px"
        @ok="submit"
        @cancel="resetForm"
      >
        <a-form :model="form" layout="vertical">
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="name" label="元素名称">
                <a-input v-model="form.name" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item field="element_type" label="元素类型">
                <a-select v-model="form.element_type">
                  <a-option value="image">image</a-option>
                  <a-option value="pos">pos</a-option>
                  <a-option value="region">region</a-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <template v-if="form.element_type === 'image'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="图片分类">
                  <a-select v-model="form.imageCategory" placeholder="选择分类">
                    <a-option v-for="category in imageCategories" :key="category.name" :value="category.name">
                      {{ category.name }} ({{ category.count }})
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="新增分类">
                  <a-space fill>
                    <a-input v-model="newCategoryName" placeholder="输入新分类名称" />
                    <a-button :loading="categorySaving" @click="createCategory">创建分类</a-button>
                  </a-space>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="图片资源">
              <div class="upload-shell">
                <input ref="fileInputRef" type="file" accept="image/*" class="hidden-input" @change="handleFileChange" />
                <a-space>
                  <a-button :loading="uploading" @click="triggerUpload">选择图片</a-button>
                  <span class="muted-text">{{ form.image_path || '未上传图片' }}</span>
                </a-space>
                <div v-if="imagePreviewUrl" class="form-preview">
                  <img :src="imagePreviewUrl" alt="uploaded preview" class="preview-image large" />
                </div>
              </div>
            </a-form-item>
          </template>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item field="selector_type" label="定位方式">
                <a-input v-model="form.selector_type" placeholder="id / xpath / text / image" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item field="image_path" label="图片路径">
                <a-input v-model="form.image_path" placeholder="上传图片后自动填充" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item field="selector_value" label="定位值">
            <a-input v-model="form.selector_value" />
          </a-form-item>

          <a-form-item field="tags" label="标签">
            <a-input v-model="form.tagsText" placeholder="使用逗号分隔，例如：登录,首页,支付" />
          </a-form-item>

          <a-form-item field="config" label="扩展配置 JSON">
            <a-textarea v-model="form.configText" :auto-size="{ minRows: 6, maxRows: 10 }" />
          </a-form-item>

          <a-form-item field="description" label="描述">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" />
          </a-form-item>
        </a-form>
      </a-modal>

      <AppAutomationCaptureElementModal
        v-model:visible="captureVisible"
        :project-id="projectStore.currentProjectId"
        @success="handleCaptureSuccess"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppElement, AppImageCategory } from '../types'
import AppAutomationCaptureElementModal from '../components/AppAutomationCaptureElementModal.vue'

const projectStore = useProjectStore()
const loading = ref(false)
const visible = ref(false)
const captureVisible = ref(false)
const uploading = ref(false)
const categorySaving = ref(false)
const search = ref('')
const typeFilter = ref<string>()
const elements = ref<AppElement[]>([])
const imageCategories = ref<AppImageCategory[]>([])
const newCategoryName = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const localPreviewUrl = ref('')

const form = reactive({
  id: 0,
  name: '',
  element_type: 'image',
  selector_type: '',
  selector_value: '',
  description: '',
  tagsText: '',
  configText: '{\n  "threshold": 0.7\n}',
  image_path: '',
  imageCategory: 'common',
  fileHash: '',
  is_active: true,
})

const imagePreviewUrl = computed(() => {
  if (localPreviewUrl.value) {
    return localPreviewUrl.value
  }
  if (form.image_path) {
    return AppAutomationService.getElementAssetUrl(form.image_path)
  }
  return ''
})

const updateLocalPreviewUrl = (value: string) => {
  if (localPreviewUrl.value && localPreviewUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(localPreviewUrl.value)
  }
  localPreviewUrl.value = value
}

const parseConfig = (record: AppElement) => {
  const config = record.config || {}
  const imageCategory =
    String((config as Record<string, unknown>).image_category || '') ||
    (record.image_path?.includes('/') ? record.image_path.split('/')[0] : '') ||
    'common'
  const fileHash = String((config as Record<string, unknown>).file_hash || '')
  return { imageCategory, fileHash }
}

const getPreviewUrl = (imagePath?: string) => {
  if (!imagePath) return ''
  return AppAutomationService.getElementAssetUrl(imagePath)
}

const getImageCategory = (record: AppElement) => {
  const config = record.config as Record<string, unknown>
  if (config?.image_category) return String(config.image_category)
  if (record.image_path?.includes('/')) return record.image_path.split('/')[0]
  return ''
}

const renderPos = (record: AppElement) => {
  const config = record.config as Record<string, unknown>
  return `X: ${config?.x ?? '-'} / Y: ${config?.y ?? '-'}`
}

const renderRegion = (record: AppElement) => {
  const config = record.config as Record<string, unknown>
  return `(${config?.x1 ?? '-'}, ${config?.y1 ?? '-'}) - (${config?.x2 ?? '-'}, ${config?.y2 ?? '-'})`
}

const resetForm = () => {
  form.id = 0
  form.name = ''
  form.element_type = 'image'
  form.selector_type = ''
  form.selector_value = ''
  form.description = ''
  form.tagsText = ''
  form.configText = '{\n  "threshold": 0.7\n}'
  form.image_path = ''
  form.imageCategory = 'common'
  form.fileHash = ''
  form.is_active = true
  newCategoryName.value = ''
  updateLocalPreviewUrl('')
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const loadCategories = async () => {
  try {
    imageCategories.value = await AppAutomationService.getElementImageCategories()
    if (!imageCategories.value.some(item => item.name === form.imageCategory)) {
      form.imageCategory = imageCategories.value[0]?.name || 'common'
    }
  } catch (error: any) {
    Message.error(error.message || '加载图片分类失败')
  }
}

const loadElements = async () => {
  if (!projectStore.currentProjectId) {
    elements.value = []
    return
  }

  loading.value = true
  try {
    elements.value = await AppAutomationService.getElements(projectStore.currentProjectId, search.value, typeFilter.value)
  } catch (error: any) {
    Message.error(error.message || '加载元素失败')
  } finally {
    loading.value = false
  }
}

const openCreate = async () => {
  resetForm()
  await loadCategories()
  visible.value = true
}

const openEdit = async (record: AppElement) => {
  resetForm()
  await loadCategories()
  form.id = record.id
  form.name = record.name
  form.element_type = record.element_type
  form.selector_type = record.selector_type
  form.selector_value = record.selector_value
  form.description = record.description
  form.tagsText = record.tags.join(', ')
  form.configText = JSON.stringify(record.config, null, 2)
  form.image_path = record.image_path
  form.is_active = record.is_active
  const { imageCategory, fileHash } = parseConfig(record)
  form.imageCategory = imageCategory
  form.fileHash = fileHash
  visible.value = true
}

const triggerUpload = () => {
  fileInputRef.value?.click()
}

const handleFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || !projectStore.currentProjectId) {
    return
  }

  updateLocalPreviewUrl(URL.createObjectURL(file))
  uploading.value = true
  try {
    const result = await AppAutomationService.uploadElementAsset(
      file,
      projectStore.currentProjectId,
      form.imageCategory || 'common',
      form.id || undefined,
    )
    form.image_path = result.image_path
    form.imageCategory = result.image_category || form.imageCategory
    form.fileHash = result.file_hash
    Message.success(result.duplicate ? '检测到重复图片，已复用现有资源' : '图片已上传')
    await loadCategories()
  } catch (error: any) {
    Message.error(error.message || '上传图片失败')
  } finally {
    uploading.value = false
  }
}

const createCategory = async () => {
  if (!newCategoryName.value.trim()) {
    Message.warning('请输入分类名称')
    return
  }
  categorySaving.value = true
  try {
    const created = await AppAutomationService.createElementImageCategory(newCategoryName.value.trim())
    form.imageCategory = created.name
    newCategoryName.value = ''
    Message.success('图片分类已创建')
    await loadCategories()
  } catch (error: any) {
    Message.error(error.message || '创建图片分类失败')
  } finally {
    categorySaving.value = false
  }
}

const submit = async () => {
  if (!projectStore.currentProjectId) {
    return
  }

  try {
    const parsedConfig = JSON.parse(form.configText || '{}') as Record<string, unknown>
    if (form.element_type === 'image') {
      parsedConfig.image_category = form.imageCategory || 'common'
      parsedConfig.image_path = form.image_path
      if (form.fileHash) {
        parsedConfig.file_hash = form.fileHash
      }
      if (parsedConfig.threshold === undefined) {
        parsedConfig.threshold = 0.7
      }
    }

    const payload = {
      project_id: projectStore.currentProjectId,
      name: form.name.trim(),
      element_type: form.element_type,
      selector_type: form.selector_type.trim(),
      selector_value: form.selector_value.trim(),
      description: form.description.trim(),
      tags: form.tagsText
        .split(',')
        .map(item => item.trim())
        .filter(Boolean),
      config: parsedConfig,
      image_path: form.image_path,
      is_active: form.is_active,
    }

    if (form.id) {
      await AppAutomationService.updateElement(form.id, payload)
      Message.success('元素已更新')
    } else {
      await AppAutomationService.createElement(payload)
      Message.success('元素已创建')
    }

    visible.value = false
    resetForm()
    await Promise.all([loadElements(), loadCategories()])
  } catch (error: any) {
    Message.error(error.message || '保存元素失败，请检查 JSON 配置')
  }
}

const remove = (id: number) => {
  Modal.confirm({
    title: '删除元素',
    content: '确认删除这个元素吗？',
    onOk: async () => {
      await AppAutomationService.deleteElement(id)
      Message.success('元素已删除')
      await loadElements()
    },
  })
}

const handleCaptureSuccess = async () => {
  await Promise.all([loadElements(), loadCategories()])
}

watch(
  () => projectStore.currentProjectId,
  () => {
    resetForm()
    void Promise.all([loadElements(), loadCategories()])
  },
  { immediate: true },
)
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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h3 {
  margin: 0;
  color: var(--theme-text);
}

.page-header p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.table-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.table-preview,
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
  max-height: 240px;
  padding: 8px;
}

.coordinate-preview,
.muted-text {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.upload-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hidden-input {
  display: none;
}
</style>

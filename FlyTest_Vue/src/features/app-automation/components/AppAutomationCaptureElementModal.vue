<template>
  <a-modal
    v-model:visible="visibleProxy"
    title="从设备截图创建元素"
    width="1180px"
    :mask-closable="false"
    :ok-loading="submitting"
    :ok-button-props="{ disabled: !canSubmit }"
    @ok="submit"
    @cancel="closeModal"
  >
    <div class="capture-layout">
      <div class="capture-stage-panel">
        <div
          v-if="screenshotContent"
          ref="stageRef"
          class="capture-stage"
          @mousedown="handlePointerDown"
          @mousemove="handlePointerMove"
          @mouseup="handlePointerUp"
          @mouseleave="handlePointerUp"
        >
          <img ref="imageRef" :src="screenshotContent" alt="device screenshot" class="capture-image" draggable="false" @load="handleImageLoad" />

          <div v-if="selection && form.element_type !== 'pos'" class="selection-box" :style="selectionStyle">
            <span class="selection-label">{{ selectionLabel }}</span>
          </div>

          <div v-if="point && form.element_type === 'pos'" class="point-marker" :style="pointStyle">
            <span class="point-label">{{ pointLabel }}</span>
          </div>
        </div>

        <div v-else class="capture-empty">
          <h4>先选择设备并截图</h4>
          <p>截图后可以拖拽框选区域，或在坐标模式下单击截图直接取点。</p>
        </div>

        <div class="capture-footer">
          <span v-if="captureMeta.device_id">设备：{{ captureMeta.device_id }}</span>
          <span v-if="captureMeta.timestamp">截图时间：{{ formatCaptureTime(captureMeta.timestamp) }}</span>
          <span v-if="form.element_type === 'image' && !selection && screenshotContent">未框选时将使用整张截图上传</span>
        </div>
      </div>

      <div class="capture-sidebar">
        <a-form :model="form" layout="vertical">
          <a-form-item label="选择设备" required>
            <a-select v-model="selectedDeviceId" :loading="devicesLoading" placeholder="请选择设备" allow-search>
              <a-option v-for="device in devices" :key="device.id" :value="device.id">
                {{ device.name || device.device_id }} · {{ device.status }}
              </a-option>
            </a-select>
          </a-form-item>

          <div class="action-row">
            <a-button :loading="devicesRefreshing" @click="refreshDevices">刷新设备</a-button>
            <a-button type="primary" :loading="capturing" :disabled="!selectedDeviceId" @click="captureScreenshot">立即截图</a-button>
            <a-button :disabled="!selection && !point" @click="clearInteractiveState">清空标记</a-button>
          </div>

          <a-form-item label="元素名称" required>
            <a-input v-model="form.name" placeholder="例如：登录按钮、首页搜索框" />
          </a-form-item>

          <a-form-item label="元素类型" required>
            <a-radio-group v-model="form.element_type">
              <a-radio value="image">图片</a-radio>
              <a-radio value="pos">坐标</a-radio>
              <a-radio value="region">区域</a-radio>
            </a-radio-group>
          </a-form-item>

          <template v-if="form.element_type === 'image'">
            <a-form-item label="图片分类" required>
              <a-select v-model="form.image_category" :loading="categoriesLoading" placeholder="选择图片分类" allow-search>
                <a-option v-for="category in imageCategories" :key="category.name" :value="category.name">
                  {{ category.name }} ({{ category.count }})
                </a-option>
              </a-select>
            </a-form-item>

            <a-form-item label="新增分类">
              <div class="inline-input-action">
                <a-input v-model="newCategoryName" placeholder="例如：button、login、popup" />
                <a-button :loading="creatingCategory" @click="createCategory">创建</a-button>
              </div>
            </a-form-item>

            <div class="summary-grid">
              <div class="summary-card">
                <span class="summary-label">匹配阈值</span>
                <a-input-number v-model="form.threshold" :min="0.5" :max="1" :step="0.05" />
              </div>
              <div class="summary-card summary-card-switch">
                <span class="summary-label">颜色模式</span>
                <label class="switch-row">
                  <a-switch v-model="form.rgb" />
                  <span>{{ form.rgb ? 'RGB' : '灰度' }}</span>
                </label>
              </div>
            </div>
          </template>

          <template v-else-if="form.element_type === 'pos'">
            <div class="summary-grid">
              <div class="summary-card">
                <span class="summary-label">坐标 X</span>
                <strong>{{ pointNatural?.x ?? '-' }}</strong>
              </div>
              <div class="summary-card">
                <span class="summary-label">坐标 Y</span>
                <strong>{{ pointNatural?.y ?? '-' }}</strong>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="summary-grid summary-grid-region">
              <div class="summary-card">
                <span class="summary-label">左上角</span>
                <strong>{{ regionSummary.start }}</strong>
              </div>
              <div class="summary-card">
                <span class="summary-label">右下角</span>
                <strong>{{ regionSummary.end }}</strong>
              </div>
              <div class="summary-card">
                <span class="summary-label">尺寸</span>
                <strong>{{ regionSummary.size }}</strong>
              </div>
            </div>
          </template>

          <a-form-item label="标签">
            <a-input v-model="form.tagsText" placeholder="使用逗号分隔，例如：登录、首页、关键路径" />
          </a-form-item>

          <a-form-item label="描述">
            <a-textarea v-model="form.description" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="补充说明元素用途或使用场景" />
          </a-form-item>

          <p class="hint-text">
            图片元素支持框选截图后直接入库；坐标元素请在截图上单击；区域元素请拖拽选择范围。
          </p>
        </a-form>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { AppAutomationService } from '../services/appAutomationService'
import type { AppDevice, AppDeviceScreenshot, AppImageCategory } from '../types'

type ElementMode = 'image' | 'pos' | 'region'

type DisplayPoint = {
  x: number
  y: number
}

type DisplaySelection = {
  x1: number
  y1: number
  x2: number
  y2: number
}

const props = defineProps<{
  visible: boolean
  projectId: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const visibleProxy = computed({
  get: () => props.visible,
  set: value => emit('update:visible', value),
})

const stageRef = ref<HTMLDivElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const devices = ref<AppDevice[]>([])
const imageCategories = ref<AppImageCategory[]>([])
const selectedDeviceId = ref<number>()
const devicesLoading = ref(false)
const devicesRefreshing = ref(false)
const categoriesLoading = ref(false)
const creatingCategory = ref(false)
const capturing = ref(false)
const submitting = ref(false)
const newCategoryName = ref('')
const screenshotContent = ref('')
const captureMeta = reactive<Pick<AppDeviceScreenshot, 'device_id' | 'timestamp'>>({
  device_id: '',
  timestamp: 0,
})
const imageSize = reactive({
  naturalWidth: 0,
  naturalHeight: 0,
  clientWidth: 0,
  clientHeight: 0,
})
const form = reactive({
  name: '',
  element_type: 'image' as ElementMode,
  image_category: 'common',
  threshold: 0.7,
  rgb: false,
  tagsText: '',
  description: '',
})

const selection = ref<DisplaySelection | null>(null)
const point = ref<DisplayPoint | null>(null)
const dragging = ref(false)
const dragStart = ref<DisplayPoint | null>(null)

const normalizePointer = (event: MouseEvent) => {
  const stage = stageRef.value
  if (!stage) {
    return null
  }
  const rect = stage.getBoundingClientRect()
  const x = Math.max(0, Math.min(event.clientX - rect.left, rect.width))
  const y = Math.max(0, Math.min(event.clientY - rect.top, rect.height))
  return { x, y }
}

const selectionStyle = computed(() => {
  if (!selection.value) {
    return {}
  }
  const x = Math.min(selection.value.x1, selection.value.x2)
  const y = Math.min(selection.value.y1, selection.value.y2)
  const width = Math.abs(selection.value.x2 - selection.value.x1)
  const height = Math.abs(selection.value.y2 - selection.value.y1)
  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${width}px`,
    height: `${height}px`,
  }
})

const pointStyle = computed(() => {
  if (!point.value) {
    return {}
  }
  return {
    left: `${point.value.x}px`,
    top: `${point.value.y}px`,
  }
})

const pointNatural = computed(() => {
  if (!point.value || !imageSize.clientWidth || !imageSize.clientHeight) {
    return null
  }
  const scaleX = imageSize.naturalWidth / imageSize.clientWidth
  const scaleY = imageSize.naturalHeight / imageSize.clientHeight
  return {
    x: Math.round(point.value.x * scaleX),
    y: Math.round(point.value.y * scaleY),
  }
})

const selectionNatural = computed(() => {
  if (!selection.value || !imageSize.clientWidth || !imageSize.clientHeight) {
    return null
  }
  const scaleX = imageSize.naturalWidth / imageSize.clientWidth
  const scaleY = imageSize.naturalHeight / imageSize.clientHeight
  const x = Math.min(selection.value.x1, selection.value.x2)
  const y = Math.min(selection.value.y1, selection.value.y2)
  const width = Math.abs(selection.value.x2 - selection.value.x1)
  const height = Math.abs(selection.value.y2 - selection.value.y1)
  return {
    x: Math.round(x * scaleX),
    y: Math.round(y * scaleY),
    width: Math.round(width * scaleX),
    height: Math.round(height * scaleY),
  }
})

const selectionLabel = computed(() => {
  if (!selectionNatural.value) {
    return ''
  }
  return `${selectionNatural.value.width} × ${selectionNatural.value.height}`
})

const pointLabel = computed(() => {
  if (!pointNatural.value) {
    return ''
  }
  return `${pointNatural.value.x}, ${pointNatural.value.y}`
})

const regionSummary = computed(() => {
  if (!selectionNatural.value) {
    return {
      start: '-',
      end: '-',
      size: '-',
    }
  }
  const { x, y, width, height } = selectionNatural.value
  return {
    start: `${x}, ${y}`,
    end: `${x + width}, ${y + height}`,
    size: `${width} × ${height}`,
  }
})

const canSubmit = computed(() => {
  if (!props.projectId || !form.name.trim() || !screenshotContent.value) {
    return false
  }
  if (form.element_type === 'image') {
    return Boolean(form.image_category)
  }
  if (form.element_type === 'pos') {
    return Boolean(pointNatural.value)
  }
  return Boolean(selectionNatural.value && selectionNatural.value.width > 0 && selectionNatural.value.height > 0)
})

const formatCaptureTime = (timestamp: number) => new Date(timestamp * 1000).toLocaleString('zh-CN')

const clearInteractiveState = () => {
  selection.value = null
  point.value = null
  dragging.value = false
  dragStart.value = null
}

const resetState = () => {
  form.name = ''
  form.element_type = 'image'
  form.image_category = 'common'
  form.threshold = 0.7
  form.rgb = false
  form.tagsText = ''
  form.description = ''
  newCategoryName.value = ''
  screenshotContent.value = ''
  captureMeta.device_id = ''
  captureMeta.timestamp = 0
  imageSize.naturalWidth = 0
  imageSize.naturalHeight = 0
  imageSize.clientWidth = 0
  imageSize.clientHeight = 0
  clearInteractiveState()
}

const closeModal = () => {
  visibleProxy.value = false
}

const loadDevices = async (discover = false) => {
  if (discover) {
    devicesRefreshing.value = true
  } else {
    devicesLoading.value = true
  }
  try {
    const nextDevices = discover ? await AppAutomationService.discoverDevices() : await AppAutomationService.getDevices()
    devices.value = nextDevices
    if (selectedDeviceId.value && nextDevices.some(item => item.id === selectedDeviceId.value)) {
      return
    }
    selectedDeviceId.value = nextDevices[0]?.id
  } catch (error: any) {
    Message.error(error.message || '加载设备失败')
  } finally {
    devicesLoading.value = false
    devicesRefreshing.value = false
  }
}

const refreshDevices = async () => {
  await loadDevices(true)
}

const loadCategories = async () => {
  categoriesLoading.value = true
  try {
    const nextCategories = await AppAutomationService.getElementImageCategories()
    imageCategories.value = nextCategories
    if (!nextCategories.some(item => item.name === form.image_category)) {
      form.image_category = nextCategories[0]?.name || 'common'
    }
  } catch (error: any) {
    Message.error(error.message || '加载图片分类失败')
  } finally {
    categoriesLoading.value = false
  }
}

const createCategory = async () => {
  const name = newCategoryName.value.trim()
  if (!name) {
    Message.warning('请输入分类名称')
    return
  }
  creatingCategory.value = true
  try {
    const category = await AppAutomationService.createElementImageCategory(name)
    form.image_category = category.name
    newCategoryName.value = ''
    Message.success('图片分类已创建')
    await loadCategories()
  } catch (error: any) {
    Message.error(error.message || '创建图片分类失败')
  } finally {
    creatingCategory.value = false
  }
}

const captureScreenshot = async () => {
  if (!selectedDeviceId.value) {
    Message.warning('请先选择设备')
    return
  }
  capturing.value = true
  try {
    const screenshot = await AppAutomationService.captureDeviceScreenshot(selectedDeviceId.value)
    screenshotContent.value = screenshot.content
    captureMeta.device_id = screenshot.device_id
    captureMeta.timestamp = screenshot.timestamp
    clearInteractiveState()
    Message.success('设备截图已获取')
  } catch (error: any) {
    Message.error(error.message || '设备截图失败')
  } finally {
    capturing.value = false
  }
}

const handleImageLoad = () => {
  if (!imageRef.value) {
    return
  }
  imageSize.naturalWidth = imageRef.value.naturalWidth || 0
  imageSize.naturalHeight = imageRef.value.naturalHeight || 0
  imageSize.clientWidth = imageRef.value.clientWidth || 0
  imageSize.clientHeight = imageRef.value.clientHeight || 0
}

const handlePointerDown = (event: MouseEvent) => {
  if (!screenshotContent.value) {
    return
  }
  const pointerPosition = normalizePointer(event)
  if (!pointerPosition) {
    return
  }
  if (form.element_type === 'pos') {
    point.value = pointerPosition
    selection.value = null
    return
  }
  dragging.value = true
  dragStart.value = pointerPosition
  selection.value = {
    x1: pointerPosition.x,
    y1: pointerPosition.y,
    x2: pointerPosition.x,
    y2: pointerPosition.y,
  }
  point.value = null
}

const handlePointerMove = (event: MouseEvent) => {
  if (!dragging.value || !dragStart.value || form.element_type === 'pos') {
    return
  }
  const pointerPosition = normalizePointer(event)
  if (!pointerPosition) {
    return
  }
  selection.value = {
    x1: dragStart.value.x,
    y1: dragStart.value.y,
    x2: pointerPosition.x,
    y2: pointerPosition.y,
  }
}

const handlePointerUp = () => {
  if (!dragging.value) {
    return
  }
  dragging.value = false
  dragStart.value = null
  if (!selection.value) {
    return
  }
  const width = Math.abs(selection.value.x2 - selection.value.x1)
  const height = Math.abs(selection.value.y2 - selection.value.y1)
  if (width < 4 || height < 4) {
    selection.value = null
  }
}

const normalizeFileName = (name: string) => {
  const safeBase = name.trim().replace(/[^\u4e00-\u9fa5\w-]+/g, '_').replace(/^_+|_+$/g, '')
  return `${safeBase || 'captured_element'}.png`
}

const buildImageBlob = async () => {
  const imageElement = imageRef.value
  if (!imageElement) {
    throw new Error('截图尚未准备完成')
  }

  const crop = selectionNatural.value ?? {
    x: 0,
    y: 0,
    width: imageSize.naturalWidth,
    height: imageSize.naturalHeight,
  }

  const canvas = document.createElement('canvas')
  canvas.width = Math.max(crop.width, 1)
  canvas.height = Math.max(crop.height, 1)
  const context = canvas.getContext('2d')
  if (!context) {
    throw new Error('浏览器无法创建图像画布')
  }

  context.drawImage(
    imageElement,
    crop.x,
    crop.y,
    crop.width,
    crop.height,
    0,
    0,
    crop.width,
    crop.height,
  )

  const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
  if (!blob) {
    throw new Error('截图裁剪失败')
  }
  return blob
}

const buildPayload = async () => {
  const tags = form.tagsText
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)

  if (form.element_type === 'image') {
    const blob = await buildImageBlob()
    const file = new File([blob], normalizeFileName(form.name), { type: 'image/png' })
    const uploadResult = await AppAutomationService.uploadElementAsset(file, props.projectId, form.image_category)
    return {
      project_id: props.projectId,
      name: form.name.trim(),
      element_type: 'image' as const,
      selector_type: 'image',
      selector_value: uploadResult.image_path,
      description: form.description.trim(),
      tags,
      config: {
        threshold: form.threshold,
        rgb: form.rgb,
        image_path: uploadResult.image_path,
        image_category: uploadResult.image_category,
        file_hash: uploadResult.file_hash,
        capture_device_id: captureMeta.device_id,
        capture_timestamp: captureMeta.timestamp,
        crop_region: selectionNatural.value,
      },
      image_path: uploadResult.image_path,
      is_active: true,
    }
  }

  if (form.element_type === 'pos') {
    if (!pointNatural.value) {
      throw new Error('请在截图上单击选择坐标')
    }
    return {
      project_id: props.projectId,
      name: form.name.trim(),
      element_type: 'pos' as const,
      selector_type: 'pos',
      selector_value: `${pointNatural.value.x},${pointNatural.value.y}`,
      description: form.description.trim(),
      tags,
      config: {
        x: pointNatural.value.x,
        y: pointNatural.value.y,
        capture_device_id: captureMeta.device_id,
        capture_timestamp: captureMeta.timestamp,
      },
      image_path: '',
      is_active: true,
    }
  }

  if (!selectionNatural.value || selectionNatural.value.width <= 0 || selectionNatural.value.height <= 0) {
    throw new Error('请先框选区域')
  }

  return {
    project_id: props.projectId,
    name: form.name.trim(),
    element_type: 'region' as const,
    selector_type: 'region',
    selector_value: `${selectionNatural.value.x},${selectionNatural.value.y},${selectionNatural.value.x + selectionNatural.value.width},${selectionNatural.value.y + selectionNatural.value.height}`,
    description: form.description.trim(),
    tags,
    config: {
      x1: selectionNatural.value.x,
      y1: selectionNatural.value.y,
      x2: selectionNatural.value.x + selectionNatural.value.width,
      y2: selectionNatural.value.y + selectionNatural.value.height,
      width: selectionNatural.value.width,
      height: selectionNatural.value.height,
      capture_device_id: captureMeta.device_id,
      capture_timestamp: captureMeta.timestamp,
    },
    image_path: '',
    is_active: true,
  }
}

const submit = async () => {
  if (!canSubmit.value) {
    Message.warning('请先补齐必填信息并完成截图标注')
    return
  }
  submitting.value = true
  try {
    const payload = await buildPayload()
    await AppAutomationService.createElement(payload)
    Message.success('元素已从设备截图创建')
    emit('success')
    closeModal()
  } catch (error: any) {
    Message.error(error.message || '保存元素失败')
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.visible,
  async value => {
    if (value) {
      resetState()
      await Promise.all([loadDevices(), loadCategories()])
      return
    }
    resetState()
  },
)

watch(
  () => form.element_type,
  value => {
    if (value === 'pos') {
      selection.value = null
      return
    }
    point.value = null
  },
)
</script>

<style scoped>
.capture-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 20px;
  min-height: 620px;
}

.capture-stage-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.capture-stage {
  position: relative;
  min-height: 560px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  border-radius: 20px;
  border: 1px solid var(--theme-card-border);
  background:
    radial-gradient(circle at top, rgba(37, 99, 235, 0.12), transparent 48%),
    rgba(9, 15, 28, 0.24);
  cursor: crosshair;
}

.capture-image {
  display: block;
  max-width: 100%;
  max-height: 560px;
  user-select: none;
  border-radius: 18px;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.28);
}

.capture-empty {
  min-height: 560px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 20px;
  border: 1px dashed var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--theme-text-secondary);
  text-align: center;
  padding: 24px;
}

.capture-empty h4 {
  margin: 0;
  color: var(--theme-text);
  font-size: 18px;
}

.capture-empty p {
  margin: 0;
  max-width: 360px;
  line-height: 1.6;
}

.selection-box {
  position: absolute;
  border: 2px solid rgba(59, 130, 246, 0.96);
  border-radius: 16px;
  background: rgba(59, 130, 246, 0.18);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18);
}

.selection-label {
  position: absolute;
  top: -34px;
  left: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgb(37, 99, 235);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.point-marker {
  position: absolute;
  width: 16px;
  height: 16px;
  margin-left: -8px;
  margin-top: -8px;
  border-radius: 999px;
  background: rgb(37, 99, 235);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18);
}

.point-label {
  position: absolute;
  top: -32px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 10px;
  border-radius: 999px;
  background: rgb(37, 99, 235);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.capture-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.capture-sidebar {
  border-radius: 20px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
  padding: 18px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.inline-input-action {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.summary-grid-region {
  grid-template-columns: 1fr;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(255, 255, 255, 0.03);
}

.summary-card-switch {
  justify-content: space-between;
}

.summary-label {
  color: var(--theme-text-secondary);
  font-size: 12px;
}

.summary-card strong {
  color: var(--theme-text);
  font-size: 15px;
}

.switch-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--theme-text);
}

.hint-text {
  margin: 0;
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .capture-layout {
    grid-template-columns: 1fr;
  }

  .capture-sidebar {
    order: -1;
  }
}
</style>

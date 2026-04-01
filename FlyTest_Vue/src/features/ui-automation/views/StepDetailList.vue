<template>
  <div class="step-detail-list">
    <div class="step-header">
      <span class="step-title">操作步骤（拖拽可排序）</span>
      <a-space>
        <a-select v-model="selectedEnvConfig" placeholder="执行环境" size="small" style="width: 120px" allow-clear>
          <a-option v-for="env in envConfigs" :key="env.id" :value="env.id">
            {{ env.name }}
            <a-tag v-if="env.is_default" size="small" color="arcoblue" style="margin-left: 4px">默认</a-tag>
          </a-option>
        </a-select>
        <a-select v-model="selectedActuator" placeholder="选择执行器" size="small" style="width: 150px" allow-clear>
          <a-option v-for="act in actuators" :key="act.id" :value="act.id" :disabled="!act.is_open">
            {{ act.name || act.id }}
            <a-tag v-if="!act.is_open" size="small" color="gray" style="margin-left: 4px">离线</a-tag>
          </a-option>
        </a-select>
        <a-button type="outline" status="success" size="small" :loading="executing" :disabled="!selectedActuator" @click="executePageStep">
          <template #icon><icon-play-arrow /></template>
          调试执行
        </a-button>
        <a-button type="primary" size="small" @click="showAddModal">
          <template #icon><icon-plus /></template>
          添加操作
        </a-button>
      </a-space>
    </div>

    <a-spin :loading="loading">
      <div v-if="stepData.length === 0" class="empty-tips">
        <a-empty description="暂无操作步骤" />
      </div>
      <draggable
        v-else
        v-model="stepData"
        item-key="id"
        handle=".drag-handle"
        @end="onDragEnd"
      >
        <template #item="{ element, index }">
          <div class="step-card">
            <div class="step-left">
              <div class="drag-handle">
                <icon-drag-dot-vertical />
              </div>
              <div class="step-index">{{ index + 1 }}</div>
              <div class="step-type">
                <a-tag :color="stepTypeColors[element.step_type as StepType]" size="small">
                  {{ STEP_TYPE_LABELS[element.step_type as StepType] }}
                </a-tag>
              </div>
            </div>
            <div class="step-content">
              <span v-if="element.element_name" class="info-item">
                <span class="info-label">元素:</span>
                <span class="element-name">{{ element.element_name }}</span>
              </span>
              <span v-if="element.ope_key" class="info-item">
                <span class="info-label">操作:</span>
                <span class="ope-key">{{ getOpeKeyLabel(element.ope_key) }}</span>
              </span>
              <span v-if="element.ope_value && Object.keys(element.ope_value).length > 0" class="info-item">
                <span class="info-label">参数:</span>
                <span class="ope-value">{{ formatOpeValue(element.ope_value) }}</span>
              </span>
              <span v-if="element.sql_execute && Object.keys(element.sql_execute).length > 0" class="sql-info">SQL操作</span>
              <span v-if="element.custom && Object.keys(element.custom).length > 0" class="custom-info">自定义变量</span>
              <span v-if="element.condition_value && Object.keys(element.condition_value).length > 0" class="condition-info">条件判断</span>
              <span v-if="element.description" class="step-desc" :title="element.description">{{ element.description }}</span>
            </div>
            <div class="step-actions">
              <a-button type="text" size="mini" @click="editStep(element)">
                <template #icon><icon-edit /></template>
              </a-button>
              <a-popconfirm content="确定删除该操作？" @ok="deleteStep(element)">
                <a-button type="text" status="danger" size="mini">
                  <template #icon><icon-delete /></template>
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </template>
      </draggable>
    </a-spin>

    <!-- 添加/编辑操作弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑操作' : '添加操作'"
      :ok-loading="submitting"
      width="700px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="step_type" label="操作类型" required>
          <a-select v-model="formData.step_type" @change="onStepTypeChange">
            <a-option v-for="(label, value) in STEP_TYPE_LABELS" :key="value" :value="Number(value)">
              {{ label }}
            </a-option>
          </a-select>
        </a-form-item>

        <!-- 元素操作 -->
        <template v-if="formData.step_type === 0">
          <a-form-item field="element" label="选择元素">
            <a-select v-model="formData.element" placeholder="请选择元素" allow-search allow-clear>
              <a-option v-for="el in elementOptions" :key="el.id" :value="el.id">
                {{ el.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="ope_key" label="操作方法">
            <a-select v-model="formData.ope_key" allow-search @change="onOpeKeyChange">
              <a-optgroup label="鼠标操作">
                <a-option value="click">点击 (click)</a-option>
                <a-option value="dblclick">双击 (dblclick)</a-option>
                <a-option value="hover">悬停 (hover)</a-option>
              </a-optgroup>
              <a-optgroup label="输入操作">
                <a-option value="fill">填充 (fill)</a-option>
                <a-option value="type">输入 (type)</a-option>
                <a-option value="clear">清空 (clear)</a-option>
              </a-optgroup>
              <a-optgroup label="其他">
                <a-option value="wait">等待 (wait)</a-option>
                <a-option value="screenshot">截图 (screenshot)</a-option>
                <a-option value="select_option">选择下拉 (select_option)</a-option>
              </a-optgroup>
            </a-select>
          </a-form-item>
          <!-- 根据操作类型动态渲染参数表单 -->
          <template v-if="currentOpeParams.length > 0">
            <a-form-item
              v-for="param in currentOpeParams"
              :key="param.field"
              :field="'opeParams.' + param.field"
              :label="param.label"
              :required="param.required"
            >
              <a-input
                v-if="param.type === 'input'"
                v-model="opeParams[param.field]"
                :placeholder="param.placeholder"
              />
              <a-input-number
                v-else-if="param.type === 'number'"
                v-model="opeParams[param.field]"
                :placeholder="param.placeholder"
                :min="param.min"
                :max="param.max"
              />
              <a-textarea
                v-else-if="param.type === 'textarea'"
                v-model="opeParams[param.field]"
                :placeholder="param.placeholder"
                :auto-size="{ minRows: 2, maxRows: 5 }"
              />
            </a-form-item>
          </template>
        </template>

        <!-- 断言操作 -->
        <template v-else-if="formData.step_type === 1">
          <a-form-item field="element" label="断言元素">
            <a-select v-model="formData.element" placeholder="请选择元素" allow-search allow-clear>
              <a-option v-for="el in elementOptions" :key="el.id" :value="el.id">
                {{ el.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="ope_key" label="断言方法">
            <a-select v-model="formData.ope_key" @change="onOpeKeyChange">
              <a-option value="assert_visible">元素可见</a-option>
              <a-option value="assert_hidden">元素隐藏</a-option>
              <a-option value="assert_text">文本断言</a-option>
              <a-option value="assert_value">值断言</a-option>
              <a-option value="assert_count">数量断言</a-option>
            </a-select>
          </a-form-item>
          <!-- 根据断言类型动态渲染参数 -->
          <template v-if="currentOpeParams.length > 0">
            <a-form-item
              v-for="param in currentOpeParams"
              :key="param.field"
              :label="param.label"
              :required="param.required"
            >
              <a-input
                v-if="param.type === 'input'"
                v-model="opeParams[param.field]"
                :placeholder="param.placeholder"
              />
              <a-input-number
                v-else-if="param.type === 'number'"
                v-model="opeParams[param.field]"
                :placeholder="param.placeholder"
                :min="param.min"
                :max="param.max"
              />
            </a-form-item>
          </template>
        </template>

        <!-- SQL 操作 -->
        <template v-else-if="formData.step_type === 2">
          <a-form-item field="sql_execute" label="SQL 配置">
            <a-textarea v-model="sqlExecuteStr" placeholder="JSON 格式 SQL 配置" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <!-- 自定义变量 -->
        <template v-else-if="formData.step_type === 3">
          <a-form-item field="custom" label="自定义变量">
            <a-textarea v-model="customStr" placeholder="JSON 格式变量定义" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <!-- 条件判断 -->
        <template v-else-if="formData.step_type === 4">
          <a-form-item field="condition_value" label="条件配置">
            <a-textarea v-model="conditionValueStr" placeholder="JSON 格式条件配置" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <a-form-item field="description" label="描述">
          <a-input v-model="formData.description" placeholder="可选描述" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconDragDotVertical, IconPlayArrow } from '@arco-design/web-vue/es/icon'
import draggable from 'vuedraggable'
import { pageStepsDetailedApi, elementApi, actuatorApi, envConfigApi, type ActuatorInfo } from '../api'
import type { UiPageStepsDetailed, UiPageSteps, UiElement, StepType, UiEnvironmentConfig } from '../types'
import { STEP_TYPE_LABELS, extractListData, extractResponseData } from '../types'
import { uiWebSocket, UiSocketEnum } from '../services/websocket'

/** 操作参数定义 */
interface OpeParamDef {
  field: string
  label: string
  type: 'input' | 'number' | 'textarea'
  placeholder: string
  required?: boolean
  min?: number
  max?: number
}

/** 操作方法与参数的映射 */
const OPE_PARAMS_MAP: Record<string, OpeParamDef[]> = {
  // 元素操作
  fill: [{ field: 'text', label: '输入内容', type: 'input', placeholder: '请输入要填充的文本', required: true }],
  type: [{ field: 'text', label: '输入内容', type: 'input', placeholder: '请输入要键入的文本', required: true }],
  wait: [{ field: 'timeout', label: '等待时间(毫秒)', type: 'number', placeholder: '默认1000', min: 0, max: 60000 }],
  screenshot: [{ field: 'name', label: '截图文件名', type: 'input', placeholder: '可选，留空自动生成' }],
  select_option: [{ field: 'value', label: '选项值', type: 'input', placeholder: '请输入要选择的选项值', required: true }],
  // 断言操作
  assert_text: [{ field: 'expected', label: '期望文本', type: 'input', placeholder: '请输入期望的文本内容', required: true }],
  assert_value: [{ field: 'expected', label: '期望值', type: 'input', placeholder: '请输入期望的值', required: true }],
  assert_count: [{ field: 'expected', label: '期望数量', type: 'number', placeholder: '请输入期望的元素数量', required: true, min: 0 }],
}

/** 操作方法标签映射 */
const OPE_KEY_LABELS: Record<string, string> = {
  click: '点击',
  dblclick: '双击',
  hover: '悬停',
  fill: '填充',
  type: '输入',
  clear: '清空',
  wait: '等待',
  screenshot: '截图',
  select_option: '选择下拉',
  assert_visible: '元素可见',
  assert_hidden: '元素隐藏',
  assert_text: '文本断言',
  assert_value: '值断言',
  assert_count: '数量断言',
}

/** 格式化操作值显示 */
const formatOpeValue = (opeValue: Record<string, any>) => {
  const entries = Object.entries(opeValue).filter(([, v]) => v !== null && v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${typeof v === 'string' && v.length > 30 ? v.slice(0, 30) + '...' : v}`).join(', ')
}

/** 获取操作方法的显示标签 */
const getOpeKeyLabel = (opeKey: string) => OPE_KEY_LABELS[opeKey] || opeKey

const props = defineProps<{ pageStep: UiPageSteps }>()

const loading = ref(false)
const submitting = ref(false)
const stepData = ref<UiPageStepsDetailed[]>([])
const elementOptions = ref<UiElement[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const currentStep = ref<UiPageStepsDetailed | null>(null)
const formRef = ref()

// 执行器相关
const actuators = ref<ActuatorInfo[]>([])
const selectedActuator = ref<string>('')
const executing = ref(false)

// 执行环境相关
const envConfigs = ref<UiEnvironmentConfig[]>([])
const selectedEnvConfig = ref<number | undefined>(undefined)

const formData = reactive<Partial<UiPageStepsDetailed>>({
  step_type: 0,
  element: null,
  ope_key: '',
  ope_value: {},
  sql_execute: {},
  custom: {},
  condition_value: {},
  func: '',
  description: '',
})

const opeParams = reactive<Record<string, any>>({})
const sqlExecuteStr = ref('{}')
const customStr = ref('{}')
const conditionValueStr = ref('{}')

/** 当前操作方法的参数定义 */
const currentOpeParams = computed(() => {
  return OPE_PARAMS_MAP[formData.ope_key || ''] || []
})

/** 操作方法变更时重置参数 */
const onOpeKeyChange = () => {
  Object.keys(opeParams).forEach(k => delete opeParams[k])
}

const rules = {
  step_type: [{ required: true, message: '请选择操作类型' }],
  // 动态验证规则将在提交时检查
}

const stepTypeColors: Record<StepType, string> = {
  0: 'arcoblue',
  1: 'orange',
  2: 'purple',
  3: 'green',
  4: 'magenta',
}

const fetchSteps = async () => {
  loading.value = true
  try {
    const res = await pageStepsDetailedApi.list({ page_step: props.pageStep.id })
    stepData.value = extractListData<UiPageStepsDetailed>(res)
  } catch {
    Message.error('获取操作步骤失败')
  } finally {
    loading.value = false
  }
}

const fetchActuators = async () => {
  try {
    const res = await actuatorApi.list()
    const data = extractResponseData<{ count: number; items: ActuatorInfo[] }>(res)
    actuators.value = data?.items ?? []
    // 自动选择第一个在线的执行器
    if (!selectedActuator.value && actuators.value.length > 0) {
      const available = actuators.value.find((a: ActuatorInfo) => a.is_open)
      if (available) selectedActuator.value = available.id
    }
  } catch {
    // 静默失败
  }
}

/** 获取执行环境列表 */
const fetchEnvConfigs = async () => {
  try {
    // 从页面步骤获取关联的项目ID
    const res = await envConfigApi.list({ project: props.pageStep.project })
    envConfigs.value = extractListData<UiEnvironmentConfig>(res)
    // 优先选择默认环境，如果没有默认环境则选择第一个环境配置
    if (!selectedEnvConfig.value && envConfigs.value.length > 0) {
      const defaultEnv = envConfigs.value.find(e => e.is_default)
      if (defaultEnv) {
        selectedEnvConfig.value = defaultEnv.id
      } else {
        // 如果没有默认环境，选择第一个环境配置
        selectedEnvConfig.value = envConfigs.value[0].id
      }
    }
  } catch {
    // 静默失败
  }
}

/** 执行页面步骤 */
const executePageStep = async () => {
  // 防止重复执行
  if (executing.value) {
    return
  }
  if (!selectedActuator.value) {
    Message.warning('请先选择执行器')
    return
  }
  if (stepData.value.length === 0) {
    Message.warning('该页面步骤没有操作')
    return
  }
  
  executing.value = true
  
  // 确保 WebSocket 已连接
  if (!uiWebSocket.connected.value) {
    try {
      await uiWebSocket.connect()
    } catch {
      Message.error('WebSocket 连接失败，请刷新页面重试')
      executing.value = false
      return
    }
  }
  
  const sent = uiWebSocket.send(UiSocketEnum.PAGE_STEPS, {
    page_step_id: props.pageStep.id,
    env_config_id: selectedEnvConfig.value,
    actuator_id: selectedActuator.value,
  })
  
  if (!sent) {
    Message.error('发送执行命令失败')
    executing.value = false
  }
}

/** 处理页面步骤执行结果 */
const handleStepResult = (data: any) => {
  executing.value = false
  const result = data.data?.func_args
  if (!result) return
  
  if (result.status === 'success') {
    Message.success(`执行成功: ${result.passed_steps || 0}/${result.total_steps || 0} 步骤通过`)
  } else {
    Message.error(`执行失败: ${result.message || '未知错误'}`)
  }
}

const fetchElements = async () => {
  try {
    const res = await elementApi.list({ page: props.pageStep.page })
    elementOptions.value = extractListData<UiElement>(res)
  } catch {
    Message.error('获取元素列表失败')
  }
}

const resetForm = () => {
  Object.assign(formData, {
    step_type: 0,
    element: null,
    ope_key: '',
    ope_value: {},
    sql_execute: {},
    custom: {},
    condition_value: {},
    func: '',
    description: '',
  })
  Object.keys(opeParams).forEach(k => delete opeParams[k])
  sqlExecuteStr.value = '{}'
  customStr.value = '{}'
  conditionValueStr.value = '{}'
  formRef.value?.clearValidate()
}

const onStepTypeChange = () => {
  formData.ope_key = ''
  formData.element = null
}

const showAddModal = () => {
  isEdit.value = false
  resetForm()
  modalVisible.value = true
}

const editStep = (step: UiPageStepsDetailed) => {
  isEdit.value = true
  currentStep.value = step
  Object.assign(formData, {
    step_type: step.step_type,
    element: step.element,
    ope_key: step.ope_key || '',
    ope_value: step.ope_value || {},
    sql_execute: step.sql_execute || {},
    custom: step.custom || {},
    condition_value: step.condition_value || {},
    func: step.func || '',
    description: step.description || '',
  })
  // 从 ope_value 还原参数到 opeParams
  Object.keys(opeParams).forEach(k => delete opeParams[k])
  if (step.ope_value && typeof step.ope_value === 'object') {
    Object.assign(opeParams, step.ope_value)
    
    // 兼容性处理：如果 ope_value 使用 'value' 字段而不是 'text' 字段，进行转换
    if (step.ope_key === 'fill' && step.ope_value.value !== undefined && step.ope_value.text === undefined) {
      // 将 value 字段的内容复制到 text 字段，以兼容前端表单
      opeParams.text = step.ope_value.value
    }
  }
  sqlExecuteStr.value = JSON.stringify(step.sql_execute || {}, null, 2)
  customStr.value = JSON.stringify(step.custom || {}, null, 2)
  conditionValueStr.value = JSON.stringify(step.condition_value || {}, null, 2)
  modalVisible.value = true
}

const parseJson = (str: string, defaultVal: Record<string, unknown> = {}) => {
  try {
    return JSON.parse(str)
  } catch {
    return defaultVal
  }
}

/** 构建 ope_value：从 opeParams 中过滤空值 */
const buildOpeValue = () => {
  const result: Record<string, any> = {}
  for (const [k, v] of Object.entries(opeParams)) {
    if (v !== '' && v !== undefined && v !== null) {
      result[k] = v
    }
  }
  
  // 兼容性处理：对于 fill 操作，如果存在 text 字段，也同步到 value 字段
  // 这样后端执行器可以正确识别两种格式
  if (formData.ope_key === 'fill' && result.text !== undefined) {
    result.value = result.text
  }
  
  return Object.keys(result).length > 0 ? result : undefined
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }
  
  // 额外的业务逻辑校验：对于 fill 操作，必须填写输入内容
  if (formData.ope_key === 'fill') {
    const textValue = opeParams.text
    if (!textValue || textValue.trim() === '') {
      Message.warning('请输入内容')
      done(false)
      return
    }
  }
  submitting.value = true
  try {
    const data: Omit<UiPageStepsDetailed, 'id' | 'created_at' | 'updated_at'> = {
      page_step: props.pageStep.id,
      step_type: formData.step_type as StepType,
      element: formData.element || null,
      step_sort: isEdit.value && currentStep.value ? currentStep.value.step_sort : stepData.value.length,
      ope_key: formData.ope_key || undefined,
      ope_value: buildOpeValue(),
      sql_execute: parseJson(sqlExecuteStr.value),
      custom: parseJson(customStr.value),
      condition_value: parseJson(conditionValueStr.value),
      func: formData.func || undefined,
      description: formData.description || undefined,
    }

    if (isEdit.value && currentStep.value?.id) {
      await pageStepsDetailedApi.update(currentStep.value.id, data)
      Message.success('更新成功')
    } else {
      await pageStepsDetailedApi.create(data)
      Message.success('添加成功')
    }
    done(true)
    fetchSteps()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? '更新失败' : '添加失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteStep = async (step: UiPageStepsDetailed) => {
  if (!step.id) return
  try {
    await pageStepsDetailedApi.delete(step.id)
    Message.success('删除成功')
    fetchSteps()
  } catch {
    Message.error('删除失败')
  }
}

const onDragEnd = async () => {
  try {
    const steps = stepData.value.map((s, idx) => ({
      step_type: s.step_type,
      element: s.element,
      step_sort: idx,
      ope_key: s.ope_key,
      ope_value: s.ope_value,
      sql_execute: s.sql_execute,
      custom: s.custom,
      condition_value: s.condition_value,
      func: s.func,
      description: s.description,
    }))
    await pageStepsDetailedApi.batchUpdate(props.pageStep.id, steps)
    Message.success('排序已保存')
  } catch {
    Message.error('保存排序失败')
    fetchSteps()
  }
}

// WebSocket 事件监听
let offStepResult: (() => void) | null = null

watch(() => props.pageStep, async () => {
  fetchSteps()
  fetchElements()
  // 同时获取环境配置和执行器列表，并自动选择默认值
  await Promise.all([
    fetchActuators(),
    fetchEnvConfigs()
  ])
}, { immediate: true })

onMounted(() => {
  fetchActuators()
  fetchEnvConfigs()
  // 监听页面步骤执行结果
  offStepResult = uiWebSocket.on(UiSocketEnum.PAGE_STEP_RESULT, handleStepResult)
})

onUnmounted(() => {
  offStepResult?.()
})
</script>

<style scoped>
.step-detail-list {
  padding: 8px 0;
  overflow-x: hidden;
}
.step-detail-list :deep(.arco-spin) {
  width: 100%;
}
.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.step-title {
  font-weight: 500;
}
.empty-tips {
  padding: 40px 0;
}
.step-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-sizing: border-box;
  min-height: 48px;
  font-size: 13px;
  gap: 12px;
}
.step-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.drag-handle {
  cursor: move;
  color: var(--color-text-3);
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
}
.step-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-fill-3);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  margin-right: 10px;
}
.step-type {
  flex-shrink: 0;
}
.step-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.info-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.info-label {
  color: var(--color-text-3);
  font-size: 12px;
  flex-shrink: 0;
}
.element-name {
  color: rgb(var(--primary-6));
  font-weight: 500;
}
.ope-key {
  background: var(--color-fill-2);
  padding: 2px 6px;
  border-radius: 3px;
}
.ope-value {
  color: var(--color-text-2);
  background: var(--color-fill-1);
  padding: 2px 6px;
  border-radius: 3px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sql-info,
.custom-info,
.condition-info {
  background: rgb(var(--orange-2));
  color: rgb(var(--orange-6));
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}
.step-desc {
  color: var(--color-text-3);
  font-style: italic;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>

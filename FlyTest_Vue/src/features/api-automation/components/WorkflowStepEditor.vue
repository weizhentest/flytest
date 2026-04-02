<template>
  <div class="workflow-step-editor">
    <div class="workflow-step-editor__header">
      <div>
        <div class="workflow-step-editor__title">工作流步骤</div>
        <div class="workflow-step-editor__description">
          执行顺序按列表从上到下。`prepare` 和 `request` 会在主请求前执行，`teardown` 会在主请求后执行。
        </div>
      </div>
      <a-button type="outline" @click="addStep">新增步骤</a-button>
    </div>

    <a-spin :loading="loading" class="workflow-step-editor__spin">
      <div v-if="!localSteps.length" class="workflow-step-editor__empty">
        暂无工作流步骤。适合补登录、令牌准备、上下文预处理、收尾清理等场景。
      </div>

      <div v-for="(step, index) in localSteps" :key="step.key" class="workflow-step-card">
        <div class="workflow-step-card__header">
          <div class="workflow-step-card__summary">
            <a-space :size="8" wrap>
              <a-tag size="small" color="arcoblue">#{{ index + 1 }}</a-tag>
              <a-tag :color="stageColorMap[step.stage]">{{ stageLabelMap[step.stage] }}</a-tag>
              <a-tag v-if="!step.enabled" color="gray">已停用</a-tag>
            </a-space>
            <div class="workflow-step-card__name">{{ step.name || `步骤 ${index + 1}` }}</div>
            <div class="workflow-step-card__meta">{{ getStepRequestSummary(step) }}</div>
          </div>

          <a-space wrap>
            <a-button type="text" size="small" :disabled="index === 0" @click="moveStep(index, -1)">上移</a-button>
            <a-button
              type="text"
              size="small"
              :disabled="index === localSteps.length - 1"
              @click="moveStep(index, 1)"
            >
              下移
            </a-button>
            <a-button type="text" size="small" @click="toggleExpanded(step.key)">
              {{ isExpanded(step.key) ? '收起' : '展开' }}
            </a-button>
            <a-button type="text" size="small" status="danger" @click="removeStep(index)">删除</a-button>
          </a-space>
        </div>

        <div v-if="isExpanded(step.key)" class="workflow-step-card__body">
          <a-row :gutter="16">
            <a-col :xs="24" :md="12" :xl="8">
              <a-form-item label="步骤名称">
                <a-input v-model="step.name" placeholder="例如：登录获取 token" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12" :xl="6">
              <a-form-item label="步骤阶段">
                <a-select v-model="step.stage">
                  <a-option value="prepare" label="prepare" />
                  <a-option value="request" label="request" />
                  <a-option value="teardown" label="teardown" />
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12" :xl="10">
              <a-form-item label="目标接口">
                <a-select
                  :model-value="getStepRequestValue(step)"
                  allow-search
                  placeholder="选择这个步骤要执行的接口"
                  @change="value => handleRequestChange(step, value)"
                >
                  <a-option :value="MAIN_REQUEST_VALUE" :label="mainRequestOptionLabel" />
                  <a-option
                    v-for="request in availableRequests"
                    :key="request.id"
                    :value="request.id"
                    :label="formatRequestOptionLabel(request)"
                  />
                  <a-option
                    v-if="step.request_id && !resolveRequestById(step.request_id)"
                    :value="step.request_id"
                    :label="step.request_name || `已失效接口 #${step.request_id}`"
                  />
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12" :xl="6">
              <a-form-item label="启用步骤">
                <a-switch v-model="step.enabled" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12" :xl="6">
              <a-form-item label="失败后继续">
                <a-switch v-model="step.continue_on_failure" />
              </a-form-item>
            </a-col>
          </a-row>

          <div v-if="step.request_id && !resolveRequestById(step.request_id)" class="workflow-step-card__warning">
            当前步骤绑定的接口已不存在，请重新选择目标接口后再保存。
          </div>

          <div class="workflow-step-card__note">
            这里编辑的是该步骤的实际执行请求。保存时会自动和目标接口做比对，没有变化的内容不会重复写入。
          </div>

          <StructuredHttpEditor v-model="step.editor" :show-request-target="false" />
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import StructuredHttpEditor from './StructuredHttpEditor.vue'
import { createWorkflowStepEditorStep, workflowStepToHttpEditorModel } from '../state/httpEditor'
import type { ApiRequest, ApiTestCaseWorkflowEditorStep, ApiTestCaseWorkflowStage } from '../types'

const MAIN_REQUEST_VALUE = '__main_request__'

const props = withDefaults(
  defineProps<{
    modelValue: ApiTestCaseWorkflowEditorStep[]
    requests?: ApiRequest[]
    mainRequest?: ApiRequest | null
    loading?: boolean
  }>(),
  {
    requests: () => [],
    mainRequest: null,
    loading: false,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: ApiTestCaseWorkflowEditorStep[]): void
}>()

const stageLabelMap: Record<ApiTestCaseWorkflowStage, string> = {
  prepare: 'Prepare',
  request: 'Request',
  teardown: 'Teardown',
}

const stageColorMap: Record<ApiTestCaseWorkflowStage, string> = {
  prepare: 'arcoblue',
  request: 'green',
  teardown: 'orange',
}

const cloneSteps = (value: ApiTestCaseWorkflowEditorStep[]) =>
  JSON.parse(JSON.stringify(value || [])) as ApiTestCaseWorkflowEditorStep[]

const localSteps = ref<ApiTestCaseWorkflowEditorStep[]>([])
const expandedKeys = ref<string[]>([])
const seenKeys = new Set<string>()
let syncingFromProps = false

const availableRequests = computed(() =>
  (props.requests || []).filter(item => !props.mainRequest || item.id !== props.mainRequest.id)
)

const mainRequestOptionLabel = computed(() => {
  if (!props.mainRequest) return '当前测试用例主接口'
  return `当前测试用例主接口 · ${formatRequestOptionLabel(props.mainRequest)}`
})

watch(
  () => props.modelValue,
  value => {
    syncingFromProps = true
    localSteps.value = cloneSteps(value)
    Promise.resolve().then(() => {
      syncingFromProps = false
    })
  },
  { deep: true, immediate: true }
)

watch(
  localSteps,
  value => {
    if (syncingFromProps) return
    emit('update:modelValue', cloneSteps(value))
  },
  { deep: true }
)

watch(
  () => localSteps.value.map(step => step.key).join('|'),
  () => {
    const currentKeys = localSteps.value.map(step => step.key)
    expandedKeys.value = expandedKeys.value.filter(key => currentKeys.includes(key))

    currentKeys.forEach(key => {
      if (!seenKeys.has(key)) {
        seenKeys.add(key)
        expandedKeys.value.push(key)
      }
    })
  },
  { immediate: true }
)

const resolveRequestById = (requestId?: number | null) => {
  if (requestId === null || requestId === undefined) return props.mainRequest || null
  return (props.requests || []).find(item => item.id === Number(requestId)) || null
}

const formatRequestOptionLabel = (request: ApiRequest) => {
  const collectionText = request.collection_name ? `${request.collection_name} / ` : ''
  return `${collectionText}${request.name} (${request.method} ${request.url})`
}

const getStepRequestSummary = (step: ApiTestCaseWorkflowEditorStep) => {
  const request = resolveRequestById(step.request_id)
  if (step.request_id && !request) {
    return step.request_name ? `已失效接口 · ${step.request_name}` : `已失效接口 #${step.request_id}`
  }
  if (!step.request_id) {
    return props.mainRequest ? `主接口 · ${formatRequestOptionLabel(props.mainRequest)}` : '主接口'
  }
  return request ? formatRequestOptionLabel(request) : step.request_name || '-'
}

const getStepRequestValue = (step: ApiTestCaseWorkflowEditorStep) => step.request_id ?? MAIN_REQUEST_VALUE

const isExpanded = (key: string) => expandedKeys.value.includes(key)

const toggleExpanded = (key: string) => {
  if (isExpanded(key)) {
    expandedKeys.value = expandedKeys.value.filter(item => item !== key)
    return
  }
  expandedKeys.value = [...expandedKeys.value, key]
}

const addStep = () => {
  localSteps.value.push(
    createWorkflowStepEditorStep(
      {},
      {
        request: props.mainRequest,
        mainRequest: props.mainRequest,
        index: localSteps.value.length,
      }
    )
  )
}

const removeStep = (index: number) => {
  localSteps.value.splice(index, 1)
}

const moveStep = (index: number, offset: number) => {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= localSteps.value.length) return
  const cloned = [...localSteps.value]
  ;[cloned[index], cloned[targetIndex]] = [cloned[targetIndex], cloned[index]]
  localSteps.value = cloned
}

const handleRequestChange = (step: ApiTestCaseWorkflowEditorStep, value: string | number | boolean) => {
  const currentIndex = localSteps.value.findIndex(item => item.key === step.key)
  const previousRequest = resolveRequestById(step.request_id)
  const previousName = step.name.trim()
  const nextRequestId = value === MAIN_REQUEST_VALUE ? null : Number(value)
  const nextRequest = resolveRequestById(nextRequestId)
  const defaultStepName = `步骤 ${currentIndex + 1}`

  step.request_id =
    nextRequestId && props.mainRequest && nextRequestId === props.mainRequest.id ? null : (nextRequestId ?? null)
  step.request_name = step.request_id ? nextRequest?.name || step.request_name || '' : ''
  step.editor = workflowStepToHttpEditorModel(undefined, nextRequest || props.mainRequest || null)

  const autoGeneratedNames = new Set([defaultStepName, previousRequest?.name || '', props.mainRequest?.name || ''])
  if (!previousName || autoGeneratedNames.has(previousName)) {
    step.name = nextRequest?.name || props.mainRequest?.name || defaultStepName
  }
}
</script>

<style scoped>
.workflow-step-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workflow-step-editor__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.82), rgba(255, 255, 255, 0.96));
}

.workflow-step-editor__title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.workflow-step-editor__description {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.workflow-step-editor__spin,
.workflow-step-editor__spin :deep(.arco-spin-children) {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workflow-step-editor__empty {
  padding: 20px;
  border: 1px dashed rgba(148, 163, 184, 0.36);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.75);
  color: #64748b;
}

.workflow-step-card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.workflow-step-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(255, 255, 255, 0.92));
}

.workflow-step-card__summary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workflow-step-card__name {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.workflow-step-card__meta {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-word;
}

.workflow-step-card__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

.workflow-step-card__warning {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(254, 242, 242, 0.92);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
}

.workflow-step-card__note {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(239, 246, 255, 0.92);
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .workflow-step-editor__header,
  .workflow-step-card__header {
    flex-direction: column;
  }
}
</style>

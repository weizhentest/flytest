<template>
  <a-card class="canvas-panel">
    <template #title>场景步骤</template>
    <template #extra>
      <a-space>
        <span class="step-counter">共 {{ steps.length }} 步</span>
        <a-button size="mini" status="danger" :disabled="!steps.length" @click="emit('clear-steps')">清空</a-button>
      </a-space>
    </template>

    <div v-if="steps.length" class="step-list">
      <draggable
        :model-value="steps"
        item-key="id"
        handle=".drag-handle"
        class="draggable-root"
        :animation="180"
        @update:model-value="updateSteps"
      >
        <template #item="{ element, index }">
          <div class="step-item-wrapper">
            <div
              class="step-item"
              :class="{ active: selectedStepIndex === index && selectedSubStepIndex === null }"
              @click="emit('select-step', index)"
            >
              <div class="step-main">
                <span class="drag-handle">⋮⋮</span>
                <span class="step-index">{{ index + 1 }}</span>
                <div class="step-copy">
                  <strong>{{ element.name || resolveStepTitle(element) }}</strong>
                  <span>{{ resolveStepMeta(element) }}</span>
                </div>
                <a-tag v-if="isCustomStep(element)" size="small">自定义组件</a-tag>
                <a-tag v-else-if="isFlowContainerStep(element)" size="small">流程容器</a-tag>
              </div>
              <a-space>
                <a-button v-if="isContainerStep(element)" size="mini" type="text" @click.stop="emit('toggle-expand', index)">
                  {{ element._expanded ? '收起' : '展开' }}
                </a-button>
                <a-button size="mini" type="text" @click.stop="emit('duplicate-step', index)">复制</a-button>
                <a-button size="mini" type="text" status="danger" @click.stop="emit('remove-step', index)">
                  删除
                </a-button>
              </a-space>
            </div>

            <div v-if="isContainerStep(element) && element._expanded" class="sub-step-shell">
              <div
                v-for="group in getStepChildGroups(element)"
                :key="`${getNodeKey(element)}-${group.key}`"
                class="sub-step-group"
              >
                <div class="sub-step-group-header">
                  <div class="sub-step-group-copy">
                    <strong>{{ group.label }}</strong>
                    <span>{{ getStepGroupSteps(element, group.key).length }} 个子步骤</span>
                  </div>
                  <div class="sub-step-toolbar">
                    <a-select
                      :model-value="subStepSelections[getSubStepSelectionKey(element, group.key)]"
                      allow-search
                      placeholder="选择基础组件后添加为子步骤"
                      @change="value => handleSubStepSelectionChange(element, group.key, value)"
                    >
                      <a-option v-for="item in components" :key="item.id" :value="item.type">
                        {{ item.name }}
                      </a-option>
                    </a-select>
                    <a-button size="mini" type="primary" @click.stop="emit('add-sub-step', { index, groupKey: group.key })">
                      添加子步骤
                    </a-button>
                  </div>
                </div>

                <draggable
                  :model-value="getStepGroupSteps(element, group.key)"
                  item-key="id"
                  handle=".drag-handle"
                  class="sub-step-list"
                  :animation="160"
                  @update:model-value="items => emit('update-step-group-items', { step: element, groupKey: group.key, items })"
                >
                  <template #item="{ element: subStep, index: subIndex }">
                    <div
                      class="sub-step-item"
                      :class="{
                        active:
                          selectedStepIndex === index &&
                          selectedSubStepGroupKey === group.key &&
                          selectedSubStepIndex === subIndex,
                      }"
                      @click.stop="emit('select-sub-step', { index, groupKey: group.key, subIndex })"
                    >
                      <div class="step-main">
                        <span class="drag-handle">⋮⋮</span>
                        <span class="step-index sub-index">{{ index + 1 }}.{{ subIndex + 1 }}</span>
                        <div class="step-copy">
                          <strong>{{ subStep.name || resolveStepTitle(subStep) }}</strong>
                          <span>{{ resolveStepMeta(subStep) }}</span>
                        </div>
                        <a-tag v-if="isFlowContainerStep(subStep)" size="small">流程</a-tag>
                      </div>
                      <a-space>
                        <a-button
                          size="mini"
                          type="text"
                          @click.stop="emit('duplicate-sub-step', { index, groupKey: group.key, subIndex })"
                        >
                          复制
                        </a-button>
                        <a-button
                          size="mini"
                          type="text"
                          status="danger"
                          @click.stop="emit('remove-sub-step', { index, groupKey: group.key, subIndex })"
                        >
                          删除
                        </a-button>
                      </a-space>
                    </div>
                  </template>
                </draggable>

                <a-empty v-if="!getStepGroupSteps(element, group.key).length" description="当前分支还没有子步骤" />
              </div>
            </div>
          </div>
        </template>
      </draggable>
    </div>
    <a-empty v-else description="从左侧添加步骤，快速搭建 APP 自动化场景" />
  </a-card>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import type { AppComponent, AppSceneStep } from '../../types'
import {
  getNodeKey,
  getStepChildGroups,
  getStepGroupSteps,
  getSubStepSelectionKey,
  isCustomStep,
  isFlowContainerStep,
  type StepChildGroupKey,
} from './sceneBuilderDraft'

interface Props {
  steps: AppSceneStep[]
  selectedStepIndex: number | null
  selectedSubStepIndex: number | null
  selectedSubStepGroupKey: StepChildGroupKey | null
  subStepSelections: Record<string, string | undefined>
  components: AppComponent[]
  resolveStepTitle: (step?: Partial<AppSceneStep>) => string
  resolveStepMeta: (step?: Partial<AppSceneStep>) => string
}

interface IndexedSubStepPayload {
  index: number
  groupKey: StepChildGroupKey
  subIndex: number
}

interface UpdateStepGroupItemsPayload {
  step: AppSceneStep
  groupKey: StepChildGroupKey
  items: AppSceneStep[]
}

interface UpdateSubStepSelectionPayload {
  key: string
  value?: string
}

defineProps<Props>()

const emit = defineEmits<{
  'update:steps': [items: AppSceneStep[]]
  'select-step': [index: number]
  'toggle-expand': [index: number]
  'duplicate-step': [index: number]
  'remove-step': [index: number]
  'clear-steps': []
  'select-sub-step': [payload: IndexedSubStepPayload]
  'update-sub-step-selection': [payload: UpdateSubStepSelectionPayload]
  'add-sub-step': [payload: { index: number; groupKey: StepChildGroupKey }]
  'duplicate-sub-step': [payload: IndexedSubStepPayload]
  'remove-sub-step': [payload: IndexedSubStepPayload]
  'update-step-group-items': [payload: UpdateStepGroupItemsPayload]
}>()

const draggable = defineAsyncComponent(() => import('vuedraggable'))

const isContainerStep = (step?: Partial<AppSceneStep> | null) => Boolean(step && (isCustomStep(step) || isFlowContainerStep(step)))

const updateSteps = (items: unknown) => {
  emit('update:steps', Array.isArray(items) ? (items as AppSceneStep[]) : [])
}

const handleSubStepSelectionChange = (step: AppSceneStep, groupKey: StepChildGroupKey, value: unknown) => {
  emit('update-sub-step-selection', {
    key: getSubStepSelectionKey(step, groupKey),
    value: value ? String(value) : undefined,
  })
}
</script>

<style scoped>
.canvas-panel {
  min-height: 560px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.step-list,
.draggable-root,
.sub-step-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-item-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item,
.sub-step-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-accent-rgb), 0.04);
  cursor: pointer;
}

.step-item.active,
.sub-step-item.active {
  border-color: rgba(var(--theme-accent-rgb), 0.42);
  box-shadow: 0 12px 28px rgba(var(--theme-accent-rgb), 0.12);
}

.step-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.drag-handle {
  color: var(--theme-text-secondary);
  cursor: move;
  user-select: none;
}

.step-index {
  min-width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(var(--theme-accent-rgb), 0.14);
  color: var(--theme-accent);
  font-weight: 700;
}

.sub-index {
  background: rgba(var(--theme-accent-rgb), 0.22);
}

.step-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.step-copy strong {
  color: var(--theme-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-copy span,
.step-counter {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.sub-step-shell {
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.05);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sub-step-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  background: rgba(var(--theme-accent-rgb), 0.04);
}

.sub-step-group-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sub-step-group-copy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sub-step-group-copy strong {
  color: var(--theme-text);
}

.sub-step-group-copy span {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.sub-step-toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

@media (max-width: 960px) {
  .sub-step-toolbar {
    grid-template-columns: 1fr;
  }

  .sub-step-group-copy {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

import { Message, Modal } from '@arco-design/web-vue'
import { reactive, ref, type Ref } from 'vue'
import { AppAutomationService } from '../../services/appAutomationService'
import type { AppCustomComponent, AppSceneStep } from '../../types'

export type CustomComponentDialogMode = 'create' | 'edit'

interface UseSceneBuilderCustomComponentsOptions {
  steps: Ref<AppSceneStep[]>
  customComponents: Ref<AppCustomComponent[]>
  loadData: () => Promise<void>
  onSaved: () => void
  sanitizeStep: (step: AppSceneStep) => AppSceneStep
  normalizeSteps: (items: unknown, forcedKind?: 'base' | 'custom') => AppSceneStep[]
  containsCustomStep: (step: AppSceneStep) => boolean
  toComponentType: (value: string) => string
}

export const useSceneBuilderCustomComponents = ({
  steps,
  customComponents,
  loadData,
  onSaved,
  sanitizeStep,
  normalizeSteps,
  containsCustomStep,
  toComponentType,
}: UseSceneBuilderCustomComponentsOptions) => {
  const customComponentSaving = ref(false)
  const customComponentVisible = ref(false)
  const customComponentMode = ref<CustomComponentDialogMode>('create')
  const editingCustomComponentId = ref<number | null>(null)

  const customComponentForm = reactive({
    name: '',
    type: '',
    description: '',
    stepsText: '[]',
  })

  const openCreateCustomComponent = () => {
    if (!steps.value.length) {
      Message.warning('请先添加场景步骤')
      return
    }

    if (steps.value.some(item => containsCustomStep(item))) {
      Message.warning('自定义组件中暂不支持嵌套自定义组件')
      return
    }

    customComponentMode.value = 'create'
    editingCustomComponentId.value = null
    customComponentForm.name = ''
    customComponentForm.type = `scene_component_${customComponents.value.length + 1}`
    customComponentForm.description = ''
    customComponentForm.stepsText = JSON.stringify(steps.value.map(item => sanitizeStep(item)), null, 2)
    customComponentVisible.value = true
  }

  const openEditCustomComponent = (component: AppCustomComponent) => {
    customComponentMode.value = 'edit'
    editingCustomComponentId.value = component.id
    customComponentForm.name = component.name
    customComponentForm.type = component.type
    customComponentForm.description = component.description
    customComponentForm.stepsText = JSON.stringify(
      normalizeSteps(component.steps || []).map(item => sanitizeStep(item)),
      null,
      2,
    )
    customComponentVisible.value = true
  }

  const buildCustomComponentSteps = () => {
    let parsed: unknown

    try {
      parsed = JSON.parse(customComponentForm.stepsText || '[]')
    } catch {
      throw new Error('组件步骤 JSON 格式不正确')
    }

    if (!Array.isArray(parsed)) {
      throw new Error('组件步骤 JSON 必须是数组')
    }

    const normalized = normalizeSteps(parsed)
    if (normalized.some(item => containsCustomStep(item))) {
      throw new Error('自定义组件中不支持嵌套自定义组件')
    }

    return normalized.map(item => sanitizeStep(item))
  }

  const saveCustomComponent = async () => {
    const name = customComponentForm.name.trim()
    const type = toComponentType(customComponentForm.type || customComponentForm.name)

    if (!name) {
      Message.warning('请输入组件名称')
      return
    }

    customComponentSaving.value = true
    try {
      const payload = {
        name,
        type,
        description: customComponentForm.description.trim(),
        schema: {},
        default_config: {},
        steps: buildCustomComponentSteps(),
        enabled: true,
        sort_order: customComponents.value.length + 1,
      }

      if (!payload.steps.length) {
        Message.warning('请至少保留一个组件步骤')
        return
      }

      if (customComponentMode.value === 'edit' && editingCustomComponentId.value) {
        const current = customComponents.value.find(item => item.id === editingCustomComponentId.value)
        await AppAutomationService.updateCustomComponent(editingCustomComponentId.value, {
          ...payload,
          enabled: current?.enabled ?? true,
          sort_order: current?.sort_order ?? payload.sort_order,
        })
        Message.success('自定义组件已更新')
      } else {
        await AppAutomationService.createCustomComponent(payload)
        Message.success('自定义组件已创建')
      }

      customComponentVisible.value = false
      await loadData()
      onSaved()
    } catch (error: any) {
      Message.error(error.message || '保存自定义组件失败')
    } finally {
      customComponentSaving.value = false
    }
  }

  const deleteCustomComponent = (component: AppCustomComponent) => {
    Modal.confirm({
      title: '删除自定义组件',
      content: `确认删除自定义组件“${component.name}”吗？`,
      onOk: async () => {
        await AppAutomationService.deleteCustomComponent(component.id)
        Message.success('自定义组件已删除')
        await loadData()
      },
    })
  }

  return {
    customComponentSaving,
    customComponentVisible,
    customComponentMode,
    editingCustomComponentId,
    customComponentForm,
    openCreateCustomComponent,
    openEditCustomComponent,
    buildCustomComponentSteps,
    saveCustomComponent,
    deleteCustomComponent,
  }
}

<template>
  <div class="quick-config-panel">
    <div class="quick-config-head">
      <span class="quick-config-kicker">Device Action</span>
      <div class="quick-config-title">设备动作配置</div>
    </div>

    <a-form-item v-if="selectedStepActionType === 'snapshot'" label="截图标签">
      <a-input
        :model-value="readSelectedConfigString('label')"
        placeholder="可选，不填写时默认使用步骤名称"
        @input="value => updateSelectedStepConfig('label', value || undefined)"
      />
    </a-form-item>

    <template v-if="selectedStepActionType === 'launch_app' || selectedStepActionType === 'stop_app'">
      <a-row :gutter="12">
        <a-col :span="selectedStepActionType === 'launch_app' ? 12 : 24">
          <a-form-item label="应用包名">
            <a-input
              :model-value="readSelectedConfigString('package_name')"
              placeholder="例如：com.example.demo"
              @input="value => updateSelectedStepConfig('package_name', value)"
            />
          </a-form-item>
        </a-col>
        <a-col v-if="selectedStepActionType === 'launch_app'" :span="12">
          <a-form-item label="启动 Activity">
            <a-input
              :model-value="readSelectedConfigString('activity_name')"
              placeholder="可选，例如：MainActivity"
              @input="value => updateSelectedStepConfig('activity_name', value || undefined)"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </template>

    <a-form-item v-if="selectedStepActionType === 'keyevent'" label="Android Keyevent">
      <a-input
        :model-value="readSelectedConfigString('keycode', 'KEYCODE_ENTER')"
        placeholder="例如：KEYCODE_BACK / KEYCODE_HOME / KEYCODE_ENTER"
        @input="value => updateSelectedStepConfig('keycode', value || 'KEYCODE_ENTER')"
      />
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import type {
  SceneBuilderQuickConfigStringProps,
  SceneBuilderSelectedStepActionType,
} from './sceneBuilderQuickConfigModels'

interface Props extends SceneBuilderSelectedStepActionType, SceneBuilderQuickConfigStringProps {}

defineProps<Props>()
</script>

<style scoped>
.quick-config-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.quick-config-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-config-kicker {
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.quick-config-title {
  color: var(--theme-text);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
}

:deep(.arco-form-item) {
  margin-bottom: 0;
}

:deep(.arco-input-wrapper) {
  border-radius: 12px;
}
</style>

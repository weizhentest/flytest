<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑应用包' : '新增应用包'"
    :ok-loading="submitting"
    width="640px"
    @ok="emit('submit')"
  >
    <div class="dialog-shell">
      <div class="dialog-intro">
        <span class="dialog-kicker">App Package</span>
        <strong>{{ form.id ? '维护应用包信息' : '新建可复用应用包' }}</strong>
        <p>统一维护平台、包名和启动 Activity，方便在自动化执行时快速选择目标应用。</p>
      </div>
      <a-form :model="form" layout="vertical" class="dialog-form">
        <div class="form-grid">
          <div class="field-card">
            <a-form-item field="name" label="应用名称">
              <a-input v-model="form.name" placeholder="例如 Android 设置" />
            </a-form-item>
          </div>
          <div class="field-card">
            <a-form-item field="platform" label="平台">
              <a-select v-model="form.platform" placeholder="选择平台">
                <a-option value="android">Android</a-option>
                <a-option value="ios">iOS</a-option>
              </a-select>
            </a-form-item>
          </div>
        </div>
        <div class="field-card">
          <a-form-item field="package_name" label="包名">
            <a-input v-model="form.package_name" placeholder="例如 com.android.settings" />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item field="activity_name" label="启动 Activity">
            <a-input v-model="form.activity_name" placeholder="例如 Settings" />
          </a-form-item>
        </div>
        <div class="field-card">
          <a-form-item field="description" label="描述">
            <a-textarea
              v-model="form.description"
              placeholder="补充该应用包的用途、前置条件或执行时注意事项"
              :auto-size="{ minRows: 3, maxRows: 6 }"
            />
          </a-form-item>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { PackageEditorDialogEmits } from './packageEventModels'
import type { PackageEditorDialogProps } from './packageViewModels'

defineProps<PackageEditorDialogProps>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<PackageEditorDialogEmits>()
</script>

<style scoped>
.dialog-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dialog-intro {
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(var(--theme-accent-rgb), 0.04));
}

.dialog-kicker {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--theme-text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dialog-intro strong {
  display: block;
  color: var(--theme-text);
  font-size: 18px;
  line-height: 1.2;
}

.dialog-intro p {
  margin: 8px 0 0;
  color: var(--theme-text-secondary);
  line-height: 1.7;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.field-card :deep(.arco-form-item) {
  margin-bottom: 0;
}

.field-card :deep(.arco-input-wrapper),
.field-card :deep(.arco-select-view),
.field-card :deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}

:deep(.arco-modal-title) {
  font-size: 18px;
}

:deep(.arco-modal-footer .arco-btn) {
  min-width: 96px;
  border-radius: 12px;
}
</style>

<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑应用包' : '新增应用包'"
    :ok-loading="submitting"
    width="640px"
    @ok="emit('submit')"
  >
    <a-form :model="form" layout="vertical">
      <div class="form-grid">
        <a-form-item field="name" label="应用名称">
          <a-input v-model="form.name" placeholder="例如：Android 设置" />
        </a-form-item>
        <a-form-item field="platform" label="平台">
          <a-select v-model="form.platform" placeholder="选择平台">
            <a-option value="android">Android</a-option>
            <a-option value="ios">iOS</a-option>
          </a-select>
        </a-form-item>
      </div>
      <a-form-item field="package_name" label="包名">
        <a-input v-model="form.package_name" placeholder="例如：com.android.settings" />
      </a-form-item>
      <a-form-item field="activity_name" label="启动 Activity">
        <a-input v-model="form.activity_name" placeholder="例如：.Settings" />
      </a-form-item>
      <a-form-item field="description" label="描述">
        <a-textarea
          v-model="form.description"
          placeholder="补充该应用包的用途、登录前置条件或注意事项"
          :auto-size="{ minRows: 3, maxRows: 6 }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
interface PackageForm {
  id: number
  project_id: number
  name: string
  package_name: string
  activity_name: string
  platform: string
  description: string
}

interface Props {
  form: PackageForm
  submitting: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>

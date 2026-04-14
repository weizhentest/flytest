<template>
  <a-modal
    v-model:visible="visibleModel"
    title="编辑设备信息"
    :confirm-loading="editSaving"
    @ok="emit('submit')"
  >
    <a-form :model="editForm" layout="vertical">
      <a-form-item field="name" label="设备名称">
        <a-input v-model="editForm.name" placeholder="输入设备名称" />
      </a-form-item>
      <a-form-item field="status" label="设备状态">
        <a-select v-model="editForm.status" placeholder="选择设备状态">
          <a-option value="available">可用</a-option>
          <a-option value="online">在线</a-option>
          <a-option value="locked">锁定</a-option>
          <a-option value="offline">离线</a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="location" label="位置">
        <a-input v-model="editForm.location" placeholder="例如 QA 机房 / 本地模拟器" />
      </a-form-item>
      <a-form-item field="description" label="备注">
        <a-textarea v-model="editForm.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
interface EditForm {
  name: string
  description: string
  location: string
  status: string
}

interface Props {
  editForm: EditForm
  editSaving: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  submit: []
}>()
</script>

<template>
  <a-modal v-model:visible="visibleModel" title="添加远程设备" @ok="emit('connect')">
    <a-form :model="connectForm" layout="vertical">
      <a-form-item field="ip_address" label="IP 地址">
        <a-input v-model="connectForm.ip_address" placeholder="例如 192.168.1.15" />
      </a-form-item>
      <a-form-item field="port" label="端口">
        <a-input-number v-model="connectForm.port" :min="1" :max="65535" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
interface ConnectForm {
  ip_address: string
  port: number
}

interface Props {
  connectForm: ConnectForm
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  connect: []
}>()
</script>

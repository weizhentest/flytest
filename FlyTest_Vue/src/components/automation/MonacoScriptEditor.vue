<template>
  <VueMonacoEditor
    :value="props.value"
    :language="props.language"
    theme="vs-dark"
    :options="props.options"
    @update:value="handleValueChange"
  />
</template>

<script setup lang="ts">
import { loader, VueMonacoEditor } from '@guolao/vue-monaco-editor'
import * as monaco from 'monaco-editor'

interface Props {
  value: string
  language: string
  options?: Record<string, unknown>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:value': [value: string]
}>()

let loaderConfigured = false

if (!loaderConfigured) {
  loader.config({ monaco })
  loaderConfigured = true
}

const handleValueChange = (value: string) => {
  emit('update:value', value)
}
</script>

<template>
  <div class="bug-rich-editor">
    <div class="editor-toolbar">
      <div class="editor-toolbar-left">
        <a-button size="mini" @click="execCommand('bold')">B</a-button>
        <a-button size="mini" @click="execCommand('italic')">I</a-button>
        <a-button size="mini" @click="execCommand('underline')">U</a-button>
        <a-button size="mini" @click="execCommand('insertUnorderedList')">无序列表</a-button>
        <a-button size="mini" @click="execCommand('insertOrderedList')">有序列表</a-button>
        <a-button size="mini" @click="insertLink">链接</a-button>
      </div>

      <div class="editor-toolbar-right">
        <slot name="toolbar-extra" />
        <a-button size="mini" @click="triggerFileInput">上传附件</a-button>
      </div>
    </div>

    <div
      ref="editorRef"
      class="editor-surface"
      contenteditable="true"
      :data-placeholder="placeholder"
      @input="handleInput"
      @blur="handleInput"
    />

    <input
      ref="fileInputRef"
      type="file"
      multiple
      class="hidden-file-input"
      accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.zip,.rar,.7z"
      @change="handleFileChange"
    />

    <div v-if="attachments.length" class="attachment-list">
      <div v-for="attachment in attachments" :key="attachment.id" class="attachment-item">
        <template v-if="attachment.file_type === 'image'">
          <a :href="attachment.url" target="_blank" rel="noreferrer">
            <img :src="attachment.url" :alt="attachment.original_name" class="attachment-image" />
          </a>
        </template>
        <template v-else-if="attachment.file_type === 'video'">
          <video class="attachment-video" controls :src="attachment.url" />
        </template>
        <template v-else>
          <a :href="attachment.url" target="_blank" rel="noreferrer" class="attachment-file-link">
            {{ attachment.original_name }}
          </a>
        </template>

        <div class="attachment-meta">
          <span class="attachment-name">{{ attachment.original_name }}</span>
          <a-button size="mini" status="danger" @click="$emit('remove-attachment', attachment)">删除</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import type { TestBugAttachment } from '@/services/testBugService';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    placeholder?: string;
    attachments?: TestBugAttachment[];
  }>(),
  {
    placeholder: '请输入内容',
    attachments: () => [],
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'upload-files', files: File[]): void;
  (e: 'remove-attachment', attachment: TestBugAttachment): void;
}>();

const editorRef = ref<HTMLDivElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);

const syncEditorHtml = async (value: string) => {
  await nextTick();
  if (!editorRef.value) {
    return;
  }
  if (editorRef.value.innerHTML !== value) {
    editorRef.value.innerHTML = value || '';
  }
};

watch(
  () => props.modelValue,
  (value) => {
    void syncEditorHtml(value || '');
  },
  { immediate: true }
);

const handleInput = () => {
  emit('update:modelValue', editorRef.value?.innerHTML || '');
};

const execCommand = (command: string) => {
  editorRef.value?.focus();
  document.execCommand(command, false);
  handleInput();
};

const insertLink = () => {
  const url = window.prompt('请输入链接地址');
  if (!url) {
    return;
  }
  editorRef.value?.focus();
  document.execCommand('createLink', false, url);
  handleInput();
};

const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files || []);
  if (files.length) {
    emit('upload-files', files);
  }
  target.value = '';
};
</script>

<style scoped>
.bug-rich-editor {
  width: 100%;
  max-width: 100%;
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  background: #fff;
  box-sizing: border-box;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px;
  border-bottom: 1px solid var(--color-neutral-3);
  background: var(--color-fill-1);
}

.editor-toolbar-left,
.editor-toolbar-right {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.editor-surface {
  width: 100%;
  box-sizing: border-box;
  min-height: 180px;
  padding: 12px;
  outline: none;
  line-height: 1.7;
  word-break: break-word;
}

.editor-surface:empty::before {
  content: attr(data-placeholder);
  color: var(--color-text-3);
}

.hidden-file-input {
  display: none;
}

.attachment-list {
  display: grid;
  gap: 10px;
  padding: 0 12px 12px;
}

.attachment-item {
  padding: 10px;
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  background: var(--color-fill-1);
}

.attachment-image,
.attachment-video {
  width: 100%;
  max-height: 220px;
  object-fit: contain;
  border-radius: 6px;
  background: #000;
}

.attachment-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.attachment-name,
.attachment-file-link {
  min-width: 0;
  color: var(--color-text-1);
  word-break: break-all;
}

@media (max-width: 768px) {
  .editor-toolbar,
  .attachment-meta {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

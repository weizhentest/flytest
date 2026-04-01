<template>
  <div class="chat-input-container">
    <!-- 引用消息预览 -->
    <div v-if="quotedMessage" class="quote-preview-wrapper">
      <div class="quote-preview">
        <icon-reply class="quote-icon" />
        <span class="quote-text">{{ truncateQuote(quotedMessage.content) }}</span>
        <a-button type="text" size="mini" class="quote-close-btn" @click="$emit('clear-quote')">
          <template #icon><icon-close /></template>
        </a-button>
      </div>
    </div>

    <!-- 图片预览区域 -->
    <div v-if="imagePreview" class="image-preview-wrapper">
      <div class="image-preview">
        <img :src="imagePreview" alt="预览图片" />
        <a-button
          class="remove-image-btn"
          type="text"
          size="small"
          @click="removeImage"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
    </div>

    <div 
      class="input-wrapper"
      :class="{ 'drag-over': isDragOver }"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
    >
      <div class="textarea-wrapper">
        <a-textarea
          v-model="inputMessage"
          :placeholder="supportsVision ? '输入消息、拖拽或粘贴图片... (Shift+Enter换行，Enter发送)' : '请输入你的消息... (Shift+Enter换行，Enter发送)'"
          :disabled="isLoading"
          class="chat-input"
          :auto-size="{ minRows: 1, maxRows: 6 }"
          @keydown="handleKeyDown"
          @paste="handlePaste"
        />

        <!-- 拖拽提示遮罩 -->
        <div v-if="isDragOver && supportsVision" class="drag-overlay">
          <icon-image class="drag-icon" />
          <span>释放以上传图片</span>
        </div>
      </div>

      <!-- Token 使用率指示器 -->
      <TokenUsageIndicator
        v-if="contextTokenCount > 0 || contextLimit > 0"
        :current-tokens="contextTokenCount"
        :max-tokens="contextLimit"
      />

      <!-- 发送/停止按钮 -->
      <a-button
        v-if="!isLoading"
        type="primary"
        class="send-button"
        @click="handleSendMessage"
      >
        <template #icon>
          <icon-send />
        </template>
        <span>发送</span>
      </a-button>
      <a-button
        v-else
        type="primary"
        status="danger"
        class="stop-button"
        @click="handleStopGeneration"
      >
        <template #icon>
          <icon-record-stop />
        </template>
        <span>停止</span>
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import {
  Textarea as ATextarea,
  Button as AButton,
  Message
} from '@arco-design/web-vue';
import { IconImage, IconClose, IconReply, IconSend, IconRecordStop } from '@arco-design/web-vue/es/icon';
import TokenUsageIndicator from './TokenUsageIndicator.vue';

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';
  imageBase64?: string;
  imageDataUrl?: string;
}

interface Props {
  isLoading: boolean;
  supportsVision?: boolean;
  contextTokenCount?: number;
  contextLimit?: number;
  quotedMessage?: ChatMessage | null;
}

const props = withDefaults(defineProps<Props>(), {
  supportsVision: false,
  contextTokenCount: 0,
  contextLimit: 128000,
  quotedMessage: null
});

const emit = defineEmits<{
  'send-message': [data: { message: string; image?: string; imageDataUrl?: string; quotedMessage?: ChatMessage | null }];
  'clear-quote': [];
  'stop-generation': [];
}>();

// 截断引用文本
const truncateQuote = (text: string): string => {
  const maxLen = 80;
  const singleLine = text.replace(/\n/g, ' ').trim();
  return singleLine.length > maxLen ? singleLine.slice(0, maxLen) + '...' : singleLine;
};

const inputMessage = ref('');
const imageFile = ref<File | null>(null);
const imagePreview = ref<string>('');
const isDragOver = ref(false);

// 停止生成
const handleStopGeneration = () => {
  emit('stop-generation');
};

// 移除图片
const removeImage = () => {
  imageFile.value = null;
  imagePreview.value = '';
};

// 发送消息
const handleSendMessage = async () => {
  const message = inputMessage.value.trim();
  
  // 检查是否有内容（文本或图片）
  if (!message && !imageFile.value) {
    Message.warning('请输入消息或上传图片！');
    return;
  }

  // 如果有图片但模型不支持
  if (imageFile.value && !props.supportsVision) {
    Message.error({
      content: '❌ 当前AI模型不支持图片输入\n' +
               '请先移除图片或切换到支持多模态的模型\n' +
               '（推荐：GPT-4V、Claude 3、Gemini Vision、Qwen-VL）',
      duration: 5000
    });
    return;
  }

  let imageBase64: string | undefined;
  let imageDataUrl: string | undefined;
  
  // 如果有图片，转换为base64
  if (imageFile.value) {
    try {
      const result = await fileToBase64WithDataUrl(imageFile.value);
      imageBase64 = result.base64;
      imageDataUrl = result.dataUrl;
    } catch (error) {
      Message.error('图片处理失败，请重试');
      return;
    }
  }

  emit('send-message', {
    message: message || '请查看图片',
    image: imageBase64,
    imageDataUrl: imageDataUrl,
    quotedMessage: props.quotedMessage
  });

  // 清空输入
  inputMessage.value = '';
  removeImage();
};

// 文件转base64（返回纯Base64和完整Data URL）
const fileToBase64WithDataUrl = (file: File): Promise<{ base64: string; dataUrl: string }> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      // 移除data:image/xxx;base64,前缀得到纯Base64
      const base64 = dataUrl.split(',')[1];
      resolve({ base64, dataUrl });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

// 处理键盘事件
const handleKeyDown = (event: KeyboardEvent) => {
  // Enter键发送消息，Shift+Enter换行
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault(); // 阻止默认的换行行为
    handleSendMessage();
  }
  // Shift+Enter允许换行，不做任何处理，让默认行为发生
};

// 处理图片文件（公共方法）
const processImageFile = (file: File) => {
  // 检查是否是图片
  if (!file.type.startsWith('image/')) {
    Message.error('只能上传图片文件');
    return false;
  }

  // 检查文件大小（最大10MB）
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    Message.error('图片大小不能超过10MB');
    return false;
  }

  // 检查文件类型
  const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
  if (!validTypes.includes(file.type)) {
    Message.error('仅支持JPG、PNG、GIF格式的图片');
    return false;
  }

  imageFile.value = file;

  // 生成预览
  const reader = new FileReader();
  reader.onload = (e) => {
    imagePreview.value = e.target?.result as string;
  };
  reader.readAsDataURL(file);
  
  return true;
};

// 拖拽相关处理
const handleDragOver = (_e: DragEvent) => {
  if (!props.supportsVision || props.isLoading || imageFile.value) return;
  isDragOver.value = true;
};

const handleDragLeave = (_e: DragEvent) => {
  isDragOver.value = false;
};

const handleDrop = (e: DragEvent) => {
  isDragOver.value = false;
  
  if (!props.supportsVision) {
    Message.warning({
      content: '💡 当前AI模型不支持图片输入\n请在模型管理中选择支持多模态的模型（如GPT-4V、Claude 3、Qwen-VL等）',
      duration: 4000
    });
    return;
  }
  
  if (props.isLoading || imageFile.value) return;

  const files = e.dataTransfer?.files;
  if (!files || files.length === 0) return;

  processImageFile(files[0]);
};

// 粘贴处理
const handlePaste = (e: ClipboardEvent) => {
  if (props.isLoading || imageFile.value) return;

  const items = e.clipboardData?.items;
  if (!items) return;

  // 查找图片项
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (item.type.startsWith('image/')) {
      e.preventDefault(); // 阻止默认粘贴行为
      
      // 如果不支持视觉模型,拦截并提示
      if (!props.supportsVision) {
        Message.warning({
          content: '💡 当前AI模型不支持图片输入\n请在模型管理中选择支持多模态的模型\n（推荐：GPT-4V、Claude 3、Gemini Vision、Qwen-VL）',
          duration: 4000
        });
        return;
      }
      
      const file = item.getAsFile();
      if (file) {
        processImageFile(file);
        Message.success('图片已粘贴');
      }
      break;
    }
  }
};
</script>

<style scoped>
.chat-input-container {
  padding: 16px 20px;
  background-color: white;
  border-top: 1px solid #e5e6eb;
}

/* 引用消息预览 */
.quote-preview-wrapper {
  margin-bottom: 12px;
}

.quote-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f3ff 100%);
  border-left: 3px solid #165dff;
  border-radius: 0 8px 8px 0;
}

.quote-icon {
  color: #165dff;
  font-size: 14px;
  flex-shrink: 0;
}

.quote-text {
  flex: 1;
  font-size: 13px;
  color: #4e5969;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quote-close-btn {
  flex-shrink: 0;
  color: #86909c !important;
}

.quote-close-btn:hover {
  color: #f53f3f !important;
}

/* 图片预览区域 */
.image-preview-wrapper {
  margin-bottom: 12px;
}

.image-preview {
  position: relative;
  display: inline-block;
  max-width: 200px;
  max-height: 150px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.image-preview img {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

.remove-image-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.remove-image-btn:hover {
  background-color: rgba(0, 0, 0, 0.8);
}

.input-wrapper {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
  position: relative;
  transition: all 0.3s;
}

.input-wrapper.drag-over {
  transform: scale(1.02);
}

/* 文本框容器 */
.textarea-wrapper {
  position: relative;
  flex: 1;
}

.chat-input {
  width: 100%;
  border-radius: 12px;
  background-color: #f2f3f5;
  transition: all 0.2s;
  resize: none;
  min-height: 36px;
}

.chat-input:hover, .chat-input:focus {
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 确保文本框内容样式正确 */
.chat-input :deep(.arco-textarea) {
  border-radius: 12px;
  padding: 8px 12px;
  line-height: 20px;
  min-height: 36px;
}

/* 拖拽覆盖层 */
.drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.1), rgba(22, 93, 255, 0.05));
  border: 2px dashed #165dff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  pointer-events: none;
  z-index: 10;
  animation: pulse 1.5s ease-in-out infinite;
}

.drag-icon {
  font-size: 32px;
  color: #165dff;
}

.drag-overlay span {
  font-size: 14px;
  color: #165dff;
  font-weight: 500;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.02);
  }
}

.send-button {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 20px;
  padding: 0 16px;
  height: 36px;
  flex-shrink: 0;
}

.stop-button {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 20px;
  padding: 0 16px;
  height: 36px;
  flex-shrink: 0;
  animation: pulse-stop 1.5s ease-in-out infinite;
}

@keyframes pulse-stop {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.icon-send {
  margin-right: 4px;
  font-size: 16px;
}
</style>

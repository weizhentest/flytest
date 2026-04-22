<template>
  <a-modal
    :visible="visible"
    title="添加用例"
    :footer="false"
    width="520px"
    @cancel="handleCancel"
  >
    <div class="mode-list">
      <button type="button" class="mode-card" @click="emit('manual')">
        <div class="mode-title">手动输入</div>
        <div class="mode-desc">保持当前添加用例逻辑不变，手动填写名称、步骤和预期结果。</div>
      </button>

      <button type="button" class="mode-card mode-card--ai" @click="emit('ai')">
        <div class="mode-title">AI生成</div>
        <div class="mode-desc">自动带入当前模块的已有用例和需求上下文，按追加方式生成并自动避重。</div>
      </button>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'manual'): void;
  (e: 'ai'): void;
}>();

const handleCancel = () => {
  emit('update:visible', false);
};
</script>

<style scoped>
.mode-list {
  display: grid;
  gap: 14px;
}

.mode-card {
  width: 100%;
  padding: 18px;
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-card:hover {
  border-color: rgb(var(--primary-6));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.mode-card--ai {
  background: linear-gradient(135deg, #f6fbff 0%, #eef7ff 100%);
}

.mode-title {
  margin-bottom: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.mode-desc {
  color: var(--color-text-3);
  line-height: 1.6;
  font-size: 13px;
}
</style>

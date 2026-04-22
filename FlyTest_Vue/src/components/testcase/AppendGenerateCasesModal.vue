<template>
  <a-modal
    :visible="visible"
    title="AI生成用例"
    :confirm-loading="generating"
    width="620px"
    @cancel="handleCancel"
    @ok="handleOk"
  >
    <a-alert type="info" show-icon class="tip-alert">
      <template #title>追加生成说明</template>
      会自动带入当前模块的已有测试用例和需求来源，按追加方式生成新用例，并尽量避免与现有列表重复。
    </a-alert>

    <a-form :model="formState" layout="vertical">
      <a-form-item label="当前模块">
        <a-input :model-value="moduleName || '未选择模块'" disabled />
      </a-form-item>

      <a-form-item label="追加提示词">
        <a-textarea
          v-model="formState.extraPrompt"
          :max-length="1000"
          allow-clear
          placeholder="可选。比如：更关注异常场景、补齐边界值、优先补充登录失败场景。"
          :auto-size="{ minRows: 4, maxRows: 8 }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';

const props = defineProps<{
  visible: boolean;
  generating?: boolean;
  moduleName?: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', payload: { extraPrompt: string }): void;
}>();

const formState = reactive({
  extraPrompt: '',
});

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      formState.extraPrompt = '';
    }
  }
);

const handleCancel = () => {
  emit('update:visible', false);
};

const handleOk = () => {
  emit('submit', {
    extraPrompt: formState.extraPrompt.trim(),
  });
  emit('update:visible', false);
};
</script>

<style scoped>
.tip-alert {
  margin-bottom: 16px;
}
</style>

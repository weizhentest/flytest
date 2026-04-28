<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEditing ? '编辑测试套件' : '新建测试套件'"
    :width="720"
    :mask-closable="false"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-spin :loading="initializing || loading" style="width: 100%">
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item label="套件名称" field="name" required>
          <a-input
            v-model="formData.name"
            placeholder="请输入测试套件名称"
            :max-length="100"
            show-word-limit
          />
        </a-form-item>

        <a-form-item label="套件描述" field="description">
          <a-textarea
            v-model="formData.description"
            placeholder="请输入测试套件描述"
            :max-length="500"
            :auto-size="{ minRows: 3, maxRows: 6 }"
            show-word-limit
          />
        </a-form-item>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  createTestSuite,
  getTestSuiteDetail,
  updateTestSuite,
  type CreateTestSuiteRequest,
} from '@/services/testSuiteService';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
  suiteId?: number | null;
  initialParentId?: number | null;
}

const props = withDefaults(defineProps<Props>(), {
  suiteId: null,
  initialParentId: null,
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}>();

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const isEditing = computed(() => !!props.suiteId);
const formRef = ref();
const loading = ref(false);
const initializing = ref(false);

const formData = ref<CreateTestSuiteRequest>({
  name: '',
  description: '',
  parent_id: undefined,
  max_concurrent_tasks: 1,
});

const rules = {
  name: [
    { required: true, message: '请输入测试套件名称' },
    { minLength: 2, message: '套件名称至少 2 个字符' },
  ],
};

const resetFormState = () => {
  formData.value = {
    name: '',
    description: '',
    parent: props.initialParentId ?? undefined,
    parent_id: props.initialParentId ?? undefined,
    max_concurrent_tasks: 1,
  };
  formRef.value?.resetFields();
};

const initializeModal = async () => {
  if (!props.currentProjectId) {
    return;
  }

  resetFormState();

  if (!isEditing.value || !props.suiteId) {
    return;
  }

  initializing.value = true;
  try {
    const response = await getTestSuiteDetail(props.currentProjectId, props.suiteId);
    if (!response.success || !response.data) {
      throw new Error(response.error || '获取测试套件详情失败');
    }

    formData.value.name = response.data.name;
    formData.value.description = response.data.description || '';
    formData.value.parent = response.data.parent ?? undefined;
    formData.value.parent_id = response.data.parent_id ?? response.data.parent ?? undefined;
    formData.value.max_concurrent_tasks = response.data.max_concurrent_tasks || 1;
  } catch (error) {
    console.error('初始化测试套件表单失败:', error);
    Message.error(error instanceof Error ? error.message : '初始化测试套件表单失败');
  } finally {
    initializing.value = false;
  }
};

const handleSubmit = async () => {
  if (!props.currentProjectId) {
    Message.error('缺少项目 ID');
    return false;
  }

  try {
    await formRef.value?.validate();
    loading.value = true;

    const submitData: CreateTestSuiteRequest = {
      name: formData.value.name,
      description: formData.value.description,
      parent: formData.value.parent_id ?? formData.value.parent ?? null,
      parent_id: formData.value.parent_id ?? formData.value.parent ?? null,
      max_concurrent_tasks: formData.value.max_concurrent_tasks,
    };

    const response = isEditing.value
      ? await updateTestSuite(props.currentProjectId, props.suiteId!, submitData)
      : await createTestSuite(props.currentProjectId, submitData);

    if (!response.success) {
      Message.error(response.error || '保存测试套件失败');
      return false;
    }

    Message.success(response.message || (isEditing.value ? '测试套件更新成功' : '测试套件创建成功'));
    emit('success');
    handleCancel();
    return true;
  } catch (error) {
    console.error('提交测试套件失败:', error);
    Message.error('提交测试套件失败');
    return false;
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  resetFormState();
  emit('update:visible', false);
};

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      void initializeModal();
    } else {
      resetFormState();
    }
  }
);
</script>

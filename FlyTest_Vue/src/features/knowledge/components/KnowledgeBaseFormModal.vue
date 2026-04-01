<template>
  <a-modal
    :visible="visible"
    :title="isEdit ? '编辑知识库' : '新建知识库'"
    :width="500"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="loading"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item label="知识库名称" field="name">
        <a-input
          v-model="formData.name"
          placeholder="请输入知识库名称"
          :max-length="100"
        />
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-textarea
          v-model="formData.description"
          placeholder="请输入知识库描述（可选）"
          :rows="3"
          :max-length="500"
        />
      </a-form-item>

      <a-form-item label="所属项目" field="project">
        <a-select
          v-model="formData.project"
          placeholder="请选择所属项目"
          :loading="projectStore.loading"
          :disabled="isEdit"
        >
          <a-option
            v-for="project in projects"
            :key="project.value"
            :value="project.value"
            :label="project.label"
          />
        </a-select>
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="分块大小" field="chunk_size">
            <a-input-number
              v-model="formData.chunk_size"
              placeholder="分块大小"
              :min="100"
              :max="4000"
              :step="100"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="分块重叠" field="chunk_overlap">
            <a-input-number
              v-model="formData.chunk_overlap"
              placeholder="分块重叠"
              :min="0"
              :max="500"
              :step="50"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item v-if="!isEdit" label="状态" field="is_active">
        <a-switch
          v-model="formData.is_active"
          checked-text="启用"
          unchecked-text="禁用"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { KnowledgeService } from '../services/knowledgeService';
import type {
  KnowledgeBase,
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
} from '../types/knowledge';

interface Props {
  visible: boolean;
  knowledgeBase?: KnowledgeBase | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  submit: [];
  cancel: [];
}>();

const projectStore = useProjectStore();
const formRef = ref();
const loading = ref(false);

const isEdit = computed(() => !!props.knowledgeBase);

// 表单数据（简化版，嵌入服务配置使用全局配置）
const formData = reactive<CreateKnowledgeBaseRequest>({
  name: '',
  description: '',
  project: 0,
  chunk_size: 1000,
  chunk_overlap: 200,
  is_active: true,
});

const projects = computed(() => projectStore.projectOptions);

const rules = {
  name: [
    { required: true, message: '请输入知识库名称' },
    { minLength: 2, message: '知识库名称至少2个字符' },
    { maxLength: 200, message: '知识库名称不能超过200个字符' },
  ],
  project: [
    { required: true, message: '请选择所属项目' },
  ],
  chunk_size: [
    { required: true, message: '请输入分块大小' },
    { type: 'number', min: 100, max: 4000, message: '分块大小必须在100-4000之间' },
  ],
  chunk_overlap: [
    { required: true, message: '请输入分块重叠' },
    { type: 'number', min: 0, max: 500, message: '分块重叠必须在0-500之间' },
  ],
};

watch(() => props.visible, async (visible) => {
  if (visible) {
    resetForm();

    if (projects.value.length === 0) {
      await projectStore.fetchProjects();
    }

    if (props.knowledgeBase) {
      Object.assign(formData, {
        name: props.knowledgeBase.name,
        description: props.knowledgeBase.description || '',
        project: typeof props.knowledgeBase.project === 'string' 
          ? Number(props.knowledgeBase.project) 
          : props.knowledgeBase.project,
        chunk_size: props.knowledgeBase.chunk_size,
        chunk_overlap: props.knowledgeBase.chunk_overlap,
      });
    } else {
      if (projectStore.currentProjectId) {
        formData.project = Number(projectStore.currentProjectId);
      }
    }
  }
});

watch(
  () => projects.value,
  (newProjects) => {
    if (props.visible && props.knowledgeBase && newProjects.length > 0) {
      const correctProjectId = typeof props.knowledgeBase.project === 'string' 
        ? Number(props.knowledgeBase.project) 
        : props.knowledgeBase.project;
      
      if (formData.project === 0 || formData.project !== correctProjectId) {
        formData.project = correctProjectId;
      }
    }
  },
  { immediate: true }
);

const resetForm = () => {
  Object.assign(formData, {
    name: '',
    description: '',
    project: 0,
    chunk_size: 1000,
    chunk_overlap: 200,
    is_active: true,
  });
  formRef.value?.clearValidate();
};

const handleSubmit = async () => {
  try {
    await formRef.value?.validate();
    loading.value = true;

    if (isEdit.value && props.knowledgeBase) {
      const updateData: UpdateKnowledgeBaseRequest = {
        name: formData.name,
        description: formData.description,
        project: formData.project,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
      };
      await KnowledgeService.updateKnowledgeBase(props.knowledgeBase.id, updateData);
    } else {
      const createData: CreateKnowledgeBaseRequest = {
        name: formData.name,
        description: formData.description,
        project: formData.project,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
        is_active: formData.is_active,
      };
      await KnowledgeService.createKnowledgeBase(createData);
    }

    emit('submit');
  } catch (error: any) {
    console.error('保存知识库失败:', error);
    if (error && typeof error === 'object' && 'errorFields' in error) {
      Message.error('请检查表单填写是否正确');
    } else {
      Message.error(error?.message || '保存知识库失败');
    }
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  emit('cancel');
};
</script>

<style scoped>
:deep(.arco-form-item-label) {
  font-weight: 500;
}

:deep(.arco-input-number) {
  width: 100%;
}
</style>

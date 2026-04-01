<template>
  <a-modal
    :visible="visible"
    title="我的提示词"
    @cancel="handleCancel"
    :mask-closable="false"
    width="800px"
    :footer="false"
  >
    <div class="prompt-management-modal">
      <div class="user-prompts-section">

            <!-- 提示词列表头部 -->
            <div class="prompts-header">
              <div class="header-left">
                <span class="section-title">我的提示词</span>
                <a-tag v-if="defaultPrompt" color="blue" size="small">
                  默认：{{ defaultPrompt.name }}
                </a-tag>
              </div>
              <div class="header-right">
                <a-button 
                  type="outline" 
                  size="small" 
                  @click="handleInitializePrompts" 
                  :loading="initializeLoading"
                  style="margin-right: 8px;"
                >
                  <template #icon>
                    <icon-settings />
                  </template>
                  初始化提示词
                </a-button>
                <a-button type="primary" size="small" @click="showCreatePromptForm">
                  <template #icon>
                    <icon-plus />
                  </template>
                  新建提示词
                </a-button>
              </div>
            </div>

            <!-- 提示词列表 -->
            <div class="prompts-list">
              <div v-if="userPromptsLoading" class="loading-state">
                <a-spin />
                <span>加载中...</span>
              </div>

              <div v-else-if="!userPrompts || userPrompts.length === 0" class="empty-state">
                <div class="empty-icon">📝</div>
                <div class="empty-text">暂无提示词</div>
                <div class="empty-desc">创建您的第一个提示词来开始使用</div>
              </div>

              <div v-else-if="userPrompts && userPrompts.length > 0" class="prompts-list-compact">
                <div
                  v-for="prompt in userPrompts"
                  :key="prompt.id"
                  class="prompt-item"
                  :class="{ 'is-default': prompt.is_default }"
                >
                  <div class="prompt-info">
                    <div class="prompt-name">{{ prompt.name }}</div>
                    <div class="prompt-description">{{ prompt.description || '暂无描述' }}</div>
                  </div>
                  <div class="prompt-meta">
                    <span class="prompt-time">{{ formatDateTime(prompt.created_at) }}</span>
                  </div>
                  <div class="prompt-status">
                    <div style="width: 45px;">
                      <a-tag v-if="prompt.is_active" color="green" size="small">启用</a-tag>
                      <a-tag v-else color="red" size="small">禁用</a-tag>
                    </div>
                    <div style="width: 45px;">
                      <a-tag v-if="prompt.is_default" color="blue" size="small">默认</a-tag>
                    </div>
                  </div>
                  <div class="prompt-actions">
                    <a-button
                      type="text"
                      size="mini"
                      @click="editPrompt(prompt)"
                      title="编辑"
                    >
                      <template #icon>
                        <icon-edit />
                      </template>
                    </a-button>
                    <a-button
                      v-if="!prompt.is_default && !isProgramCallPromptType(prompt.prompt_type)"
                      type="text"
                      size="mini"
                      @click="setAsDefault(prompt)"
                      title="设为默认"
                    >
                      <template #icon>
                        <icon-star />
                      </template>
                    </a-button>
                    <a-button
                      type="text"
                      size="mini"
                      @click="duplicatePrompt(prompt)"
                      title="复制"
                    >
                      <template #icon>
                        <icon-copy />
                      </template>
                    </a-button>
                    <a-popconfirm
                      content="确定要删除这个提示词吗？"
                      @ok="deletePrompt(prompt)"
                    >
                      <a-button
                        type="text"
                        size="mini"
                        status="danger"
                        title="删除"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>
            </div>
          </div>
    </div>

    <!-- 提示词表单弹窗 -->
    <a-modal
      v-model:visible="isPromptFormVisible"
      :title="isEditingPrompt ? '编辑提示词' : '新建提示词'"
      @ok="handlePromptSubmit"
      @cancel="closePromptForm"
      :confirm-loading="promptFormLoading"
      width="600px"
      ok-text="保存"
      cancel-text="取消"
    >
      <a-form
        ref="promptFormRef"
        :model="promptFormData"
        :rules="promptFormRules"
        layout="vertical"
      >
        <a-form-item field="prompt_type" label="提示词类型">
          <div class="prompt-type-container">
            <a-select
              v-model="promptFormData.prompt_type"
              placeholder="请选择提示词类型"
              @change="handlePromptTypeChange"
              :fallback-option="false"
            >
              <a-option
                v-for="type in PROMPT_TYPE_CHOICES"
                :key="type.key"
                :value="type.key"
                :label="type.name"
              >
                {{ type.name }}
              </a-option>
            </a-select>
            <a-tooltip
              v-if="isRequirementType"
              content="每种需求评审类型只能创建一个提示词，用于该类型的专门分析"
              position="right"
            >
              <icon-info-circle class="type-info-icon" />
            </a-tooltip>
          </div>
        </a-form-item>

        <a-form-item field="name" label="提示词名称">
          <a-input
            v-model="promptFormData.name"
            placeholder="请输入提示词名称"
            :max-length="255"
          />
        </a-form-item>

        <a-form-item field="description" label="描述">
          <a-input
            v-model="promptFormData.description"
            placeholder="请输入提示词描述（可选）"
            :max-length="500"
          />
        </a-form-item>

        <a-form-item field="content" label="提示词内容">
          <a-textarea
            v-model="promptFormData.content"
            placeholder="请输入提示词内容"
            :rows="6"
            :max-length="10000"
            show-word-limit
            :auto-size="{ minRows: 6, maxRows: 12 }"
          />
        </a-form-item>

        <a-form-item
          v-if="!isRequirementType"
          field="is_default"
          label="设为默认"
        >
          <a-switch v-model="promptFormData.is_default" />
          <span style="margin-left: 8px; font-size: 12px; color: #86909c;">
            设为默认后，聊天时会自动使用此提示词
          </span>
        </a-form-item>
      </a-form>
    </a-modal>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue';
import { Message, Modal, type FormInstance } from '@arco-design/web-vue';
import { IconPlus, IconEdit, IconStar, IconDelete, IconCopy, IconInfoCircle, IconSettings } from '@arco-design/web-vue/es/icon';
import {
  getUserPrompts,
  createUserPrompt,
  updateUserPrompt,
  deleteUserPrompt,
  setDefaultPrompt,
  getDefaultPrompt,
  getUserPrompt,
  duplicateUserPrompt,
  initializeUserPrompts,
  getInitializationStatus,
} from '@/features/prompts/services/promptService';
import type {
  UserPrompt,
  PromptType
} from '@/features/prompts/types/prompt';
import {
  PROMPT_TYPE_CHOICES,
  isProgramCallPromptType
} from '@/features/prompts/types/prompt';
import { formatDateTime } from '@/utils/formatters';

// 定义组件属性
interface Props {
  visible: boolean;
  currentLlmConfig?: {
    id: number;
    name: string;
    system_prompt?: string;
  } | null;
  loading: boolean;
}

// 定义事件
interface Emits {
  (e: 'update-system-prompt', id: number, prompt: string): void;
  (e: 'cancel'): void;
  (e: 'prompts-updated'): void; // 新增：提示词数据更新事件
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const promptFormRef = ref<FormInstance | null>(null);

// 用户提示词相关
const userPrompts = ref<UserPrompt[]>([]);
const defaultPrompt = ref<UserPrompt | null>(null);
const userPromptsLoading = ref(false);
const isPromptFormVisible = ref(false);
const promptFormLoading = ref(false);
const isEditingPrompt = ref(false);
const currentEditingPrompt = ref<UserPrompt | null>(null);
const initializeLoading = ref(false);

// 提示词表单数据
const promptFormData = ref({
  name: '',
  description: '',
  content: '',
  is_default: false,
  prompt_type: 'general' as PromptType, // 新增字段，默认为通用对话类型
});

// 默认提示词表单数据
const defaultPromptFormData = {
  name: '',
  description: '',
  content: '',
  is_default: false,
  prompt_type: 'general' as PromptType, // 新增字段
};

// 提示词表单验证规则
const promptFormRules = {
  name: [
    { required: true, message: '请输入提示词名称' },
    { minLength: 2, message: '提示词名称至少需要2个字符' },
    { maxLength: 255, message: '提示词名称不能超过255个字符' }
  ],
  content: [
    { required: true, message: '请输入提示词内容' },
    { minLength: 10, message: '提示词内容至少需要10个字符' },
    { maxLength: 10000, message: '提示词内容不能超过10000个字符' }
  ],
  description: [
    { maxLength: 500, message: '描述不能超过500个字符' }
  ],
  prompt_type: [
    { required: true, message: '请选择提示词类型' }
  ]
};

// 加载用户提示词列表
const loadUserPrompts = async () => {
  userPromptsLoading.value = true;

  try {
    const [promptsResponse, defaultResponse] = await Promise.all([
      getUserPrompts({
        ordering: 'name', // 先按名称排序
        page_size: 100
      }),
      getDefaultPrompt()
    ]);

    if (promptsResponse.status === 'success' && promptsResponse.data) {
      // 检查返回的数据格式
      let allPrompts: UserPrompt[] = [];
      if (Array.isArray(promptsResponse.data)) {
        // 直接是数组格式
        allPrompts = promptsResponse.data;
      } else if (promptsResponse.data.results) {
        // 分页格式
        allPrompts = promptsResponse.data.results;
      }
      
      // 🆕 在前端手动排序：默认提示词在前，然后按类型和名称排序
      userPrompts.value = allPrompts.sort((a, b) => {
        // 第一级：按 is_default 排序，默认的在前
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        
        // 第二级：按提示词类型排序，通用对话类型在前
        const getTypeSort = (type: string) => {
          if (type === 'general') return 1; // 通用对话类型
          return 2; // 其他程序调用类型
        };
        
        const aTypeSort = getTypeSort(a.prompt_type || 'general');
        const bTypeSort = getTypeSort(b.prompt_type || 'general');
        if (aTypeSort !== bTypeSort) return aTypeSort - bTypeSort;
        
        // 第三级：按名称排序
        return a.name.localeCompare(b.name);
      });
    } else {
      userPrompts.value = []; // 确保设置为空数组
    }

    if (defaultResponse.status === 'success' && defaultResponse.data) {
      defaultPrompt.value = defaultResponse.data;
    } else {
      defaultPrompt.value = null;
    }
  } catch (error) {
    console.error('加载用户提示词失败:', error);
    Message.error('加载用户提示词失败，但您仍可以创建新的提示词');
    // 确保即使失败也设置为空数组，这样界面能正常显示
    userPrompts.value = [];
    defaultPrompt.value = null;
  } finally {
    userPromptsLoading.value = false;
  }
};
// 显示创建提示词表单
const showCreatePromptForm = () => {
  console.log('🔘 新建提示词按钮被点击');
  console.log('📝 当前表单可见状态:', isPromptFormVisible.value);

  isEditingPrompt.value = false;
  currentEditingPrompt.value = null;
  promptFormData.value = { ...defaultPromptFormData };
  isPromptFormVisible.value = true;

  console.log('✅ 设置表单可见状态为:', isPromptFormVisible.value);
  console.log('📋 表单数据:', promptFormData.value);
};

// 初始化提示词
const handleInitializePrompts = async () => {
  try {
    initializeLoading.value = true;
    
    // 先检查初始化状态
    const statusResponse = await getInitializationStatus();
    if (statusResponse.status !== 'success') {
      Message.error(statusResponse.message || '获取初始化状态失败');
      return;
    }

    const statusData = statusResponse.data;
    const missingCount = statusData.summary?.missing_count || 0;
    const existingCount = statusData.summary?.existing_count || 0;
    
    let forceUpdate = false;
    
    // 如果已有提示词，询问是否强制更新
    if (existingCount > 0) {
      const result = await new Promise((resolve) => {
        Modal.confirm({
          title: '提示词初始化确认',
          content: `检测到已存在 ${existingCount} 个提示词。\n\n是否强制更新所有提示词到最新版本？\n（更新后将覆盖现有提示词内容）`,
          okText: '强制更新',
          cancelText: missingCount > 0 ? '仅创建缺失的' : '取消',
          onOk: () => resolve('force'),
          onCancel: () => resolve(missingCount > 0 ? 'create' : 'cancel')
        });
      });
      
      if (result === 'cancel') {
        return;
      }
      forceUpdate = (result === 'force');
    }

    // 执行初始化
    const response = await initializeUserPrompts(forceUpdate);
    if (response.status === 'success') {
      const data = response.data;
      const createdCount = data.summary?.created_count || 0;
      const skippedCount = data.summary?.skipped_count || 0;
      
      if (forceUpdate) {
        Message.success(`强制更新完成！更新了 ${createdCount} 个提示词`);
      } else {
        Message.success(`${response.message || '初始化完成！'}创建了 ${createdCount} 个提示词，跳过 ${skippedCount} 个`);
      }
      
      // 重新加载用户提示词列表
      await loadUserPrompts();
    } else {
      Message.error(response.message || '初始化失败');
    }
  } catch (error) {
    console.error('初始化提示词失败:', error);
    Message.error('初始化提示词失败');
  } finally {
    initializeLoading.value = false;
  }
};

// 编辑提示词
const editPrompt = async (prompt: UserPrompt) => {
  try {
    // 获取完整的提示词详情（包含content字段）
    const response = await getUserPrompt(prompt.id);
    if (response.status === 'success' && response.data) {
      const fullPrompt = response.data;
      isEditingPrompt.value = true;
      currentEditingPrompt.value = fullPrompt;
      promptFormData.value = {
        name: fullPrompt.name,
        description: fullPrompt.description || '',
        content: fullPrompt.content || '',
        is_default: fullPrompt.is_default,
        prompt_type: fullPrompt.prompt_type || 'general', // 添加提示词类型字段
      };

      console.log('📋 编辑提示词 - 表单数据:', promptFormData.value);
      console.log('📋 编辑提示词 - 提示词类型:', fullPrompt.prompt_type);
      console.log('📋 编辑提示词 - 类型选项:', PROMPT_TYPE_CHOICES);
      isPromptFormVisible.value = true;
    } else {
      Message.error('获取提示词详情失败');
    }
  } catch (error) {
    console.error('获取提示词详情失败:', error);
    Message.error('获取提示词详情失败');
  }
};

// 设为默认提示词
const setAsDefault = async (prompt: UserPrompt) => {
  try {
    await setDefaultPrompt(prompt.id);
    Message.success('设置默认提示词成功');
    await loadUserPrompts();
    emit('prompts-updated'); 
  } catch (error: any) {
    Message.error(error.message || '设置默认提示词失败');
    console.error('设置默认提示词失败:', error);
  }
};

// 复制提示词
const duplicatePrompt = async (prompt: UserPrompt) => {
  try {
    const response = await duplicateUserPrompt(prompt.id);
    if (response.status === 'success') {
      Message.success('复制提示词成功');
      await loadUserPrompts();
      emit('prompts-updated'); // 通知父组件刷新提示词数据
    } else {
      Message.error(response.message || '复制提示词失败');
    }
  } catch (error) {
    console.error('复制提示词失败:', error);
    Message.error('复制提示词失败');
  }
};

// 删除提示词
const deletePrompt = async (prompt: UserPrompt) => {
  console.log('🗑️ 开始删除提示词:', prompt.name, 'ID:', prompt.id);
  try {
    const response = await deleteUserPrompt(prompt.id);
    if (response.status === 'success') {
      console.log('✅ 删除提示词API调用成功');
      Message.success('删除提示词成功');
      await loadUserPrompts();
      console.log('🔄 发送提示词更新事件...');
      emit('prompts-updated'); // 通知父组件刷新提示词数据
      console.log('📤 提示词更新事件已发送');
    } else {
      console.error('❌ 删除提示词API返回失败:', response.message);
      Message.error(response.message || '删除提示词失败');
    }
  } catch (error) {
    console.error('删除提示词失败:', error);
    Message.error('删除提示词失败');
  }
};

// 关闭提示词表单
const closePromptForm = () => {
  isPromptFormVisible.value = false;
  isEditingPrompt.value = false;
  currentEditingPrompt.value = null;
  promptFormData.value = { ...defaultPromptFormData };
};

// 提交提示词表单
const handlePromptSubmit = async () => {
  if (!promptFormRef.value) return;

  try {
    const validation = await promptFormRef.value.validate();
    if (validation) {
      // 如果有验证错误，显示错误信息
      Message.error('请检查表单输入！');
      return;
    }
  } catch (error) {
    // 验证失败时会抛出异常
    Message.error('请检查表单输入！');
    return;
  }

  promptFormLoading.value = true;
  try {
    let response;
    const submitData = {
      name: promptFormData.value.name,
      description: promptFormData.value.description || undefined,
      content: promptFormData.value.content,
      is_default: promptFormData.value.is_default,
      is_active: true,
      prompt_type: promptFormData.value.prompt_type, // 添加提示词类型字段
    };

    if (isEditingPrompt.value && currentEditingPrompt.value) {
      // 编辑模式
      response = await updateUserPrompt(currentEditingPrompt.value.id, submitData);
    } else {
      // 新增模式
      response = await createUserPrompt(submitData);
    }

    if (response.status === 'success') {
      Message.success(isEditingPrompt.value ? '更新提示词成功' : '创建提示词成功');
      closePromptForm();
      await loadUserPrompts();
      emit('prompts-updated'); // 通知父组件刷新提示词数据
    } else {
      Message.error(response.message || (isEditingPrompt.value ? '更新提示词失败' : '创建提示词失败'));
    }
  } catch (error) {
    console.error('提交失败:', error);
    Message.error(isEditingPrompt.value ? '更新提示词失败' : '创建提示词失败');
  } finally {
    promptFormLoading.value = false;
  }
};

// 监听弹窗显示状态，加载用户提示词数据
watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      // 弹窗打开时加载用户提示词数据
      loadUserPrompts();
    }
  }
);

// 组件挂载时加载用户提示词
onMounted(() => {
  if (props.visible) {
    loadUserPrompts();
  }
});

// 取消操作
const handleCancel = () => {
  emit('cancel');
};

// ==================== 需求评审提示词相关 ====================

// 计算属性：是否为需求评审类型
const isRequirementType = computed(() => {
  return isProgramCallPromptType(promptFormData.value.prompt_type);
});

// 处理提示词类型变更
const handlePromptTypeChange = (type: PromptType) => {
  // 如果切换到程序调用类型，则禁用默认设置
  if (isProgramCallPromptType(type)) {
    promptFormData.value.is_default = false;
  }
};
</script>

<style scoped>
.prompt-management-modal {
  max-height: 70vh;
  overflow-y: auto;
}

.current-config-info {
  margin-bottom: 20px;
}

.system-prompt-form {
  margin-bottom: 20px;
}

/* 用户提示词管理样式 */
.user-prompts-section {
  padding: 16px 0;
}

.prompts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title {
  font-weight: 600;
  color: #1d2129;
  font-size: 16px;
}

.prompts-list {
  min-height: 200px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #86909c;
  gap: 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-text {
  font-size: 16px;
  font-weight: 500;
  color: #4e5969;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #86909c;
}

.prompts-list-compact {
  max-height: 400px;
  overflow-y: auto;
}

.prompt-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: #fafbfc;
  margin-bottom: 8px;
  transition: all 0.2s ease;
}

.prompt-item:hover {
  border-color: #165dff;
  background: #f2f3ff;
}

.prompt-item.is-default {
  border-color: #165dff;
  background: #f2f3ff;
}

.prompt-info {
  flex: 1;
    min-width: 0;
  max-width: 350px;
}

.prompt-name {
  font-weight: 600;
  color: #1d2129;
  font-size: 14px;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.prompt-description {
  font-size: 12px;
  color: #86909c;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.prompt-meta {
  flex-shrink: 0;
  font-size: 11px;
  color: #86909c;
    width: 120px;
  text-align: left;
}

.prompt-time {
  color: #86909c;
}

.prompt-status {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  min-width: 80px;
}

.prompt-actions {
  display: flex;
  gap: 4px;
  opacity: 0.7;
  transition: opacity 0.2s ease;
  flex-shrink: 0;
}

.prompt-item:hover .prompt-actions {
  opacity: 1;
}

.icon-info::before {
  content: 'ℹ️';
}

.icon-up::before {
  content: '▲';
}

.icon-down::before {
  content: '▼';
}

/* 提示词类型选择器样式 */
.prompt-type-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prompt-type-container .arco-select {
  flex: 1;
}

.type-info-icon {
  color: #165dff;
  font-size: 16px;
  cursor: help;
  flex-shrink: 0;
}

.type-info-icon:hover {
  color: #0e42d2;
}
</style>

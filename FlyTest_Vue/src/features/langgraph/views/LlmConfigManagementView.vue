<template>
  <div class="llm-config-management">
    <div class="page-header">
      <h1 class="text-2xl font-semibold mb-4">LLM 配置管理</h1>
      <div class="header-actions">
        <a-button @click="showPromptManagement">
          <template #icon><icon-file /></template>
          提示词管理
        </a-button>
        <a-button type="primary" @click="handleAddNewConfig">
          <template #icon><icon-plus /></template>
          新增配置
        </a-button>
      </div>
    </div>

    <LlmConfigTable
      :configs="llmConfigs"
      :loading="isLoading"
      :pagination="pagination"
      @edit="handleEditConfig"
      @delete="handleDeleteConfig"
      @toggle-active="handleToggleActive"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
    />

    <LlmConfigFormModal
      :visible="isModalVisible"
      :config-data="currentConfig"
      :form-loading="isFormLoading"
      @submit="handleSubmitConfig"
      @cancel="handleCloseModal"
      @auto-saved="handleAutoSaved"
    />

    <!-- 提示词管理弹窗 -->
    <SystemPromptModal
      :visible="isPromptModalVisible"
      :current-llm-config="currentLlmConfigForPrompt"
      :loading="false"
      @cancel="closePromptModal"
      @prompts-updated="handlePromptsUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, watch } from 'vue';
import { Button as AButton, Message, Modal as AModal } from '@arco-design/web-vue';
import { IconPlus, IconFile } from '@arco-design/web-vue/es/icon';
import LlmConfigTable from '@/features/langgraph/components/LlmConfigTable.vue';
import LlmConfigFormModal from '@/features/langgraph/components/LlmConfigFormModal.vue';
import SystemPromptModal from '@/features/langgraph/components/SystemPromptModal.vue';
import type { LlmConfig, CreateLlmConfigRequest, PartialUpdateLlmConfigRequest } from '@/features/langgraph/types/llmConfig';
import {
  listLlmConfigs,
  createLlmConfig,
  updateLlmConfig,
  partialUpdateLlmConfig,
  deleteLlmConfig,
  getLlmConfigDetails
} from '@/features/langgraph/services/llmConfigService';
import type { PaginationProps } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { useLlmConfigRefresh } from '@/composables/useLlmConfigRefresh';
import { useRouter } from 'vue-router';

const router = useRouter();
const projectStore = useProjectStore();
const { triggerLlmConfigRefresh } = useLlmConfigRefresh();

const llmConfigs = ref<LlmConfig[]>([]);
const isLoading = ref(false);
const isModalVisible = ref(false);
const currentConfig = ref<LlmConfig | null>(null);
const isFormLoading = ref(false);

// 提示词管理弹窗相关
const isPromptModalVisible = ref(false);
const currentLlmConfigForPrompt = ref<LlmConfig | null>(null);

const showPromptManagement = () => {
  // 获取第一个激活的LLM配置作为默认配置
  const activeConfig = llmConfigs.value.find(c => c.is_active);
  currentLlmConfigForPrompt.value = activeConfig || null;
  isPromptModalVisible.value = true;
};

const closePromptModal = () => {
  isPromptModalVisible.value = false;
};

const handlePromptsUpdated = () => {
  // 提示词更新后可以执行一些刷新操作
  Message.success('提示词已更新');
};

const pagination = reactive<PaginationProps>({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

const fetchLlmConfigs = async () => {
  isLoading.value = true;
  try {
    // 注意：实际的 listLlmConfigs API 可能需要支持分页参数
    // 这里暂时获取所有数据，实际项目中应根据后端分页能力调整
    const response = await listLlmConfigs();
    if (response.status === 'success') {
      llmConfigs.value = response.data;
      // 假设 API 返回的数据本身就是分页好的，或者前端进行简单分页
      // 如果 API 支持分页，应该用 API 返回的 total
      pagination.total = response.data.length; // 简单示例，实际应从 API 获取 total
    } else {
      Message.error(response.message || '获取 LLM 配置列表失败');
    }
  } catch (error) {
    console.error('Error fetching LLM configs:', error);
    Message.error('获取 LLM 配置列表失败，请检查网络或联系管理员');
  } finally {
    isLoading.value = false;
  }
};

const handlePageChange = (page: number) => {
  pagination.current = page;
  // fetchLlmConfigs(); // 如果后端支持分页，则重新获取数据
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 通常页码大小改变后回到第一页
  // fetchLlmConfigs(); // 如果后端支持分页，则重新获取数据
};

const handleAddNewConfig = () => {
  currentConfig.value = null;
  isModalVisible.value = true;
};

const handleEditConfig = async (config: LlmConfig) => {
  // 为了获取最新的、可能包含 API Key（如果后端允许）的完整信息，或者只是为了确认数据最新
  // 可以选择在编辑前重新请求一次详细信息，但这取决于业务需求和API设计
  // 如果列表数据已足够，则不需要下面这步
  isLoading.value = true; // 可以用一个不同的 loading 状态，比如 isDetailLoading
  try {
    const response = await getLlmConfigDetails(config.id);
    if (response.status === 'success') {
      currentConfig.value = response.data;
      isModalVisible.value = true;
    } else {
      Message.error(response.message || '获取配置详情失败');
    }
  } catch (error) {
    Message.error('获取配置详情失败');
  } finally {
    isLoading.value = false;
  }
};

const handleDeleteConfig = async (configId: number) => {
  try {
    isLoading.value = true; // 或者用一个特定的删除 loading
    const response = await deleteLlmConfig(configId);
    // API 文档中 204 响应也带了 body，但通常 204 无 body
    // deleteLlmConfig service 内部已处理了 204 的情况
    if (response.status === 'success') {
      Message.success('LLM 配置删除成功');
      await fetchLlmConfigs(); // 刷新列表
      // 通知其他组件配置已更新
      triggerLlmConfigRefresh();
      // 检查当前页码是否仍然有效，如果当前页码超出了新的总页数，则调整到最后一页或第一页
      if (pagination.total > 0 && pagination.current > Math.ceil(pagination.total / pagination.pageSize)) {
        pagination.current = Math.ceil(pagination.total / pagination.pageSize);
      } else if (pagination.total === 0) {
        pagination.current = 1;
      }
    } else {
      Message.error(response.message || '删除失败');
    }
  } catch (error) {
    console.error('Error deleting LLM config:', error);
    Message.error('删除失败，请稍后再试');
  } finally {
    isLoading.value = false;
  }
};

const handleSubmitConfig = async (
  data: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest,
  id?: number
) => {
  isFormLoading.value = true;
  try {
    let response;
    if (id) {
      // 编辑模式 - API 文档中 PUT 和 PATCH 都有，这里用 PATCH 作为示例，因为它更灵活
      // 如果后端严格区分 PUT (全量) 和 PATCH (部分)，需要根据 LlmConfigFormModal 的实现来决定调用哪个
      // LlmConfigFormModal 实现的是：如果 api_key 为空字符串，则不提交该字段，适合 PATCH
      response = await partialUpdateLlmConfig(id, data as PartialUpdateLlmConfigRequest);
      // 如果需要严格的 PUT，则 LlmConfigFormModal 需要确保所有字段都提交
      // 示例：response = await updateLlmConfig(id, data as CreateLlmConfigRequest);
    } else {
      // 新增模式
      response = await createLlmConfig(data as CreateLlmConfigRequest);
    }

    if (response.status === 'success') {
      Message.success(id ? 'LLM 配置更新成功' : 'LLM 配置创建成功');
      isModalVisible.value = false;
      await fetchLlmConfigs(); // 刷新列表
      // 通知其他组件配置已更新
      triggerLlmConfigRefresh();
    } else {
      // API 返回的 errors 对象可以用于在表单中显示具体字段错误，此处简化处理
      const errorMessages = response.errors ? Object.values(response.errors).flat().join('; ') : '';
      Message.error(`${response.message}${errorMessages ? ` (${errorMessages})` : ''}` || (id ? '更新失败' : '创建失败'));
    }
  } catch (error: any) {
    console.error('Error submitting LLM config:', error);
    const errorDetail = error.response?.data?.message || error.message || (id ? '更新失败' : '创建失败');
    Message.error(errorDetail);
  } finally {
    isFormLoading.value = false;
  }
};

const handleToggleActive = async (configId: number, isActive: boolean) => {
  try {
    const response = await partialUpdateLlmConfig(configId, { is_active: isActive });
    if (response.status === 'success') {
      Message.success(isActive ? 'LLM 配置已激活' : 'LLM 配置已停用');
      await fetchLlmConfigs(); // 刷新列表
      // 通知其他组件配置已更新
      triggerLlmConfigRefresh();
    } else {
      Message.error(response.message || '更新状态失败');
      // 如果失败，刷新列表以恢复开关状态
      await fetchLlmConfigs();
    }
  } catch (error: any) {
    console.error('Error toggling LLM config active state:', error);
    const errorDetail = error.response?.data?.message || error.message || '更新状态失败';
    Message.error(errorDetail);
    // 如果失败，刷新列表以恢复开关状态
    await fetchLlmConfigs();
  }
};

const handleCloseModal = () => {
  isModalVisible.value = false;
  currentConfig.value = null; // 清除当前编辑项
};

// 处理自动保存后刷新列表（测试连接时自动保存）
const handleAutoSaved = async (closeModal = false) => {
  if (closeModal) {
    isModalVisible.value = false;
    currentConfig.value = null;
  }
  await fetchLlmConfigs();
  triggerLlmConfigRefresh();
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 项目切换时重置状态
    pagination.current = 1;

    // 重新获取LLM配置列表
    fetchLlmConfigs();
  }
}, { immediate: false });

onMounted(() => {
  fetchLlmConfigs();
});
</script>

<style scoped>
.llm-config-management {
  padding: 20px 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}
</style>

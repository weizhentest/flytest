<template>
  <a-modal
    :visible="props.visible"
    :title="isEditing ? '编辑 LLM 配置' : '新增 LLM 配置'"
    @cancel="handleCancel"
    :confirm-loading="formLoading"
    :mask-closable="false"
    width="700px"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      layout="vertical"
      @submit="handleSubmit"
    >
      <a-row :gutter="24">
        <!-- 第一行：配置名称 (全宽) -->
        <a-col :span="24">
          <a-form-item field="config_name" label="配置名称" required>
            <a-input v-model="formData.config_name" placeholder="例如: GPT-4 生产环境" />
          </a-form-item>
        </a-col>

        <!-- 第二行：供应商 + 模型名称 -->
        <a-col :span="showWireApiField ? 6 : 8">
          <a-form-item field="provider" label="供应商" required>
            <a-select
              v-model="formData.provider"
              :options="providerOptions"
              placeholder="请选择供应商"
              allow-clear
              @change="handleProviderChange"
            />
          </a-form-item>
        </a-col>
        <a-col v-if="showWireApiField" :span="6">
          <a-form-item field="wire_api" label="协议类型" required>
            <a-select
              v-model="formData.wire_api"
              :options="wireApiOptions"
              placeholder="请选择协议"
            />
          </a-form-item>
        </a-col>
        <a-col :span="showWireApiField ? 12 : 16">
          <a-form-item field="name" label="模型名称" required>
            <div class="model-input-wrapper">
              <a-auto-complete
                v-model="formData.name"
                :data="modelOptions"
                :loading="loadingModels"
                placeholder="输入或选择模型名称 (如: gpt-4-turbo)"
                allow-clear
                :filter-option="filterModelOption"
                @focus="handleModelInputFocus"
                class="model-input"
              />
              <a-tooltip content="从 API 刷新模型列表">
                <a-button
                  type="secondary"
                  :loading="loadingModels"
                  @click="fetchAvailableModels"
                >
                  <template #icon><icon-refresh /></template>
                </a-button>
              </a-tooltip>
            </div>
          </a-form-item>
        </a-col>

        <!-- 第三行：API URL + API Key -->
        <a-col :span="12">
          <a-form-item field="api_url" label="API URL" required>
            <div class="api-url-input-wrapper">
              <a-input v-model="formData.api_url" :placeholder="apiUrlPlaceholder" />
            </div>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="api_key" label="API Key" :help="apiKeyFieldHelp">
            <a-input-password
              v-model="formData.api_key"
              :placeholder="isEditing
                ? (apiKeyConfigured ? '已配置 API Key，如需修改请重新输入' : '留空不修改')
                : '请输入 API Key（可选）'"
            />
          </a-form-item>
        </a-col>

        <!-- 提示信息 + 测试按钮 -->
        <a-col :span="24" class="test-button-row">
          <span class="api-hint">{{ apiHintText }}</span>
          <a-button
            type="outline"
            status="success"
            size="small"
            :loading="testingModel"
            @click="testLlmModel"
          >
            <template #icon><icon-thunderbolt /></template>
            测试连接
          </a-button>
        </a-col>
        <a-col :span="24" v-if="diagnosticSummary || llmNoticeMessage">
          <a-alert
            :type="llmNoticeType"
            :show-icon="true"
            class="llm-diagnostic-alert"
          >
            <template #title>{{ llmNoticeTitle }}</template>
            <template #content>
              <div>{{ llmNoticeMessage }}</div>
              <div v-if="diagnosticSummary" class="llm-diagnostic-extra">{{ diagnosticSummary }}</div>
              <div v-if="hasDiagnosticsDetails" class="llm-diagnostic-actions">
                <a-button type="text" size="small" @click="showDiagnosticsDetails = !showDiagnosticsDetails">
                  {{ showDiagnosticsDetails ? '收起诊断详情' : '展开诊断详情' }}
                </a-button>
              </div>
              <div v-if="showDiagnosticsDetails && diagnosticsDetailRows.length" class="llm-diagnostic-details">
                <div
                  v-for="row in diagnosticsDetailRows"
                  :key="`${row.label}-${row.value}`"
                  class="llm-diagnostic-detail-row"
                >
                  <span class="llm-diagnostic-detail-label">{{ row.label }}</span>
                  <span class="llm-diagnostic-detail-value">{{ row.value }}</span>
                </div>
              </div>
              <div v-if="hasCompatibilityIssue" class="llm-diagnostic-actions">
                <a-button type="outline" status="warning" size="small" @click="showCompatibilitySuggestion">
                  建议切换兼容网关
                </a-button>
              </div>
            </template>
          </a-alert>
        </a-col>
        <a-col :span="24">
          <a-alert type="info" :show-icon="true" class="llm-sharing-alert">
            <template #title>共享范围</template>
            <template #content>
              管理员可以把当前 AI 大模型配置共享给组织或指定成员。被共享的成员可以直接使用，但看不到 API 地址、Key 和系统提示词等敏感内容。
            </template>
          </a-alert>
        </a-col>
        <a-col :span="12">
          <a-form-item field="shared_group_ids" label="共享给组织">
            <a-select
              v-model="formData.shared_group_ids"
              :options="organizationOptions"
              :loading="loadingOrganizations"
              placeholder="可选择多个组织共享"
              multiple
              allow-search
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="shared_user_ids" label="共享给成员">
            <a-select
              v-model="formData.shared_user_ids"
              :options="memberOptions"
              :loading="loadingMembers"
              placeholder="可选择单个或多个成员"
              multiple
              allow-search
              allow-clear
            />
          </a-form-item>
        </a-col>

        <!-- 第四行：系统提示词 (全宽) -->
        <a-col :span="24">
          <a-form-item field="system_prompt" label="系统提示词">
            <a-textarea
              v-model="formData.system_prompt"
              placeholder="设置模型的默认 System Prompt（可选）"
              :auto-size="{ minRows: 1, maxRows: 6 }"
              :max-length="2000"
              show-word-limit
            />
          </a-form-item>
        </a-col>

        <!-- 第五行：上下文限制 + 基础开关 -->
        <a-col :span="6">
          <a-form-item field="context_limit" label="上下文限制">
            <a-input-number
              v-model="formData.context_limit"
              :min="1000"
              :max="2000000"
              :step="1000"
              placeholder="128000"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="supports_vision" label="多模态">
            <a-space>
              <a-switch v-model="formData.supports_vision" />
              <span class="switch-desc">Vision</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="enable_streaming" label="流式输出">
            <a-space>
              <a-switch v-model="formData.enable_streaming" checked-color="#722ed1" />
              <span class="switch-desc">Stream</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="is_active" label="状态">
            <a-space>
              <a-switch v-model="formData.is_active" checked-color="#00b42a" />
              <span class="switch-desc">激活</span>
            </a-space>
          </a-form-item>
        </a-col>

        <!-- 第六行：中间件配置 -->
        <a-col :span="8">
          <a-form-item field="enable_summarization" label="上下文摘要">
            <a-space>
              <a-switch v-model="formData.enable_summarization" checked-color="#165dff" />
              <span class="switch-desc">超限时自动压缩对话历史</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="enable_hitl" label="人工审批">
            <a-space>
              <a-switch v-model="formData.enable_hitl" checked-color="#f77234" />
              <span class="switch-desc">高风险操作需确认</span>
            </a-space>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
    <template #footer>
      <div class="llm-modal-footer">
        <div v-if="activationRisk" class="activation-risk-hint">
          <span class="activation-risk-dot"></span>
          <span>当前配置已检测到“模型列表可用，但聊天补全异常”，不建议直接设为激活。</span>
        </div>
        <div class="llm-modal-footer-actions">
          <a-button @click="handleCancel">取消</a-button>
          <a-button
            type="primary"
            :status="activationRisk ? 'danger' : undefined"
            :loading="formLoading"
            @click="handleSubmit"
          >
            {{ submitButtonLabel }}
          </a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue';
import {
  Modal as AModal,
  Alert as AAlert,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
  InputNumber as AInputNumber,
  Textarea as ATextarea,
  Switch as ASwitch,
  AutoComplete as AAutoComplete,
  Select as ASelect,
  Button as AButton,
  Row as ARow,
  Col as ACol,
  Space as ASpace,
  Tooltip as ATooltip,
  Message,
  type FormInstance,
  type FieldRule,
} from '@arco-design/web-vue';
import { IconThunderbolt } from '@arco-design/web-vue/es/icon';
import { createLlmConfig, partialUpdateLlmConfig, testLlmConnection, fetchModels, getProviders } from '@/features/langgraph/services/llmConfigService';
import { getOrganizationList } from '@/services/organizationService';
import { getUserList } from '@/services/userService';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
  LlmConnectionDiagnostics,
} from '@/features/langgraph/types/llmConfig';

interface Props {
  visible: boolean;
  configData?: LlmConfig | null; // 用于编辑时预填数据
  formLoading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  configData: null,
  formLoading: false,
});

const emit = defineEmits<{
  (e: 'submit', data: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest, id?: number): void;
  (e: 'cancel'): void;
  (e: 'auto-saved', closeModal?: boolean): void;
}>();

const formRef = ref<FormInstance | null>(null);
const modelOptions = ref<string[]>([]);
const providerOptions = ref<Array<{ label: string; value: string }>>([
  { label: 'OpenAI 兼容', value: 'openai_compatible' },
  { label: '硅基流动', value: 'siliconflow' },
  { label: 'Qwen/通义千问', value: 'qwen' },
]);
const wireApiOptions = ref<Array<{ label: string; value: string }>>([
  { label: 'OpenAI Chat', value: 'chat_completions' },
  { label: 'Claude Messages', value: 'messages' },
]);
const loadingModels = ref(false);
const testingModel = ref(false);
const lastModelsFetchStatus = ref<'success' | 'error' | ''>('');
const lastModelsFetchMessage = ref('');
const lastModelsDiagnostics = ref<LlmConnectionDiagnostics | null>(null);
const lastConnectionMessage = ref('');
const lastConnectionStatus = ref<'success' | 'warning' | 'error' | ''>('');
const lastConnectionDiagnostics = ref<LlmConnectionDiagnostics | null>(null);
const showDiagnosticsDetails = ref(false);
const hasPersistedApiKey = ref(false);
const organizationOptions = ref<Array<{ label: string; value: number }>>([]);
const memberOptions = ref<Array<{ label: string; value: number }>>([]);
const loadingOrganizations = ref(false);
const loadingMembers = ref(false);
const QWEN_DEFAULT_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
const SILICONFLOW_DEFAULT_API_URL = 'https://api.siliconflow.cn/v1';
const defaultFormData: CreateLlmConfigRequest = {
  config_name: '',
  provider: 'openai_compatible',
  wire_api: 'chat_completions',
  name: '',
  api_url: '',
  api_key: '',
  system_prompt: '',
  supports_vision: false,
  context_limit: 128000,
  enable_summarization: true,
  enable_hitl: false,
  enable_streaming: true,
  is_active: false,
  shared_group_ids: [],
  shared_user_ids: [],
};
const formData = ref<CreateLlmConfigRequest>({ ...defaultFormData });
const currentConfigId = ref<number | null>(null);

// 编辑模式：考虑 props.configData 或自动保存后的 currentConfigId
const isEditing = computed(() => !!(props.configData?.id || currentConfigId.value));
// 获取当前配置ID（优先 props，其次是自动保存后的 currentConfigId）
const effectiveConfigId = computed(() => props.configData?.id || currentConfigId.value);
const apiKeyConfigured = computed(() => hasPersistedApiKey.value || Boolean(props.configData?.has_api_key));
const showWireApiField = computed(() => formData.value.provider === 'openai_compatible');

const formRules: Record<string, FieldRule[]> = {
  config_name: [{ required: true, message: '配置名称不能为空' }],
  provider: [{ required: true, message: '供应商不能为空' }],
  wire_api: [{ required: true, message: '协议类型不能为空' }],
  name: [{ required: true, message: '模型名称不能为空' }],
  api_url: [
    { required: true, message: 'API URL 不能为空' },
    { type: 'url', message: '请输入有效的 URL' },
  ],
};

const apiUrlPlaceholder = computed(() => (
  formData.value.provider === 'siliconflow'
    ? SILICONFLOW_DEFAULT_API_URL
    : formData.value.provider === 'qwen'
    ? QWEN_DEFAULT_API_URL
    : 'https://api.openai.com/v1'
));

const apiHintText = computed(() => (
  formData.value.wire_api === 'messages'
    ? 'Claude Messages 将调用 /messages，并使用 Claude 兼容请求格式'
    : formData.value.provider === 'siliconflow'
    ? '硅基流动使用官方 OpenAI 兼容接口，可通过 /v1/models 获取模型列表'
    : formData.value.provider === 'qwen'
    ? 'Qwen 建议使用 DashScope 兼容地址（可自定义）'
    : 'OpenAI 兼容供应商请填写兼容 API 地址'
));

const apiKeyFieldHelp = computed(() => (
  isEditing.value && apiKeyConfigured.value
    ? '当前已保存 API Key。如需修改，请重新输入新的 Key；留空表示保持原值。'
    : undefined
));

const diagnosticSummary = computed(() => {
  const tips: string[] = [];

  if (!formData.value.name.trim()) {
    tips.push('建议先点击“刷新模型列表”，确认当前模型名称与接口实际返回的模型 ID 一致。');
  }

  if (isEditing.value && !formData.value.api_key) {
    tips.push('编辑已有配置时，如果本次不修改 API Key，可以留空继续测试。');
  }

  return tips.join(' ');
});

const llmNoticeType = computed<'info' | 'warning' | 'success' | 'error'>(() => {
  if (hasCompatibilityIssue.value) return 'warning';
  if (lastConnectionStatus.value === 'success') return 'success';
  if (lastConnectionStatus.value === 'warning') return 'warning';
  if (lastConnectionStatus.value === 'error') return 'error';
  return diagnosticSummary.value ? 'warning' : 'info';
});

const llmNoticeTitle = computed(() => {
  if (hasCompatibilityIssue.value) return '基础连通性正常，聊天补全异常';
  if (lastConnectionStatus.value === 'success') return '最近一次连接测试';
  if (lastConnectionStatus.value === 'warning') return '连接测试提示';
  if (lastConnectionStatus.value === 'error') return '连接测试失败';
  return '配置建议';
});

const llmNoticeMessage = computed(() => {
  if (hasCompatibilityIssue.value) {
    return (
      `${lastModelsFetchMessage.value || '模型列表接口可用。'} `
      + '但聊天补全返回空正文，说明当前网关很可能只部分兼容 OpenAI。'
    );
  }
  return lastConnectionMessage.value;
});

const hasCompatibilityIssue = computed(() => (
  lastModelsFetchStatus.value === 'success'
  && lastConnectionStatus.value === 'warning'
  && /聊天响应正文为空|不完全兼容/i.test(lastConnectionMessage.value)
));

const hasDiagnosticsDetails = computed(() => (
  Boolean(lastModelsDiagnostics.value || lastConnectionDiagnostics.value)
));

const diagnosticsDetailRows = computed(() => {
  const rows: Array<{ label: string; value: string }> = [];

  const modelRows = lastModelsDiagnostics.value
    ? [
        { label: '模型列表接口', value: lastModelsFetchMessage.value || lastModelsDiagnostics.value.conclusion || '-' },
        { label: '模型列表结论', value: lastModelsDiagnostics.value.conclusion || '-' },
        { label: '模型数量', value: String(lastModelsDiagnostics.value.models_count ?? '-') },
      ]
    : [];

  const connectionRows = lastConnectionDiagnostics.value
    ? [
        { label: '聊天补全接口', value: lastConnectionMessage.value || lastConnectionDiagnostics.value.conclusion || '-' },
        { label: '聊天补全结论', value: lastConnectionDiagnostics.value.conclusion || '-' },
        { label: 'Finish Reason', value: lastConnectionDiagnostics.value.finish_reason || '-' },
        { label: 'Prompt Tokens', value: String(lastConnectionDiagnostics.value.prompt_tokens ?? '-') },
        { label: 'Completion Tokens', value: String(lastConnectionDiagnostics.value.completion_tokens ?? '-') },
        { label: 'Total Tokens', value: String(lastConnectionDiagnostics.value.total_tokens ?? '-') },
        { label: '返回正文', value: lastConnectionDiagnostics.value.response_text_present ? '有' : '无' },
      ]
    : [];

  const sharedSource = lastConnectionDiagnostics.value || lastModelsDiagnostics.value;
  if (sharedSource) {
    rows.push(
      { label: '接口地址', value: sharedSource.endpoint || formData.value.api_url || '-' },
      { label: '供应商', value: sharedSource.provider || formData.value.provider || '-' },
      { label: '模型名称', value: sharedSource.model || formData.value.name || '-' },
    );
  }

  return [...rows, ...modelRows, ...connectionRows].filter(
    (row, index, self) =>
      row.value &&
      self.findIndex((item) => item.label === row.label && item.value === row.value) === index
  );
});

const activationRisk = computed(() => hasCompatibilityIssue.value && formData.value.is_active);

const submitButtonLabel = computed(() => (
  isEditing.value ? '保存配置' : '创建配置'
));

const loadProviderOptions = async () => {
  try {
    const response = await getProviders();
    if (response.status === 'success' && response.data?.choices?.length) {
      providerOptions.value = response.data.choices.map((item) => ({
        label: item.label,
        value: item.value,
      }));
    }
  } catch (error) {
    console.warn('加载供应商列表失败，使用默认选项', error);
  }
};

const handleProviderChange = (provider?: string) => {
  if (provider && provider !== 'openai_compatible') {
    formData.value.wire_api = 'chat_completions';
  }
  if (provider === 'siliconflow' && !formData.value.api_url) {
    formData.value.api_url = SILICONFLOW_DEFAULT_API_URL;
  }
  if (provider === 'qwen' && !formData.value.api_url) {
    formData.value.api_url = QWEN_DEFAULT_API_URL;
  }
  if (provider === 'qwen' && formData.value.wire_api === 'messages') {
    formData.value.wire_api = 'chat_completions';
  }
};

const loadShareTargets = async () => {
  loadingOrganizations.value = true;
  loadingMembers.value = true;
  try {
    const [orgResponse, userResponse] = await Promise.all([
      getOrganizationList({ page: 1, pageSize: 200, search: '' }),
      getUserList({ page: 1, pageSize: 200, search: '' }),
    ]);

    if (orgResponse.success && orgResponse.data) {
      organizationOptions.value = orgResponse.data.map(item => ({
        label: item.name,
        value: item.id,
      }));
    }

    if (userResponse.success && userResponse.data) {
      memberOptions.value = userResponse.data.map(item => ({
        label: `${item.username}${item.email ? ` (${item.email})` : ''}`,
        value: item.id,
      }));
    }
  } finally {
    loadingOrganizations.value = false;
    loadingMembers.value = false;
  }
};


watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      currentConfigId.value = null;
      hasPersistedApiKey.value = Boolean(props.configData?.has_api_key);
      void loadProviderOptions();
      void loadShareTargets();
      if (props.configData && props.configData.id) {
        // 编辑模式：填充表单，但不包括 API Key（除非用户想修改）
        formData.value = {
          config_name: props.configData.config_name,
          provider: props.configData.provider || 'openai_compatible',
          wire_api: props.configData.wire_api || 'chat_completions',
          name: props.configData.name,
          api_url: props.configData.api_url,
          api_key: '', // 编辑时不显示旧 Key，留空表示不修改
          system_prompt: props.configData.system_prompt || '',
          supports_vision: props.configData.supports_vision || false,
          context_limit: props.configData.context_limit || 128000,
          enable_summarization: props.configData.enable_summarization ?? true,
          enable_hitl: props.configData.enable_hitl || false,
          enable_streaming: props.configData.enable_streaming ?? true,
          is_active: props.configData.is_active,
          shared_group_ids: props.configData.shared_groups?.map(item => item.id) || [],
          shared_user_ids: props.configData.shared_users?.map(item => item.id) || [],
        };
      } else {
        // 新增模式：重置表单
        formData.value = { ...defaultFormData };
      }
      handleProviderChange(formData.value.provider);
      lastModelsFetchStatus.value = '';
      lastModelsFetchMessage.value = '';
      lastModelsDiagnostics.value = null;
      lastConnectionMessage.value = '';
      lastConnectionStatus.value = '';
      lastConnectionDiagnostics.value = null;
      showDiagnosticsDetails.value = false;
      // 清除之前的校验状态
      nextTick(() => {
        formRef.value?.clearValidate();
      });
    }
  }
);

watch(
  () => [formData.value.provider, formData.value.api_url, formData.value.api_key, formData.value.name],
  () => {
    lastModelsFetchStatus.value = '';
    lastModelsFetchMessage.value = '';
    lastModelsDiagnostics.value = null;
    lastConnectionMessage.value = '';
    lastConnectionStatus.value = '';
    lastConnectionDiagnostics.value = null;
    showDiagnosticsDetails.value = false;
  }
);

const handleSubmit = async () => {
  if (!formRef.value) return;
  if (activationRisk.value) {
    showToast('warning', '当前配置存在兼容风险，建议先修复连接问题后再设为激活。');
  }
  const validation = await formRef.value.validate();
  if (validation) {
    // 校验失败
    showToast('error', '请检查表单输入！');
    return;
  }

  let submitData: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest;

  if (isEditing.value && effectiveConfigId.value) {
    // 编辑模式（包括自动保存后的情况）
    const partialData: PartialUpdateLlmConfigRequest = {
      config_name: formData.value.config_name,
      provider: formData.value.provider,
      wire_api: formData.value.wire_api,
      name: formData.value.name,
      api_url: formData.value.api_url,
      is_active: formData.value.is_active,
      shared_group_ids: formData.value.shared_group_ids || [],
      shared_user_ids: formData.value.shared_user_ids || [],
    };
    if (formData.value.api_key) { // 只有当用户输入了新的 API Key 时才包含它
      partialData.api_key = formData.value.api_key;
    }
    if (formData.value.system_prompt !== undefined) { // 包含系统提示词（可以为空字符串）
      partialData.system_prompt = formData.value.system_prompt;
    }
    if (formData.value.supports_vision !== undefined) { // 包含多模态支持
      partialData.supports_vision = formData.value.supports_vision;
    }
    if (formData.value.context_limit !== undefined) { // 包含上下文限制
      partialData.context_limit = formData.value.context_limit;
    }
    if (formData.value.enable_summarization !== undefined) { // 包含上下文摘要
      partialData.enable_summarization = formData.value.enable_summarization;
    }
    if (formData.value.enable_hitl !== undefined) { // 包含人工审批
      partialData.enable_hitl = formData.value.enable_hitl;
    }
    if (formData.value.enable_streaming !== undefined) { // 包含流式输出
      partialData.enable_streaming = formData.value.enable_streaming;
    }
    submitData = partialData;
    emit('submit', submitData, effectiveConfigId.value);
  } else {
    // 新增模式
    submitData = { ...formData.value };
    emit('submit', submitData);
  }
};

const handleCancel = () => {
  emit('cancel');
};

const getReadableErrorMessage = (error: any, fallback: string) => {
  return (
    error?.error
    || error?.message
    || error?.response?.data?.message
    || error?.response?.data?.detail
    || fallback
  );
};

const showToast = (
  type: 'success' | 'warning' | 'error',
  content: string,
  duration = 10000
) => {
  Message[type]({
    content,
    duration,
  });
};

const showCompatibilitySuggestion = () => {
  const suggestion = '建议切换到能够稳定返回正文的模型或网关，或联系服务商确认当前模型是否支持标准文本输出。';
  showToast('warning', suggestion);
};

// 从后端 API 获取可用模型列表
const fetchAvailableModels = async () => {
  if (!formData.value.api_url) {
    showToast('warning', '请先填写 API URL');
    return;
  }

  loadingModels.value = true;

  try {
    // 编辑模式时传递 configId，让后端从数据库获取 API Key
    const configId = props.configData?.id;
    const response = await fetchModels(
      formData.value.api_url,
      formData.value.api_key || undefined,
      configId
    );
    
    if (response.status === 'success' && response.data?.models) {
      lastModelsFetchStatus.value = 'success';
      lastModelsFetchMessage.value = response.data.models.length > 0
        ? `模型列表接口可用，已检测到 ${response.data.models.length} 个模型。`
        : '模型列表接口可用，但当前未返回任何模型。';
      lastModelsDiagnostics.value = response.data.diagnostics || null;
      modelOptions.value = response.data.models;
      if (response.data.models.length > 0) {
        showToast('success', `成功获取 ${response.data.models.length} 个模型`);
      } else {
        showToast('warning', '未找到可用模型');
      }
    } else {
      lastModelsFetchStatus.value = 'error';
      lastModelsFetchMessage.value = response.message || '模型列表接口不可用';
      lastModelsDiagnostics.value = response.data?.diagnostics || null;
      showToast('error', response.message || '获取模型列表失败');
      modelOptions.value = [];
    }
  } catch (error: any) {
    console.error('获取模型列表失败:', error);
    const readableMessage = getReadableErrorMessage(error, '获取模型列表失败');
    lastModelsFetchStatus.value = 'error';
    lastModelsFetchMessage.value = readableMessage;
    lastModelsDiagnostics.value = null;
    showToast('error', readableMessage);
    modelOptions.value = [];
  } finally {
    loadingModels.value = false;
  }
};

// 测试 LLM 模型连接（后端发起测试）
const testLlmModel = async () => {
  if (!formRef.value) return;
  const validation = await formRef.value.validate();
  if (validation) {
    showToast('error', '请先完善表单必填项');
    return;
  }

  testingModel.value = true;
  try {
    let configId = props.configData?.id || currentConfigId.value;

    // 如果是新建且未保存，先保存
    if (!configId) {
      const createResp = await createLlmConfig(formData.value);
      if (createResp.status !== 'success' || !createResp.data) {
        showToast('error', createResp.message || '保存配置失败');
        return;
      }
      configId = createResp.data.id;
      currentConfigId.value = configId;
      hasPersistedApiKey.value = hasPersistedApiKey.value || Boolean(formData.value.api_key);
      showToast('success', '配置已自动保存');
      emit('auto-saved', false); // false 表示不关闭弹窗
    } else if (isEditing.value) {
      // 编辑模式：先保存更改
      const partialData: PartialUpdateLlmConfigRequest = {
        config_name: formData.value.config_name,
        provider: formData.value.provider,
        name: formData.value.name,
        api_url: formData.value.api_url,
        is_active: formData.value.is_active,
      };
      if (formData.value.api_key) partialData.api_key = formData.value.api_key;
      if (formData.value.system_prompt !== undefined) partialData.system_prompt = formData.value.system_prompt;
      if (formData.value.supports_vision !== undefined) partialData.supports_vision = formData.value.supports_vision;
      if (formData.value.context_limit !== undefined) partialData.context_limit = formData.value.context_limit;
      const updateResp = await partialUpdateLlmConfig(configId, partialData);
      if (updateResp.status !== 'success') {
        showToast('error', updateResp.message || '保存配置失败');
        return;
      }
      hasPersistedApiKey.value = hasPersistedApiKey.value || Boolean(formData.value.api_key) || Boolean(props.configData?.has_api_key);
    }

    // 调用后端测试接口
    const testResp = await testLlmConnection(configId);
    const backendStatus = testResp.data?.status || testResp.status;
    const backendMessage = testResp.data?.message || testResp.message || '连接测试完成';
    lastConnectionDiagnostics.value = testResp.data?.diagnostics || null;
    lastConnectionStatus.value =
      backendStatus === 'success' || backendStatus === 'warning' || backendStatus === 'error'
        ? backendStatus
        : 'error';
    lastConnectionMessage.value = backendMessage;
    if (backendStatus === 'success') {
      showToast('success', backendMessage);
    } else if (backendStatus === 'warning') {
      showToast('warning', backendMessage);
    } else {
      showToast('error', backendMessage);
    }
  } catch (error: any) {
    console.error('测试失败:', error);
    const readableMessage = getReadableErrorMessage(error, '测试连接失败');
    lastConnectionDiagnostics.value = null;
    lastConnectionStatus.value = 'error';
    lastConnectionMessage.value = readableMessage;
    showToast('error', readableMessage);
  } finally {
    testingModel.value = false;
  }
};

// 处理模型输入框聚焦
const handleModelInputFocus = () => {
  if (formData.value.api_url && modelOptions.value.length === 0) {
    fetchAvailableModels();
  }
};

// 自定义模型过滤，没输入时显示全部，输入时模糊匹配
const filterModelOption = (inputValue: string, option: { value: string }) => {
  if (!inputValue) {
    return true; // 没有输入时显示全部
  }
  return option.value.toLowerCase().includes(inputValue.toLowerCase());
};
</script>

<style scoped>
.model-input-wrapper {
  display: flex;
  width: 100%;
  gap: 8px;
  align-items: center;
}

.model-input {
  flex: 1;
}

.api-url-input-wrapper {
  display: flex;
  width: 100%;
  gap: 8px;
  align-items: center;
}

.api-url-input-wrapper :deep(.arco-input-wrapper) {
  flex: 1;
}

.api-url-fix-button {
  flex-shrink: 0;
}

.test-button-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  margin-top: -8px;
}

.api-hint {
  font-size: 12px;
  color: var(--color-text-3);
}

.llm-diagnostic-alert {
  margin-bottom: 16px;
}

.llm-sharing-alert {
  margin-bottom: 16px;
}

.llm-diagnostic-extra {
  margin-top: 8px;
  color: var(--color-text-2);
  line-height: 1.6;
}

.llm-diagnostic-actions {
  margin-top: 12px;
}

.llm-diagnostic-details {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
  display: grid;
  gap: 8px;
}

.llm-diagnostic-detail-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px;
  align-items: start;
}

.llm-diagnostic-detail-label {
  font-size: 12px;
  color: var(--color-text-3);
  font-weight: 600;
}

.llm-diagnostic-detail-value {
  font-size: 12px;
  color: var(--color-text-2);
  line-height: 1.6;
  word-break: break-word;
}

.llm-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}

.llm-modal-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.activation-risk-hint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #b42318;
  font-size: 12px;
  line-height: 1.5;
  max-width: 420px;
}

.activation-risk-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
  flex-shrink: 0;
}

.switch-desc {
  font-size: 13px;
  color: var(--color-text-3);
  cursor: pointer;
}
</style>

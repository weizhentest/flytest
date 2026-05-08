<template>
  <a-modal
    :visible="visible"
    title="AI生成测试用例"
    :width="840"
    :confirm-loading="generating"
    @cancel="handleCancel"
    @ok="handleOk"
  >
    <a-form :model="formState" layout="vertical">
      <div class="header-row">
        <div class="header-item">
          <span class="header-label">当前项目</span>
          <a-input :model-value="currentProjectName" disabled />
        </div>
        <div class="header-item header-item--mode">
          <span class="header-label">生成模式</span>
          <a-radio-group v-model="formState.generateMode" type="button" @change="handleModeChange">
            <a-radio value="full">完整生成</a-radio>
            <a-radio value="title_only">标题生成</a-radio>
            <a-radio value="kb_complete">知识库补全</a-radio>
            <a-radio value="kb_generate">知识生成</a-radio>
          </a-radio-group>
        </div>
      </div>

      <div class="test-type-row">
        <span class="section-title required">测试类型</span>
        <a-checkbox-group v-model="formState.testTypes" class="test-type-checkboxes">
          <a-checkbox value="smoke">冒烟测试</a-checkbox>
          <a-checkbox value="functional">功能测试</a-checkbox>
          <a-checkbox value="boundary">边界测试</a-checkbox>
          <a-checkbox value="exception">异常测试</a-checkbox>
          <a-checkbox value="permission">权限测试</a-checkbox>
          <a-checkbox value="security">安全测试</a-checkbox>
          <a-checkbox value="compatibility">兼容性测试</a-checkbox>
        </a-checkbox-group>
      </div>

      <div v-if="showRequirementFields" class="form-row">
        <div class="form-row-item">
          <span class="section-title required">需求文档</span>
          <a-select
            v-model="formState.requirementDocumentId"
            placeholder="请选择需求文档"
            :loading="isDocLoading"
            allow-search
            @change="handleDocumentChange"
          >
            <a-option v-for="doc in requirementDocuments" :key="doc.id" :value="doc.id">
              {{ doc.title }}
            </a-option>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="section-title required">需求模块</span>
          <a-select
            v-model="formState.requirementModuleId"
            placeholder="请先选择需求文档"
            :loading="isReqModuleLoading"
            :disabled="!formState.requirementDocumentId"
            allow-search
          >
            <a-option v-for="module in requirementModules" :key="module.id" :value="module.id">
              {{ module.title }}
            </a-option>
          </a-select>
        </div>
      </div>

      <div v-if="showSaveModuleField" class="form-row form-row-3">
        <div class="form-row-item">
          <span class="section-title required">提示词</span>
          <a-select
            v-model="formState.promptId"
            placeholder="请选择提示词"
            :loading="isPromptsLoading"
            allow-search
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div class="empty-wrap">
                <a-empty description="暂无可用提示词" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="section-title">知识库</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            placeholder="不使用知识库"
            :loading="isKbLoading"
            allow-clear
            allow-search
            @clear="formState.useKnowledgeBase = false"
            @change="(val: string | null) => (formState.useKnowledgeBase = !!val)"
          >
            <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="section-title required">保存模块</span>
          <a-tree-select
            v-model="formState.testCaseModuleId"
            :data="testCaseModuleTree"
            placeholder="请选择保存模块"
            allow-clear
          />
        </div>
      </div>

      <div v-if="showSaveModuleField" class="form-row">
        <div class="form-row-item form-row-item-full">
          <span class="section-title">追加提示词</span>
          <a-textarea
            v-model="formState.extraPrompt"
            placeholder="选填。比如补充关注异常场景、边界值、权限差异等。"
            allow-clear
            :max-length="1000"
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </div>
      </div>

      <div v-else class="form-row">
        <div class="form-row-item">
          <span class="section-title required">提示词</span>
          <a-select
            v-model="formState.promptId"
            placeholder="请选择提示词"
            :loading="isPromptsLoading"
            allow-search
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div class="empty-wrap">
                <a-empty description="暂无可用提示词" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="section-title required">关联知识库</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            placeholder="请选择知识库"
            :loading="isKbLoading"
            allow-clear
            allow-search
          >
            <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </div>
      </div>

      <div v-if="showTestCaseSelector" class="selector-section">
        <div class="selector-header">
          <span class="section-title required">选择测试用例</span>
          <span class="selected-count">已选 {{ selectedTestCaseIds.length }} 条</span>
        </div>
        <div class="selector-toolbar">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索用例名称"
            allow-clear
            @search="handleSearch"
          />
          <a-select
            v-model="selectedModule"
            placeholder="筛选模块"
            allow-clear
            :loading="modulesLoading"
            @change="handleModuleFilterChange"
          >
            <a-option v-for="module in flatModuleList" :key="module.id" :value="module.id">
              {{ module.indentName }}
            </a-option>
          </a-select>
          <a-select
            v-model="selectedLevel"
            placeholder="优先级"
            allow-clear
            @change="handleLevelFilterChange"
          >
            <a-option value="P0">P0</a-option>
            <a-option value="P1">P1</a-option>
            <a-option value="P2">P2</a-option>
            <a-option value="P3">P3</a-option>
          </a-select>
        </div>

        <a-table
          :columns="testCaseColumns"
          :data="testCaseData"
          :pagination="paginationConfig"
          :loading="testCaseLoading"
          :scroll="{ y: 260 }"
          :bordered="{ cell: true }"
          row-key="id"
          size="small"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
        >
          <template #selection="{ record }">
            <a-checkbox
              :model-value="selectedTestCaseIds.includes(record.id)"
              @change="(checked: boolean) => handleCheckboxChange(record.id, checked)"
            />
          </template>
          <template #selectAll>
            <a-checkbox
              :model-value="isCurrentPageAllSelected"
              :indeterminate="isCurrentPageIndeterminate"
              @change="handleSelectCurrentPage"
            />
          </template>
          <template #level="{ record }">
            <a-tag :color="getLevelColor(record.level)">{{ record.level }}</a-tag>
          </template>
        </a-table>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import type { TreeNodeData } from '@arco-design/web-vue';
import { RequirementDocumentService } from '@/features/requirements/services/requirementService';
import type { DocumentModule, RequirementDocument } from '@/features/requirements/types';
import { getUserPrompts } from '@/features/prompts/services/promptService';
import type { UserPrompt, UserPromptListResponseData } from '@/features/prompts/types/prompt';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';
import { getTestCaseModules, type TestCaseModule } from '@/services/testcaseModuleService';
import { getLevelColor } from '@/utils/formatters';

type GenerateMode = 'full' | 'title_only' | 'kb_complete' | 'kb_generate';
type InitialValues = {
  generateMode?: GenerateMode;
  requirementDocumentId?: string | null;
  requirementModuleId?: string | null;
  promptId?: number | null;
  useKnowledgeBase?: boolean;
  knowledgeBaseId?: string | null;
  testTypes?: string[];
  extraPrompt?: string;
} | null;

const props = defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  generating: {
    type: Boolean,
    default: false,
  },
  testCaseModuleTree: {
    type: Array as PropType<TreeNodeData[]>,
    default: () => [],
  },
  initialModuleId: {
    type: Number,
    default: null,
  },
  initialValues: {
    type: Object as PropType<InitialValues>,
    default: null,
  },
});

const emit = defineEmits(['update:visible', 'submit']);

const projectStore = useProjectStore();

const isDocLoading = ref(false);
const isReqModuleLoading = ref(false);
const isPromptsLoading = ref(false);
const isKbLoading = ref(false);
const testCaseLoading = ref(false);
const modulesLoading = ref(false);

const requirementDocuments = ref<RequirementDocument[]>([]);
const requirementModules = ref<DocumentModule[]>([]);
const prompts = ref<UserPrompt[]>([]);
const knowledgeBases = ref<KnowledgeBase[]>([]);
const testCaseData = ref<TestCase[]>([]);
const moduleList = ref<TestCaseModule[]>([]);
const selectedTestCaseIds = ref<number[]>([]);
const searchKeyword = ref('');
const selectedModule = ref<number | undefined>(undefined);
const selectedLevel = ref('');

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
});

const testCaseColumns = [
  { title: '选择', slotName: 'selection', width: 56, titleSlotName: 'selectAll', align: 'center' as const },
  { title: 'ID', dataIndex: 'id', width: 72 },
  { title: '用例名称', dataIndex: 'name', ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 88 },
  { title: '所属模块', dataIndex: 'module_detail', ellipsis: true, tooltip: true, width: 180 },
];

const formState = reactive({
  generateMode: 'full' as GenerateMode,
  requirementDocumentId: null as string | null,
  requirementModuleId: null as string | null,
  promptId: null as number | null,
  useKnowledgeBase: false,
  knowledgeBaseId: null as string | null,
  testCaseModuleId: null as number | null,
  testTypes: ['functional'] as string[],
  extraPrompt: '',
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '未命名项目');
const showRequirementFields = computed(() => ['full', 'title_only', 'kb_generate'].includes(formState.generateMode));
const showSaveModuleField = computed(() => ['full', 'title_only'].includes(formState.generateMode));
const showTestCaseSelector = computed(() => ['kb_complete', 'kb_generate'].includes(formState.generateMode));

const flatModuleList = computed(() => {
  const flatList: Array<TestCaseModule & { indentName: string }> = [];
  const flatten = (modules: TestCaseModule[], level = 0) => {
    modules.forEach((module) => {
      flatList.push({
        ...module,
        indentName: `${'  '.repeat(level)}${module.name}`,
      });
      if (Array.isArray(module.children) && module.children.length > 0) {
        flatten(module.children, level + 1);
      }
    });
  };
  flatten(moduleList.value);
  return flatList;
});

const isCurrentPageAllSelected = computed(() => {
  if (testCaseData.value.length === 0) return false;
  return testCaseData.value.every((item) => selectedTestCaseIds.value.includes(item.id));
});

const isCurrentPageIndeterminate = computed(() => {
  const count = testCaseData.value.filter((item) => selectedTestCaseIds.value.includes(item.id)).length;
  return count > 0 && count < testCaseData.value.length;
});

const resetModalState = () => {
  formState.generateMode = 'full';
  formState.requirementDocumentId = null;
  formState.requirementModuleId = null;
  formState.promptId = null;
  formState.useKnowledgeBase = false;
  formState.knowledgeBaseId = null;
  formState.testCaseModuleId = props.initialModuleId ?? null;
  formState.testTypes = ['functional'];
  formState.extraPrompt = '';

  requirementDocuments.value = [];
  requirementModules.value = [];
  prompts.value = [];
  knowledgeBases.value = [];
  testCaseData.value = [];
  moduleList.value = [];
  selectedTestCaseIds.value = [];
  searchKeyword.value = '';
  selectedModule.value = undefined;
  selectedLevel.value = '';
  paginationConfig.current = 1;
  paginationConfig.total = 0;
};

const applyInitialValues = async () => {
  const initialValues = props.initialValues;
  formState.testCaseModuleId = props.initialModuleId ?? formState.testCaseModuleId;

  if (!initialValues) {
    return;
  }

  formState.generateMode = initialValues.generateMode || 'full';
  formState.promptId = initialValues.promptId ?? null;
  formState.useKnowledgeBase = !!initialValues.useKnowledgeBase;
  formState.knowledgeBaseId = initialValues.knowledgeBaseId ?? null;
  formState.testTypes =
    Array.isArray(initialValues.testTypes) && initialValues.testTypes.length > 0
      ? [...initialValues.testTypes]
      : ['functional'];
  formState.extraPrompt = initialValues.extraPrompt || '';

  if (initialValues.requirementDocumentId) {
    formState.requirementDocumentId = initialValues.requirementDocumentId;
    await fetchRequirementModules(initialValues.requirementDocumentId, {
      preserveSelection: true,
      preferredModuleId: initialValues.requirementModuleId ?? null,
    });
  }
};

const initializeModalData = async () => {
  resetModalState();
  await Promise.all([fetchRequirementDocuments(), fetchPrompts(), fetchKnowledgeBases()]);
  await applyInitialValues();
  if (showTestCaseSelector.value) {
    await Promise.all([fetchModules(), fetchTestCases()]);
  }
};

const handleCancel = () => {
  emit('update:visible', false);
};

const handleOk = () => {
  if (!formState.testTypes.length) {
    Message.error('请至少选择一种测试类型');
    return;
  }

  if (!formState.promptId) {
    Message.error('请选择提示词');
    return;
  }

  if (showSaveModuleField.value) {
    if (!formState.requirementDocumentId || !formState.requirementModuleId || !formState.testCaseModuleId) {
      Message.error('请填写所有必填项');
      return;
    }
  }

  if (formState.generateMode === 'kb_generate') {
    if (!formState.requirementDocumentId || !formState.requirementModuleId) {
      Message.error('请选择需求文档和需求模块');
      return;
    }
  }

  if (showTestCaseSelector.value) {
    if (!formState.knowledgeBaseId) {
      Message.error('请选择知识库');
      return;
    }
    if (selectedTestCaseIds.value.length === 0) {
      Message.error('请至少选择一条测试用例');
      return;
    }
  }

  if (showSaveModuleField.value && formState.useKnowledgeBase && !formState.knowledgeBaseId) {
    Message.error('启用知识库后必须选择一个知识库');
    return;
  }

  const selectedReqDocument = requirementDocuments.value.find((item) => item.id === formState.requirementDocumentId);
  const selectedReqModule = requirementModules.value.find((item) => item.id === formState.requirementModuleId);
  const selectedTestCases = testCaseData.value.filter((item) => selectedTestCaseIds.value.includes(item.id));

  emit('submit', {
    ...formState,
    selectedDocument: selectedReqDocument,
    selectedModule: selectedReqModule,
    selectedTestCaseIds: selectedTestCaseIds.value,
    selectedTestCases,
  });
  emit('update:visible', false);
};

const handleModeChange = async () => {
  selectedTestCaseIds.value = [];
  if (showTestCaseSelector.value) {
    await Promise.all([fetchModules(), fetchTestCases()]);
  }
};

const fetchRequirementDocuments = async () => {
  if (!projectStore.currentProjectId) return;
  isDocLoading.value = true;
  try {
    const response = await RequirementDocumentService.getDocumentList({
      project: String(projectStore.currentProjectId),
    });
    if (response.status === 'success' && Array.isArray(response.data)) {
      requirementDocuments.value = response.data;
      return;
    }
    if (response.status === 'success' && response.data && 'results' in response.data) {
      requirementDocuments.value = response.data.results;
      return;
    }
    requirementDocuments.value = [];
    Message.error('加载需求文档失败');
  } catch (error) {
    requirementDocuments.value = [];
    Message.error('加载需求文档失败');
  } finally {
    isDocLoading.value = false;
  }
};

const fetchRequirementModules = async (
  documentId: string,
  options?: { preserveSelection?: boolean; preferredModuleId?: string | null }
) => {
  isReqModuleLoading.value = true;
  requirementModules.value = [];
  if (!options?.preserveSelection) {
    formState.requirementModuleId = null;
  }

  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);
    if (response.status === 'success' && response.data?.modules) {
      requirementModules.value = response.data.modules;
      if (options?.preferredModuleId) {
        const matched = requirementModules.value.find((item) => item.id === options.preferredModuleId);
        formState.requirementModuleId = matched ? matched.id : null;
      }
      return;
    }
    Message.error('加载需求模块失败');
  } catch (error) {
    Message.error('加载需求模块失败');
  } finally {
    isReqModuleLoading.value = false;
  }
};

const handleDocumentChange = async (value: string | null) => {
  if (!value) {
    requirementModules.value = [];
    formState.requirementModuleId = null;
    return;
  }
  await fetchRequirementModules(value);
};

const fetchPrompts = async () => {
  isPromptsLoading.value = true;
  try {
    const response = await getUserPrompts({ prompt_type: 'general' });
    if (response.status === 'success') {
      if (Array.isArray(response.data)) {
        prompts.value = response.data;
      } else if ((response.data as UserPromptListResponseData)?.results) {
        prompts.value = (response.data as UserPromptListResponseData).results;
      } else {
        prompts.value = [];
      }
      return;
    }
    prompts.value = [];
    Message.error(response.message || '加载提示词失败');
  } catch (error) {
    prompts.value = [];
    Message.error('加载提示词失败');
  } finally {
    isPromptsLoading.value = false;
  }
};

const fetchKnowledgeBases = async () => {
  if (!projectStore.currentProjectId) return;
  isKbLoading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({ project: projectStore.currentProjectId });
    knowledgeBases.value = Array.isArray(response) ? response : response.results;
  } catch (error) {
    knowledgeBases.value = [];
    Message.error('加载知识库失败');
  } finally {
    isKbLoading.value = false;
  }
};

const fetchTestCases = async () => {
  if (!projectStore.currentProjectId) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    return;
  }

  testCaseLoading.value = true;
  try {
    const response = await getTestCaseList(projectStore.currentProjectId, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: searchKeyword.value,
      level: selectedLevel.value || undefined,
      module_id: selectedModule.value,
    });
    if (response.success && response.data) {
      testCaseData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
      return;
    }
    testCaseData.value = [];
    paginationConfig.total = 0;
    Message.error(response.error || '获取测试用例失败');
  } catch (error) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    Message.error('获取测试用例失败');
  } finally {
    testCaseLoading.value = false;
  }
};

const fetchModules = async () => {
  if (!projectStore.currentProjectId) {
    moduleList.value = [];
    return;
  }

  modulesLoading.value = true;
  try {
    const response = await getTestCaseModules(projectStore.currentProjectId);
    moduleList.value = response.success && response.data ? response.data : [];
  } catch (error) {
    moduleList.value = [];
  } finally {
    modulesLoading.value = false;
  }
};

const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!selectedTestCaseIds.value.includes(id)) {
      selectedTestCaseIds.value.push(id);
    }
    return;
  }
  selectedTestCaseIds.value = selectedTestCaseIds.value.filter((item) => item !== id);
};

const handleSelectCurrentPage = (checked: boolean) => {
  if (checked) {
    testCaseData.value.forEach((item) => {
      if (!selectedTestCaseIds.value.includes(item.id)) {
        selectedTestCaseIds.value.push(item.id);
      }
    });
    return;
  }
  const currentPageIds = testCaseData.value.map((item) => item.id);
  selectedTestCaseIds.value = selectedTestCaseIds.value.filter((id) => !currentPageIds.includes(id));
};

const handleSearch = async () => {
  paginationConfig.current = 1;
  await fetchTestCases();
};

const handleModuleFilterChange = async () => {
  paginationConfig.current = 1;
  await fetchTestCases();
};

const handleLevelFilterChange = async () => {
  paginationConfig.current = 1;
  await fetchTestCases();
};

const onPageChange = async (page: number) => {
  paginationConfig.current = page;
  await fetchTestCases();
};

const onPageSizeChange = async (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  await fetchTestCases();
};

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      await initializeModalData();
    }
  },
  { immediate: true }
);

watch(
  () => projectStore.currentProjectId,
  async (newProjectId, oldProjectId) => {
    if (props.visible && newProjectId && newProjectId !== oldProjectId) {
      await initializeModalData();
    }
  }
);

watch(
  () => [props.initialValues, props.initialModuleId] as const,
  async () => {
    if (props.visible) {
      await initializeModalData();
    }
  }
);
</script>

<style scoped>
.header-row {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 20px;
  margin-bottom: 18px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--color-border-2);
}

.header-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.header-item--mode {
  min-width: 0;
}

.header-label,
.section-title {
  font-size: 14px;
  color: var(--color-text-1);
}

.required::before {
  content: '*';
  margin-right: 4px;
  color: rgb(var(--danger-6));
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.form-row-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.form-row-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.form-row-item-full {
  grid-column: 1 / -1;
}

.test-type-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.test-type-checkboxes {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 12px;
}

.test-type-checkboxes :deep(.arco-checkbox) {
  margin-right: 0;
}

.selector-section {
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-2);
}

.selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.selected-count {
  font-size: 13px;
  color: var(--color-text-2);
}

.selector-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 180px 120px;
  gap: 12px;
  margin-bottom: 12px;
}

.empty-wrap {
  padding: 10px;
  text-align: center;
}

@media (max-width: 900px) {
  .header-row,
  .form-row,
  .form-row-3,
  .selector-toolbar,
  .test-type-checkboxes {
    grid-template-columns: 1fr;
  }
}
</style>

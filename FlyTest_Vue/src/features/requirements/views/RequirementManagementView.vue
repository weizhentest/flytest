<template>
  <div class="requirement-management">
    <section class="workspace-hero workspace-hero--requirements workspace-hero--compact workspace-hero--requirement-command">
      <div class="workspace-hero-copy">
        <span class="workspace-hero-eyebrow">Requirement Intelligence</span>
        <h2 class="workspace-hero-title">{{ projectStore.currentProject?.name || '当前项目' }} 需求评审中心</h2>
        <p class="workspace-hero-description">
          让需求文档接入 AI 理解、结构化拆解与评审闭环，在上传、分析、复审到报告沉淀之间形成更专业的测试输入中台。
        </p>
        <div class="workspace-chip-row">
          <span class="workspace-chip">AI 语义理解</span>
          <span class="workspace-chip">结构化拆解</span>
          <span class="workspace-chip">评审闭环</span>
          <span class="workspace-chip">报告沉淀</span>
        </div>
      </div>
      <div class="workspace-hero-stats">
        <div class="workspace-stat-card">
          <span class="workspace-stat-value">{{ pagination.total || documentList.length }}</span>
          <span class="workspace-stat-label">需求文档</span>
        </div>
        <div class="workspace-stat-card">
          <span class="workspace-stat-value">{{ currentProjectId || '--' }}</span>
          <span class="workspace-stat-label">项目编号</span>
        </div>
      </div>
      <div class="workspace-hero-orb" aria-hidden="true"></div>
    </section>

    <div class="filter-section">
      <div class="filter-row">
        <a-input-search
          v-model="searchKeyword"
          class="filter-search"
          placeholder="搜索文档标题或描述"
          @search="handleSearch"
          @clear="handleSearch"
          allow-clear
        />
        <a-select
          v-model="statusFilter"
          class="filter-select"
          placeholder="文档状态"
          @change="handleSearch"
          allow-clear
        >
          <a-option value="">全部状态</a-option>
          <a-option value="uploaded">已上传</a-option>
          <a-option value="processing">处理中</a-option>
          <a-option value="module_split">模块拆分中</a-option>
          <a-option value="user_reviewing">用户调整中</a-option>
          <a-option value="ready_for_review">待评审</a-option>
          <a-option value="reviewing">评审中</a-option>
          <a-option value="review_completed">评审完成</a-option>
          <a-option value="failed">处理失败</a-option>
        </a-select>
        <a-select
          v-model="typeFilter"
          class="filter-select"
          placeholder="文档类型"
          @change="handleSearch"
          allow-clear
        >
          <a-option value="">全部类型</a-option>
          <a-option value="pdf">PDF</a-option>
          <a-option value="docx">Word</a-option>
          <a-option value="pptx">PPT</a-option>
          <a-option value="md">Markdown</a-option>
          <a-option value="txt">文本</a-option>
          <a-option value="html">HTML</a-option>
        </a-select>
        <a-button type="primary" class="filter-upload-button" @click="showUploadModal">
          <template #icon><icon-plus /></template>
          上传需求文档
        </a-button>
      </div>
    </div>

    <div class="content-section">
      <a-table
        :columns="columns"
        :data="documentList"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1000 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        row-key="id"
      >
        <template #status="{ record }">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>

        <template #document_type="{ record }">
          <a-tag color="blue">{{ getTypeText(record.document_type) }}</a-tag>
        </template>

        <template #stats="{ record }">
          <div class="stats-info">
            <span class="stat-item">{{ record.word_count || 0 }} 字</span>
            <span class="stat-item">{{ record.page_count || 0 }} 页</span>
            <span class="stat-item">{{ record.modules_count || 0 }} 模块</span>
          </div>
        </template>

        <template #actions="{ record }">
          <div class="actions-wrapper">
            <a-button type="text" size="small" @click="viewDocument(record)">
              详情
            </a-button>
            <a-button
              v-if="record.status === 'uploaded'"
              type="text"
              size="small"
              @click="viewDocument(record)"
            >
              拆分
            </a-button>
            <a-button
              v-if="record.status === 'ready_for_review'"
              type="text"
              size="small"
              @click="startReview(record)"
            >
              评审
            </a-button>
            <a-button
              v-if="record.status === 'reviewing'"
              type="text"
              size="small"
              status="warning"
              @click="viewDocument(record)"
            >
              查看进度
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="viewReports(record)"
            >
              报告
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="restartReview(record)"
            >
              重审
            </a-button>
            <a-button
              v-if="record.status === 'failed'"
              type="text"
              size="small"
              @click="retryReview(record)"
            >
              重试
            </a-button>
            <a-popconfirm
              content="确定要删除这个文档吗？"
              @ok="deleteDocument(record)"
            >
              <a-button type="text" size="small" status="danger">
                删除
              </a-button>
            </a-popconfirm>
          </div>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:visible="uploadModalVisible"
      title="上传需求文档"
      width="600px"
      @ok="handleUpload"
      @cancel="resetUploadForm"
      :confirm-loading="uploadLoading"
    >
      <a-form
        ref="uploadFormRef"
        :model="uploadForm"
        :rules="uploadRules"
        layout="vertical"
      >
        <a-form-item label="文档标题" field="title">
          <a-input v-model="uploadForm.title" placeholder="请输入文档标题" />
        </a-form-item>
        <a-form-item label="文档描述" field="description">
          <a-textarea
            v-model="uploadForm.description"
            placeholder="请输入文档描述（可选）"
            :rows="3"
          />
        </a-form-item>
        <a-form-item label="上传方式" field="uploadType">
          <a-radio-group v-model="uploadForm.uploadType" @change="handleUploadTypeChange">
            <a-radio value="file">上传文件</a-radio>
            <a-radio value="content">直接输入</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item
          v-if="uploadForm.uploadType === 'file'"
          label="选择文件"
          field="file"
        >
          <a-upload
            ref="uploadRef"
            :file-list="fileList"
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept=".pdf,.doc,.docx,.txt,.md"
            @change="handleFileChange"
          >
            <template #upload-button>
              <div class="upload-area">
                <icon-upload />
                <div>点击上传文件</div>
                <div class="upload-tip">支持 PDF、Word(.doc/.docx)、TXT、Markdown</div>
              </div>
            </template>
            <template #upload-item="{ fileItem, index }">
              <div class="upload-file-item">
                <div class="file-info">
                  <icon-file />
                  <span class="file-name">{{ fileItem.name }}</span>
                  <span class="file-size">({{ formatFileSize(fileItem.file?.size || fileItem.size) }})</span>
                </div>
                <a-button
                  type="text"
                  size="mini"
                  status="danger"
                  @click="removeFile(index)"
                >
                  <template #icon><icon-delete /></template>
                </a-button>
              </div>
            </template>
          </a-upload>
        </a-form-item>
        <a-form-item
          v-if="uploadForm.uploadType === 'content'"
          label="文档内容"
          field="content"
        >
          <a-textarea
            v-model="uploadForm.content"
            placeholder="请输入或粘贴文档内容"
            :rows="8"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="reviewConfigVisible"
      :title="reviewAction === 'restart' ? '重新评审配置' : '评审配置'"
      @ok="confirmReview"
      @cancel="reviewConfigVisible = false"
    >
      <a-alert v-if="reviewAction === 'restart'" type="warning" style="margin-bottom: 16px">
        重新评审将创建新的评审报告，原有报告会保留。
      </a-alert>
      
      <a-form :model="reviewConfig" layout="vertical">
        <a-form-item label="并发分析数量" field="max_workers">
          <a-select v-model="reviewConfig.max_workers" placeholder="请选择并发数量">
            <a-option :value="1">1（串行分析，最慢但最稳定）</a-option>
            <a-option :value="2">2（低并发，适合低配环境）</a-option>
            <a-option :value="3">3（推荐，平衡速度与稳定性）</a-option>
            <a-option :value="5">5（高并发，速度最快）</a-option>
          </a-select>
          <template #help>
            并发数量决定了同时进行的专项分析任务数。如果遇到 API 限流错误，请尝试降低并发数。
          </template>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconUpload, IconFile, IconDelete } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { RequirementDocumentService } from '../services/requirementService';
import type {
  RequirementDocument,
  DocumentDetail,
  DocumentStatus,
  DocumentType,
  CreateDocumentRequest,
  DocumentListParams
} from '../types';
import {
  DocumentStatusDisplay,
  DocumentTypeDisplay
} from '../types';

const projectStore = useProjectStore();
const router = useRouter();

const loading = ref(false);
const documentList = ref<RequirementDocument[]>([]);
const searchKeyword = ref('');
const statusFilter = ref<DocumentStatus | ''>('');
const typeFilter = ref<DocumentType | ''>('');

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

const uploadModalVisible = ref(false);
const uploadLoading = ref(false);
const uploadFormRef = ref();
const uploadRef = ref();
const fileList = ref<any[]>([]);

const uploadForm = reactive<CreateDocumentRequest & { uploadType: 'file' | 'content' }>({
  title: '',
  description: '',
  document_type: 'pdf',
  project: '',
  uploadType: 'file',
  file: undefined,
  content: ''
});

const reviewConfigVisible = ref(false);
const reviewAction = ref<'start' | 'restart' | 'retry'>('start');
const currentDocument = ref<RequirementDocument | null>(null);
const reviewConfig = ref({
  max_workers: 3
});
const REVIEW_POLL_INTERVAL_MS = 3000;
const REVIEW_POLL_MAX_ATTEMPTS = 120;
let reviewPollTimer: ReturnType<typeof setTimeout> | null = null;
let reviewPollAttempts = 0;
const trackedReviewingDocumentIds = new Set<string>();

const uploadRules = {
  title: [
    { required: true, message: '请输入文档标题' },
    { maxLength: 200, message: '标题长度不能超过200个字符' }
  ],
  description: [
    { maxLength: 500, message: '描述长度不能超过500个字符' }
  ],
  file: [
    {
      required: true,
      message: '请选择文件',
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'file' && !uploadForm.file) {
          callback('请选择文件');
        } else {
          callback();
        }
      }
    }
  ],
  content: [
    {
      required: true,
      message: '请输入文档内容',
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'content' && !uploadForm.content) {
          callback('请输入文档内容');
        } else {
          callback();
        }
      }
    }
  ]
};

const columns = [
  {
    title: '文档标题',
    dataIndex: 'title',
    width: 200,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100
  },
  {
    title: '类型',
    dataIndex: 'document_type',
    slotName: 'document_type',
    width: 80
  },
  {
    title: '统计',
    slotName: 'stats',
    width: 180
  },
  {
    title: '上传者',
    dataIndex: 'uploader_name',
    width: 80,
    ellipsis: true
  },
  {
    title: '上传时间',
    dataIndex: 'uploaded_at',
    width: 170,
    render: ({ record }: { record: RequirementDocument }) => {
      return new Date(record.uploaded_at).toLocaleString();
    }
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 260,
    fixed: 'right',
    align: 'center'
  }
];

const currentProjectId = computed(() => projectStore.currentProjectId);

const hasReviewingDocuments = (documents: RequirementDocument[] = documentList.value) => {
  return trackedReviewingDocumentIds.size > 0 || documents.some((document) => document.status === 'reviewing');
};

const resetTrackedReviewingDocuments = () => {
  trackedReviewingDocumentIds.clear();
};

const trackReviewingDocument = (documentId: string) => {
  if (documentId) {
    trackedReviewingDocumentIds.add(documentId);
  }
};

const untrackReviewingDocument = (documentId: string) => {
  trackedReviewingDocumentIds.delete(documentId);
};

const syncTrackedReviewingDocuments = (documents: RequirementDocument[] = documentList.value) => {
  documents.forEach((document) => {
    if (document.status === 'reviewing') {
      trackReviewingDocument(document.id);
    } else if (trackedReviewingDocumentIds.has(document.id)) {
      untrackReviewingDocument(document.id);
    }
  });
};

const clearReviewPollingTimer = () => {
  if (reviewPollTimer !== null) {
    clearTimeout(reviewPollTimer);
    reviewPollTimer = null;
  }
};

const stopReviewPolling = () => {
  clearReviewPollingTimer();
  reviewPollAttempts = 0;
};

const markDocumentAsReviewing = (documentId: string) => {
  trackReviewingDocument(documentId);
  const target = documentList.value.find((document) => document.id === documentId);
  if (target) {
    target.status = 'reviewing';
  }
};

const updateDocumentInList = (nextDocument: DocumentDetail | RequirementDocument) => {
  const target = documentList.value.find((document) => document.id === nextDocument.id);
  if (target) {
    Object.assign(target, nextDocument);
  }
};

const notifyTrackedDocumentFinalStatus = (document: RequirementDocument) => {
  if (document.status === 'review_completed') {
    Message.success('需求文档《' + document.title + '》评审已完成');
  } else if (document.status === 'failed') {
    Message.error('需求文档《' + document.title + '》评审失败，请重试');
  }
};

const notifyReviewStatusChanges = (
  previousStatuses: Map<string, DocumentStatus>,
  nextDocuments: RequirementDocument[]
) => {
  nextDocuments.forEach((document) => {
    const previousStatus = previousStatuses.get(document.id);

    if (previousStatus === 'reviewing' && document.status === 'review_completed') {
      Message.success('需求文档《' + document.title + '》评审已完成');
    } else if (previousStatus === 'reviewing' && document.status === 'failed') {
      Message.error('需求文档《' + document.title + '》评审失败，请重试');
    }
  });
};

const refreshTrackedReviewStatuses = async () => {
  const trackedIds = Array.from(trackedReviewingDocumentIds);
  if (trackedIds.length === 0) {
    return loadDocuments({ silent: true });
  }

  let shouldReloadList = false;
  const responses = await Promise.all(
    trackedIds.map((documentId) => RequirementDocumentService.getDocumentDetail(documentId))
  );

  responses.forEach((response, index) => {
    if (response.status !== 'success' || !response.data) {
      return;
    }

    const nextDocument = response.data;
    updateDocumentInList(nextDocument);

    if (nextDocument.status === 'reviewing') {
      trackReviewingDocument(nextDocument.id);
      return;
    }

    if (trackedReviewingDocumentIds.has(nextDocument.id)) {
      untrackReviewingDocument(nextDocument.id);
      notifyTrackedDocumentFinalStatus(nextDocument);
    }
    shouldReloadList = true;
  });

  if (shouldReloadList || !hasReviewingDocuments()) {
    await loadDocuments({ silent: true });
  }

  return true;
};

const refreshReviewStatuses = async () => {
  reviewPollAttempts = 0;
  if (trackedReviewingDocumentIds.size > 0) {
    await refreshTrackedReviewStatuses();
    return;
  }
  await loadDocuments({ silent: true });
};

const handleWindowFocus = () => {
  if (hasReviewingDocuments()) {
    void refreshReviewStatuses();
  }
};

const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible' && hasReviewingDocuments()) {
    void refreshReviewStatuses();
  }
};

const scheduleReviewPolling = () => {
  clearReviewPollingTimer();

  if (!hasReviewingDocuments()) {
    reviewPollAttempts = 0;
    return;
  }

  reviewPollTimer = setTimeout(async () => {
    reviewPollTimer = null;
    reviewPollAttempts += 1;

    if (reviewPollAttempts >= REVIEW_POLL_MAX_ATTEMPTS) {
      stopReviewPolling();
      Message.warning('需求评审耗时较长，请稍后手动刷新查看结果');
      return;
    }

    if (trackedReviewingDocumentIds.size > 0) {
      await refreshTrackedReviewStatuses();
    } else {
      await loadDocuments({ silent: true });
    }

    if (hasReviewingDocuments()) {
      scheduleReviewPolling();
    }
  }, REVIEW_POLL_INTERVAL_MS);
};

const getStatusColor = (status: DocumentStatus) => {
  const colorMap = {
    uploaded: 'blue',
    processing: 'orange',
    module_split: 'orange',
    user_reviewing: 'purple',
    ready_for_review: 'cyan',
    reviewing: 'orange',
    review_completed: 'green',
    failed: 'red'
  };
  return colorMap[status] || 'gray';
};

const getStatusText = (status: DocumentStatus) => {
  return DocumentStatusDisplay[status] || status;
};

const getTypeText = (type: DocumentType) => {
  return DocumentTypeDisplay[type] || type;
};

const loadDocuments = async ({ silent = false }: { silent?: boolean } = {}) => {
  if (!currentProjectId.value) {
    stopReviewPolling();
    resetTrackedReviewingDocuments();
    if (!silent) {
      Message.warning('请先选择项目');
    }
    return false;
  }

  const previousStatuses = new Map(
    documentList.value.map((document) => [document.id, document.status] as const)
  );

  if (!silent) {
    loading.value = true;
  }
  try {
    const params: DocumentListParams = {
      project: String(currentProjectId.value),
      page: pagination.current,
      page_size: pagination.pageSize
    };

    if (searchKeyword.value) {
      params.search = searchKeyword.value;
    }
    if (statusFilter.value) {
      params.status = statusFilter.value;
    }
    if (typeFilter.value) {
      params.document_type = typeFilter.value;
    }

    const response = await RequirementDocumentService.getDocumentList(params);

    console.log('API响应:', response);

    if (response.status === 'success') {
      if (Array.isArray(response.data)) {
        documentList.value = response.data;
        pagination.total = response.data.length;
      } else if (response.data.results) {
        documentList.value = response.data.results;
        pagination.total = response.data.count;
      } else {
        documentList.value = [];
        pagination.total = 0;
      }
      notifyReviewStatusChanges(previousStatuses, documentList.value);
      syncTrackedReviewingDocuments(documentList.value);
      if (hasReviewingDocuments(documentList.value)) {
        scheduleReviewPolling();
      } else {
        stopReviewPolling();
      }
      return true;
    } else {
      if (!silent) {
      Message.error(response.message || '加载文档列表失败');
      }
    }
  } catch (error) {
    if (!silent) {
    console.error('加载文档列表失败:', error);
    Message.error('加载文档列表失败');
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }

  return false;
};

const handleSearch = () => {
  pagination.current = 1;
  loadDocuments();
};

const handlePageChange = (page: number) => {
  pagination.current = page;
  loadDocuments();
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
  loadDocuments();
};

const showUploadModal = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择项目');
    return;
  }
  uploadForm.project = String(currentProjectId.value);
  console.log('鎵撳紑涓婁紶妯℃€佹锛岄」鐩甀D:', uploadForm.project);
  uploadModalVisible.value = true;
};

const handleFileChange = (fileListParam: any[], file: any) => {
  console.log('文件选择变化:', fileListParam, file);

  fileList.value = fileListParam;

  if (file && file.file) {
    uploadForm.file = file.file;
    console.log('设置文件列表项:', file.file);

    const fileName = file.file.name;
    const extension = fileName.split('.').pop()?.toLowerCase();
    if (extension && ['pdf', 'doc', 'docx', 'txt', 'md'].includes(extension)) {
      uploadForm.document_type = extension as DocumentType;
    }
    if (!uploadForm.title) {
      uploadForm.title = fileName.substring(0, fileName.lastIndexOf('.')) || fileName;
    }
  } else if (fileListParam.length === 0) {
    uploadForm.file = undefined;
    console.log('文件被移除');
  }
};

const handleUploadTypeChange = () => {
  if (uploadForm.uploadType === 'content') {
    uploadForm.document_type = 'txt';
    uploadForm.file = undefined;
    fileList.value = [];
  } else if (uploadForm.uploadType === 'file') {
    uploadForm.document_type = 'pdf';
    uploadForm.content = '';
  }
};

const handleUpload = async () => {
  try {
    if (!uploadForm.title.trim()) {
      Message.error('请输入文档标题');
      return;
    }

    if (uploadForm.uploadType === 'file' && !uploadForm.file) {
      Message.error('请选择文件');
      return;
    }

    if (uploadForm.uploadType === 'content' && (!uploadForm.content || !uploadForm.content.trim())) {
      Message.error('请输入文档内容');
      return;
    }

    if (!uploadForm.project) {
      Message.error('请先选择项目');
      return;
    }

    uploadLoading.value = true;

    console.log('涓婁紶鏁版嵁:', uploadForm);

    const response = await RequirementDocumentService.uploadDocument(uploadForm);

    console.log('涓婁紶鍝嶅簲:', response);

    if (response.status === 'success') {
      Message.success('文档上传成功');
      uploadModalVisible.value = false;
      resetUploadForm();
      await loadDocuments();
    } else {
      Message.error(response.message || '文档上传失败');
    }
  } catch (error) {
    console.error('文档上传失败:', error);
    Message.error('文档上传失败');
  } finally {
    uploadLoading.value = false;
  }
};

const resetUploadForm = () => {
  uploadFormRef.value?.resetFields();
  fileList.value = [];
  Object.assign(uploadForm, {
    title: '',
    description: '',
    document_type: 'pdf',
    project: String(currentProjectId.value || ''),
    uploadType: 'file',
    file: undefined,
    content: ''
  });
};

const formatFileSize = (size: number | undefined): string => {
  if (!size || isNaN(size)) return '未知大小';
  if (size < 1024) return size + ' B';
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB';
  return (size / (1024 * 1024)).toFixed(1) + ' MB';
};

const removeFile = (index: number) => {
  fileList.value.splice(index, 1);
  uploadForm.file = undefined;
};

const viewDocument = (document: RequirementDocument) => {
  router.push(`/requirements/${document.id}`);
};


const startReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'start';
  reviewConfigVisible.value = true;
};

const restartReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'restart';
  reviewConfigVisible.value = true;
};

const retryReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'retry';
  reviewConfigVisible.value = true;
};

const confirmReview = async () => {
  if (!currentDocument.value) return;
  
  reviewConfigVisible.value = false;
  loading.value = true;
  
  const options = {
    analysis_type: 'comprehensive' as const,
    parallel_processing: true,
    max_workers: reviewConfig.value.max_workers
  };

  try {
    let response;
    const documentId = currentDocument.value.id;
    
    if (reviewAction.value === 'restart') {
      response = await RequirementDocumentService.restartReview(documentId, options);
    } else {
      response = await RequirementDocumentService.startReview(documentId, options);
    }

    if (response.status === 'success') {
      const actionText = reviewAction.value === 'restart' ? '重新评审' : '需求评审';
      Message.success(`${actionText}已启动（并发数：${reviewConfig.value.max_workers}）`);
      markDocumentAsReviewing(documentId);
      reviewPollAttempts = 0;
      scheduleReviewPolling();
      await loadDocuments({ silent: true });
    } else {
      Message.error(response.message || '评审启动失败');
    }
  } catch (error) {
    console.error('评审启动失败:', error);
    Message.error('评审启动失败');
  } finally {
    loading.value = false;
    currentDocument.value = null;
  }
};

const viewReports = (document: RequirementDocument) => {
  if (document.id) {
    router.push(`/requirements/${document.id}/report`);
  } else {
    Message.warning('暂无评审报告');
  }
};

const deleteDocument = async (document: RequirementDocument) => {
  try {
    loading.value = true;
    const response = await RequirementDocumentService.deleteDocument(document.id);

    if (response.status === 'success') {
      Message.success('文档删除成功');
      loadDocuments();
    } else {
      Message.error(response.message || '文档删除失败');
    }
  } catch (error) {
    console.error('文档删除失败:', error);
    Message.error('文档删除失败');
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  window.addEventListener('focus', handleWindowFocus);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  if (currentProjectId.value) {
    void loadDocuments();
  }
});

onUnmounted(() => {
  window.removeEventListener('focus', handleWindowFocus);
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  stopReviewPolling();
  resetTrackedReviewingDocuments();
});

projectStore.$subscribe((_mutation, state) => {
  const projectId = state.currentProject?.id;
  if (projectId && String(projectId) !== uploadForm.project) {
    uploadForm.project = String(projectId);
    stopReviewPolling();
    resetTrackedReviewingDocuments();
    loadDocuments();
  }
});
</script>

<style scoped>
.requirement-management {
  padding: 24px;
  background: transparent; /* 浣跨敤涓诲竷灞€鐨勮儗鏅?*/
}

.workspace-hero--requirement-command {
  gap: 14px;
  padding: 16px 18px;
  border-radius: 24px;
  border: 1px solid var(--theme-card-border);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.12), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.78));
  box-shadow: var(--theme-card-shadow);
  backdrop-filter: blur(16px);
}

.workspace-hero--requirement-command::before {
  background-image:
    linear-gradient(to right, rgba(var(--theme-accent-rgb), 0.06) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(var(--theme-accent-rgb), 0.06) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.08));
}

.workspace-hero--requirement-command::after {
  width: 160px;
  height: 160px;
  right: -44px;
  top: -56px;
  background: radial-gradient(circle, rgba(var(--theme-accent-rgb), 0.16), transparent 66%);
  filter: blur(10px);
}

.workspace-hero--requirement-command .workspace-hero-copy {
  gap: 8px;
}

.workspace-hero--requirement-command .workspace-hero-eyebrow {
  padding: 5px 10px;
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--theme-accent);
  background: rgba(var(--theme-accent-rgb), 0.08);
  border-color: rgba(var(--theme-accent-rgb), 0.14);
}

.workspace-hero--requirement-command .workspace-hero-title {
  font-size: clamp(24px, 2.5vw, 30px);
  line-height: 1.08;
  color: var(--theme-text);
}

.workspace-hero--requirement-command .workspace-hero-description {
  max-width: 620px;
  font-size: 13px;
  line-height: 1.58;
  color: var(--theme-text-secondary);
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.workspace-hero--requirement-command .workspace-chip-row {
  gap: 8px;
}

.workspace-hero--requirement-command .workspace-chip {
  padding: 6px 10px;
  border-color: rgba(var(--theme-accent-rgb), 0.12);
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-accent);
  font-size: 11px;
  backdrop-filter: blur(10px);
}

.workspace-hero--requirement-command .workspace-hero-stats {
  grid-template-columns: repeat(2, minmax(108px, 128px));
  gap: 10px;
}

.workspace-hero--requirement-command .workspace-stat-card {
  min-height: 92px;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 18px;
  border-color: rgba(var(--theme-accent-rgb), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--theme-accent-rgb), 0.08), rgba(255, 255, 255, 0.62));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px);
}

.workspace-hero--requirement-command .workspace-stat-value {
  font-size: clamp(20px, 1.8vw, 28px);
  color: var(--theme-text);
}

.workspace-hero--requirement-command .workspace-stat-label {
  font-size: 11px;
  color: var(--theme-text-tertiary);
}

.workspace-hero--requirement-command .workspace-hero-orb {
  width: 118px;
  height: 118px;
  right: 8px;
  bottom: -18px;
  opacity: 0.58;
  background:
    radial-gradient(circle at 35% 35%, rgba(135, 244, 255, 0.2), transparent 34%),
    radial-gradient(circle at 50% 50%, rgba(var(--theme-accent-rgb), 0.16), transparent 72%);
}

.filter-section {
  margin-bottom: 16px;
  padding: 16px 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-row {
  display: grid;
  grid-template-columns: minmax(240px, 280px) 128px 128px 150px;
  align-items: center;
  justify-content: start;
  gap: 10px;
}

.filter-search,
.filter-select,
.filter-upload-button {
  min-width: 0;
}

.filter-search {
  width: 100%;
}

.filter-select {
  width: 128px;
}

.filter-upload-button {
  width: 150px;
  justify-content: center;
  padding-inline: 14px;
  white-space: nowrap;
}

.content-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.stats-info {
  display: flex;
  flex-direction: row; /* 鏀逛负姘村钩鎺掑垪 */
  gap: 8px; /* 澧炲姞闂磋窛 */
  flex-wrap: wrap; /* 鍏佽鎹㈣ */
}

.stat-item {
  font-size: 12px;
  color: #86909c;
  white-space: nowrap; /* 闃叉鍗曚釜缁熻椤规崲琛?*/
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #00a0e9;
  background: #f0f8ff;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #86909c;
}

.upload-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-top: 8px;
  background: #f7f8fa;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.file-name {
  font-size: 14px;
  color: #1d2129;
  font-weight: 500;
}

.file-size {
  font-size: 12px;
  color: #86909c;
}

.actions-wrapper {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.requirement-management {
  gap: 16px;
}

.filter-section {
  position: relative;
  overflow: hidden;
}

.filter-section::before,
.content-section::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.24), transparent 22%),
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.08), transparent 22%);
  pointer-events: none;
}

.filter-row,
.content-section > * {
  position: relative;
  z-index: 1;
}

.filter-section {
  padding: 18px 22px;
  border-radius: 24px;
}

.filter-search :deep(.arco-input-wrapper),
.filter-select :deep(.arco-select-view),
.filter-upload-button {
  height: 36px;
  border-radius: 12px;
}

.filter-search :deep(.arco-input-wrapper),
.filter-select :deep(.arco-select-view) {
  font-size: 13px;
}

.filter-upload-button {
  font-size: 13px;
  font-weight: 600;
}

.content-section {
  border-radius: 26px;
}

@media (max-width: 768px) {
  .workspace-hero--requirement-command {
    padding: 14px;
    border-radius: 20px;
  }

  .workspace-hero--requirement-command .workspace-hero-title {
    font-size: 22px;
  }

  .filter-row {
    grid-template-columns: 1fr;
  }
}
</style>







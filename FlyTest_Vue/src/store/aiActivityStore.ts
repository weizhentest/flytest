import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  getTestCaseGenerationJobStatus,
  type TestCaseGenerationJobStatus,
} from '@/services/testcaseService';

const POLL_INTERVAL_MS = 1500;
const COMPLETED_HIDE_DELAY_MS = 10000;
const GENERATION_JOB_STORAGE_KEY = 'flytest_ai_generation_job';
const DEFAULT_GENERATION_LABEL = 'AI正在生成用例';
const GENERATION_STAGE_LABELS: Record<string, string> = {
  queued: '排队中',
  prepare: '准备中',
  generate: '生成中',
  parse: '解析中',
  save: '保存中',
  review: '评审中',
  completed: '已完成',
  failed: '失败',
};

type GenerationJobMeta = {
  mode: 'standard' | 'append';
  targetModuleId: number | null;
};

type PersistedGenerationJobState = {
  projectId: number | null;
  label: string;
  error: string;
  visible: boolean;
  handledStateKey: string;
  job: TestCaseGenerationJobStatus | null;
  meta: GenerationJobMeta;
};

const DEFAULT_GENERATION_META: GenerationJobMeta = {
  mode: 'standard',
  targetModuleId: null,
};

export const useAiActivityStore = defineStore('aiActivity', () => {
  const generationJob = ref<TestCaseGenerationJobStatus | null>(null);
  const generationJobProjectId = ref<number | null>(null);
  const generationJobLabel = ref(DEFAULT_GENERATION_LABEL);
  const generationJobError = ref('');
  const generationJobVisible = ref(false);
  const generationJobMeta = ref<GenerationJobMeta>({ ...DEFAULT_GENERATION_META });
  const generationJobHandledStateKey = ref('');
  const isPolling = ref(false);

  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let completedHideTimer: ReturnType<typeof setTimeout> | null = null;

  const persistGenerationJob = () => {
    if (typeof window === 'undefined') {
      return;
    }

    const payload: PersistedGenerationJobState = {
      projectId: generationJobProjectId.value,
      label: generationJobLabel.value,
      error: generationJobError.value,
      visible: generationJobVisible.value,
      handledStateKey: generationJobHandledStateKey.value,
      job: generationJob.value,
      meta: generationJobMeta.value,
    };

    window.localStorage.setItem(GENERATION_JOB_STORAGE_KEY, JSON.stringify(payload));
  };

  const removePersistedGenerationJob = () => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.removeItem(GENERATION_JOB_STORAGE_KEY);
  };

  const stopPolling = () => {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
    isPolling.value = false;
  };

  const stopCompletedHideTimer = () => {
    if (completedHideTimer) {
      clearTimeout(completedHideTimer);
      completedHideTimer = null;
    }
  };

  const clearGenerationJob = () => {
    stopPolling();
    stopCompletedHideTimer();
    generationJob.value = null;
    generationJobProjectId.value = null;
    generationJobLabel.value = DEFAULT_GENERATION_LABEL;
    generationJobError.value = '';
    generationJobVisible.value = false;
    generationJobMeta.value = { ...DEFAULT_GENERATION_META };
    generationJobHandledStateKey.value = '';
    removePersistedGenerationJob();
  };

  const scheduleCompletedHide = (delayMs = COMPLETED_HIDE_DELAY_MS) => {
    stopCompletedHideTimer();
    completedHideTimer = setTimeout(() => {
      clearGenerationJob();
    }, Math.max(delayMs, 0));
  };

  const scheduleNextPoll = () => {
    stopPolling();
    isPolling.value = true;
    pollTimer = setTimeout(() => {
      void pollGenerationJob();
    }, POLL_INTERVAL_MS);
  };

  const restorePersistedGenerationJob = () => {
    if (typeof window === 'undefined') {
      return;
    }

    const raw = window.localStorage.getItem(GENERATION_JOB_STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const payload = JSON.parse(raw) as PersistedGenerationJobState;
      generationJobProjectId.value = payload.projectId ?? null;
      generationJobLabel.value = payload.label || DEFAULT_GENERATION_LABEL;
      generationJobError.value = payload.error || '';
      generationJobVisible.value = payload.visible ?? !!payload.job;
      generationJobHandledStateKey.value = payload.handledStateKey || '';
      generationJob.value = payload.job ?? null;
      generationJobMeta.value = payload.meta || { ...DEFAULT_GENERATION_META };

      if (
        generationJob.value &&
        generationJobProjectId.value &&
        (generationJob.value.status === 'pending' || generationJob.value.status === 'running')
      ) {
        void pollGenerationJob();
        return;
      }

      if (generationJob.value?.status === 'success') {
        const completedAt = generationJob.value.completed_at
          ? new Date(generationJob.value.completed_at).getTime()
          : Date.now();
        const remainingMs = COMPLETED_HIDE_DELAY_MS - (Date.now() - completedAt);
        if (remainingMs > 0) {
          scheduleCompletedHide(remainingMs);
        } else {
          clearGenerationJob();
        }
      }
    } catch (error) {
      console.error('恢复 AI 生成状态失败:', error);
      removePersistedGenerationJob();
    }
  };

  const startGenerationJob = (
    projectId: number,
    jobId: string,
    label = DEFAULT_GENERATION_LABEL,
    meta: Partial<GenerationJobMeta> = {}
  ) => {
    stopCompletedHideTimer();
    generationJobProjectId.value = projectId;
    generationJobLabel.value = label?.trim() || DEFAULT_GENERATION_LABEL;
    generationJobError.value = '';
    generationJobVisible.value = true;
    generationJobMeta.value = {
      ...DEFAULT_GENERATION_META,
      ...meta,
    };
    generationJobHandledStateKey.value = '';
    generationJob.value = {
      job_id: jobId,
      status: 'pending',
      progress_percent: 0,
      progress_stage: 'queued',
      progress_message: '任务已创建，等待开始',
      error_message: '',
      generated_count: 0,
      summary: '',
      gaps: [],
      result_payload: null,
      created_at: null,
      started_at: null,
      completed_at: null,
    };
    persistGenerationJob();
    void pollGenerationJob();
  };

  const markGenerationJobHandled = (stateKey: string) => {
    generationJobHandledStateKey.value = stateKey || '';
    persistGenerationJob();
  };

  const pollGenerationJob = async () => {
    const currentJob = generationJob.value;
    const currentProjectId = generationJobProjectId.value;
    if (!currentJob?.job_id || !currentProjectId) {
      stopPolling();
      return;
    }

    try {
      const response = await getTestCaseGenerationJobStatus(currentProjectId, currentJob.job_id);
      if (!response.success || !response.data) {
        generationJobError.value = response.error || '获取生成进度失败';
        generationJob.value = {
          ...currentJob,
          status: 'failed',
          progress_percent: 100,
          progress_stage: 'failed',
          progress_message: generationJobError.value,
          error_message: generationJobError.value,
        };
        generationJobVisible.value = true;
        persistGenerationJob();
        stopPolling();
        stopCompletedHideTimer();
        return;
      }

      generationJob.value = response.data;
      generationJobError.value = response.data.error_message || '';
      generationJobVisible.value = true;
      persistGenerationJob();

      if (response.data.status === 'pending' || response.data.status === 'running') {
        stopCompletedHideTimer();
        scheduleNextPoll();
        return;
      }

      stopPolling();
      generationJobVisible.value = true;
      if (response.data.status === 'success') {
        scheduleCompletedHide();
      } else {
        stopCompletedHideTimer();
      }
    } catch (error) {
      generationJobError.value = error instanceof Error ? error.message : '获取生成进度失败';
      generationJob.value = {
        ...currentJob,
        status: 'failed',
        progress_percent: 100,
        progress_stage: 'failed',
        progress_message: generationJobError.value,
        error_message: generationJobError.value,
      };
      generationJobVisible.value = true;
      persistGenerationJob();
      stopPolling();
      stopCompletedHideTimer();
    }
  };

  const generationProgressText = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    const effectiveGeneratedCount = Math.max(
      generationJob.value.generated_count || 0,
      Array.isArray(generationJob.value.result_payload?.data)
        ? generationJob.value.result_payload.data.filter((item) => typeof item?.id === 'number' && item.id > 0).length
        : 0
    );
    if (generationJob.value.status === 'success') {
      if (
        generationJob.value.result_payload?.coverage_complete === false ||
        effectiveGeneratedCount === 0
      ) {
        return '需补充';
      }
      return '已完成';
    }
    if (generationJob.value.status === 'failed') {
      return '失败';
    }
    return `${generationJob.value.progress_percent}%`;
  });

  const generationStageText = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    const effectiveGeneratedCount = Math.max(
      generationJob.value.generated_count || 0,
      Array.isArray(generationJob.value.result_payload?.data)
        ? generationJob.value.result_payload.data.filter((item) => typeof item?.id === 'number' && item.id > 0).length
        : 0
    );
    if (generationJob.value.status === 'success') {
      if (
        generationJob.value.result_payload?.coverage_complete === false ||
        effectiveGeneratedCount === 0
      ) {
        return '需补充';
      }
      return '已完成';
    }
    if (generationJob.value.status === 'failed') {
      return '失败';
    }
    const stage = (generationJob.value.progress_stage || '').trim().toLowerCase();
    return GENERATION_STAGE_LABELS[stage] || '处理中';
  });

  const generationStatusText = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    const effectiveGeneratedCount = Math.max(
      generationJob.value.generated_count || 0,
      Array.isArray(generationJob.value.result_payload?.data)
        ? generationJob.value.result_payload.data.filter((item) => typeof item?.id === 'number' && item.id > 0).length
        : 0
    );
    if (generationJob.value.status === 'success') {
      if (
        generationJob.value.result_payload?.coverage_complete === false ||
        effectiveGeneratedCount === 0
      ) {
        return `${generationJobLabel.value}:需补充`;
      }
      return `${generationJobLabel.value}:已完成`;
    }
    if (generationJob.value.status === 'failed') {
      return `${generationJobLabel.value}:失败`;
    }
    return `${generationJobLabel.value}:${generationJob.value.progress_percent}%`;
  });

  const generationTooltip = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    if (generationJob.value.error_message) {
      return generationJob.value.error_message;
    }
    const parts = [generationStatusText.value];
    if (generationJob.value.status === 'pending' || generationJob.value.status === 'running') {
      parts.push(`阶段：${generationStageText.value}`);
    }
    if (generationJob.value.progress_message) {
      parts.push(generationJob.value.progress_message);
    }
    return parts.filter(Boolean).join(' | ');
  });

  restorePersistedGenerationJob();

  return {
    generationJob,
    generationJobProjectId,
    generationJobLabel,
    generationJobError,
    generationJobVisible,
    generationJobMeta,
    generationJobHandledStateKey,
    generationProgressText,
    generationStageText,
    generationStatusText,
    generationTooltip,
    markGenerationJobHandled,
    startGenerationJob,
    pollGenerationJob,
    clearGenerationJob,
  };
});

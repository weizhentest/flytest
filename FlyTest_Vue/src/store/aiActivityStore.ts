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

type PersistedGenerationJobState = {
  projectId: number | null;
  label: string;
  error: string;
  visible: boolean;
  job: TestCaseGenerationJobStatus | null;
};

export const useAiActivityStore = defineStore('aiActivity', () => {
  const generationJob = ref<TestCaseGenerationJobStatus | null>(null);
  const generationJobProjectId = ref<number | null>(null);
  const generationJobLabel = ref(DEFAULT_GENERATION_LABEL);
  const generationJobError = ref('');
  const generationJobVisible = ref(false);
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
      job: generationJob.value,
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
      generationJob.value = payload.job ?? null;

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
      console.error('恢复 AI 生成状态失败', error);
      removePersistedGenerationJob();
    }
  };

  const startGenerationJob = (
    projectId: number,
    jobId: string,
    label = DEFAULT_GENERATION_LABEL
  ) => {
    stopCompletedHideTimer();
    generationJobProjectId.value = projectId;
    generationJobLabel.value = label?.trim() ? DEFAULT_GENERATION_LABEL : DEFAULT_GENERATION_LABEL;
    generationJobError.value = '';
    generationJobVisible.value = true;
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

  const pollGenerationJob = async () => {
    const currentJob = generationJob.value;
    const currentProjectId = generationJobProjectId.value;
    if (!currentJob?.job_id || !currentProjectId) {
      stopPolling();
      return;
    }

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
  };

  const generationProgressText = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    if (generationJob.value.status === 'success') {
      return '已完成';
    }
    if (generationJob.value.status === 'failed') {
      return '失败';
    }
    return `${generationJob.value.progress_percent}%`;
  });

  const generationStatusText = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    if (generationJob.value.status === 'success') {
      return `${generationJobLabel.value}:已完成`;
    }
    if (generationJob.value.status === 'failed') {
      return `${generationJobLabel.value}:失败`;
    }
    return `${generationJobLabel.value}：${generationJob.value.progress_percent}%`;
  });

  const generationTooltip = computed(() => {
    if (!generationJobVisible.value || !generationJob.value) {
      return '';
    }
    return generationJob.value.error_message || generationJob.value.progress_message || generationStatusText.value;
  });

  restorePersistedGenerationJob();

  return {
    generationJob,
    generationJobProjectId,
    generationJobLabel,
    generationJobError,
    generationJobVisible,
    generationProgressText,
    generationStatusText,
    generationTooltip,
    startGenerationJob,
    pollGenerationJob,
    clearGenerationJob,
  };
});

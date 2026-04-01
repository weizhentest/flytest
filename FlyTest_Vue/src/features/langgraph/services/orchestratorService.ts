import request from '@/utils/request';

/**
 * Orchestrator任务状态
 */
export interface OrchestratorTask {
  id: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  requirement: string;
  requirement_analysis?: any;
  knowledge_docs?: any[];
  testcases?: any[];
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}

interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T;
  message: string;
}

/**
 * 创建Orchestrator任务
 */
export async function createOrchestratorTask(params: {
  requirement: string;
  project: number;
}): Promise<ApiResponse<OrchestratorTask>> {
  return await request({
    url: '/orchestrator/tasks/',
    method: 'POST',
    data: params
  });
}

/**
 * 获取Orchestrator任务状态
 */
export async function getOrchestratorTask(taskId: number): Promise<ApiResponse<OrchestratorTask>> {
  return await request({
    url: `/orchestrator/tasks/${taskId}/`,
    method: 'GET'
  });
}

/**
 * 轮询Orchestrator任务状态
 */
export async function pollOrchestratorTask(
  taskId: number,
  onUpdate?: (task: OrchestratorTask) => void,
  maxAttempts: number = 60,
  interval: number = 2000
): Promise<OrchestratorTask> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await getOrchestratorTask(taskId);

    if (response.status === 'error') {
      throw new Error(response.message);
    }

    const task = response.data;

    if (onUpdate) {
      onUpdate(task);
    }

    if (task.status === 'completed' || task.status === 'failed') {
      return task;
    }

    await new Promise(resolve => setTimeout(resolve, interval));
    attempts++;
  }

  throw new Error('任务执行超时');
}

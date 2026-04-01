import http from '@/utils/request';

export type AutomationScriptListParams = {
  project_id?: number;
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  source?: string;
};

export function listAutomationScripts(params: AutomationScriptListParams) {
  return http.get('/automation-scripts/', { params });
}

export function getAutomationScript(projectId: number, id: number) {
  return http.get(`/automation-scripts/${id}/`, { params: { project_id: projectId } });
}

export function updateAutomationScript(projectId: number, id: number, payload: any) {
  return http.patch(`/automation-scripts/${id}/`, payload, { params: { project_id: projectId } });
}

export function createAutomationScript(projectId: number, payload: any) {
  return http.post('/automation-scripts/', payload, { params: { project_id: projectId } });
}

export function deleteAutomationScript(projectId: number, id: number) {
  return http.delete(`/automation-scripts/${id}/`, { params: { project_id: projectId } });
}

export function executeAutomationScript(
  projectId: number,
  id: number,
  payload: { record_video?: boolean } = {}
) {
  return http.post(`/automation-scripts/${id}/execute/`, payload, { params: { project_id: projectId } });
}

export function listAutomationScriptExecutions(projectId: number, id: number) {
  return http.get(`/automation-scripts/${id}/executions/`, { params: { project_id: projectId } });
}

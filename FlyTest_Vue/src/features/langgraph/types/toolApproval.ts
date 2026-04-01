/**
 * 用户工具审批偏好类型定义
 *
 * 支持"记住审批选择"功能
 */

/** 审批策略 */
export type ApprovalPolicy = 'always_allow' | 'always_reject' | 'ask_every_time';

/** 生效范围 */
export type ApprovalScope = 'session' | 'permanent';

/** 用户工具审批偏好 */
export interface UserToolApproval {
  id: number;
  tool_name: string;
  policy: ApprovalPolicy;
  scope: ApprovalScope;
  session_id?: string | null;
  created_at: string;
  updated_at: string;
}

/** 可用工具信息（包含当前用户偏好） */
export interface AvailableTool {
  tool_name: string;
  description: string;
  allowed_decisions: string[];
  current_policy: ApprovalPolicy;
  current_scope: ApprovalScope;
  require_hitl?: boolean;
}

/** 工具分组 */
export interface ToolGroup {
  group_name: string;
  group_id: string;
  tools: AvailableTool[];
}

/** 策略选项 */
export interface PolicyChoice {
  value: ApprovalPolicy;
  label: string;
}

/** 范围选项 */
export interface ScopeChoice {
  value: ApprovalScope;
  label: string;
}

/** 可用工具列表响应 */
export interface AvailableToolsResponse {
  tools: AvailableTool[];
  tool_groups?: ToolGroup[];
  policy_choices: PolicyChoice[];
  scope_choices: ScopeChoice[];
}

/** 批量更新请求项 */
export interface ToolApprovalUpdateItem {
  tool_name: string;
  policy: ApprovalPolicy;
  scope?: ApprovalScope;
  session_id?: string | null;
}

/** 批量更新请求 */
export interface BatchUpdateRequest {
  approvals: ToolApprovalUpdateItem[];
}

/** 批量更新响应 */
export interface BatchUpdateResponse {
  updated: Array<{
    tool_name: string;
    policy: ApprovalPolicy;
    scope: ApprovalScope;
    created: boolean;
  }>;
  errors: Array<{
    tool_name: string;
    errors: Record<string, string[]>;
  }> | null;
}

/** 重置请求 */
export interface ResetRequest {
  tool_name?: string;
  scope?: ApprovalScope;
  session_id?: string;
}

/** 重置响应 */
export interface ResetResponse {
  message: string;
  deleted_count: number;
}

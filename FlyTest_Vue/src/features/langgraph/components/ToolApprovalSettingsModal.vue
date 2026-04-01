<template>
  <a-modal
    :visible="props.visible"
    title="工具审批偏好设置"
    @ok="handleSave"
    @cancel="handleCancel"
    :confirm-loading="saving"
    :mask-closable="false"
    width="640px"
  >
    <div class="approval-settings">
      <a-alert type="info" class="info-alert">
        <template #icon><icon-info-circle /></template>
        设置后，系统将自动应用您的审批选择，无需每次手动确认。
      </a-alert>

      <a-spin :loading="loading" tip="加载中...">
        <div v-if="toolGroups.length === 0 && !loading" class="empty-state">
          <icon-empty />
          <p>暂无需要审批的工具</p>
          <p class="empty-hint">请先添加 MCP 配置并同步工具</p>
        </div>

        <div v-else class="tool-groups">
          <div
            v-for="group in localToolGroups"
            :key="group.group_id"
            class="tool-group"
          >
            <div 
              class="group-header" 
              :class="{ 'collapsed': collapsedGroups.has(group.group_id) }"
              @click="toggleGroup(group.group_id)"
            >
              <icon-apps v-if="group.group_id.startsWith('builtin')" class="group-icon builtin" />
              <icon-cloud-download v-else class="group-icon mcp" />
              <span class="group-name">{{ group.group_name }}</span>
              <span class="group-count">{{ group.tools.length }} 个工具</span>
              <icon-down v-if="!collapsedGroups.has(group.group_id)" class="expand-icon" />
              <icon-right v-else class="expand-icon" />
            </div>

            <div v-show="!collapsedGroups.has(group.group_id)" class="tool-list">
              <div
                v-for="tool in group.tools"
                :key="tool.tool_name"
                class="tool-row"
              >
                <div class="tool-info">
                  <span class="tool-name">{{ tool.tool_name }}</span>
                  <a-tooltip v-if="tool.description" :content="tool.description" position="top">
                    <icon-info-circle class="tool-tip-icon" />
                  </a-tooltip>
                </div>
                <div class="tool-selects">
                  <a-select
                    v-model="tool.current_policy"
                    :options="policyOptions"
                    size="small"
                    class="policy-select"
                  />
                  <a-select
                    v-model="tool.current_scope"
                    :options="scopeOptions"
                    size="small"
                    class="scope-select"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </div>

    <template #footer>
      <div class="modal-footer">
        <a-button @click="handleReset" :loading="resetting" status="danger" type="text">
          重置全部
        </a-button>
        <div class="footer-right">
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" @click="handleSave" :loading="saving">
            保存
          </a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconInfoCircle, IconEmpty, IconApps, IconCloudDownload, IconDown, IconRight } from '@arco-design/web-vue/es/icon';
import {
  getAvailableTools,
  batchUpdateToolApprovals,
  resetToolApprovals,
} from '@/features/langgraph/services/toolApprovalService';
import type { ToolGroup, PolicyChoice, ScopeChoice } from '@/features/langgraph/types/toolApproval';

const props = defineProps<{
  visible: boolean;
  sessionId?: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'saved'): void;
}>();

const loading = ref(false);
const saving = ref(false);
const resetting = ref(false);
const toolGroups = ref<ToolGroup[]>([]);
const localToolGroups = ref<ToolGroup[]>([]);
const policyChoices = ref<PolicyChoice[]>([]);
const scopeChoices = ref<ScopeChoice[]>([]);
const collapsedGroups = ref<Set<string>>(new Set());

// 切换分组的折叠状态
const toggleGroup = (groupId: string) => {
  if (collapsedGroups.value.has(groupId)) {
    collapsedGroups.value.delete(groupId);
  } else {
    collapsedGroups.value.add(groupId);
  }
  // 触发响应式更新
  collapsedGroups.value = new Set(collapsedGroups.value);
};

const policyOptions = computed(() =>
  policyChoices.value.map((c) => ({ label: c.label, value: c.value }))
);

const scopeOptions = computed(() =>
  scopeChoices.value.map((c) => ({ label: c.label, value: c.value }))
);

// 加载数据
const fetchData = async () => {
  loading.value = true;
  try {
    const resp = await getAvailableTools(props.sessionId);
    if (resp.status === 'success' && resp.data) {
      // 优先使用分组数据，否则降级到扁平列表
      if (resp.data.tool_groups && resp.data.tool_groups.length > 0) {
        toolGroups.value = resp.data.tool_groups;
        localToolGroups.value = JSON.parse(JSON.stringify(resp.data.tool_groups));
      } else if (resp.data.tools && resp.data.tools.length > 0) {
        // 降级：将扁平列表包装成单个分组
        const fallbackGroup: ToolGroup = {
          group_name: '所有工具',
          group_id: 'all',
          tools: resp.data.tools,
        };
        toolGroups.value = [fallbackGroup];
        localToolGroups.value = [JSON.parse(JSON.stringify(fallbackGroup))];
      } else {
        toolGroups.value = [];
        localToolGroups.value = [];
      }
      policyChoices.value = resp.data.policy_choices;
      scopeChoices.value = resp.data.scope_choices;
      // 默认收起所有分组
      collapsedGroups.value = new Set(localToolGroups.value.map(g => g.group_id));
    } else {
      Message.error(resp.message || '加载失败');
    }
  } catch (error: any) {
    Message.error('加载失败: ' + (error.message || '未知错误'));
  } finally {
    loading.value = false;
  }
};

// 监听 visible 变化
watch(
  () => props.visible,
  (val) => {
    if (val) {
      fetchData();
    }
  }
);

// 保存
const handleSave = async () => {
  saving.value = true;
  try {
    // 从所有分组中收集工具
    const approvals = localToolGroups.value.flatMap((group) =>
      group.tools.map((tool) => ({
        tool_name: tool.tool_name,
        policy: tool.current_policy,
        scope: tool.current_scope,
        session_id: tool.current_scope === 'session' ? props.sessionId : null,
      }))
    );

    const resp = await batchUpdateToolApprovals({ approvals });
    if (resp.status === 'success') {
      Message.success('保存成功');
      emit('saved');
      emit('update:visible', false);
    } else {
      Message.error(resp.message || '保存失败');
    }
  } catch (error: any) {
    Message.error('保存失败: ' + (error.message || '未知错误'));
  } finally {
    saving.value = false;
  }
};

// 重置
const handleReset = async () => {
  resetting.value = true;
  try {
    const resp = await resetToolApprovals();
    if (resp.status === 'success') {
      Message.success(resp.data?.message || '已重置');
      await fetchData();
    } else {
      Message.error(resp.message || '重置失败');
    }
  } catch (error: any) {
    Message.error('重置失败: ' + (error.message || '未知错误'));
  } finally {
    resetting.value = false;
  }
};

// 取消
const handleCancel = () => {
  emit('update:visible', false);
};
</script>

<style scoped>
.approval-settings {
  min-height: 200px;
  max-height: 520px;
  overflow-y: auto;
}

.approval-settings :deep(.arco-spin) {
  width: 100%;
}

.approval-settings :deep(.arco-spin-children) {
  width: 100%;
}

.info-alert {
  margin-bottom: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--color-text-3);
}

.empty-state p {
  margin-top: 8px;
}

.empty-hint {
  font-size: 12px;
  color: var(--color-text-4);
}

.tool-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tool-group {
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--color-fill-2);
  border-bottom: 1px solid var(--color-border-2);
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.group-header.collapsed {
  border-bottom: none;
}

.group-header:hover {
  background: var(--color-fill-3);
}

.expand-icon {
  font-size: 14px;
  color: var(--color-text-3);
  transition: transform 0.2s;
}

.group-icon {
  font-size: 16px;
}

.group-icon.builtin {
  color: var(--color-primary);
}

.group-icon.mcp {
  color: #52c41a;
}

.group-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text-1);
}

.group-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-text-3);
}

.tool-list {
  display: flex;
  flex-direction: column;
}

.tool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border-1);
  transition: background 0.2s;
}

.tool-row:last-child {
  border-bottom: none;
}

.tool-row:hover {
  background: var(--color-fill-1);
}

.tool-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-tip-icon {
  font-size: 14px;
  color: var(--color-text-3);
  cursor: help;
  flex-shrink: 0;
}

.tool-tip-icon:hover {
  color: var(--color-primary);
}

.tool-selects {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.policy-select,
.scope-select {
  width: auto;
  min-width: 90px;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-right {
  display: flex;
  gap: 8px;
}
</style>

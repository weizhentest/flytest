<template>
  <a-layout class="main-layout">
    <!-- 顶部导航栏 -->
    <a-layout-header class="header">
      <div class="left-section">
        <div class="logo" unselectable="on">
          <img :src="brandLogoUrl" alt="FlyTest Logo" class="logo-icon" />
          <div class="logo-copy">
            <span class="logo-text">FlyTest</span>
            <span class="logo-subtitle">AI智能测试平台</span>
          </div>
        </div>
        <div class="project-selector" v-if="showProjectSelector">
          <a-select
            v-model="selectedProjectId"
            :loading="projectStore.loading"
            :disabled="projectStore.loading"
            placeholder="请选择项目"
            style="width: 200px; margin-left: 10px;"
            @change="handleProjectChange"
            @popup-visible-change="handlePopupVisibleChange"
          >
            <a-option
              v-for="option in projectStore.projectOptions"
              :key="option.value"
              :value="option.value"
              :label="option.label"
            />
          </a-select>
        </div>
        <div class="workspace-badge" :class="`workspace-badge--${aiStatus.state}`" :title="aiStatusTooltip">
          <span class="workspace-dot"></span>
          <span>{{ aiStatusLabel }}</span>
        </div>
        <ImportJobStatusBadge v-if="hasApiAutomationPermission" />
      </div>
      <div class="user-info">
        <button
          type="button"
          class="theme-switch-button"
          :aria-label="themeButtonLabel"
          :title="themeButtonLabel"
          @click="themeStore.toggleTheme"
        >
          <icon-sun-fill v-if="themeStore.isBlack" class="theme-switch-icon" />
          <icon-moon-fill v-else class="theme-switch-icon" />
        </button>
        <!-- 版本号显示 -->
        <a-popover v-if="hasUpdate" position="bottom" trigger="hover" content-class="version-popover">
          <a 
            class="version-badge update-available" 
            :href="versionInfo?.releaseUrl || versionUpdatesUrl"
            target="_blank"
          >
            当前版本: {{ currentVersion }}
            <span class="update-dot"></span>
          </a>
          <template #content>
            <div class="version-update-info">
              <div class="version-update-header">
                <span class="update-title">新版本可用</span>
                <span class="update-version">v{{ versionInfo?.latest }}</span>
              </div>
              <div class="version-update-notes" v-if="releaseNotesPreview">
                {{ releaseNotesPreview }}
              </div>
              <a 
                class="version-update-footer"
                :href="versionInfo?.releaseUrl || versionUpdatesUrl"
                target="_blank"
              >
                点击查看完整更新日志
              </a>
            </div>
          </template>
        </a-popover>
        <span v-else class="version-badge">当前版本: {{ currentVersion }}</span>
        
        <a-avatar class="avatar">
          <span>{{ userInitial }}</span>
        </a-avatar>
        <a-dropdown
          trigger="click"
          class="user-dropdown-wrapper"
          :trigger-props="{ contentClass: 'user-panel-dropdown' }"
        >
          <div class="user-dropdown">
            <span class="username">{{ displayName }}</span>
            <icon-down />
          </div>
          <template #content>
            <div class="dropdown-user-info">
              <div class="dropdown-username">{{ displayName }}</div>
              <div class="dropdown-email" v-if="user?.real_name && user?.username">{{ user.username }}</div>
              <div class="dropdown-email" v-if="user?.email">{{ user.email }}</div>
              <div class="dropdown-role" v-if="user?.is_staff">管理员</div>
            </div>
            <a-divider style="margin: 4px 0" />
            <a-doption @click="handleOpenPersonalCenter">个人中心</a-doption>
            <a-doption @click="handleLogout">退出登录</a-doption>
          </template>
        </a-dropdown>
      </div>
    </a-layout-header>

    <a-layout class="inner-layout">
      <!-- 左侧菜单栏 -->
      <a-layout-sider
        :width="196"
        :collapsed-width="56"
        :collapsed="collapsed"
        :trigger="null"
        hide-trigger
        class="sider"
      >
        <a-menu
          mode="vertical"
          :selected-keys="[activeMenu]"
          v-model:open-keys="openKeys"
          :auto-open-selected="true"
          :collapsed="collapsed"
          :popup-max-height="false"
          :trigger-props="{ contentClass: 'layout-menu-popup' }"
          class="menu"
          @menu-item-click="handleMenuItemClick"
          @sub-menu-click="handleSubMenuClick"
        >
          <a-menu-item key="dashboard" v-if="isApproved">
            <template #icon><icon-home /></template>
            <span class="menu-link">首页</span>
          </a-menu-item>

          <a-menu-item key="projects" v-if="hasProjectsPermission">
            <template #icon><icon-storage /></template>
            <span class="menu-link">项目管理</span>
          </a-menu-item>

          <a-menu-item key="requirements" v-if="hasRequirementsPermission">
            <template #icon><icon-file /></template>
            <span class="menu-link">需求管理</span>
          </a-menu-item>

          <a-sub-menu key="test-management" v-if="hasTestManagementMenuItems">
            <template #icon><icon-experiment /></template>
            <template #title>测试管理</template>
            <a-menu-item key="testcases" v-if="hasTestcasesPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">测试用例</span>
            </a-menu-item>
            <a-menu-item key="testsuites" v-if="hasTestSuitesPermission">
              <template #icon><icon-folder /></template>
              <span class="menu-link">测试套件</span>
            </a-menu-item>
            <a-menu-item key="test-executions" v-if="hasTestExecutionsPermission">
              <template #icon><icon-history /></template>
              <span class="menu-link">执行历史</span>
            </a-menu-item>
          </a-sub-menu>

          <a-sub-menu key="api-automation" v-if="hasApiAutomationMenuItems">
            <template #icon><icon-code-block /></template>
            <template #title>AI接口自动化</template>
            <a-menu-item key="api-automation-requests" v-if="hasApiAutomationRequestsPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">请求管理</span>
            </a-menu-item>
            <a-menu-item key="api-automation-test-cases" v-if="hasApiAutomationTestCasesPermission">
              <template #icon><icon-folder /></template>
              <span class="menu-link">测试用例</span>
            </a-menu-item>
            <a-menu-item key="api-automation-environments" v-if="hasApiAutomationEnvironmentsPermission">
              <template #icon><icon-tool /></template>
              <span class="menu-link">环境配置</span>
            </a-menu-item>
            <a-menu-item key="api-automation-execution-records" v-if="hasApiAutomationExecutionRecordsPermission">
              <template #icon><icon-history /></template>
              <span class="menu-link">执行记录</span>
            </a-menu-item>
            <a-menu-item key="api-automation-execution-report" v-if="hasApiAutomationExecutionReportPermission">
              <template #icon><icon-bar-chart /></template>
              <span class="menu-link">测试报告</span>
            </a-menu-item>
          </a-sub-menu>

          <a-sub-menu key="app-automation" v-if="hasAppAutomationMenuItems">
            <template #icon><icon-apps /></template>
            <template #title>APP自动化</template>
            <a-menu-item key="app-automation-overview" v-if="hasAppAutomationOverviewPermission">
              <template #icon><icon-home /></template>
              <span class="menu-link">概览</span>
            </a-menu-item>
            <a-menu-item key="app-automation-devices" v-if="hasAppAutomationDevicesPermission">
              <template #icon><icon-storage /></template>
              <span class="menu-link">设备管理</span>
            </a-menu-item>
            <a-menu-item key="app-automation-packages" v-if="hasAppAutomationPackagesPermission">
              <template #icon><icon-folder /></template>
              <span class="menu-link">应用包</span>
            </a-menu-item>
            <a-menu-item key="app-automation-elements" v-if="hasAppAutomationElementsPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">元素管理</span>
            </a-menu-item>
            <a-menu-item key="app-automation-scene-builder" v-if="hasAppAutomationSceneBuilderPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">场景编排</span>
            </a-menu-item>
            <a-menu-item key="app-automation-test-cases" v-if="hasAppAutomationTestCasesPermission">
              <template #icon><icon-experiment /></template>
              <span class="menu-link">测试用例</span>
            </a-menu-item>
            <a-menu-item key="app-automation-suites" v-if="hasAppAutomationSuitesPermission">
              <template #icon><icon-folder /></template>
              <span class="menu-link">测试套件</span>
            </a-menu-item>
            <a-menu-item key="app-automation-executions" v-if="hasAppAutomationExecutionsPermission">
              <template #icon><icon-history /></template>
              <span class="menu-link">执行记录</span>
            </a-menu-item>
            <a-menu-item key="app-automation-scheduled-tasks" v-if="hasAppAutomationScheduledTasksPermission">
              <template #icon><icon-tool /></template>
              <span class="menu-link">定时任务</span>
            </a-menu-item>
            <a-menu-item key="app-automation-notifications" v-if="hasAppAutomationNotificationsPermission">
              <template #icon><icon-message /></template>
              <span class="menu-link">通知日志</span>
            </a-menu-item>
            <a-menu-item key="app-automation-reports" v-if="hasAppAutomationReportsPermission">
              <template #icon><icon-bar-chart /></template>
              <span class="menu-link">执行报告</span>
            </a-menu-item>
            <a-menu-item key="app-automation-settings" v-if="hasAppAutomationSettingsPermission">
              <template #icon><icon-tool /></template>
              <span class="menu-link">环境设置</span>
            </a-menu-item>
          </a-sub-menu>

          <a-sub-menu key="ui-automation" v-if="hasUiAutomationMenuItems">
            <template #icon><icon-computer /></template>
            <template #title>UI自动化</template>
            <a-menu-item key="ui-automation-ai-intelligent" v-if="hasUiAutomationAiIntelligentPermission">
              <template #icon><icon-message /></template>
              <span class="menu-link">AI智能模式</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-pages" v-if="hasUiAutomationPagesPermission">
              <template #icon><icon-computer /></template>
              <span class="menu-link">页面管理</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-page-steps" v-if="hasUiAutomationPageStepsPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">页面步骤</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-testcases" v-if="hasUiAutomationTestCasesPermission">
              <template #icon><icon-folder /></template>
              <span class="menu-link">测试用例</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-execution-records" v-if="hasUiAutomationExecutionRecordsPermission">
              <template #icon><icon-history /></template>
              <span class="menu-link">执行记录</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-batch-records" v-if="hasUiAutomationBatchRecordsPermission">
              <template #icon><icon-bar-chart /></template>
              <span class="menu-link">批量执行</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-public-data" v-if="hasUiAutomationPublicDataPermission">
              <template #icon><icon-book /></template>
              <span class="menu-link">公共数据</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-env-config" v-if="hasUiAutomationEnvConfigPermission">
              <template #icon><icon-tool /></template>
              <span class="menu-link">环境配置</span>
            </a-menu-item>
            <a-menu-item key="ui-automation-actuators" v-if="hasUiAutomationActuatorsPermission">
              <template #icon><icon-apps /></template>
              <span class="menu-link">执行器</span>
            </a-menu-item>
          </a-sub-menu>

          <a-menu-item key="langgraph-chat" v-if="hasLangGraphChatPermission">
            <template #icon><icon-message /></template>
            <span class="menu-link">AI 对话</span>
          </a-menu-item>

          <a-menu-item key="knowledge-management" v-if="hasKnowledgePermission">
            <template #icon><icon-book /></template>
            <span class="menu-link">知识库管理</span>
          </a-menu-item>
          <a-sub-menu key="data-factory" v-if="hasDataFactoryMenuItems">
            <template #icon><icon-tool /></template>
            <template #title>数据工厂</template>
            <a-menu-item key="data-factory-all" v-if="hasDataFactoryPermission">
              <template #icon><icon-apps /></template>
              <span class="menu-link">工具面板</span>
            </a-menu-item>
            <a-menu-item key="data-factory-string" v-if="hasDataFactoryPermission">
              <template #icon><icon-font-colors /></template>
              <span class="menu-link">字符工具</span>
            </a-menu-item>
            <a-menu-item key="data-factory-encoding" v-if="hasDataFactoryPermission">
              <template #icon><icon-code-block /></template>
              <span class="menu-link">编码工具</span>
            </a-menu-item>
            <a-menu-item key="data-factory-random" v-if="hasDataFactoryPermission">
              <template #icon><icon-fire /></template>
              <span class="menu-link">随机工具</span>
            </a-menu-item>
            <a-menu-item key="data-factory-encryption" v-if="hasDataFactoryPermission">
              <template #icon><icon-lock /></template>
              <span class="menu-link">加密工具</span>
            </a-menu-item>
            <a-menu-item key="data-factory-test-data" v-if="hasDataFactoryPermission">
              <template #icon><icon-user-group /></template>
              <span class="menu-link">测试数据</span>
            </a-menu-item>
            <a-menu-item key="data-factory-json" v-if="hasDataFactoryPermission">
              <template #icon><icon-file /></template>
              <span class="menu-link">JSON工具</span>
            </a-menu-item>
            <a-menu-item key="data-factory-crontab" v-if="hasDataFactoryPermission">
              <template #icon><icon-clock-circle /></template>
              <span class="menu-link">Crontab工具</span>
            </a-menu-item>
          </a-sub-menu>


          <a-sub-menu key="settings" v-if="hasSystemMenuItems">
            <template #icon><icon-settings /></template>
            <template #title>系统管理</template>
            <a-menu-item key="users" v-if="hasUsersPermission">
              <template #icon><icon-user /></template>
              <span class="menu-link">用户管理</span>
            </a-menu-item>
            <a-menu-item key="organizations" v-if="hasOrganizationsPermission">
              <template #icon><icon-apps /></template>
              <span class="menu-link">组织管理</span>
            </a-menu-item>
            <a-menu-item key="permissions" v-if="hasPermissionsPermission">
              <template #icon><icon-safe /></template>
              <span class="menu-link">权限管理</span>
            </a-menu-item>
            <a-menu-item key="llm-configs" v-if="hasLlmConfigsPermission">
              <template #icon><icon-tool /></template>
              <span class="menu-link">AI大模型配置</span>
            </a-menu-item>
            <a-menu-item key="api-keys" v-if="hasApiKeysPermission">
              <template #icon><icon-safe /></template>
              <span class="menu-link">API KEY 管理</span>
            </a-menu-item>
            <a-menu-item key="remote-mcp-configs" v-if="hasMcpConfigsPermission">
              <template #icon><icon-cloud /></template>
              <span class="menu-link">MCP 配置</span>
            </a-menu-item>
            <a-menu-item key="skills" v-if="hasSkillsPermission">
              <template #icon><icon-apps /></template>
              <span class="menu-link">Skills 管理</span>
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
        <!-- 侧边栏底部收起/展开按钮 -->
        <div class="sider-footer">
          <a-button
            type="text"
            size="small"
            @click="toggleCollapse"
            class="collapse-button"
          >
            <template #icon>
              <icon-menu-fold v-if="!collapsed" />
              <icon-menu-unfold v-else />
            </template>
            <span v-if="!collapsed">收起</span>
          </a-button>
        </div>
      </a-layout-sider>

      <!-- 右侧内容区域 -->
      <a-layout-content class="content">
        <router-view v-slot="{ Component }">
          <keep-alive include="LangGraphChat">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import { useThemeStore } from '@/store/themeStore';
import { brandLogoUrl } from '@/utils/assetUrl';
import ImportJobStatusBadge from '@/features/api-automation/components/ImportJobStatusBadge.vue';
import { fetchModels, getActiveLlmConfig, testLlmConnection } from '@/features/langgraph/services/llmConfigService';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import {
  getCurrentVersion,
  formatVersion,
  checkLatestVersion,
  getVersionUpdatesUrl,
  type VersionInfo
} from '@/services/versionService';
import {
  Layout as ALayout,
  Menu as AMenu,
  Avatar as AAvatar,
  Dropdown as ADropdown,
  Doption as ADoption,
  SubMenu as ASubMenu,
  Select as ASelect,
  Popover as APopover,
  Message
} from '@arco-design/web-vue';
import {
  IconSettings,
  IconUser,
  IconDown,
  IconApps,
  IconSafe,
  IconMenuFold,
  IconMenuUnfold,
  IconStorage,
  IconCodeBlock,
  IconFile,
  IconTool,
  IconMessage,
  IconCloud,
  IconBook,
  IconFolder,
  IconHistory,
  IconExperiment,
  IconHome,
  IconComputer,
  IconBarChart,
  IconClockCircle,
  IconFire,
  IconFontColors,
  IconLock,
  IconSunFill,
  IconMoonFill,
  IconUserGroup,
} from '@arco-design/web-vue/es/icon';
import '@arco-design/web-vue/dist/arco.css'; // 引入 Arco Design 样式

const ALayoutHeader = ALayout.Header;
const ALayoutSider = ALayout.Sider;
const ALayoutContent = ALayout.Content;
const AMenuItem = AMenu.Item;
const AOption = ASelect.Option;

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const projectStore = useProjectStore();
const themeStore = useThemeStore();
const AI_STATUS_REFRESH_INTERVAL_MS = 30000;
type AiStatusState = 'checking' | 'online' | 'warning' | 'offline' | 'unconfigured';
const aiStatus = ref<{
  state: AiStatusState;
  configName: string;
  modelName: string;
  message: string;
}>({
  state: 'checking',
  configName: '',
  modelName: '',
  message: '正在检测 AI 接口状态'
});
let aiStatusTimer: ReturnType<typeof setTimeout> | null = null;
let aiStatusRefreshInFlight = false;

// 版本信息
const currentVersion = ref(formatVersion(getCurrentVersion()));
const versionInfo = ref<VersionInfo | null>(null);
const hasUpdate = computed(() => versionInfo.value?.hasUpdate ?? false);
const versionUpdatesUrl = getVersionUpdatesUrl();

// 更新说明预览（显示完整内容）
const releaseNotesPreview = computed(() => {
  const notes = versionInfo.value?.releaseNotes;
  if (!notes) return '';
  // 移除 Markdown 标题符号，提取纯文本
  return notes
    .replace(/^#+\s*/gm, '')  // 移除标题 #
    .replace(/\r\n/g, '\n')    // 统一换行符
    .replace(/\*\*/g, '')      // 移除粗体
    .replace(/`[^`]+`/g, '')   // 移除代码
    .trim();
});

// 检查版本更新
const aiStatusLabel = computed(() => {
  switch (aiStatus.value.state) {
    case 'online':
      return 'AI 在线';
    case 'warning':
      return 'AI 异常';
    case 'offline':
      return 'AI 离线';
    case 'unconfigured':
      return 'AI 未配置';
    default:
      return 'AI 检测中';
  }
});

const aiStatusTooltip = computed(() => {
  const parts = [aiStatusLabel.value];
  if (aiStatus.value.modelName) {
    parts.push(`模型: ${aiStatus.value.modelName}`);
  } else if (aiStatus.value.configName) {
    parts.push(`配置: ${aiStatus.value.configName}`);
  }
  if (aiStatus.value.message) {
    parts.push(aiStatus.value.message);
  }
  return parts.join(' · ');
});

async function checkVersion() {
  try {
    versionInfo.value = await checkLatestVersion();
  } catch (error) {
    console.warn('版本检查失败', error);
  }
}

const clearAiStatusTimer = () => {
  if (aiStatusTimer !== null) {
    clearTimeout(aiStatusTimer);
    aiStatusTimer = null;
  }
};

const scheduleAiStatusRefresh = (delay = AI_STATUS_REFRESH_INTERVAL_MS) => {
  clearAiStatusTimer();
  aiStatusTimer = setTimeout(() => {
    void refreshAiStatus({ silent: true });
  }, delay);
};

const refreshAiStatus = async ({ silent = false }: { silent?: boolean } = {}) => {
  if (aiStatusRefreshInFlight) {
    return;
  }

  aiStatusRefreshInFlight = true;
  if (!silent) {
    aiStatus.value = {
      ...aiStatus.value,
      state: 'checking',
      message: '正在检测 AI 接口状态'
    };
  }

  try {
    const activeConfigResponse = await getActiveLlmConfig();
    const activeConfig: LlmConfig | null = activeConfigResponse.data;

    if (activeConfigResponse.status !== 'success' || !activeConfig) {
      aiStatus.value = {
        state: 'unconfigured',
        configName: '',
        modelName: '',
        message: activeConfigResponse.status === 'success'
          ? '当前没有激活的 AI 配置'
          : (activeConfigResponse.message || '无法获取 AI 配置')
      };
      scheduleAiStatusRefresh();
      return;
    }

    let remoteStatus: string = 'error';
    let message = '';

    const fetchModelsResponse = await fetchModels(activeConfig.api_url, undefined, activeConfig.id);
    if (fetchModelsResponse.status === 'success') {
      remoteStatus = 'success';
      message = fetchModelsResponse.data?.models?.length
        ? `已检测到 ${fetchModelsResponse.data.models.length} 个可用模型`
        : 'AI 接口连通正常';
    } else {
      const testResponse = await testLlmConnection(activeConfig.id);
      remoteStatus = testResponse.data?.status || (testResponse.status === 'success' ? 'success' : 'error');
      message = testResponse.message || fetchModelsResponse.message;
    }

    const state: AiStatusState =
      remoteStatus === 'success' ? 'online' :
      remoteStatus === 'warning' ? 'warning' :
      'offline';

    aiStatus.value = {
      state,
      configName: activeConfig.config_name,
      modelName: activeConfig.name,
      message: message || (state === 'online' ? 'AI 接口连接正常' : 'AI 接口连接异常')
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'AI 接口连接异常';
    aiStatus.value = {
      state: 'offline',
      configName: '',
      modelName: '',
      message
    };
  } finally {
    aiStatusRefreshInFlight = false;
    scheduleAiStatusRefresh();
  }
};

const handleWindowFocus = () => {
  void refreshAiStatus({ silent: true });
};

const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible') {
    void refreshAiStatus({ silent: true });
  }
};

// 用户信息
const user = computed(() => authStore.currentUser);
const isApproved = computed(() => authStore.isApproved);
const username = computed(() => user.value?.username || '');
const displayName = computed(() => user.value?.real_name || user.value?.username || '');
const userInitial = computed(() => {
  if (user.value?.real_name && user.value.real_name.length > 0) {
    return user.value.real_name.charAt(0).toUpperCase();
  }
  if (user.value?.first_name && user.value.first_name.length > 0) {
    return user.value.first_name.charAt(0).toUpperCase();
  }
  return displayName.value.charAt(0).toUpperCase();
});

const themeButtonLabel = computed(() => (themeStore.isBlack ? '切换到默认主题' : '切换到黑色主题'));
type MenuNavigationTarget = {
  route: RouteLocationRaw;
  requiresProject?: boolean;
};

const menuNavigationMap: Record<string, MenuNavigationTarget> = {
  dashboard: { route: '/dashboard' },
  projects: { route: '/projects' },
  requirements: { route: '/requirements', requiresProject: true },
  'api-automation-requests': { route: { path: '/api-automation', query: { tab: 'requests' } }, requiresProject: true },
  'api-automation-test-cases': { route: { path: '/api-automation', query: { tab: 'test-cases' } }, requiresProject: true },
  'api-automation-environments': { route: { path: '/api-automation', query: { tab: 'environments' } }, requiresProject: true },
  'api-automation-execution-records': { route: { path: '/api-automation', query: { tab: 'execution-records' } }, requiresProject: true },
  'api-automation-execution-report': { route: { path: '/api-automation', query: { tab: 'execution-report' } }, requiresProject: true },
  'app-automation-overview': { route: { path: '/app-automation', query: { tab: 'overview' } }, requiresProject: true },
  'app-automation-devices': { route: { path: '/app-automation', query: { tab: 'devices' } }, requiresProject: true },
  'app-automation-packages': { route: { path: '/app-automation', query: { tab: 'packages' } }, requiresProject: true },
  'app-automation-elements': { route: { path: '/app-automation', query: { tab: 'elements' } }, requiresProject: true },
  'app-automation-scene-builder': { route: { path: '/app-automation', query: { tab: 'scene-builder' } }, requiresProject: true },
  'app-automation-test-cases': { route: { path: '/app-automation', query: { tab: 'test-cases' } }, requiresProject: true },
  'app-automation-suites': { route: { path: '/app-automation', query: { tab: 'suites' } }, requiresProject: true },
  'app-automation-executions': { route: { path: '/app-automation', query: { tab: 'executions' } }, requiresProject: true },
  'app-automation-scheduled-tasks': { route: { path: '/app-automation', query: { tab: 'scheduled-tasks' } }, requiresProject: true },
  'app-automation-notifications': { route: { path: '/app-automation', query: { tab: 'notifications' } }, requiresProject: true },
  'app-automation-reports': { route: { path: '/app-automation', query: { tab: 'reports' } }, requiresProject: true },
  'app-automation-settings': { route: { path: '/app-automation', query: { tab: 'settings' } }, requiresProject: true },
  'ui-automation-pages': { route: { path: '/ui-automation', query: { tab: 'pages' } }, requiresProject: true },
  'ui-automation-page-steps': { route: { path: '/ui-automation', query: { tab: 'page-steps' } }, requiresProject: true },
  'ui-automation-testcases': { route: { path: '/ui-automation', query: { tab: 'testcases' } }, requiresProject: true },
  'ui-automation-ai-intelligent': { route: { path: '/ui-automation', query: { tab: 'ai-intelligent' } }, requiresProject: true },
  'ui-automation-execution-records': { route: { path: '/ui-automation', query: { tab: 'execution-records' } }, requiresProject: true },
  'ui-automation-batch-records': { route: { path: '/ui-automation', query: { tab: 'batch-records' } }, requiresProject: true },
  'ui-automation-public-data': { route: { path: '/ui-automation', query: { tab: 'public-data' } }, requiresProject: true },
  'ui-automation-env-config': { route: { path: '/ui-automation', query: { tab: 'env-config' } }, requiresProject: true },
  'ui-automation-actuators': { route: { path: '/ui-automation', query: { tab: 'actuators' } }, requiresProject: true },
  testcases: { route: '/testcases', requiresProject: true },
  testsuites: { route: '/testsuites', requiresProject: true },
  'test-executions': { route: '/test-executions', requiresProject: true },
  'langgraph-chat': { route: '/langgraph-chat', requiresProject: true },
  'knowledge-management': { route: '/knowledge-management', requiresProject: true },
  'data-factory-all': { route: '/data-factory' },
  'data-factory-string': { route: { path: '/data-factory', query: { category: 'string' } } },
  'data-factory-encoding': { route: { path: '/data-factory', query: { category: 'encoding' } } },
  'data-factory-random': { route: { path: '/data-factory', query: { category: 'random' } } },
  'data-factory-encryption': { route: { path: '/data-factory', query: { category: 'encryption' } } },
  'data-factory-test-data': { route: { path: '/data-factory', query: { category: 'test_data' } } },
  'data-factory-json': { route: { path: '/data-factory', query: { category: 'json' } } },
  'data-factory-crontab': { route: { path: '/data-factory', query: { category: 'crontab' } } },
  users: { route: '/users' },
  organizations: { route: '/organizations' },
  permissions: { route: '/permissions' },
  'llm-configs': { route: '/llm-configs' },
  'api-keys': { route: '/api-keys' },
  'remote-mcp-configs': { route: '/remote-mcp-configs' },
  skills: { route: '/skills' },
};

const activeMenu = computed(() => {
  const path = route.path;

  if (path.startsWith('/dashboard')) return 'dashboard';
  if (path.startsWith('/projects')) return 'projects';
  if (path.startsWith('/requirements')) return 'requirements';
  if (path.startsWith('/testsuites')) return 'testsuites';
  if (path.startsWith('/test-executions')) return 'test-executions';
  if (path.startsWith('/testcases')) return 'testcases';
  if (path.startsWith('/users')) return 'users';
  if (path.startsWith('/organizations')) return 'organizations';
  if (path.startsWith('/permissions')) return 'permissions';
  if (path.startsWith('/llm-configs')) return 'llm-configs';
  if (path.startsWith('/langgraph-chat')) return 'langgraph-chat';
  if (path.startsWith('/knowledge-management')) return 'knowledge-management';
  if (path.startsWith('/data-factory')) {
    const category = String(route.query.category || 'all');
    if (category === 'string') return 'data-factory-string';
    if (category === 'encoding') return 'data-factory-encoding';
    if (category === 'random') return 'data-factory-random';
    if (category === 'encryption') return 'data-factory-encryption';
    if (category === 'test_data') return 'data-factory-test-data';
    if (category === 'json') return 'data-factory-json';
    if (category === 'crontab') return 'data-factory-crontab';
    return 'data-factory-all';
  }
  if (path.startsWith('/api-keys')) return 'api-keys';
  if (path.startsWith('/remote-mcp-configs')) return 'remote-mcp-configs';
  if (path.startsWith('/skills')) return 'skills';
  if (path.startsWith('/api-automation')) {
    const tab = String(route.query.tab || 'requests');
    if (tab === 'test-cases') return 'api-automation-test-cases';
    if (tab === 'environments') return 'api-automation-environments';
    if (tab === 'execution-records') return 'api-automation-execution-records';
    if (tab === 'execution-report') return 'api-automation-execution-report';
    return 'api-automation-requests';
  }
  if (path.startsWith('/app-automation')) {
    const tab = String(route.query.tab || 'overview');
    if (tab === 'devices') return 'app-automation-devices';
    if (tab === 'packages') return 'app-automation-packages';
    if (tab === 'elements') return 'app-automation-elements';
    if (tab === 'scene-builder') return 'app-automation-scene-builder';
    if (tab === 'test-cases') return 'app-automation-test-cases';
    if (tab === 'suites') return 'app-automation-suites';
    if (tab === 'executions') return 'app-automation-executions';
    if (tab === 'scheduled-tasks') return 'app-automation-scheduled-tasks';
    if (tab === 'notifications') return 'app-automation-notifications';
    if (tab === 'reports') return 'app-automation-reports';
    if (tab === 'settings') return 'app-automation-settings';
    return 'app-automation-overview';
  }
  if (path.startsWith('/ui-automation/trace')) return 'ui-automation-execution-records';
  if (path.startsWith('/ui-automation')) {
    const tab = String(route.query.tab || 'pages');
    if (tab === 'page-steps') return 'ui-automation-page-steps';
    if (tab === 'testcases') return 'ui-automation-testcases';
    if (tab === 'ai-intelligent') return 'ui-automation-ai-intelligent';
    if (tab === 'execution-records') return 'ui-automation-execution-records';
    if (tab === 'batch-records') return 'ui-automation-batch-records';
    if (tab === 'public-data') return 'ui-automation-public-data';
    if (tab === 'env-config') return 'ui-automation-env-config';
    if (tab === 'actuators') return 'ui-automation-actuators';
    return 'ui-automation-pages';
  }

  return '';
});

const activeGroupKey = computed(() => {
  if (activeMenu.value.startsWith('api-automation-')) return 'api-automation';
  if (activeMenu.value.startsWith('app-automation-')) return 'app-automation';
  if (activeMenu.value.startsWith('ui-automation-')) return 'ui-automation';
  if (activeMenu.value.startsWith('data-factory-')) return 'data-factory';
  if (['testcases', 'testsuites', 'test-executions'].includes(activeMenu.value)) return 'test-management';
  if (['users', 'organizations', 'permissions', 'llm-configs', 'api-keys', 'remote-mcp-configs', 'skills'].includes(activeMenu.value)) {
    return 'settings';
  }
  return '';
});

const openKeys = ref<string[]>([]);
const collapsed = ref(false);

// 检查各个菜单项的权限
const hasProjectsPermission = computed(() => {
  return authStore.hasPermission('projects.view_project');
});

const hasRequirementsPermission = computed(() => {
  return authStore.hasPermission('requirements.view_requirementdocument');
});

const hasTestcasesPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testcase');
});

const hasTestSuitesPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testsuite');
});

const hasTestExecutionsPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testexecution');
});

const hasLangGraphChatPermission = computed(() => {
  return authStore.hasPermission('langgraph_integration.view_llmconfig') ||
         authStore.hasPermission('langgraph_integration.view_chatsession') ||
         authStore.hasPermission('langgraph_integration.view_chatmessage');
});

const hasApiAutomationRequestsPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apicollection') ||
         authStore.hasPermission('api_automation.view_apirequest') ||
         authStore.hasPermission('api_automation.view_apiimportjob');
});

const hasApiAutomationTestCasesPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apitestcase') ||
         authStore.hasPermission('api_automation.view_apicasegenerationjob');
});

const hasApiAutomationEnvironmentsPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apienvironment');
});

const hasApiAutomationExecutionRecordsPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apiexecutionrecord');
});

const hasApiAutomationExecutionReportPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apiexecutionreport') ||
         authStore.hasPermission('api_automation.view_apiexecutionrecord');
});

const hasApiAutomationPermission = computed(() => {
  return hasApiAutomationRequestsPermission.value ||
         hasApiAutomationTestCasesPermission.value ||
         hasApiAutomationEnvironmentsPermission.value ||
         hasApiAutomationExecutionRecordsPermission.value ||
         hasApiAutomationExecutionReportPermission.value;
});

const hasApiAutomationMenuItems = computed(() => hasApiAutomationPermission.value);

const hasAppAutomationOverviewPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationoverview'));
const hasAppAutomationDevicesPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationdevice'));
const hasAppAutomationPackagesPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationpackage'));
const hasAppAutomationElementsPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationelement'));
const hasAppAutomationSceneBuilderPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationscenebuilder'));
const hasAppAutomationTestCasesPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationtestcase'));
const hasAppAutomationSuitesPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationsuite'));
const hasAppAutomationExecutionsPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationexecution'));
const hasAppAutomationScheduledTasksPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationscheduledtask'));
const hasAppAutomationNotificationsPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationnotification'));
const hasAppAutomationReportsPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationreport'));
const hasAppAutomationSettingsPermission = computed(() => authStore.hasPermission('app_automation.view_appautomationsettings'));

const hasAppAutomationMenuItems = computed(() => {
  return hasAppAutomationOverviewPermission.value ||
         hasAppAutomationDevicesPermission.value ||
         hasAppAutomationPackagesPermission.value ||
         hasAppAutomationElementsPermission.value ||
         hasAppAutomationSceneBuilderPermission.value ||
         hasAppAutomationTestCasesPermission.value ||
         hasAppAutomationSuitesPermission.value ||
         hasAppAutomationExecutionsPermission.value ||
         hasAppAutomationScheduledTasksPermission.value ||
         hasAppAutomationNotificationsPermission.value ||
         hasAppAutomationReportsPermission.value ||
         hasAppAutomationSettingsPermission.value;
});

const hasUiAutomationPagesPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uimodule') ||
         authStore.hasPermission('ui_automation.view_uipage');
});

const hasUiAutomationPageStepsPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uipagesteps') ||
         authStore.hasPermission('ui_automation.view_uipagestepsdetailed');
});

const hasUiAutomationTestCasesPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uitestcase') ||
         authStore.hasPermission('ui_automation.view_uicasestepsdetailed');
});

const hasUiAutomationAiIntelligentPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uiaicase') ||
         authStore.hasPermission('ui_automation.view_uiaiexecutionrecord');
});

const hasUiAutomationExecutionRecordsPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uiexecutionrecord');
});

const hasUiAutomationBatchRecordsPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uibatchexecutionrecord');
});

const hasUiAutomationPublicDataPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uipublicdata');
});

const hasUiAutomationEnvConfigPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uienvironmentconfig');
});

const hasUiAutomationActuatorsPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uiactuator');
});

const hasUiAutomationPermission = computed(() => {
  return hasUiAutomationPagesPermission.value ||
         hasUiAutomationPageStepsPermission.value ||
         hasUiAutomationTestCasesPermission.value ||
         hasUiAutomationAiIntelligentPermission.value ||
         hasUiAutomationExecutionRecordsPermission.value ||
         hasUiAutomationBatchRecordsPermission.value ||
         hasUiAutomationPublicDataPermission.value ||
         hasUiAutomationEnvConfigPermission.value ||
         hasUiAutomationActuatorsPermission.value;
});

const hasUiAutomationMenuItems = computed(() => hasUiAutomationPermission.value);

const hasKnowledgePermission = computed(() => {
  return authStore.hasPermission('knowledge.view_knowledgebase');
});

const hasDataFactoryPermission = computed(() => {
  return authStore.hasPermission('data_factory.view_datafactoryrecord') ||
         authStore.hasPermission('data_factory.view_datafactorytag');
});

const hasDataFactoryMenuItems = computed(() => hasDataFactoryPermission.value);

const hasUsersPermission = computed(() => {
  return authStore.hasPermission('auth.view_user');
});

const hasOrganizationsPermission = computed(() => {
  return authStore.hasPermission('auth.view_group');
});

const hasPermissionsPermission = computed(() => {
  return authStore.hasPermission('auth.view_permission');
});

const hasLlmConfigsPermission = computed(() => {
  return authStore.hasPermission('langgraph_integration.view_llmconfig') ||
         authStore.hasPermission('llm_config.view_llmconfiguration') ||
         authStore.hasPermission('llms.view_llmmodel');
});

const hasApiKeysPermission = computed(() => {
  return authStore.hasPermission('api_keys.view_apikey') ||
         authStore.hasPermission('llms.view_apikey');
});

const hasMcpConfigsPermission = computed(() => {
  return authStore.hasPermission('mcp_tools.view_remotemcpconfig');
});

const hasSkillsPermission = computed(() => {
  return authStore.hasPermission('skills.view_skill');
});

// 检查是否有测试管理菜单项的权限
const hasTestManagementMenuItems = computed(() => {
  return hasTestcasesPermission.value ||
         hasTestSuitesPermission.value ||
         hasTestExecutionsPermission.value;
});

// 检查是否有系统管理菜单项的权限
const hasSystemMenuItems = computed(() => {
  return hasUsersPermission.value ||
         hasOrganizationsPermission.value ||
         hasPermissionsPermission.value ||
         hasLlmConfigsPermission.value ||
         hasApiKeysPermission.value ||
         hasMcpConfigsPermission.value ||
         hasSkillsPermission.value;
});

// 切换侧边栏收起状态
const toggleCollapse = () => {
  collapsed.value = !collapsed.value;

  if (!collapsed.value && activeGroupKey.value && !openKeys.value.includes(activeGroupKey.value)) {
    openKeys.value = [...openKeys.value, activeGroupKey.value];
  }
};

const navigateToMenuTarget = (target: MenuNavigationTarget) => {
  if (target.requiresProject && !projectStore.currentProjectId) {
    Message.warning('请先选择或创建项目');
    return;
  }

  void router.push(target.route);
};

const handleMenuItemClick = (key: string) => {
  const target = menuNavigationMap[key];
  if (!target) {
    return;
  }

  navigateToMenuTarget(target);
};

const handleSubMenuClick = (key: string) => {
  if (!collapsed.value) {
    return;
  }

  collapsed.value = false;

  if (!openKeys.value.includes(key)) {
    openKeys.value = [...openKeys.value, key];
  }
};

watch(
  activeGroupKey,
  groupKey => {
    if (collapsed.value || !groupKey || openKeys.value.includes(groupKey)) {
      return;
    }

    openKeys.value = [...openKeys.value, groupKey];
  },
  { immediate: true }
);

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};

const handleOpenPersonalCenter = () => {
  router.push('/personal-center');
};

// 项目选择器相关
const showProjectSelector = computed(() => isApproved.value);

// 当前选中的项目 ID
const selectedProjectId = computed({
  get: () => projectStore.currentProjectId,
  set: (value) => {
    if (value) {
      projectStore.setCurrentProjectById(value);
    }
  }
});

// 处理项目变更
const handleProjectChange = (projectId: number) => {
  projectStore.setCurrentProjectById(projectId);
};

// 处理下拉框显示状态变化
const handlePopupVisibleChange = (visible: boolean) => {
  if (visible) {
    // 当下拉框打开时，重新获取项目列表
    projectStore.fetchProjects();
  }
};

// 在组件挂载时检查认证状态并加载项目列表
onMounted(async () => {
  window.addEventListener('focus', handleWindowFocus);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  // 确保用户信息在组件挂载时被正确加载
  authStore.checkAuthStatus();
  console.log('MainLayout mounted, user:', user.value?.username);

  // 加载项目列表
  await projectStore.fetchProjects();

  if (activeGroupKey.value && !openKeys.value.includes(activeGroupKey.value)) {
    openKeys.value = [...openKeys.value, activeGroupKey.value];
  }
  
  // 检查版本更新，在后台执行且不阻塞页面
  checkVersion();
  await refreshAiStatus();
});

onUnmounted(() => {
  window.removeEventListener('focus', handleWindowFocus);
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  clearAiStatusTimer();
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  padding: 0 20px;
  height: 56px;
  line-height: 56px;
  color: #333333;
  margin: 10px 10px;
  border-radius: 8px;
  box-shadow: -4px -4px 10px rgba(0, 0, 0, 0.2), 4px 0 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

.left-section {
  display: flex;
  align-items: center;
  margin-left: 0; /* 移除左边距，让 logo 顶着边缘 */
}

.logo {
  font-size: 1.2em;
  font-weight: bold;
  color: #ffffff;
  text-align: left;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  padding: 0;
  margin: 0;
  margin-right: 12px;
  box-sizing: border-box;
  width: auto;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  flex-shrink: 0;
}

.logo-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 4px;
  transform: translateY(-2px);
}

.logo-icon {
  width: 56px;
  height: 56px;
  object-fit: contain;
  margin-right: 0;
}

.logo-text {
  flex-shrink: 0;
  font-size: 22px;
  font-family: "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-weight: 600;
  letter-spacing: 0.015em;
  line-height: 0.96;
  color: #1f2329;
  text-shadow: none;
}

.logo-subtitle {
  flex-shrink: 0;
  font-size: 11px;
  font-family: "Segoe UI Variable Text", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-weight: 600;
  letter-spacing: 0.16em;
  line-height: 1;
  color: rgba(0, 0, 0, 0.58);
  white-space: nowrap;
}

.project-selector {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  margin-right: 20px;
  gap: 12px;
}

.theme-switch-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--theme-border);
  border-radius: 999px;
  background: var(--theme-toggle-bg);
  color: var(--theme-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-switch-button:hover {
  color: var(--theme-text);
  border-color: rgba(var(--theme-accent-rgb), 0.36);
  background: var(--theme-toggle-hover);
}

.theme-switch-button:focus-visible {
  outline: 2px solid rgba(var(--theme-accent-rgb), 0.45);
  outline-offset: 2px;
}

.theme-switch-icon {
  font-size: 16px;
  line-height: 1;
}

/* 版本号样式 */
.version-badge {
  font-size: 13px;
  color: #86909c;
  background: #f2f3f5;
  padding: 2px 8px;
  border-radius: 10px;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  line-height: 1.5;
}

.version-badge.update-available {
  color: #00b42a;
  background: #e8ffea;
  cursor: pointer;
}

.version-badge.update-available:hover {
  background: #d4f7d4;
}

.update-dot {
  width: 5px;
  height: 5px;
  background: #00b42a;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}

/* 版本更新弹出框样式 */
.version-update-info {
  max-width: 320px;
  padding: 4px;
}

.version-update-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e6eb;
}

.update-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.update-version {
  font-size: 13px;
  color: #00b42a;
  font-weight: 500;
  background: #e8ffea;
  padding: 2px 8px;
  border-radius: 4px;
}

.version-update-notes {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
}

.version-update-notes::-webkit-scrollbar {
  display: none; /* Chrome/Safari/Opera */
}

.version-update-footer {
  display: block;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5e6eb;
  font-size: 12px;
  color: #165dff;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}

.version-update-footer:hover {
  color: #0e42d2;
  text-decoration: underline;
}

.avatar {
  margin-right: 8px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.menu-link {
  display: block;
  width: 100%;
}

.username {
  margin-right: 4px;
  font-size: 14px;
  color: #333333;
}

.dropdown-user-info {
  padding: 6px 8px;
  min-width: 120px;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-username {
  font-weight: bold;
  font-size: 13px;
  color: #333333;
  margin-bottom: 3px;
}

.dropdown-email {
  font-size: 11px;
  color: #666666;
  margin-bottom: 3px;
}

.dropdown-role {
  font-size: 11px;
  color: var(--theme-accent);
  background-color: rgba(var(--theme-accent-rgb), 0.1);
  padding: 1px 4px;
  border-radius: 3px;
  display: inline-block;
}

.avatar {
  background-color: var(--theme-accent);
  color: #ffffff;
}

.user-dropdown-wrapper :deep(.arco-dropdown-content) {
  right: 35px !important;
  left: auto !important;
  transform: none !important;
}

.sider {
  background: #ffffff;
  margin: 0 0 10px 10px;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  height: auto; /* 让 flex 自动撑开 */
}

.menu {
  background: #ffffff;
  color: #333333;
  border-right: none;
  border-radius: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  text-align: left;
  max-height: calc(100% - 50px);
}

:deep(.arco-menu-light) {
  background-color: #ffffff;
}

:deep(.arco-menu-light .arco-menu-item) {
  color: #666666;
  text-align: left;
  padding-left: 14px;
}

:deep(.arco-menu-light .arco-menu-item a) {
  color: inherit;
  text-decoration: none;
  display: block;
}

:deep(.arco-menu-light .arco-menu-item .arco-icon) {
  margin-right: 1px;
  margin-left: 0;
  float: left;
  color: inherit;
}

/* 收起状态下的菜单项样式 */
:deep(.arco-menu-collapse .arco-menu-item) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  border-left: none !important;
}

:deep(.arco-menu-collapse .arco-menu-selected) {
  border-left: none !important;
}

:deep(.arco-menu-collapse .arco-menu-item .arco-icon) {
  margin-right: 0;
  margin-left: 0;
  float: none;
  font-size: 18px;
}

:deep(.arco-menu-collapse .arco-menu-inline-header) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

:deep(.arco-menu-light .arco-menu-item:hover) {
  color: var(--theme-accent);
}

:deep(.arco-menu-light .arco-menu-selected) {
  color: var(--theme-accent);
  background-color: transparent;
  border-left: none;
}

:deep(.arco-menu-light .arco-menu-inline-header) {
  color: #666666;
  cursor: pointer;
  text-align: left;
  padding-left: 14px;
}

:deep(.arco-menu-light .arco-menu-inline-header:hover) {
  color: var(--theme-accent);
}

:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-selected) {
  color: var(--theme-accent);
  background-color: transparent;
  border-left: none;
}

:deep(.arco-menu-light .arco-menu-inline-header .arco-icon) {
  margin-right: 1px;
  margin-left: 0;
  float: left;
  color: inherit;
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item) {
  padding-left: 1px;
  padding-right: 0;
  text-align: left;
}

/* 收起状态下的子菜单图标样式 */
:deep(.arco-menu-collapse .arco-menu-inline-header .arco-icon) {
  margin-right: 0;
  margin-left: 0;
  float: none;
  position: relative;
  left: 0;
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item a) {
  color: inherit;
  text-decoration: none;
  display: block;
}

:deep(.arco-menu-light .arco-menu-inline-header .arco-icon-down) {
  font-size: 12px;
  margin-right: 0;
  margin-left: 5px;
  transition: transform 0.2s;
  float: none;
}

:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-inline-header-open .arco-icon-down) {
  transform: rotate(180deg);
}
</style>

<!-- 全局样式 - 用于菜单弹出层备用 -->
<style>
/* 备用样式：确保弹出菜单不受高度限制 */
.arco-menu-pop .arco-menu-inner {
  max-height: unset !important;
}

.main-layout {
  --dashboard-header-height: 104px;
  --dashboard-header-total-height: 136px;
  height: 100vh;
  min-height: 100vh;
  background-color: var(--theme-page-bg);
  overflow: hidden;
}

.inner-layout {
  height: calc(100vh - var(--dashboard-header-total-height));
  min-height: 0;
}

.content {
  padding: 0;
  background-color: var(--theme-page-bg);
  height: calc(100vh - var(--dashboard-header-total-height) - 16px);
  margin: 0 10px 10px 10px;
  overflow: hidden; /* 让子组件自行控制滚动 */
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

.sider-footer {
  position: absolute;
  bottom: 0;
  width: 100%;
  padding: 10px 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-top: 1px solid var(--theme-border);
}

.collapse-button {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
  padding: 0;
  margin: 0 auto;
}

.collapse-button:hover {
  color: var(--theme-accent);
}

/* 收起状态下的按钮样式 */
.sider-footer .arco-btn-icon-only {
  width: 32px;
  height: 32px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.header {
  height: var(--dashboard-header-height);
  margin: 16px 16px;
  padding: 0 28px;
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 253, 0.84));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: var(--theme-card-shadow-strong);
  backdrop-filter: blur(18px);
}

.left-section {
  gap: 22px;
}

.logo {
  width: auto;
  gap: 8px;
  margin-right: 8px;
}

.logo-copy {
  gap: 5px;
  transform: translateY(-3px);
}

.logo-icon {
  width: 60px;
  height: 60px;
  margin-right: 0;
}

.logo-text {
  display: inline-flex;
  align-items: center;
  padding-top: 2px;
  font-size: 24px;
  font-family: "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #1f2329;
  text-shadow: none;
}

.logo-subtitle {
  font-size: 11px;
  font-family: "Segoe UI Variable Text", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  letter-spacing: 0.18em;
}

.project-selector :deep(.arco-select-view) {
  min-width: 240px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.user-info {
  gap: 14px;
  margin-right: 0;
}

.version-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 600;
  background: rgba(240, 245, 251, 0.94);
}

.avatar {
  width: 38px;
  height: 38px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(var(--theme-accent-rgb), 0.18);
}

.username {
  font-weight: 600;
  color: var(--theme-text);
}

.sider {
  margin: 0 0 16px 16px;
  border-radius: 28px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(246, 249, 253, 0.58));
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: var(--theme-card-shadow-strong);
  backdrop-filter: blur(22px);
}

.menu {
  flex: 1;
  min-height: 0;
  padding: 16px 12px 68px;
  border-radius: 28px;
  background: transparent;
}

:deep(.arco-menu-light .arco-menu-item),
:deep(.arco-menu-light .arco-menu-inline-header) {
  min-height: 46px;
  margin-bottom: 8px;
  border-radius: 16px;
  color: var(--theme-text-secondary);
  font-weight: 600;
  font-size: 15px;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

:deep(.arco-menu-light .arco-menu-item:hover),
:deep(.arco-menu-light .arco-menu-inline-header:hover) {
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-accent);
}

:deep(.arco-menu-light .arco-menu-selected),
:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-selected) {
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.12), rgba(15, 126, 168, 0.08));
  color: var(--theme-accent-active);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

.content {
  margin: 0 16px 16px;
  border-radius: 30px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(246, 249, 253, 0.72));
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: var(--theme-card-shadow-strong);
  backdrop-filter: blur(16px);
}

.sider-footer {
  padding: 12px 0 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(245, 248, 252, 0.92) 45%);
}

.collapse-button {
  padding: 6px 12px;
  border-radius: 999px;
}

.collapse-button:hover {
  background: rgba(var(--theme-accent-rgb), 0.08);
}

.main-layout {
  position: relative;
}

.main-layout::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 10%, rgba(var(--theme-accent-rgb), 0.1), transparent 22%),
    radial-gradient(circle at 88% 16%, rgba(15, 126, 168, 0.08), transparent 18%);
  pointer-events: none;
}

.workspace-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.workspace-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #34d399, #0ea5e9);
  box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.12);
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.workspace-badge--checking {
  color: #b45309;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(255, 251, 235, 0.92);
}

.workspace-badge--checking .workspace-dot {
  background: linear-gradient(135deg, #f59e0b, #f97316);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.16);
}

.workspace-badge--online {
  color: #0f766e;
  border-color: rgba(16, 185, 129, 0.26);
  background: rgba(236, 253, 245, 0.92);
}

.workspace-badge--online .workspace-dot {
  background: linear-gradient(135deg, #34d399, #0ea5e9);
  box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.14);
}

.workspace-badge--warning {
  color: #9a3412;
  border-color: rgba(249, 115, 22, 0.26);
  background: rgba(255, 247, 237, 0.92);
}

.workspace-badge--warning .workspace-dot {
  background: linear-gradient(135deg, #f97316, #fb7185);
  box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.14);
}

.workspace-badge--offline,
.workspace-badge--unconfigured {
  color: #991b1b;
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(254, 242, 242, 0.92);
}

.workspace-badge--offline .workspace-dot,
.workspace-badge--unconfigured .workspace-dot {
  background: linear-gradient(135deg, #ef4444, #f43f5e);
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
}

.header {
  position: relative;
  overflow: hidden;
}

.header::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.26), transparent 26%),
    radial-gradient(circle at 82% 12%, rgba(var(--theme-accent-rgb), 0.1), transparent 20%);
  pointer-events: none;
}

.header > * {
  position: relative;
  z-index: 1;
}

.project-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.project-selector :deep(.arco-select-view) {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.sider {
  position: relative;
  overflow: hidden;
}

.sider::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.26), transparent 16%),
    radial-gradient(circle at top center, rgba(var(--theme-accent-rgb), 0.08), transparent 24%);
  pointer-events: none;
}

.menu {
  position: relative;
  z-index: 1;
}

:deep(.arco-menu-light .arco-menu-item),
:deep(.arco-menu-light .arco-menu-inline-header) {
  padding-left: 18px !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.58);
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item) {
  padding-left: 18px !important;
}

.content {
  position: relative;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.content::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.22), transparent 18%),
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.06), transparent 24%);
  pointer-events: none;
}

.content > * {
  position: relative;
  z-index: 1;
  display: block;
  min-height: 100%;
  width: 100%;
}

.layout-menu-popup,
.user-panel-dropdown {
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(245, 248, 252, 0.58));
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(22px);
}

.layout-menu-popup .arco-menu,
.layout-menu-popup .arco-menu-light,
.user-panel-dropdown .arco-dropdown,
.user-panel-dropdown .arco-dropdown-list-wrapper {
  background: transparent !important;
  box-shadow: none !important;
}

.layout-menu-popup .arco-menu-item,
.layout-menu-popup .arco-menu-pop-header,
.user-panel-dropdown .arco-dropdown-option {
  border-radius: 14px;
}

.layout-menu-popup .arco-menu-item:hover,
.layout-menu-popup .arco-menu-pop-header:hover,
.user-panel-dropdown .arco-dropdown-option:not(.arco-dropdown-option-disabled):hover {
  background: rgba(var(--theme-accent-rgb), 0.1);
}

.main-layout,
.main-layout * {
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.32) transparent;
}

.main-layout ::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.main-layout ::-webkit-scrollbar-track {
  background: transparent;
}

.main-layout ::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.28);
  border: 2px solid transparent;
  background-clip: padding-box;
}

.main-layout ::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.4);
  border: 2px solid transparent;
  background-clip: padding-box;
}

@media (max-width: 1100px) {
  .workspace-badge {
    display: none;
  }
}
</style>

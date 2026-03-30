<template>
  <a-layout class="main-layout">
    <!-- 顶部导航栏 -->
    <a-layout-header class="header">
      <div class="left-section">
        <div class="logo" unselectable="on">
          <div class="logo-mark">
            <img :src="brandLogoUrl" alt="FlyTest Logo" class="logo-icon" />
          </div>
          <div class="logo-copy">
            <span class="logo-eyebrow">AI Test Command Center</span>
            <span class="logo-text">FlyTest</span>
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
        <div class="workspace-badge">
          <span class="workspace-dot"></span>
          <span>AI Workspace</span>
        </div>
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
                <span class="update-title">🎉 新版本可用</span>
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
        <a-dropdown trigger="click" class="user-dropdown-wrapper">
          <div class="user-dropdown">
            <span class="username">{{ username }}</span>
            <icon-down />
          </div>
          <template #content>
            <div class="dropdown-user-info">
              <div class="dropdown-username">{{ username }}</div>
              <div class="dropdown-email" v-if="user?.email">{{ user.email }}</div>
              <div class="dropdown-role" v-if="user?.is_staff">管理员</div>
            </div>
            <a-divider style="margin: 4px 0" />
            <a-doption @click="handleLogout">登出</a-doption>
          </template>
        </a-dropdown>
      </div>
    </a-layout-header>

    <a-layout class="inner-layout">
      <!-- 左侧菜单栏 -->
      <a-layout-sider
        :width="170"
        :collapsed-width="50"
        :collapsed="collapsed"
        :trigger="null"
        hide-trigger
        class="sider"
      >
        <a-menu
          mode="vertical"
          :default-selected-keys="[activeMenu]"
          v-model:open-keys="openKeys"
          :auto-open-selected="true"
          :collapsed="collapsed"
          :popup-max-height="false"
          class="menu"
        >

          <a-menu-item key="dashboard">
            <template #icon><icon-home /></template>
            <router-link to="/dashboard">首页</router-link>
          </a-menu-item>

          <a-menu-item key="projects" v-if="hasProjectsPermission">
            <template #icon><icon-storage /></template>
            <router-link to="/projects">项目管理</router-link>
          </a-menu-item>

          <a-menu-item key="requirements" v-if="hasRequirementsPermission">
            <template #icon><icon-file /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/requirements')">需求管理</a>
          </a-menu-item>

          <a-menu-item key="ai-diagram" v-if="hasLangGraphChatPermission">
            <template #icon><icon-mind-mapping /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/ai-diagram')">智能图表</a>
          </a-menu-item>

          <a-menu-item key="api-automation" v-if="hasApiAutomationPermission">
            <template #icon><icon-code-block /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/api-automation')">API自动化</a>
          </a-menu-item>

          <a-menu-item key="ui-automation" v-if="hasUiAutomationPermission">
            <template #icon><icon-computer /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/ui-automation')">UI自动化</a>
          </a-menu-item>

          <!-- 测试管理子菜单 -->
          <a-sub-menu key="test-management" v-if="hasTestManagementMenuItems">
            <template #icon><icon-experiment /></template>
            <template #title>
              <span @click="handleTestManagementClick">测试管理</span>
            </template>
            <a-menu-item key="testcases" v-if="hasTestcasesPermission">
              <template #icon><icon-code-block /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/testcases')">用例管理</a>
            </a-menu-item>
            <a-menu-item key="testsuites" v-if="hasTestSuitesPermission">
              <template #icon><icon-folder /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/testsuites')">测试套件</a>
            </a-menu-item>
            <a-menu-item key="test-executions" v-if="hasTestExecutionsPermission">
              <template #icon><icon-history /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/test-executions')">执行历史</a>
            </a-menu-item>
          </a-sub-menu>

          <a-menu-item key="langgraph-chat" v-if="hasLangGraphChatPermission">
            <template #icon><icon-message /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/langgraph-chat')">AI对话</a>
          </a-menu-item>

          <a-menu-item key="knowledge-management" v-if="hasKnowledgePermission">
            <template #icon><icon-book /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/knowledge-management')">知识库管理</a>
          </a-menu-item>

          <!-- 系统管理子菜单 -->
          <a-sub-menu key="settings" v-if="hasSystemMenuItems">
            <template #icon><icon-settings /></template>
            <template #title>
              <span @click="handleSystemManagementClick">系统管理</span>
            </template>
            <a-menu-item key="users" v-if="hasUsersPermission">
              <template #icon><icon-user /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/users')">用户管理</a>
            </a-menu-item>
            <a-menu-item key="organizations" v-if="hasOrganizationsPermission">
              <template #icon><icon-apps /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/organizations')">组织管理</a>
            </a-menu-item>
            <a-menu-item key="permissions" v-if="hasPermissionsPermission">
              <template #icon><icon-safe /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/permissions')">权限管理</a>
            </a-menu-item>
            <a-menu-item key="llm-configs" v-if="hasLlmConfigsPermission">
              <template #icon><icon-tool /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/llm-configs')">LLM配置</a>
            </a-menu-item>
            <a-menu-item key="api-keys" v-if="hasApiKeysPermission">
              <template #icon><icon-safe /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/api-keys')">KEY管理</a>
            </a-menu-item>
            <a-menu-item key="remote-mcp-configs" v-if="hasMcpConfigsPermission">
              <template #icon><icon-cloud /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/remote-mcp-configs')">MCP配置</a>
            </a-menu-item>
            <a-menu-item key="skills" v-if="hasSkillsPermission">
              <template #icon><icon-apps /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/skills')">Skills管理</a>
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
import { ref, computed, nextTick, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import { useThemeStore } from '@/store/themeStore';
import { brandLogoUrl } from '@/utils/assetUrl';
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
  IconSunFill,
  IconMoonFill,
} from '@arco-design/web-vue/es/icon';
import '@arco-design/web-vue/dist/arco.css'; // 引入 Arco Design 样式

const ALayoutHeader = ALayout.Header;
const ALayoutSider = ALayout.Sider;
const ALayoutContent = ALayout.Content;
const AMenuItem = AMenu.Item;
const AOption = ASelect.Option;

const router = useRouter();
const authStore = useAuthStore();
const projectStore = useProjectStore();
const themeStore = useThemeStore();

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
async function checkVersion() {
  try {
    versionInfo.value = await checkLatestVersion();
  } catch (error) {
    console.warn('版本检查失败:', error);
  }
}

// 用户信息
const user = computed(() => authStore.currentUser);
const username = computed(() => user.value?.username || '');
const userInitial = computed(() => {
  if (user.value?.first_name && user.value.first_name.length > 0) {
    return user.value.first_name.charAt(0).toUpperCase();
  }
  return username.value.charAt(0).toUpperCase();
});

const themeButtonLabel = computed(() => themeStore.isBlack ? '切换到默认主题' : '切换到黑色主题');

// 当前激活的菜单项
const activeMenu = computed(() => {
  const path = router.currentRoute.value.path;
  if (path.startsWith('/dashboard')) return 'dashboard';
  if (path.startsWith('/projects')) return 'projects';
  if (path.startsWith('/requirements')) return 'requirements'; // 添加对需求管理路由的识别
  if (path.startsWith('/testsuites')) return 'testsuites'; // 添加对测试套件路由的识别
  if (path.startsWith('/test-executions')) return 'test-executions'; // 添加对执行历史路由的识别
  if (path.startsWith('/testcases')) return 'testcases';
  if (path.startsWith('/users')) return 'users';
  if (path.startsWith('/organizations')) return 'organizations';
  if (path.startsWith('/permissions')) return 'permissions';
  if (path.startsWith('/llm-configs')) return 'llm-configs';
  if (path.startsWith('/langgraph-chat')) return 'langgraph-chat';
  if (path.startsWith('/ai-diagram')) return 'ai-diagram';
  if (path.startsWith('/api-automation')) return 'api-automation';
  if (path.startsWith('/knowledge-management')) return 'knowledge-management';
  if (path.startsWith('/api-keys')) return 'api-keys';
  if (path.startsWith('/remote-mcp-configs')) return 'remote-mcp-configs';
  // 其他路由对应的菜单项
  return '';
});

// 当前打开的子菜单
const openKeys = ref<string[]>([]); // 默认所有子菜单都收起

// 侧边栏收起状态
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

const hasApiAutomationPermission = computed(() => {
  return authStore.hasPermission('api_automation.view_apicollection') ||
         authStore.hasPermission('api_automation.view_apirequest') ||
         authStore.hasPermission('api_automation.view_apienvironment');
});

const hasUiAutomationPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uimodule') ||
         authStore.hasPermission('ui_automation.view_uipage') ||
         authStore.hasPermission('ui_automation.view_uitestcase');
});

const hasKnowledgePermission = computed(() => {
  return authStore.hasPermission('knowledge.view_knowledgebase');
});

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
};

// 处理点击测试管理图标的事件
const handleTestManagementClick = (event: MouseEvent) => {
  // 阻止事件冒泡，防止触发其他事件
  if (event) {
    event.stopPropagation();
  }

  // 如果是收起状态，点击测试管理图标时展开侧边栏
  if (collapsed.value) {
    collapsed.value = false;
    // 展开测试管理子菜单
    openKeys.value = ['test-management'];
  } else {
    // 如果已经展开，则切换子菜单的展开状态
    if (openKeys.value.includes('test-management')) {
      openKeys.value = openKeys.value.filter(key => key !== 'test-management');
    } else {
      openKeys.value.push('test-management');
    }
  }

  // 确保状态更新后立即应用
  nextTick(() => {
    console.log('测试管理菜单状态更新:', openKeys.value);
  });
};

// 处理点击系统管理图标的事件
const handleSystemManagementClick = (event: MouseEvent) => {
  // 阻止事件冒泡，防止触发其他事件
  if (event) {
    event.stopPropagation();
  }

  // 如果是收起状态，点击系统管理图标时展开侧边栏
  if (collapsed.value) {
    collapsed.value = false;
    // 展开系统管理子菜单
    openKeys.value = ['settings'];
  } else {
    // 如果已经展开，则切换子菜单的展开状态
    if (openKeys.value.includes('settings')) {
      openKeys.value = openKeys.value.filter(key => key !== 'settings');
    } else {
      openKeys.value.push('settings');
    }
  }

  // 确保状态更新后立即应用
  nextTick(() => {
    console.log('系统管理菜单状态更新:', openKeys.value);
  });
};

// 检查是否选择了项目，用于需要项目的菜单项
const checkProjectAndNavigate = (event: MouseEvent, path: string) => {
  if (!projectStore.currentProjectId) {
    event.preventDefault();
    Message.warning('请先选择或创建项目');
    return;
  }
  router.push(path);
};

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};

// 项目选择器相关
// 在所有页面都显示项目选择器
const showProjectSelector = computed(() => true);

// 当前选中的项目ID
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
  // 确保用户信息在组件挂载时被正确加载
  authStore.checkAuthStatus();
  console.log('MainLayout mounted, user:', user.value?.username);

  // 加载项目列表
  await projectStore.fetchProjects();
  
  // 检查版本更新（后台执行，不阻塞页面）
  checkVersion();
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
  margin-left: 0; /* 移除左边距，让logo顶着边缘 */
}

.logo {
  font-size: 1.2em;
  font-weight: bold;
  color: #333333;
  text-align: left;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  padding: 0;
  margin: 0;
  margin-right: 20px;
  box-sizing: border-box;
  width: 140px;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.logo-icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
  border-radius: 3px;
  margin-right: 8px;
}

.logo-text {
  flex-shrink: 0;
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
  height: 100vh;
  background-color: var(--theme-page-bg);
  overflow: hidden;
}

.inner-layout {
  height: calc(100vh - 76px); /* Header(56px) + margin(10px*2) = 76px */
}

.content {
  padding: 0;
  background-color: var(--theme-page-bg);
  height: calc(100vh - 86px); /* 保持 86px 是因为底部还有 10px 的 margin */
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
  height: 72px;
  margin: 16px 16px 12px;
  padding: 0 24px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 253, 0.84));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: var(--theme-card-shadow-strong);
  backdrop-filter: blur(18px);
}

.left-section {
  gap: 18px;
}

.logo {
  width: auto;
  gap: 14px;
  margin-right: 10px;
}

.logo-mark {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.14), rgba(15, 126, 168, 0.12));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.logo-icon {
  width: 26px;
  height: 26px;
  margin-right: 0;
}

.logo-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1;
}

.logo-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--theme-text-tertiary);
}

.logo-text {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--theme-text);
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
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(246, 249, 253, 0.88));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: var(--theme-card-shadow-strong);
  backdrop-filter: blur(16px);
}

.menu {
  padding: 16px 12px 68px;
  border-radius: 28px;
  background: transparent;
}

:deep(.arco-menu-light .arco-menu-item),
:deep(.arco-menu-light .arco-menu-inline-header) {
  min-height: 44px;
  margin-bottom: 6px;
  border-radius: 16px;
  color: var(--theme-text-secondary);
  font-weight: 600;
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
}

.workspace-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #34d399, #0ea5e9);
  box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.12);
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

.logo-mark {
  position: relative;
}

.logo-mark::after {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 20px;
  background: radial-gradient(circle, rgba(var(--theme-accent-rgb), 0.12), transparent 72%);
  z-index: -1;
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
  padding-left: 16px !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.58);
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item) {
  padding-left: 16px !important;
}

.content {
  position: relative;
  overflow: hidden;
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
}

@media (max-width: 1100px) {
  .workspace-badge {
    display: none;
  }
}
</style>

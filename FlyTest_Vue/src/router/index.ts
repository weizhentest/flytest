import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../store/authStore'

const MainLayout = () => import('../layouts/MainLayout.vue')
const LoginView = () => import('../views/LoginView.vue')
const RegisterView = () => import('../views/RegisterView.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const PersonalCenterView = () => import('../views/PersonalCenterView.vue')
const UserManagementView = () => import('../views/UserManagementView.vue')
const OrganizationManagementView = () => import('../views/OrganizationManagementView.vue')
const PermissionManagementView = () => import('../views/PermissionManagementView.vue')
const ProjectManagementView = () => import('../views/ProjectManagementView.vue')
const ProjectDeletionLogView = () => import('../views/ProjectDeletionLogView.vue')
const TestCaseManagementView = () => import('../views/TestCaseManagementView.vue')
const TestSuiteManagementView = () => import('../views/TestSuiteManagementView.vue')
const TestBugManagementView = () => import('../views/TestBugManagementView.vue')
const TestExecutionHistoryView = () => import('../views/TestExecutionHistoryView.vue')
const ApiKeyManagementView = () => import('../views/ApiKeyManagementView.vue')
const RemoteMcpConfigManagementView = () => import('../views/RemoteMcpConfigManagementView.vue')

const LlmConfigManagementView = () => import('@/features/langgraph/views/LlmConfigManagementView.vue')
const LangGraphChatView = () => import('@/features/langgraph/views/LangGraphChatView.vue')
const KnowledgeManagementView = () => import('@/features/knowledge/views/KnowledgeManagementView.vue')
const DataFactoryView = () => import('@/features/data-factory/views/DataFactoryView.vue')
const RequirementManagementView = () => import('@/features/requirements/views/RequirementManagementView.vue')
const DocumentDetailView = () => import('@/features/requirements/views/DocumentDetailView.vue')
const SpecializedReportView = () => import('@/features/requirements/views/SpecializedReportView.vue')
const AiDiagramView = () => import('@/features/diagrams/views/AiDiagramView.vue')
const SkillsManagementView = () => import('@/features/skills/views/SkillsManagementView.vue')
const TemplateManagementView = () => import('@/features/testcase-templates/views/TemplateManagementView.vue')
const ApiAutomationView = () => import('@/features/api-automation/views/ApiAutomationView.vue')
const AppAutomationView = () => import('@/features/app-automation/views/AppAutomationView.vue')
const UiAutomationView = () => import('@/features/ui-automation/views/UiAutomationView.vue')
const TraceDetailView = () => import('@/features/ui-automation/views/TraceDetail.vue')

const privateRoutePreloaders = [
  DashboardView,
  PersonalCenterView,
  ProjectManagementView,
  ProjectDeletionLogView,
  UserManagementView,
  OrganizationManagementView,
  PermissionManagementView,
  LlmConfigManagementView,
  ApiKeyManagementView,
  RemoteMcpConfigManagementView,
  SkillsManagementView,
]

let privateRouteComponentsPreloaded = false

export const preloadPrivateRouteComponents = async () => {
  if (privateRouteComponentsPreloaded) {
    return
  }

  privateRouteComponentsPreloaded = true
  await Promise.allSettled(privateRoutePreloaders.map(load => load()))
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
  },
  {
    path: '/register',
    name: 'Register',
    component: RegisterView,
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: DashboardView,
      },
      {
        path: 'personal-center',
        name: 'PersonalCenter',
        component: PersonalCenterView,
      },
      {
        path: 'projects',
        name: 'ProjectManagement',
        component: ProjectManagementView,
      },
      {
        path: 'project-deletion-logs',
        name: 'ProjectDeletionLogs',
        component: ProjectDeletionLogView,
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: UserManagementView,
      },
      {
        path: 'organizations',
        name: 'OrganizationManagement',
        component: OrganizationManagementView,
      },
      {
        path: 'permissions',
        name: 'PermissionManagement',
        component: PermissionManagementView,
      },
      {
        path: 'testcases',
        name: 'TestCaseManagement',
        component: TestCaseManagementView,
      },
      {
        path: 'testsuites',
        name: 'TestSuiteManagement',
        component: TestSuiteManagementView,
      },
      {
        path: 'test-bugs',
        name: 'TestBugManagement',
        component: TestBugManagementView,
      },
      {
        path: 'test-executions',
        name: 'TestExecutionHistory',
        component: TestExecutionHistoryView,
      },
      {
        path: 'llm-configs',
        name: 'LlmConfigManagement',
        component: LlmConfigManagementView,
      },
      {
        path: 'langgraph-chat',
        name: 'LangGraphChat',
        component: LangGraphChatView,
      },
      {
        path: 'knowledge-management',
        name: 'KnowledgeManagement',
        component: KnowledgeManagementView,
      },
      {
        path: 'data-factory',
        name: 'DataFactory',
        component: DataFactoryView,
      },
      {
        path: 'api-keys',
        name: 'ApiKeyManagement',
        component: ApiKeyManagementView,
      },
      {
        path: 'remote-mcp-configs',
        name: 'RemoteMcpConfigManagement',
        component: RemoteMcpConfigManagementView,
      },
      {
        path: 'requirements',
        name: 'RequirementManagement',
        component: RequirementManagementView,
      },
      {
        path: 'requirements/:id',
        name: 'DocumentDetail',
        component: DocumentDetailView,
      },
      {
        path: 'requirements/:id/report',
        name: 'ReportDetail',
        component: SpecializedReportView,
      },
      {
        path: 'ai-diagram',
        name: 'AiDiagram',
        component: AiDiagramView,
      },
      {
        path: 'skills',
        name: 'SkillsManagement',
        component: SkillsManagementView,
      },
      {
        path: 'testcase-templates',
        name: 'TemplateManagement',
        component: TemplateManagementView,
      },
      {
        path: 'api-automation',
        name: 'ApiAutomation',
        component: ApiAutomationView,
      },
      {
        path: 'app-automation',
        name: 'AppAutomation',
        component: AppAutomationView,
      },
      {
        path: 'ui-automation',
        name: 'UiAutomation',
        component: UiAutomationView,
      },
      {
        path: 'ui-automation/trace/:id',
        name: 'TraceDetail',
        component: TraceDetailView,
        props: true,
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (!authStore.isInitialized) {
    await authStore.bootstrapSession()
  }

  const isLoggedIn = authStore.isAuthenticated
  const publicRoutes = new Set(['Login', 'Register'])
  const routeName = String(to.name || '')

  if (!isLoggedIn && !publicRoutes.has(routeName)) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  if (isLoggedIn && publicRoutes.has(routeName)) {
    next({ name: 'Dashboard' })
    return
  }

  if (isLoggedIn && !authStore.isApproved && !['Dashboard', 'PersonalCenter'].includes(routeName)) {
    next({ name: 'Dashboard' })
    return
  }

  next()
})

export default router

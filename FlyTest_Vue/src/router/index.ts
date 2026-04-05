import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../store/authStore'

const MainLayout = () => import('../layouts/MainLayout.vue')
const LoginView = () => import('../views/LoginView.vue')
const RegisterView = () => import('../views/RegisterView.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const UserManagementView = () => import('../views/UserManagementView.vue')
const OrganizationManagementView = () => import('../views/OrganizationManagementView.vue')
const PermissionManagementView = () => import('../views/PermissionManagementView.vue')
const ProjectManagementView = () => import('../views/ProjectManagementView.vue')
const TestCaseManagementView = () => import('../views/TestCaseManagementView.vue')
const TestSuiteManagementView = () => import('../views/TestSuiteManagementView.vue')
const TestExecutionHistoryView = () => import('../views/TestExecutionHistoryView.vue')
const ApiKeyManagementView = () => import('../views/ApiKeyManagementView.vue')
const RemoteMcpConfigManagementView = () => import('../views/RemoteMcpConfigManagementView.vue')

const LlmConfigManagementView = () => import('@/features/langgraph/views/LlmConfigManagementView.vue')
const LangGraphChatView = () => import('@/features/langgraph/views/LangGraphChatView.vue')
const KnowledgeManagementView = () => import('@/features/knowledge/views/KnowledgeManagementView.vue')
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

const privateRouteLoaders = [
  DashboardView,
  ProjectManagementView,
  RequirementManagementView,
  UserManagementView,
  OrganizationManagementView,
  PermissionManagementView,
  TestCaseManagementView,
  TestSuiteManagementView,
  TestExecutionHistoryView,
  LlmConfigManagementView,
  LangGraphChatView,
  KnowledgeManagementView,
  ApiKeyManagementView,
  RemoteMcpConfigManagementView,
  SkillsManagementView,
  ApiAutomationView,
  AppAutomationView,
  UiAutomationView,
]

let privateRouteComponentsPreloaded = false

export const preloadPrivateRouteComponents = async () => {
  if (privateRouteComponentsPreloaded) {
    return
  }

  privateRouteComponentsPreloaded = true
  await Promise.allSettled(privateRouteLoaders.map(load => load()))
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
        path: 'projects',
        name: 'ProjectManagement',
        component: ProjectManagementView,
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

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (!authStore.isAuthenticated && typeof localStorage !== 'undefined') {
    authStore.checkAuthStatus()
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

  next()
})

export default router

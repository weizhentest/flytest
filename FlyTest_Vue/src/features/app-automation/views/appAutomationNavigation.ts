import type { LocationQueryRaw, RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { AppAutomationService } from '../services/appAutomationService'
import type { AppAutomationTab } from '../types'

export type AppAutomationQueryPatch = Record<string, string | undefined>

const appAutomationContextKeys = [
  'caseId',
  'executionId',
  'suiteId',
  'taskId',
  'reportMode',
] as const

const normalizeQueryValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return String(value[0] ?? '')
  }
  return String(value ?? '')
}

export const replaceAppAutomationQuery = async (
  route: RouteLocationNormalizedLoaded,
  router: Router,
  patch: AppAutomationQueryPatch,
) => {
  const nextQuery: LocationQueryRaw = { ...route.query }

  Object.entries(patch).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      delete nextQuery[key]
    } else {
      nextQuery[key] = value
    }
  })

  const keys = new Set([...Object.keys(route.query), ...Object.keys(nextQuery)])
  const changed = [...keys].some(key => normalizeQueryValue(route.query[key]) !== normalizeQueryValue(nextQuery[key]))

  if (!changed) {
    return
  }

  await router.replace({
    path: '/app-automation',
    query: nextQuery,
  })
}

export const buildAppAutomationTabChangePatch = (
  tab: AppAutomationTab,
): AppAutomationQueryPatch => {
  const patch: AppAutomationQueryPatch = { tab }

  appAutomationContextKeys.forEach(key => {
    patch[key] = undefined
  })

  return patch
}

export const pushAppAutomationTab = async (
  router: Router,
  tab: AppAutomationTab,
  patch: AppAutomationQueryPatch = {},
) => {
  await router.push({
    path: '/app-automation',
    query: {
      ...buildAppAutomationTabChangePatch(tab),
      ...patch,
    },
  })
}

export const pushAppAutomationExecutions = async (
  router: Router,
  options: { executionId?: number; suiteId?: number | null } = {},
) => {
  await pushAppAutomationTab(router, 'executions', {
    executionId: options.executionId ? String(options.executionId) : undefined,
    suiteId: options.suiteId ? String(options.suiteId) : undefined,
  })
}

export const pushAppAutomationSceneBuilder = async (
  router: Router,
  options: { caseId?: number } = {},
) => {
  await pushAppAutomationTab(router, 'scene-builder', {
    caseId: options.caseId ? String(options.caseId) : undefined,
  })
}

export const pushAppAutomationScheduledTasks = async (
  router: Router,
  options: { taskId?: number } = {},
) => {
  await pushAppAutomationTab(router, 'scheduled-tasks', {
    taskId: options.taskId ? String(options.taskId) : undefined,
  })
}

export const openExecutionReportWindow = (executionId: number) => {
  window.open(AppAutomationService.getExecutionReportUrl(executionId), '_blank', 'noopener')
}

export const openExecutionArtifactWindow = (executionId: number, relativePath: string) => {
  if (!relativePath) return

  if (
    relativePath.startsWith('http://') ||
    relativePath.startsWith('https://') ||
    relativePath.startsWith('data:')
  ) {
    window.open(relativePath, '_blank', 'noopener')
    return
  }

  window.open(
    AppAutomationService.getExecutionReportAssetUrl(executionId, relativePath),
    '_blank',
    'noopener',
  )
}

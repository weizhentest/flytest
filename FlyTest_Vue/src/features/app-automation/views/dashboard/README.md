# Dashboard Structure

`dashboard` 目录承接 APP 自动化概览页的页面壳、统计卡、AI 概览、任务快照、最近执行和快捷操作卡片。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationDashboard.ts`
  页面级 orchestration，负责概览数据加载、AI 状态刷新、任务动作和导航。

## Shared Models

- `dashboardViewModels.ts`
  概览页各卡片的 props，以及快捷操作项等视图模型。
- `dashboardEventModels.ts`
  Header、AI 卡、任务快照、最近执行、快捷操作这组组件的共享 emits。

## Components

- `DashboardHeaderBar.vue`
  页头、服务状态和刷新动作。
- `DashboardStatsGrid.vue`
  核心统计卡片。
- `DashboardExecutionSummaryCard.vue`
  执行概况摘要。
- `DashboardAiOverviewCard.vue`
  AI 模式概览。
- `DashboardTaskSnapshotCard.vue`
  定时任务快照。
- `DashboardRecentExecutionsCard.vue`
  最近执行记录。
- `DashboardQuickActionsCard.vue`
  常用跳转入口。

## Editing Rules

- 页面入口优先从 `./dashboard` barrel 引组件和 composable。
- 新增概览卡片 props 优先落到 `dashboardViewModels.ts`。
- 新增概览卡片 emits 优先落到 `dashboardEventModels.ts`。
- `useAppAutomationDashboard.ts` 继续保持 orchestration 角色，不把任务动作和 AI 状态逻辑重新塞回页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

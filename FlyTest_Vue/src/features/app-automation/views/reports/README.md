# Reports Structure

`reports` 目录承接 APP 自动化报告页的页面壳、套件报告面板、执行明细面板和相关详情弹窗。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationReports.ts`
  页面级 orchestration，负责数据加载、路由同步、筛选分页和报告打开逻辑。

## Shared Models

- `reportViewModels.ts`
  报告页的 filters、pagination、stats、status meta、artifact 和组件 props。
- `reportEventModels.ts`
  Header、Panel、Dialog 这组组件的共享 emits。

## Components

- `ReportsHeaderBar.vue`
  页头和刷新动作。
- `ReportsSuitePanel.vue`
  套件报告列表、筛选和统计。
- `ReportsExecutionPanel.vue`
  执行明细列表、筛选和统计。
- `ReportsSuiteDetailDialog.vue`
  套件基础信息和最近结果。
- `ReportsSuiteExecutionsDialog.vue`
  套件关联执行记录。
- `ReportsExecutionDetailDialog.vue`
  执行详情、日志和证据。

## Editing Rules

- 页面入口优先从 `./reports` barrel 引组件和 composable。
- 新增报告页视图模型优先落到 `reportViewModels.ts`。
- 新增组件 emits 优先落到 `reportEventModels.ts`。
- `useAppAutomationReports.ts` 继续保持 orchestration 角色，不把页面接线重新塞回入口页面。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

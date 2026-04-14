# Scheduled Tasks Structure

`scheduled-tasks` 目录承接 APP 自动化定时任务页面的页面壳、表格/弹窗组件和页面级逻辑。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationScheduledTasks.ts`
  页面级 orchestration，负责数据加载、过滤分页、动作处理和弹窗状态。

## Shared Models

- `scheduledTaskViewModels.ts`
  筛选条件、分页、表单、统计卡、详情/表格 props 这些共享视图模型。
- `scheduledTaskEventModels.ts`
  Header、Filter、Table、Detail、Form 这几组组件的共享 emits。

## Components

- `ScheduledTasksHeaderBar.vue`
  顶部页头操作。
- `ScheduledTasksFilterCard.vue`
  筛选区域。
- `ScheduledTasksStatsGrid.vue`
  统计卡片。
- `ScheduledTasksTableCard.vue`
  任务表格和分页。
- `ScheduledTaskDetailDialog.vue`
  任务详情和最近通知。
- `ScheduledTaskFormDialog.vue`
  新建/编辑任务表单。

## Editing Rules

- 页面入口优先从 `./scheduled-tasks` barrel 导入，不再散引组件。
- 新增视图模型优先落到 `scheduledTaskViewModels.ts`。
- 新增组件 emits 优先落到 `scheduledTaskEventModels.ts`。
- `useAppAutomationScheduledTasks.ts` 继续保持页面 orchestration 角色，不回塞到页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

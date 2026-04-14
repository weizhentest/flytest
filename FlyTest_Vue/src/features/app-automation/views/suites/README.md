# Suites Structure

`suites` 目录承接 APP 自动化测试套件页的页面壳、统计卡、套件表格和套件相关弹窗。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationSuites.ts`
  页面级 orchestration，负责套件加载、筛选、保存、执行、历史与详情跳转。

## Shared Models

- `suiteViewModels.ts`
  套件页的 filters、表单、运行表单、状态 meta、执行证据、统计和组件 props。
- `suiteEventModels.ts`
  Header、Editor、Run、History、ExecutionDetail、Table 这组组件的共享 emits。

## Components

- `SuitesHeaderBar.vue`
  页头、搜索/状态筛选和新建动作。
- `SuitesStatsGrid.vue`
  套件统计卡片。
- `SuitesTableCard.vue`
  套件列表和行内动作。
- `SuiteEditorDialog.vue`
  套件编辑弹窗。
- `SuiteRunDialog.vue`
  套件执行弹窗。
- `SuiteDetailDialog.vue`
  套件详情弹窗。
- `SuiteHistoryDialog.vue`
  套件执行历史弹窗。
- `SuiteExecutionDetailDialog.vue`
  套件执行明细弹窗。

## Editing Rules

- 页面入口优先从 `./suites` barrel 引组件和 composable。
- 新增套件页视图模型优先落到 `suiteViewModels.ts`。
- 新增组件 emits 优先落到 `suiteEventModels.ts`。
- `useAppAutomationSuites.ts` 继续保持 orchestration 角色，不把筛选/运行/历史逻辑重新塞回页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

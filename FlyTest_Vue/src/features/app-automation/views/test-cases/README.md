# Test Cases Structure

`test-cases` 目录承接 APP 自动化测试用例页的页面壳、统计卡、批量操作条、用例表格、最近执行和相关弹窗。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationTestCases.ts`
  页面级 orchestration，负责用例加载、筛选、创建/编辑、执行、批量执行和场景编排跳转。

## Shared Models

- `testCaseViewModels.ts`
  用例页的表单、执行表单、统计、组件 props。
- `testCaseEventModels.ts`
  Header、BatchBar、Table、RecentExecutions、Editor、Execute 这组组件的共享 emits。

## Components

- `TestCasesHeaderBar.vue`
  页头、搜索、包筛选和新建动作。
- `TestCasesStatsGrid.vue`
  用例统计卡片。
- `TestCasesBatchBar.vue`
  批量执行和清空选择操作条。
- `TestCasesTableCard.vue`
  用例列表。
- `TestCasesRecentExecutionsCard.vue`
  最近执行记录。
- `TestCaseEditorDialog.vue`
  测试用例编辑弹窗。
- `TestCaseExecuteDialog.vue`
  单个/批量执行弹窗。

## Editing Rules

- 页面入口优先从 `./test-cases` barrel 引组件和 composable。
- 新增用例页视图模型优先落到 `testCaseViewModels.ts`。
- 新增组件 emits 优先落到 `testCaseEventModels.ts`。
- `useAppAutomationTestCases.ts` 继续保持 orchestration 角色，不把筛选/批量执行/跳转逻辑重新塞回页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

# Elements Structure

`elements` 目录承接 APP 自动化元素页的页面壳、元素筛选/表格和编辑、详情弹窗。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationElements.ts`
  页面级 orchestration，负责元素加载、筛选、编辑、图片分类、截图建元素和批量删除。

## Shared Models

- `elementViewModels.ts`
  元素编辑表单、分页和组件 props。
- `elementEventModels.ts`
  Header、Editor、Table 这组组件的共享 emits。

## Components

- `ElementsHeaderBar.vue`
  页头、搜索、类型筛选和快捷动作。
- `ElementsTableCard.vue`
  元素表格、批量选择和行内动作。
- `ElementsEditorDialog.vue`
  元素编辑弹窗。
- `ElementsDetailDialog.vue`
  元素详情弹窗。

## Editing Rules

- 页面入口优先从 `./elements` barrel 引组件和 composable。
- 新增元素页视图模型优先落到 `elementViewModels.ts`。
- 新增组件 emits 优先落到 `elementEventModels.ts`。
- `useAppAutomationElements.ts` 继续保持 orchestration 角色，不把编辑/上传/分类逻辑重新塞回页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

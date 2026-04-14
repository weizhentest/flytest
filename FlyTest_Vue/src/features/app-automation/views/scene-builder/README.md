# Scene Builder Structure

`scene-builder` 目录承接 APP 场景编排页的页面壳、工作流编排、子组件和共享类型。
当前目标是把这一层长期维持成“页面入口很薄、逻辑按职责拆分、类型和事件统一收口”的结构。

## Entry

- `index.ts`
  对外统一导出页面入口组件、顶层 orchestration composable 和共享类型。
- `useAppAutomationSceneBuilder.ts`
  顶层 orchestration，负责把页面需要的状态、动作和聚合 props 组装好。
- `sceneBuilderComposables.ts`
  统一导出 `useSceneBuilder*` 逻辑模块，避免入口文件继续增长出一长串散 import。

## UI Layers

- `SceneBuilderTopSection.vue`
  顶部区域聚合层，内部继续拆成 `HeaderBar`、`AiStatusCard`、`DraftFormCard`。
- `SceneBuilderWorkspaceLayout.vue`
  三列工作区聚合层，内部接 `LibraryPanel`、`CanvasPanel`、`ConfigPanel`。
- `SceneBuilderDialogsHost.vue`
  所有 dialog 的宿主层，负责集中接线而不是把多个 dialog 直接堆在页面入口里。

## Config Area

- `SceneBuilderConfigPanel.vue`
  只负责把配置区的 header、quick-config、JSON editor 组合起来。
- `sceneBuilderConfigParts.ts`
  统一导出配置区拆分出来的子组件。
- `SceneBuilder*QuickConfigPanel.vue`
  每个文件只承接一种快捷配置场景，尽量不再混入页面级状态。

## Shared Models

- `sceneBuilderViewModels.ts`
  页面聚合 props、workspace bindings、常用 payload。
- `sceneBuilderDialogModels.ts`
  dialog 表单模型、dialog props。
- `sceneBuilderEventModels.ts`
  聚合组件 emits 约定。
- `sceneBuilderQuickConfigModels.ts`
  quick-config 子组件复用的读写函数签名和选择态。
- `sceneBuilderComposableModels.ts`
  `useSceneBuilder*` 之间共享的函数签名、store 约束和编辑器能力。
- `sceneBuilderQuickOptions.ts`
  quick-config 的下拉选项常量。
- `sceneBuilderDraft.ts`
  步骤、变量、子步骤分组这些纯草稿转换和归一化逻辑。

## Logic Modules

- `useSceneBuilderAiRuntime.ts`
  AI 运行态、配置快照、最近一次 AI 活动。
- `useSceneBuilderAiPlanning.ts`
  AI 场景生成和 AI 步骤补全。
- `useSceneBuilderDraftBridge.ts`
  草稿层 helper，连接 `sceneBuilderDraft.ts` 和页面编排逻辑。
- `useSceneBuilderSceneState.ts`
  当前选中步骤、AI 结果应用、组件过滤等场景状态。
- `useSceneBuilderStepConfig.ts`
  步骤配置编辑器和 quick-config 读写。
- `useSceneBuilderCanvas.ts`
  画布步骤树的新增、复制、删除、子步骤操作。
- `useSceneBuilderWorkflow.ts`
  数据加载、草稿保存、执行、路由 `caseId` 同步。
- `useSceneBuilderComponentPackages.ts`
  组件包导入导出。
- `useSceneBuilderCustomComponents.ts`
  自定义组件保存、编辑、删除。

## Editing Rules

- 页面入口优先只接 `index.ts` 暴露的聚合组件和顶层 composable。
- 新增聚合 props 时，优先放到 `sceneBuilderViewModels.ts` 或 `sceneBuilderDialogModels.ts`，不要在组件里重复声明一份。
- 新增聚合组件 emits 时，优先放到 `sceneBuilderEventModels.ts`。
- 新增 quick-config 子组件时，优先复用 `sceneBuilderQuickConfigModels.ts` 里的读写接口。
- 新增 composable options 里如果出现通用函数签名，优先补到 `sceneBuilderComposableModels.ts`。
- `SceneBuilderConfigPanel.vue`、`SceneBuilderTopSection.vue`、`SceneBuilderWorkspaceLayout.vue`、`SceneBuilderDialogsHost.vue` 应继续保持“聚合层”定位，不再回塞大段业务逻辑。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

## Next Steps

- 如果继续拆分，优先保持“新增逻辑进 composable，新增结构进子组件，新增约定进共享类型文件”这条路径。
- 如果后续要加新功能，先判断它属于 `draft`、`workflow`、`canvas`、`config`、`dialog`、`AI` 里的哪一层，再决定落点，避免重新把职责揉回页面入口。

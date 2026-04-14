# Settings Structure

`settings` 目录承接 APP 自动化设置页的页面壳、环境设置卡、ADB 诊断、运行能力诊断和服务状态卡片。

## Entry

- `index.ts`
  统一导出页面需要的组件、composable 和共享类型。
- `useAppAutomationSettings.ts`
  页面级 orchestration，负责设置加载、保存、ADB 检测和整体诊断刷新。

## Shared Models

- `settingsViewModels.ts`
  设置表单和各张设置卡的 props。
- `settingsEventModels.ts`
  环境设置卡、服务状态卡、运行能力卡的共享 emits。

## Components

- `SettingsServiceHealthCard.vue`
  服务状态、调度器和整体健康概览。
- `SettingsEnvironmentCard.vue`
  环境设置表单与 ADB 自动检测动作。
- `SettingsAdbDiagnosticsCard.vue`
  ADB 诊断结果展示。
- `SettingsRuntimeCard.vue`
  运行能力与依赖状态展示。

## Editing Rules

- 页面入口优先从 `./settings` barrel 引组件和 composable。
- 新增设置页视图模型优先落到 `settingsViewModels.ts`。
- 新增设置卡 emits 优先落到 `settingsEventModels.ts`。
- `useAppAutomationSettings.ts` 继续保持 orchestration 角色，不把诊断/保存逻辑重新塞回页面入口。

## Verification

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

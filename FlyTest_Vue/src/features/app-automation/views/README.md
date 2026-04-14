# App Automation Views

这个目录承接 APP 自动化前端的页面入口和页面级子目录。
当前已经把大多数复杂页面收口为统一结构：

- 页面入口文件保留在本目录，例如：
  - `AppAutomationDashboardView.vue`
  - `AppAutomationSceneBuilderView.vue`
  - `AppAutomationScheduledTasksView.vue`
  - `AppAutomationReportsView.vue`
  - `AppAutomationExecutionsView.vue`
  - `AppAutomationDevicesView.vue`
  - `AppAutomationSuitesView.vue`
  - `AppAutomationTestCasesView.vue`
  - `AppAutomationPackagesView.vue`
  - `AppAutomationNotificationsView.vue`
  - `AppAutomationElementsView.vue`
  - `AppAutomationSettingsView.vue`

- 每个页面对应一个同名职责目录，例如：
  - `dashboard/`
  - `scene-builder/`
  - `scheduled-tasks/`
  - `reports/`
  - `executions/`
  - `devices/`
  - `suites/`
  - `test-cases/`
  - `packages/`
  - `notifications/`
  - `elements/`
  - `settings/`

## Recommended Structure

每个页面子目录尽量维持这套结构：

- `index.ts`
  对外统一导出页面子组件、composable 和共享类型。
- `useAppAutomation*.ts`
  页面级 orchestration，负责数据加载、动作、路由同步和跨组件状态。
- `*ViewModels.ts`
  页面内共享 props / form / filters / stats / payload 这些视图模型。
- `*EventModels.ts`
  页面内共享 emits 定义。
- `README.md`
  说明该目录的职责、入口和改动规则。
- 多个子组件 `.vue`
  按展示职责拆分，而不是把页面重新塞回一个巨型文件。

## Editing Rules

- 页面入口优先只做“页面壳 + 从子目录 barrel 导入”。
- 新增页面级状态优先放到 `useAppAutomation*.ts`，不要回塞到页面入口。
- 新增可复用 props / form / filters / stats 时，优先补到对应目录的 `*ViewModels.ts`。
- 新增共享 emits 时，优先补到对应目录的 `*EventModels.ts`。
- 如果某个页面逻辑已经拆进子目录，就尽量继续沿用同样结构，不再回到散 import + 本地接口重复声明的写法。

## Verification

每轮目录级重构后继续保持这两个校验：

- 前端构建：`npm run build`
- 后端回归：`pytest -q`

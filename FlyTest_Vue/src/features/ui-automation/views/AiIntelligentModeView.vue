<template>
  <div class="ai-mode-view">
    <a-alert class="mode-tip" type="info" show-icon>
      AI 智能模式会优先使用已启用的 LLM 做任务规划；缺少 `browser-use / Playwright` 时会自动回退到规划执行模式。
    </a-alert>
    <div v-if="!projectId" class="empty-state">
      <a-empty description="请先选择项目后再使用 AI 智能模式" />
    </div>
    <template v-else>
      <div class="quick-run-card capability-card">
        <div class="section-heading">
          <div>
            <h3>运行能力总览</h3>
            <p>展示当前 AI 智能模式使用的执行链路、模型能力和默认环境。</p>
          </div>
          <a-button type="outline" size="small" :loading="capabilityLoading" @click="reloadRuntimeCapabilities">
            <template #icon><icon-refresh /></template>
            刷新能力
          </a-button>
        </div>
        <a-spin :loading="capabilityLoading" style="width:100%">
          <template v-if="runtimeCapabilities">
            <div class="capability-grid">
              <div class="summary-card">
                <span class="summary-label">执行后端</span>
                <strong>{{ AI_BACKEND_LABELS[runtimeCapabilities.execution_backend] }}</strong>
                <div class="capability-detail">
                  {{ runtimeCapabilities.execution_backend === 'browser_use' ? '真实浏览器智能执行' : 'AI 规划回退执行' }}
                </div>
              </div>
              <div class="summary-card">
                <span class="summary-label">当前模型</span>
                <strong>{{ runtimeCapabilities.model_config_name || '未配置' }}</strong>
                <div class="capability-detail">
                  {{ runtimeCapabilities.model_provider && runtimeCapabilities.model_name ? `${runtimeCapabilities.model_provider} · ${runtimeCapabilities.model_name}` : '未启用 LLM 配置' }}
                </div>
              </div>
              <div class="summary-card">
                <span class="summary-label">视觉模式</span>
                <strong>{{ runtimeCapabilities.vision_mode_ready ? '可执行' : '暂不可用' }}</strong>
                <div class="capability-detail">
                  {{ runtimeCapabilities.supports_vision ? '当前模型支持图片输入' : '当前模型不支持视觉能力' }}
                </div>
              </div>
              <div class="summary-card">
                <span class="summary-label">默认环境</span>
                <strong>{{ runtimeCapabilities.default_environment?.name || '未配置' }}</strong>
                <div class="capability-detail">
                  {{ runtimeCapabilities.default_environment ? `${runtimeCapabilities.default_environment.browser} · ${runtimeCapabilities.default_environment.headless ? '无头模式' : '有头模式'}` : '建议补齐基础 URL 与浏览器配置' }}
                </div>
              </div>
            </div>
            <a-alert
              v-if="runtimeCapabilityAlert"
              class="status-alert"
              :type="runtimeCapabilityAlert.type"
              show-icon
              :title="runtimeCapabilityAlert.title"
            >
              {{ runtimeCapabilityAlert.content }}
            </a-alert>
            <div v-if="runtimeCapabilities.issues?.length" class="error-list">
              <a-alert
                v-for="(item, index) in runtimeCapabilities.issues"
                :key="`${item}-${index}`"
                type="warning"
                :title="item"
              />
            </div>
            <div v-if="runtimeCapabilities.recommendations?.length" class="recommendation-list">
              <a-alert
                v-for="(item, index) in runtimeCapabilities.recommendations"
                :key="`recommendation-${item}-${index}`"
                type="info"
                :title="item"
              />
            </div>
          </template>
          <a-empty v-else description="暂未读取到 AI 运行能力信息" />
        </a-spin>
      </div>

      <div class="quick-run-layout">
        <div class="quick-run-card">
          <div class="section-heading">
            <div>
              <h3>AI 快速调试</h3>
              <p>直接输入任务并发起智能浏览器自动化，适合临时验证和快速排查。</p>
            </div>
          </div>
          <a-form layout="vertical">
            <a-row :gutter="16">
              <a-col :span="12"><a-form-item label="任务名称"><a-input v-model="adhocForm.case_name" placeholder="不填则自动生成任务名称" /></a-form-item></a-col>
              <a-col :span="12"><a-form-item label="执行模式" required><a-select v-model="adhocForm.execution_mode"><a-option value="text">文本模式</a-option><a-option value="vision" :disabled="visionSelectionDisabled">视觉模式</a-option></a-select></a-form-item></a-col>
            </a-row>
            <a-form-item label="任务描述" required>
              <a-textarea v-model="adhocForm.task_description" placeholder="例如：打开后台登录页，登录后进入 UI 自动化页面，校验 AI 智能模式菜单和执行记录列表可见" :max-length="2000" show-word-limit :auto-size="{ minRows: 6, maxRows: 10 }" />
            </a-form-item>
            <a-form-item label="GIF 录制">
              <div class="switch-row">
                <a-switch v-model="adhocForm.enable_gif" />
                <span class="switch-tip">开启后会尽量生成执行回放 GIF，便于复盘浏览器智能执行过程。</span>
              </div>
            </a-form-item>
            <div class="quick-run-actions">
              <a-button type="primary" :loading="adhocSubmitting" :disabled="!adhocForm.task_description.trim()" @click="submitQuickRun">
                <template #icon><icon-play-arrow /></template>
                开始执行
              </a-button>
              <a-button type="outline" status="warning" :disabled="!liveExecutionRecord || !isRunningStatus(liveExecutionRecord.status)" @click="stopLiveExecution">
                <template #icon><icon-stop /></template>
                停止任务
              </a-button>
              <a-button type="outline" :disabled="!adhocForm.task_description.trim()" @click="saveQuickRunAsCase">
                <template #icon><icon-plus /></template>
                保存为用例
              </a-button>
              <a-button type="outline" @click="openAdhocModal(true)">
                <template #icon><icon-edit /></template>
                弹窗编辑
              </a-button>
            </div>
          </a-form>
          <a-alert type="info" show-icon>
            文本模式基于 DOM 结构和页面上下文规划步骤，视觉模式会强依赖支持图片能力的 LLM 配置。
          </a-alert>
        </div>

        <div class="quick-run-card">
          <div class="section-heading">
            <div>
              <h3>执行观察</h3>
              <p>展示最近一次执行中的任务规划、状态与实时日志。</p>
            </div>
            <a-space v-if="liveExecutionRecord">
              <a-button type="outline" size="small" @click="openLiveExecutionDetail">
                <template #icon><icon-eye /></template>
                详情
              </a-button>
              <a-button type="outline" size="small" @click="openLiveExecutionReport" :disabled="isRunningStatus(liveExecutionRecord.status)">
                <template #icon><icon-file /></template>
                报告
              </a-button>
            </a-space>
          </div>

          <a-spin :loading="liveExecutionLoading" style="width:100%">
            <template v-if="liveExecutionRecord">
              <div class="live-metrics">
                <div class="summary-card">
                  <span class="summary-label">任务名称</span>
                  <strong class="summary-text">{{ liveExecutionRecord.case_name }}</strong>
                </div>
                <div class="summary-card">
                  <span class="summary-label">执行状态</span>
                  <strong><a-tag :color="statusColors[liveExecutionRecord.status]">{{ AI_STATUS_LABELS[liveExecutionRecord.status] }}</a-tag></strong>
                </div>
                <div class="summary-card">
                  <span class="summary-label">执行模式</span>
                  <strong><a-tag :color="modeColors[liveExecutionRecord.execution_mode]">{{ AI_MODE_LABELS[liveExecutionRecord.execution_mode] }}</a-tag></strong>
                </div>
                <div class="summary-card">
                  <span class="summary-label">任务进度</span>
                  <strong>{{ formatProgress(liveExecutionRecord) }}</strong>
                </div>
                <div class="summary-card">
                  <span class="summary-label">GIF 录制</span>
                  <strong>{{ liveExecutionRecord.enable_gif ? '已开启' : '已关闭' }}</strong>
                </div>
              </div>

              <a-alert v-if="liveExecutionAnalyzing" class="live-alert" type="info" show-icon title="AI 正在分析任务与规划步骤，请稍候..." />
              <a-alert
                v-else-if="liveExecutionStatusAlert"
                class="live-alert"
                :type="liveExecutionStatusAlert.type"
                show-icon
                :title="liveExecutionStatusAlert.title"
              >
                {{ liveExecutionStatusAlert.content }}
              </a-alert>
              <a-divider>任务规划</a-divider>
              <div v-if="liveExecutionRecord.planned_tasks?.length" class="item-list live-list">
                <div v-for="task in liveExecutionRecord.planned_tasks" :key="task.id" class="item-card">
                  <div class="item-head"><span class="item-title">{{ task.title }}</span><a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag></div>
                  <div class="item-desc">{{ task.description }}</div>
                  <div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div>
                </div>
              </div>
              <a-empty v-else description="执行开始后会在这里显示任务规划" />

              <a-divider>实时日志</a-divider>
              <pre ref="quickRunLogRef" class="log-panel quick-run-log">{{ liveExecutionRecord.logs || '暂无日志输出' }}</pre>
            </template>
            <a-empty v-else description="发起一次 AI 任务后，这里会显示实时执行过程" />
          </a-spin>
        </div>
      </div>

      <a-tabs v-model:active-key="activeView" lazy-load>
        <a-tab-pane key="cases" title="AI 用例">
          <div class="page-header">
            <div class="search-box">
              <a-input-search v-model="caseFilters.search" placeholder="搜索用例名称或任务描述" allow-clear style="width:280px" @search="reloadCases" @clear="reloadCases" />
              <a-select v-model="caseFilters.default_execution_mode" placeholder="执行模式" allow-clear style="width:140px" @change="reloadCases">
                <a-option value="text">文本模式</a-option>
                <a-option value="vision">视觉模式</a-option>
              </a-select>
              <a-button type="outline" @click="reloadCases"><template #icon><icon-refresh /></template>刷新</a-button>
            </div>
            <div class="action-buttons">
              <a-button type="outline" status="danger" :disabled="selectedCaseIds.length === 0" :loading="caseBatchDeleting" @click="batchDeleteCases">
                <template #icon><icon-delete /></template>
                批量删除
              </a-button>
              <a-button type="outline" @click="openAdhocModal(false)"><template #icon><icon-play-arrow /></template>临时执行</a-button>
              <a-button type="primary" @click="openCaseModal()"><template #icon><icon-plus /></template>新建 AI 用例</a-button>
            </div>
          </div>
          <a-table v-model:selectedKeys="selectedCaseIds" :columns="caseColumns" :data="cases" :loading="caseLoading" :pagination="casePagination" :scroll="{ x: 1080 }" :row-selection="caseRowSelection" row-key="id" @page-change="onCasePageChange" @page-size-change="onCasePageSizeChange">
            <template #default_execution_mode="{ record }"><a-tag :color="modeColors[record.default_execution_mode]">{{ AI_MODE_LABELS[record.default_execution_mode] }}</a-tag></template>
            <template #enable_gif="{ record }"><a-tag :color="gifSwitchTagColor(record.enable_gif)">{{ gifSwitchLabel(record.enable_gif) }}</a-tag></template>
            <template #updated_at="{ record }">{{ formatTime(record.updated_at) }}</template>
            <template #operations="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="fillQuickRunFromCase(record)">调试</a-button>
                <a-button type="text" size="mini" @click="runCase(record)"><template #icon><icon-play-arrow /></template>运行</a-button>
                <a-button type="text" size="mini" @click="openCaseModal(record)"><template #icon><icon-edit /></template>编辑</a-button>
                <a-popconfirm content="确定删除该 AI 用例？" @ok="deleteCase(record.id)"><a-button type="text" size="mini" status="danger"><template #icon><icon-delete /></template>删除</a-button></a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="records" title="AI 执行记录">
          <div class="page-header">
            <div class="search-box">
              <a-input-search v-model="recordFilters.search" placeholder="搜索任务名称或任务描述" allow-clear style="width:240px" @search="reloadRecords" @clear="reloadRecords" />
              <a-select v-model="recordFilters.status" placeholder="执行状态" allow-clear style="width:140px" @change="reloadRecords">
                <a-option v-for="(label, key) in AI_STATUS_LABELS" :key="key" :value="key">{{ label }}</a-option>
              </a-select>
              <a-select v-model="recordFilters.execution_mode" placeholder="执行模式" allow-clear style="width:140px" @change="reloadRecords">
                <a-option v-for="(label, key) in AI_MODE_LABELS" :key="key" :value="key">{{ label }}</a-option>
              </a-select>
              <a-select v-model="recordFilters.execution_backend" placeholder="执行后端" allow-clear style="width:150px" @change="reloadRecords">
                <a-option v-for="(label, key) in AI_BACKEND_LABELS" :key="key" :value="key">{{ label }}</a-option>
              </a-select>
              <a-button type="outline" @click="reloadRecords"><template #icon><icon-refresh /></template>刷新</a-button>
            </div>
            <div class="action-buttons">
              <a-button type="outline" status="warning" :disabled="selectedRunnableRecordIds.length === 0" :loading="batchStopping" @click="batchStopRecords">
                <template #icon><icon-stop /></template>
                批量停止
              </a-button>
              <a-button type="outline" status="danger" :disabled="selectedRecordIds.length === 0" :loading="batchDeleting" @click="batchDeleteRecords">
                <template #icon><icon-delete /></template>
                批量删除
              </a-button>
            </div>
          </div>
          <a-table v-model:selectedKeys="selectedRecordIds" :columns="recordColumns" :data="records" :loading="recordLoading" :pagination="recordPagination" :scroll="{ x: 1600 }" :row-selection="recordRowSelection" row-key="id" @page-change="onRecordPageChange" @page-size-change="onRecordPageSizeChange">
            <template #execution_mode="{ record }"><a-tag :color="modeColors[record.execution_mode]">{{ AI_MODE_LABELS[record.execution_mode] }}</a-tag></template>
            <template #execution_backend="{ record }"><a-tag :color="backendColors[record.execution_backend]">{{ AI_BACKEND_LABELS[record.execution_backend] }}</a-tag></template>
            <template #status="{ record }"><a-tag :color="statusColors[record.status]">{{ AI_STATUS_LABELS[record.status] }}</a-tag></template>
            <template #progress="{ record }">{{ formatProgress(record) }}</template>
            <template #gif_status="{ record }"><a-tag :color="gifResultColor(record)">{{ gifResultLabel(record) }}</a-tag></template>
            <template #error_message="{ record }"><span :class="{ 'error-text': !!record.error_message }">{{ record.error_message || '-' }}</span></template>
            <template #start_time="{ record }">{{ formatTime(record.start_time) }}</template>
            <template #operations="{ record }">
              <a-space :size="4">
                <a-button type="text" size="mini" @click="fillQuickRunFromRecord(record)">复用</a-button>
                <a-button type="text" size="mini" @click="viewRecord(record.id)"><template #icon><icon-eye /></template>详情</a-button>
                <a-button type="text" size="mini" @click="openReport(record.id)"><template #icon><icon-file /></template>报告</a-button>
                <a-button v-if="isRunningStatus(record.status)" type="text" size="mini" status="warning" @click="stopRecord(record.id)"><template #icon><icon-stop /></template>停止</a-button>
                <a-popconfirm content="确定删除该执行记录？" @ok="deleteRecord(record.id)"><a-button type="text" size="mini" status="danger"><template #icon><icon-delete /></template>删除</a-button></a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </template>

    <a-modal v-model:visible="caseModalVisible" :title="caseModalTitle" :confirm-loading="caseSubmitting" width="720px" @ok="submitCase">
      <a-form layout="vertical">
        <a-form-item label="用例名称" required><a-input v-model="caseForm.name" placeholder="例如：登录后台并校验首页核心概览卡片" /></a-form-item>
        <a-row :gutter="16">
          <a-col :span="12"><a-form-item label="默认执行模式" required><a-select v-model="caseForm.default_execution_mode"><a-option value="text">文本模式</a-option><a-option value="vision">视觉模式</a-option></a-select></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="所属项目"><a-input :model-value="projectStore.currentProject?.name || ''" disabled /></a-form-item></a-col>
        </a-row>
        <a-alert
          v-if="caseForm.default_execution_mode === 'vision' && runtimeCapabilities && !runtimeCapabilities.vision_mode_ready"
          class="status-alert"
          type="warning"
          show-icon
        >
          当前运行能力暂不支持视觉模式，但仍可保存该 AI 用例，后续切换到支持视觉的模型后可继续执行。
        </a-alert>
        <a-form-item label="描述"><a-textarea v-model="caseForm.description" placeholder="补充业务背景、前置条件或断言重点" :auto-size="{ minRows: 2, maxRows: 4 }" /></a-form-item>
        <a-form-item label="任务描述" required><a-textarea v-model="caseForm.task_description" placeholder="请用自然语言描述想让 AI 完成的 UI 自动化任务" :auto-size="{ minRows: 5, maxRows: 9 }" /></a-form-item>
        <a-form-item label="GIF 录制">
          <div class="switch-row">
            <a-switch v-model="caseForm.enable_gif" />
            <span class="switch-tip">保存为 AI 用例后，默认按这个设置决定是否生成执行回放 GIF。</span>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:visible="adhocModalVisible" title="临时执行 AI 任务" :confirm-loading="adhocSubmitting" width="720px" @ok="submitAdhoc">
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12"><a-form-item label="任务名称"><a-input v-model="adhocForm.case_name" placeholder="不填则自动生成" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="执行模式" required><a-select v-model="adhocForm.execution_mode"><a-option value="text">文本模式</a-option><a-option value="vision" :disabled="visionSelectionDisabled">视觉模式</a-option></a-select></a-form-item></a-col>
        </a-row>
        <a-form-item label="任务描述" required><a-textarea v-model="adhocForm.task_description" placeholder="直接输入要执行的 AI 自动化任务" :auto-size="{ minRows: 6, maxRows: 10 }" /></a-form-item>
        <a-form-item label="GIF 录制">
          <div class="switch-row">
            <a-switch v-model="adhocForm.enable_gif" />
            <span class="switch-tip">关闭后不会生成执行回放 GIF，可减少浏览器运行时的额外开销。</span>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:visible="recordDrawerVisible" title="AI 执行详情" width="820px" unmount-on-close>
      <a-spin :loading="recordDetailLoading" style="width:100%">
        <template v-if="currentRecord">
          <div class="drawer-actions">
            <a-space>
              <a-button type="outline" size="small" @click="openReport(currentRecord.id)"><template #icon><icon-file /></template>查看报告</a-button>
              <a-button v-if="isRunningStatus(currentRecord.status)" type="outline" size="small" status="warning" @click="stopRecord(currentRecord.id)"><template #icon><icon-stop /></template>停止任务</a-button>
            </a-space>
          </div>
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="任务名称">{{ currentRecord.case_name }}</a-descriptions-item>
            <a-descriptions-item label="执行人">{{ currentRecord.executed_by_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行模式"><a-tag :color="modeColors[currentRecord.execution_mode]">{{ AI_MODE_LABELS[currentRecord.execution_mode] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="执行后端"><a-tag :color="backendColors[currentRecord.execution_backend]">{{ AI_BACKEND_LABELS[currentRecord.execution_backend] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="执行状态"><a-tag :color="statusColors[currentRecord.status]">{{ AI_STATUS_LABELS[currentRecord.status] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="模型配置">{{ currentRecord.model_config_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="GIF 录制">{{ currentRecord.enable_gif ? '已开启' : '已关闭' }}</a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ formatTime(currentRecord.start_time) }}</a-descriptions-item>
            <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行时长">{{ currentRecord.duration != null ? `${currentRecord.duration.toFixed(2)}s` : '-' }}</a-descriptions-item>
            <a-descriptions-item label="任务进度">{{ formatProgress(currentRecord) }}</a-descriptions-item>
          </a-descriptions>
          <a-alert
            v-if="currentRecordStatusAlert"
            class="status-alert"
            :type="currentRecordStatusAlert.type"
            show-icon
            :title="currentRecordStatusAlert.title"
          >
            {{ currentRecordStatusAlert.content }}
          </a-alert>
          <a-divider>任务描述</a-divider>
          <div class="block-card">{{ currentRecord.task_description }}</div>
          <template v-if="currentRecord.error_message"><a-divider>错误信息</a-divider><a-alert type="error" :title="currentRecord.error_message" /></template>
          <template v-if="currentRecord.planned_tasks?.length"><a-divider>规划任务</a-divider><div class="item-list"><div v-for="task in currentRecord.planned_tasks" :key="task.id" class="item-card"><div class="item-head"><span class="item-title">{{ task.title }}</span><a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag></div><div class="item-desc">{{ task.description }}</div><div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div></div></div></template>
          <template v-if="currentRecord.steps_completed?.length">
            <a-divider>已完成步骤</a-divider>
            <div class="item-list">
              <div v-for="step in currentRecord.steps_completed" :key="`${step.step}-${step.completed_at}`" class="item-card">
                <div class="item-head">
                  <span class="item-title">步骤 {{ step.step }} · {{ step.title }}</span>
                  <a-tag :color="stepStatusColor(step.status)">{{ stepStatusLabel(step.status) }}</a-tag>
                </div>
                <div class="item-desc">{{ step.description || '-' }}</div>
                <div v-if="step.expected_result" class="item-meta"><strong>预期结果：</strong>{{ step.expected_result }}</div>
                <div v-if="step.message" class="item-meta"><strong>执行信息：</strong>{{ step.message }}</div>
                <div v-if="step.browser_step_count" class="item-meta"><strong>浏览器步骤：</strong>{{ step.browser_step_count }}</div>
                <div class="item-meta"><strong>耗时：</strong>{{ formatDuration(step.duration) }}<span v-if="step.completed_at"> · {{ formatTime(step.completed_at) }}</span></div>
                <div v-if="step.screenshots?.length" class="step-media">
                  <a-image-preview-group>
                    <div class="media-grid">
                      <a-image
                        v-for="(item, index) in step.screenshots"
                        :key="`${step.step}-${item}-${index}`"
                        :src="resolveMediaUrl(item)"
                        width="168"
                        height="108"
                        fit="cover"
                      />
                    </div>
                  </a-image-preview-group>
                </div>
              </div>
            </div>
          </template>
          <template v-if="currentRecord.screenshots_sequence?.length"><a-divider>执行截图</a-divider><a-image-preview-group><div class="media-grid"><a-image v-for="(item, index) in currentRecord.screenshots_sequence" :key="`${item}-${index}`" :src="resolveMediaUrl(item)" width="168" height="108" fit="cover" /></div></a-image-preview-group></template>
          <template v-if="currentRecord.gif_path"><a-divider>执行回放</a-divider><div class="gif-preview"><img :src="resolveMediaUrl(currentRecord.gif_path)" alt="AI execution replay" /></div></template>
          <template v-if="currentRecord.logs"><a-divider>执行日志</a-divider><pre class="log-panel">{{ currentRecord.logs }}</pre></template>
        </template>
      </a-spin>
    </a-drawer>

    <a-modal v-model:visible="reportVisible" title="AI 执行报告" width="920px" :footer="false" unmount-on-close>
      <a-spin :loading="reportLoading" style="width:100%">
        <template v-if="currentReport">
          <div class="report-toolbar">
            <a-radio-group v-model="currentReportType" type="button" size="small" @change="handleReportTypeChange">
              <a-radio v-for="option in reportTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
            </a-radio-group>
            <a-space>
              <a-button type="outline" size="small" :loading="exportingReport" @click="exportReportPdf"><template #icon><icon-file /></template>导出 PDF</a-button>
              <a-button type="outline" size="small" @click="reloadCurrentReport"><template #icon><icon-refresh /></template>刷新报告</a-button>
            </a-space>
          </div>
          <div class="report-summary">
            <div class="summary-card" v-for="item in reportStats" :key="item.label"><span class="summary-label">{{ item.label }}</span><strong>{{ item.value }}</strong></div>
          </div>
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="任务名称">{{ currentReport.case_name }}</a-descriptions-item>
            <a-descriptions-item label="执行状态"><a-tag :color="statusColors[currentReport.status]">{{ AI_STATUS_LABELS[currentReport.status] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="执行模式"><a-tag :color="modeColors[currentReport.execution_mode]">{{ AI_MODE_LABELS[currentReport.execution_mode] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="执行后端"><a-tag :color="backendColors[currentReport.execution_backend]">{{ AI_BACKEND_LABELS[currentReport.execution_backend] }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="模型配置">{{ currentReport.model_config_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行时长">{{ formatDuration(currentReport.duration) }}</a-descriptions-item>
          </a-descriptions>
          <a-alert
            v-if="reportStatusAlert"
            class="status-alert"
            :type="reportStatusAlert.type"
            show-icon
            :title="reportStatusAlert.title"
          >
            {{ reportStatusAlert.content }}
          </a-alert>
          <a-divider>任务描述</a-divider>
          <div class="block-card">{{ currentReport.task_description }}</div>
          <template v-if="currentReportType === 'summary'">
            <template v-if="overviewCards.length">
              <a-divider>执行概览</a-divider>
              <div class="metric-grid">
                <div v-for="item in overviewCards" :key="item.label" class="metric-card"><span class="summary-label">{{ item.label }}</span><strong>{{ item.value }}</strong></div>
              </div>
            </template>
            <template v-if="currentReport.timeline?.length">
              <a-divider>任务时间线</a-divider>
              <div class="timeline-list">
                <div v-for="item in currentReport.timeline" :key="item.id" class="timeline-card">
                  <div class="item-head"><span class="item-title">{{ item.title }}</span><a-tag :color="taskStatusColor(item.status)">{{ item.status_display }}</a-tag></div>
                  <div class="item-desc">{{ item.description || '-' }}</div>
                  <div v-if="item.expected_result" class="item-meta">预期结果：{{ item.expected_result }}</div>
                </div>
              </div>
            </template>
            <template v-if="currentReport.planned_tasks?.length">
              <a-divider>规划任务</a-divider>
              <div class="item-list">
                <div v-for="task in currentReport.planned_tasks" :key="task.id" class="item-card">
                  <div class="item-head"><span class="item-title">{{ task.title }}</span><a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag></div>
                  <div class="item-desc">{{ task.description }}</div>
                  <div v-if="task.expected_result" class="item-meta">预期结果：{{ task.expected_result }}</div>
                </div>
              </div>
            </template>
            <template v-if="reportActionDistribution.length">
              <a-divider>动作分布</a-divider>
              <div class="distribution-list">
                <div v-for="item in reportActionDistribution" :key="item.action" class="distribution-item">
                  <span class="distribution-label">{{ item.action }}</span>
                  <div class="distribution-bar"><div class="distribution-bar__fill" :style="{ width: `${distributionWidth(item.count)}%` }" /></div>
                  <strong class="distribution-count">{{ item.count }}</strong>
                </div>
              </div>
            </template>
            <template v-if="currentReport.error_message"><a-divider>错误信息</a-divider><a-alert type="error" :title="currentReport.error_message" /></template>
          </template>
          <template v-else-if="currentReportType === 'detailed'">
            <template v-if="reportErrors.length">
              <a-divider>错误信息</a-divider>
              <div class="error-list">
                <a-alert v-for="(item, index) in reportErrors" :key="`${item.message}-${index}`" :title="item.step_number ? `步骤 ${item.step_number}：${item.message}` : item.message" type="error" />
              </div>
            </template>
            <a-divider>步骤明细</a-divider>
            <div v-if="detailedSteps.length" class="item-list">
              <div v-for="step in detailedSteps" :key="step.step_number" class="item-card">
                <div class="item-head"><span class="item-title">步骤 {{ step.step_number }} · {{ step.title }}</span><a-tag :color="stepStatusColor(step.status)">{{ stepStatusLabel(step.status) }}</a-tag></div>
                <div class="item-desc"><strong>动作：</strong>{{ step.action || '-' }}</div>
                <div class="item-meta"><strong>描述：</strong>{{ step.description || '-' }}</div>
                <div v-if="step.expected_result" class="item-meta"><strong>预期结果：</strong>{{ step.expected_result }}</div>
                <div v-if="step.element" class="item-meta"><strong>元素：</strong>{{ step.element }}</div>
                <div v-if="step.thinking" class="item-meta"><strong>AI 思考：</strong>{{ step.thinking }}</div>
                <div v-if="step.message" class="item-meta"><strong>执行信息：</strong>{{ step.message }}</div>
                <div v-if="step.browser_step_count" class="item-meta"><strong>浏览器步骤：</strong>{{ step.browser_step_count }}</div>
                <div class="item-meta"><strong>耗时：</strong>{{ formatDuration(step.duration) }}<span v-if="step.completed_at"> · {{ formatTime(step.completed_at) }}</span></div>
                <div v-if="step.screenshots?.length" class="step-media">
                  <a-image-preview-group>
                    <div class="media-grid">
                      <a-image
                        v-for="(item, index) in step.screenshots"
                        :key="`${step.step_number}-${item}-${index}`"
                        :src="resolveMediaUrl(item)"
                        width="168"
                        height="108"
                        fit="cover"
                      />
                    </div>
                  </a-image-preview-group>
                </div>
              </div>
            </div>
            <a-empty v-else description="暂无步骤明细" />
          </template>
          <template v-else>
            <template v-if="performanceCards.length">
              <a-divider>性能指标</a-divider>
              <div class="metric-grid">
                <div v-for="item in performanceCards" :key="item.label" class="metric-card"><span class="summary-label">{{ item.label }}</span><strong>{{ item.value }}</strong></div>
              </div>
            </template>
            <template v-if="reportActionDistribution.length">
              <a-divider>动作分布</a-divider>
              <div class="distribution-list">
                <div v-for="item in reportActionDistribution" :key="item.action" class="distribution-item">
                  <span class="distribution-label">{{ item.action }}</span>
                  <div class="distribution-bar"><div class="distribution-bar__fill" :style="{ width: `${distributionWidth(item.count)}%` }" /></div>
                  <strong class="distribution-count">{{ item.count }}</strong>
                </div>
              </div>
            </template>
            <template v-if="currentReport.bottlenecks?.length">
              <a-divider>性能瓶颈</a-divider>
              <div class="item-list">
                <div v-for="item in currentReport.bottlenecks" :key="`${item.step_number}-${item.action}`" class="item-card">
                  <div class="item-head"><span class="item-title">步骤 {{ item.step_number }} · {{ item.action }}</span><a-tag color="orange">{{ item.duration.toFixed(2) }}s</a-tag></div>
                  <div class="item-meta">高于平均耗时 {{ item.slower_than_avg_by.toFixed(2) }}%</div>
                </div>
              </div>
            </template>
            <template v-if="currentReport.recommendations?.length">
              <a-divider>优化建议</a-divider>
              <div class="error-list">
                <a-alert v-for="(item, index) in currentReport.recommendations" :key="`${item}-${index}`" :title="item" type="info" />
              </div>
            </template>
          </template>
          <template v-if="currentReport.screenshots_sequence?.length"><a-divider>执行截图</a-divider><a-image-preview-group><div class="media-grid"><a-image v-for="(item, index) in currentReport.screenshots_sequence" :key="`${item}-${index}`" :src="resolveMediaUrl(item)" width="168" height="108" fit="cover" /></div></a-image-preview-group></template>
          <template v-if="currentReport.gif_path"><a-divider>执行回放</a-divider><div class="gif-preview"><img :src="resolveMediaUrl(currentReport.gif_path)" alt="AI execution replay" /></div></template>
          <template v-if="currentReport.logs"><a-divider>执行日志</a-divider><pre class="log-panel">{{ currentReport.logs }}</pre></template>
        </template>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onUnmounted, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconDelete, IconEdit, IconEye, IconFile, IconPlayArrow, IconPlus, IconRefresh, IconStop } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { aiCaseApi, aiExecutionApi } from '../api'
import type {
  UiAICase,
  UiAICaseForm,
  UiAIAdhocRunForm,
  UiAIExecutionBackend,
  UiAIRuntimeCapabilities,
  UiAITaskPlan,
  UiAIExecutionMode,
  UiAIExecutionRecord,
  UiAIExecutionReport,
  UiAIExecutionStatus,
  UiAIReportDetailedStep,
  UiAIReportType,
} from '../types'
import { AI_BACKEND_LABELS, AI_MODE_LABELS, AI_STATUS_LABELS, extractPaginationData, extractResponseData } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const activeView = ref<'cases' | 'records'>('cases')
const caseLoading = ref(false)
const caseBatchDeleting = ref(false)
const caseSubmitting = ref(false)
const cases = ref<UiAICase[]>([])
const selectedCaseIds = ref<number[]>([])
const casePagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })
const caseFilters = reactive({ search: '', default_execution_mode: undefined as UiAIExecutionMode | undefined })
const caseModalVisible = ref(false)
const editingCaseId = ref<number | null>(null)
const caseModalPurpose = ref<'create' | 'edit' | 'quick-run'>('create')
const caseForm = reactive<UiAICaseForm>({ project: 0, name: '', description: '', task_description: '', default_execution_mode: 'text', enable_gif: true })
const capabilityLoading = ref(false)
const runtimeCapabilities = ref<UiAIRuntimeCapabilities | null>(null)
const adhocModalVisible = ref(false)
const adhocSubmitting = ref(false)
const adhocForm = reactive<UiAIAdhocRunForm>({ project: 0, case_name: '', task_description: '', execution_mode: 'text', enable_gif: true })
const liveExecutionLoading = ref(false)
const liveExecutionRecordId = ref<number | null>(null)
const liveExecutionRecord = ref<UiAIExecutionRecord | null>(null)
const quickRunLogRef = ref<HTMLElement | null>(null)
const recordLoading = ref(false)
const batchStopping = ref(false)
const batchDeleting = ref(false)
const records = ref<UiAIExecutionRecord[]>([])
const selectedRecordIds = ref<number[]>([])
const recordPagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })
const recordFilters = reactive({ search: '', status: undefined as UiAIExecutionStatus | undefined, execution_mode: undefined as UiAIExecutionMode | undefined, execution_backend: undefined as UiAIExecutionBackend | undefined })
const recordDrawerVisible = ref(false)
const recordDetailLoading = ref(false)
const currentRecord = ref<UiAIExecutionRecord | null>(null)
const reportVisible = ref(false)
const reportLoading = ref(false)
const exportingReport = ref(false)
const currentReport = ref<UiAIExecutionReport | null>(null)
const currentReportId = ref<number | null>(null)
const currentReportType = ref<UiAIReportType>('summary')
let pollingTimer: number | null = null
const quickRunTrackedRecordIds = new Set<number>()
const quickRunNotifiedRecordIds = new Set<number>()

const modeColors: Record<UiAIExecutionMode, string> = { text: 'arcoblue', vision: 'purple' }
const statusColors: Record<UiAIExecutionStatus, string> = { pending: 'gray', running: 'arcoblue', passed: 'green', failed: 'red', stopped: 'orange' }
const backendColors: Record<UiAIExecutionBackend, string> = { planning: 'cyan', browser_use: 'purple' }
const caseRowSelection = { type: 'checkbox' as const, showCheckedAll: true }
const recordRowSelection = { type: 'checkbox' as const, showCheckedAll: true }
const reportTypeOptions: Array<{ label: string; value: UiAIReportType }> = [
  { label: '摘要报告', value: 'summary' },
  { label: '详细步骤', value: 'detailed' },
  { label: '性能分析', value: 'performance' },
]
const caseModalTitle = computed(() => {
  if (editingCaseId.value) return '编辑 AI 用例'
  if (caseModalPurpose.value === 'quick-run') return '保存为 AI 用例'
  return '新建 AI 用例'
})
const caseColumns = [
  { title: 'ID', dataIndex: 'id', width: 80, align: 'center' as const },
  { title: '用例名称', dataIndex: 'name', width: 180, ellipsis: true, tooltip: true },
  { title: '默认执行模式', slotName: 'default_execution_mode', width: 130, align: 'center' as const },
  { title: 'GIF 默认', slotName: 'enable_gif', width: 110, align: 'center' as const },
  { title: '任务描述', dataIndex: 'task_description', ellipsis: true, tooltip: true },
  { title: '更新人', dataIndex: 'creator_name', width: 110, align: 'center' as const },
  { title: '更新时间', slotName: 'updated_at', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 230, fixed: 'right' as const, align: 'center' as const },
]
const recordColumns = [
  { title: 'ID', dataIndex: 'id', width: 80, align: 'center' as const },
  { title: '任务名称', dataIndex: 'case_name', width: 180, ellipsis: true, tooltip: true },
  { title: '执行模式', slotName: 'execution_mode', width: 110, align: 'center' as const },
  { title: '执行后端', slotName: 'execution_backend', width: 120, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '进度', slotName: 'progress', width: 90, align: 'center' as const },
  { title: 'GIF 状态', slotName: 'gif_status', width: 110, align: 'center' as const },
  { title: '模型配置', dataIndex: 'model_config_name', width: 160, ellipsis: true, tooltip: true },
  { title: '错误信息', slotName: 'error_message', width: 220, ellipsis: true, tooltip: true },
  { title: '开始时间', slotName: 'start_time', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 290, fixed: 'right' as const, align: 'center' as const },
]

const isRunningStatus = (status: UiAIExecutionStatus) => status === 'running' || status === 'pending'
const hasRunningRecords = computed(() =>
  (currentRecord.value ? isRunningStatus(currentRecord.value.status) : false)
  || (liveExecutionRecord.value ? isRunningStatus(liveExecutionRecord.value.status) : false)
  || records.value.some(record => isRunningStatus(record.status))
)
const liveExecutionAnalyzing = computed(() =>
  !!liveExecutionRecord.value
  && isRunningStatus(liveExecutionRecord.value.status)
  && !(liveExecutionRecord.value.planned_tasks?.length)
)
type ExecutionStatusAlert = {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  content: string
}
type ExecutionStatusSource = Pick<
  UiAIExecutionRecord,
  'status' | 'execution_backend' | 'error_message' | 'planned_task_count' | 'completed_task_count' | 'planned_tasks' | 'steps_completed'
>
const visionSelectionDisabled = computed(() =>
  !!runtimeCapabilities.value && !runtimeCapabilities.value.vision_mode_ready,
)
const selectedRunnableRecordIds = computed(() => {
  const selectedIdSet = new Set(selectedRecordIds.value)
  return records.value.filter(record => selectedIdSet.has(record.id) && isRunningStatus(record.status)).map(record => record.id)
})
const reportStats = computed(() => currentReport.value ? [
  { label: '规划任务', value: currentReport.value.planned_task_count },
  { label: '完成任务', value: currentReport.value.completed_task_count },
  { label: '失败任务', value: currentReport.value.failed_task_count },
  { label: '步骤总数', value: currentReport.value.step_count },
  { label: '通过步骤', value: currentReport.value.passed_step_count },
  { label: '失败步骤', value: currentReport.value.failed_step_count },
] : [])
const overviewCards = computed(() => {
  const overview = currentReport.value?.overview
  if (!overview || !currentReport.value) return []
  return [
    { label: '执行状态', value: currentReport.value.status_display || AI_STATUS_LABELS[currentReport.value.status] },
    { label: '完成率', value: `${overview.completion_rate}%` },
    { label: '平均步耗时', value: `${overview.avg_step_time.toFixed(2)}s` },
    { label: '动作数', value: overview.total_actions },
  ]
})
const performanceCards = computed(() => {
  const metrics = currentReport.value?.metrics
  if (!metrics) return []
  return [
    { label: '平均步骤耗时', value: `${metrics.avg_step_duration.toFixed(2)}s` },
    { label: '最大步骤耗时', value: `${metrics.max_step_duration.toFixed(2)}s` },
    { label: '最小步骤耗时', value: `${metrics.min_step_duration.toFixed(2)}s` },
    { label: '步骤通过率', value: `${metrics.pass_rate}%` },
  ]
})
const reportActionDistribution = computed(() => currentReport.value?.action_distribution || [])
const reportErrors = computed(() => {
  if (currentReport.value?.errors?.length) return currentReport.value.errors
  if (currentReport.value?.error_message) return [{ type: 'error' as const, message: currentReport.value.error_message }]
  return []
})
const detailedSteps = computed<UiAIReportDetailedStep[]>(() => {
  if (currentReport.value?.detailed_steps?.length) return currentReport.value.detailed_steps
  if (!currentReport.value?.steps_completed?.length) return []
  return currentReport.value.steps_completed.map(step => ({
    step_number: step.step,
    title: step.title,
    status: step.status,
    action: step.title,
    description: step.description,
    expected_result: step.expected_result,
    message: step.message,
    completed_at: step.completed_at,
    duration: step.duration,
    browser_step_count: step.browser_step_count,
    screenshots: step.screenshots,
  }))
})

type UiAIRuntimeFailureResponse = {
  error?: string
  message?: string
  errors?: {
    error?: string
    runtime_capabilities?: UiAIRuntimeCapabilities
  }
  response?: {
    data?: {
      error?: string
      message?: string
      errors?: {
        error?: string
        runtime_capabilities?: UiAIRuntimeCapabilities
      }
    }
  }
}

const extractRuntimeFailurePayload = (error: unknown) => {
  const normalized = error as UiAIRuntimeFailureResponse
  const payload = normalized?.response?.data
  const nestedErrors = payload?.errors

  return {
    message: nestedErrors?.error || payload?.error || payload?.message || normalized?.error || normalized?.message || '',
    capabilities: nestedErrors?.runtime_capabilities || null,
  }
}

const extractErrorMessage = (error: unknown, fallback: string) => {
  const runtimeFailure = extractRuntimeFailurePayload(error)
  return runtimeFailure.message || fallback
}

const buildRuntimeCapabilityGuideLines = (message: string, capabilities: UiAIRuntimeCapabilities) => {
  const lines: string[] = [message]

  if (capabilities.summary) {
    lines.push('', capabilities.summary)
  }

  if (capabilities.issues?.length) {
    lines.push('', '当前问题：')
    capabilities.issues.forEach((item, index) => {
      lines.push(`${index + 1}. ${item}`)
    })
  }

  if (capabilities.recommendations?.length) {
    lines.push('', '建议处理：')
    capabilities.recommendations.forEach((item, index) => {
      lines.push(`${index + 1}. ${item}`)
    })
  }

  if (capabilities.default_environment?.name) {
    lines.push('', `默认环境：${capabilities.default_environment.name}`)
  }

  if (capabilities.model_config_name) {
    lines.push(`当前模型：${capabilities.model_config_name}`)
  }

  return lines
}

const showRuntimeCapabilityGuide = (
  sourceLabel: string,
  message: string,
  capabilities: UiAIRuntimeCapabilities,
) => {
  runtimeCapabilities.value = capabilities
  const lines = buildRuntimeCapabilityGuideLines(message, capabilities)

  Modal.warning({
    title: `${sourceLabel}暂时无法执行`,
    okText: '知道了',
    hideCancel: true,
    content: () => h('div', { style: 'white-space: pre-wrap; line-height: 1.75; font-size: 13px;' }, lines.join('\n')),
  })
}

const handleExecutionFailure = (error: unknown, fallback: string, sourceLabel: string) => {
  const runtimeFailure = extractRuntimeFailurePayload(error)
  if (runtimeFailure.capabilities) {
    showRuntimeCapabilityGuide(sourceLabel, runtimeFailure.message || fallback, runtimeFailure.capabilities)
    return
  }

  Message.error(runtimeFailure.message || fallback)
}
const resetCaseForm = () => Object.assign(caseForm, { project: projectId.value || 0, name: '', description: '', task_description: '', default_execution_mode: 'text', enable_gif: true })
const resetAdhocForm = () => Object.assign(adhocForm, { project: projectId.value || 0, case_name: '', task_description: '', execution_mode: 'text', enable_gif: true })
const isFinishedStatus = (status: UiAIExecutionStatus) => status === 'passed' || status === 'failed' || status === 'stopped'
const gifSwitchLabel = (enabled: boolean) => enabled ? '已开启' : '已关闭'
const gifSwitchTagColor = (enabled: boolean) => enabled ? 'green' : 'gray'
const gifResultLabel = (record: Pick<UiAIExecutionRecord, 'enable_gif' | 'gif_path' | 'status'>) => {
  if (!record.enable_gif) return '已关闭'
  if (record.gif_path) return '已生成'
  if (isRunningStatus(record.status)) return '生成中'
  return '未生成'
}
const gifResultColor = (record: Pick<UiAIExecutionRecord, 'enable_gif' | 'gif_path' | 'status'>) => {
  if (!record.enable_gif) return 'gray'
  if (record.gif_path) return 'green'
  if (isRunningStatus(record.status)) return 'arcoblue'
  return 'orange'
}
const summarizeTaskStates = (plannedTasks?: UiAITaskPlan[] | null) => {
  const summary = { total: 0, completed: 0, failed: 0, skipped: 0, stopped: 0, pending: 0, running: 0 }
  for (const task of plannedTasks || []) {
    summary.total += 1
    if (task.status === 'completed') summary.completed += 1
    else if (task.status === 'failed') summary.failed += 1
    else if (task.status === 'skipped') summary.skipped += 1
    else if (task.status === 'stopped') summary.stopped += 1
    else if (task.status === 'running' || task.status === 'in_progress') summary.running += 1
    else summary.pending += 1
  }
  return summary
}
const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
const formatDuration = (value?: number) => (value != null ? `${value.toFixed(2)}s` : '-')
const formatProgress = (record: Pick<UiAIExecutionRecord, 'planned_task_count' | 'completed_task_count' | 'planned_tasks' | 'steps_completed'>) => {
  const completed = record.completed_task_count ?? record.steps_completed?.length ?? 0
  const total = record.planned_task_count ?? record.planned_tasks?.length ?? 0
  if (!total) return completed ? `${completed}/${completed}` : '待规划'
  return `${completed}/${total}`
}
const taskStatusLabel = (status: string) => ({ pending: '待执行', running: '执行中', completed: '已完成', failed: '失败', stopped: '已停止', in_progress: '执行中', skipped: '已跳过' }[status] || status)
const taskStatusColor = (status: string) => ({ pending: 'gray', running: 'arcoblue', completed: 'green', failed: 'red', stopped: 'orange', in_progress: 'arcoblue', skipped: 'gray' }[status] || 'gray')
const stepStatusLabel = (status: string) => ({ passed: '成功', failed: '失败', stopped: '已停止', running: '执行中', pending: '待执行' }[status] || status)
const stepStatusColor = (status: string) => ({ passed: 'green', failed: 'red', stopped: 'orange', running: 'arcoblue', pending: 'gray' }[status] || 'gray')
const resolveMediaUrl = (value?: string) => !value ? '' : value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:') ? value : value.startsWith('/') ? value : value.startsWith('media/') ? `/${value}` : `/media/${value}`
const buildExecutionStatusAlert = (record?: ExecutionStatusSource | null): ExecutionStatusAlert | null => {
  if (!record) return null
  const backendLabel = AI_BACKEND_LABELS[record.execution_backend] || record.execution_backend
  const taskSummary = summarizeTaskStates(record.planned_tasks)
  const summaryParts = [`任务进度 ${formatProgress(record)}`]
  if (taskSummary.failed) summaryParts.push(`失败 ${taskSummary.failed} 项`)
  if (taskSummary.skipped) summaryParts.push(`跳过 ${taskSummary.skipped} 项`)
  if (taskSummary.stopped) summaryParts.push(`停止 ${taskSummary.stopped} 项`)
  if (taskSummary.running || taskSummary.pending) summaryParts.push(`待完成 ${taskSummary.running + taskSummary.pending} 项`)
  const summaryText = `${summaryParts.join('，')}。执行后端：${backendLabel}。`

  if (record.status === 'pending') {
    return { type: 'info', title: '任务已创建，等待开始执行', content: summaryText }
  }
  if (record.status === 'running') {
    return { type: 'info', title: 'AI 智能任务执行中', content: summaryText }
  }
  if (record.status === 'passed') {
    return { type: 'success', title: 'AI 智能任务执行完成', content: summaryText }
  }
  if (record.status === 'stopped') {
    return { type: 'warning', title: 'AI 智能任务已停止', content: `${summaryText}未完成任务已被标记为停止或跳过。` }
  }
  return {
    type: 'error',
    title: 'AI 智能任务执行失败',
    content: record.error_message ? `${record.error_message}。${summaryText}` : summaryText,
  }
}
const liveExecutionStatusAlert = computed(() => liveExecutionAnalyzing.value ? null : buildExecutionStatusAlert(liveExecutionRecord.value))
const currentRecordStatusAlert = computed(() => buildExecutionStatusAlert(currentRecord.value))
const reportStatusAlert = computed(() => {
  if (!currentReport.value) return null
  return buildExecutionStatusAlert({
    status: currentReport.value.status,
    execution_backend: currentReport.value.execution_backend,
    error_message: currentReport.value.error_message,
    planned_task_count: currentReport.value.planned_task_count,
    completed_task_count: currentReport.value.completed_task_count,
    planned_tasks: currentReport.value.planned_tasks,
    steps_completed: currentReport.value.steps_completed,
  })
})
const runtimeCapabilityAlert = computed<ExecutionStatusAlert | null>(() => {
  if (!runtimeCapabilities.value) return null
  if (runtimeCapabilities.value.execution_backend === 'browser_use' && runtimeCapabilities.value.llm_configured) {
    return {
      type: runtimeCapabilities.value.browser_executable_found ? 'success' : 'warning',
      title: runtimeCapabilities.value.browser_executable_found ? '真实浏览器链路已就绪' : '浏览器链路尚未完整就绪',
      content: runtimeCapabilities.value.summary,
    }
  }
  if (!runtimeCapabilities.value.llm_configured) {
    return {
      type: 'warning',
      title: '当前缺少激活模型配置',
      content: runtimeCapabilities.value.summary,
    }
  }
  return {
    type: 'info',
    title: '当前将使用规划回退模式',
    content: runtimeCapabilities.value.summary,
  }
})
const adjustPaginationAfterDelete = (
  pagination: { current: number },
  currentItemCount: number,
  deletedCount: number,
) => {
  if (pagination.current > 1 && currentItemCount <= deletedCount) {
    pagination.current -= 1
  }
}
const distributionWidth = (count: number) => {
  const counts = reportActionDistribution.value.map(item => item.count)
  const max = counts.length ? Math.max(...counts) : 1
  return Math.max(18, Math.round((count / max) * 100))
}
const ensureExecutionModeReady = (executionMode: UiAIExecutionMode, sourceLabel: string) => {
  const capabilities = runtimeCapabilities.value
  if (!capabilities) return true

  if (executionMode === 'vision' && !capabilities.vision_mode_ready) {
    showRuntimeCapabilityGuide(sourceLabel, '当前不能使用视觉模式，请先补齐视觉模式所需的模型与浏览器执行能力。', capabilities)
    return false
  }

  if (executionMode === 'text' && !capabilities.text_mode_ready) {
    showRuntimeCapabilityGuide(sourceLabel, '当前缺少可用的文本模式执行能力，请先检查模型配置和浏览器运行链路。', capabilities)
    return false
  }

  return true
}
const scrollQuickRunLogToBottom = () => {
  void nextTick(() => {
    if (!quickRunLogRef.value) return
    quickRunLogRef.value.scrollTop = quickRunLogRef.value.scrollHeight
  })
}
const notifyQuickRunCompletion = (record: UiAIExecutionRecord) => {
  if (!quickRunTrackedRecordIds.has(record.id) || quickRunNotifiedRecordIds.has(record.id) || !isFinishedStatus(record.status)) return
  quickRunTrackedRecordIds.delete(record.id)
  quickRunNotifiedRecordIds.add(record.id)
  if (record.status === 'passed') {
    Message.success('AI 快速调试任务已执行完成')
    return
  }
  if (record.status === 'stopped') {
    Message.warning('AI 快速调试任务已停止')
    return
  }
  Message.error(record.error_message ? `AI 快速调试任务执行失败：${record.error_message}` : 'AI 快速调试任务执行失败')
}
const closePanelsForIds = (ids: number[]) => {
  if (currentRecord.value?.id && ids.includes(currentRecord.value.id)) { recordDrawerVisible.value = false; currentRecord.value = null }
  if (currentReportId.value && ids.includes(currentReportId.value)) {
    reportVisible.value = false
    currentReport.value = null
    currentReportId.value = null
    currentReportType.value = 'summary'
  }
  if (liveExecutionRecord.value?.id && ids.includes(liveExecutionRecord.value.id)) {
    liveExecutionRecord.value = null
    liveExecutionRecordId.value = null
  }
  ids.forEach(id => {
    quickRunTrackedRecordIds.delete(id)
    quickRunNotifiedRecordIds.delete(id)
  })
}
const closeCaseModalForIds = (ids: number[]) => {
  if (editingCaseId.value && ids.includes(editingCaseId.value)) {
    caseModalVisible.value = false
    editingCaseId.value = null
    caseModalPurpose.value = 'create'
    resetCaseForm()
  }
}

const fetchRuntimeCapabilities = async (showLoading = true) => {
  if (!projectId.value) return
  if (showLoading) capabilityLoading.value = true
  try {
    const response = await aiExecutionApi.capabilities(projectId.value)
    const capabilities = extractResponseData<UiAIRuntimeCapabilities>(response)
    if (capabilities) runtimeCapabilities.value = capabilities
  } catch (error: unknown) {
    if (showLoading) Message.error(extractErrorMessage(error, '获取 AI 运行能力失败'))
  } finally {
    if (showLoading) capabilityLoading.value = false
  }
}

const fetchCases = async (showLoading = true) => {
  if (!projectId.value) return
  if (showLoading) caseLoading.value = true
  try {
    const response = await aiCaseApi.list({ project: projectId.value, default_execution_mode: caseFilters.default_execution_mode, search: caseFilters.search || undefined, page_number: casePagination.current, page_size: casePagination.pageSize })
    const { items, count } = extractPaginationData(response)
    cases.value = items
    casePagination.total = count
    const availableIds = new Set(items.map(item => item.id))
    selectedCaseIds.value = selectedCaseIds.value.filter(id => availableIds.has(id))
  } catch { Message.error('获取 AI 用例失败') } finally { if (showLoading) caseLoading.value = false }
}
const fetchRecords = async (showLoading = true) => {
  if (!projectId.value) return
  if (showLoading) recordLoading.value = true
  try {
    const response = await aiExecutionApi.list({ project: projectId.value, status: recordFilters.status, execution_mode: recordFilters.execution_mode, execution_backend: recordFilters.execution_backend, search: recordFilters.search || undefined, page_number: recordPagination.current, page_size: recordPagination.pageSize })
    const { items, count } = extractPaginationData(response)
    records.value = items
    recordPagination.total = count
    const availableIds = new Set(items.map(item => item.id))
    selectedRecordIds.value = selectedRecordIds.value.filter(id => availableIds.has(id))
    const fallbackRunningRecord = items.find(item => isRunningStatus(item.status))
    if (liveExecutionRecordId.value && availableIds.has(liveExecutionRecordId.value)) {
      if (!liveExecutionRecord.value || liveExecutionRecord.value.id !== liveExecutionRecordId.value) {
        await loadLiveExecutionRecord(liveExecutionRecordId.value, false)
      }
    } else if (fallbackRunningRecord) {
      liveExecutionRecordId.value = fallbackRunningRecord.id
      await loadLiveExecutionRecord(fallbackRunningRecord.id, false)
    } else if (liveExecutionRecord.value && !isRunningStatus(liveExecutionRecord.value.status)) {
      liveExecutionRecordId.value = liveExecutionRecord.value.id
    }
  } catch { Message.error('获取 AI 执行记录失败') } finally { if (showLoading) recordLoading.value = false }
}
const loadLiveExecutionRecord = async (id: number, showLoading = true) => {
  if (showLoading) liveExecutionLoading.value = true
  try {
    const detail = extractResponseData<UiAIExecutionRecord>(await aiExecutionApi.get(id))
    if (detail) {
      liveExecutionRecord.value = detail
      liveExecutionRecordId.value = detail.id
    }
  } catch { if (showLoading) Message.error('获取实时执行详情失败') } finally { if (showLoading) liveExecutionLoading.value = false }
}
const loadRecordDetail = async (id: number, showLoading = true) => {
  if (showLoading) recordDetailLoading.value = true
  try {
    const detail = extractResponseData<UiAIExecutionRecord>(await aiExecutionApi.get(id))
    if (detail) currentRecord.value = detail
  } catch { Message.error('获取执行详情失败') } finally { if (showLoading) recordDetailLoading.value = false }
}
const loadReport = async (id: number, showLoading = true, reportType: UiAIReportType = currentReportType.value) => {
  if (showLoading) reportLoading.value = true
  try {
    const report = extractResponseData<UiAIExecutionReport>(await aiExecutionApi.report(id, reportType))
    if (report) currentReport.value = report
  } catch (error: unknown) { Message.error(extractErrorMessage(error, '获取执行报告失败')) } finally { if (showLoading) reportLoading.value = false }
}

const reloadCases = () => { casePagination.current = 1; void fetchCases() }
const reloadRecords = () => { recordPagination.current = 1; void fetchRecords() }
const reloadRuntimeCapabilities = () => { void fetchRuntimeCapabilities() }
const reloadCurrentReport = async () => { if (currentReportId.value) await loadReport(currentReportId.value, true, currentReportType.value) }
const scrollToQuickRun = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const fillQuickRunFromCase = (record: UiAICase) => {
  Object.assign(adhocForm, {
    project: projectId.value || 0,
    case_name: record.name,
    task_description: record.task_description,
    execution_mode: record.default_execution_mode,
    enable_gif: record.enable_gif,
  })
  scrollToQuickRun()
  Message.success('已将 AI 用例填充到快速调试面板')
}
const fillQuickRunFromRecord = (record: UiAIExecutionRecord) => {
  Object.assign(adhocForm, {
    project: projectId.value || 0,
    case_name: record.case_name,
    task_description: record.task_description,
    execution_mode: record.execution_mode,
    enable_gif: record.enable_gif ?? true,
  })
  scrollToQuickRun()
  Message.success('已将执行任务填充到快速调试面板')
}
const openLiveExecutionDetail = async () => { if (liveExecutionRecordId.value) { recordDrawerVisible.value = true; await loadRecordDetail(liveExecutionRecordId.value) } }
const openLiveExecutionReport = async () => { if (liveExecutionRecordId.value) await openReport(liveExecutionRecordId.value) }
const onCasePageChange = (page: number) => { casePagination.current = page; void fetchCases() }
const onCasePageSizeChange = (size: number) => { casePagination.pageSize = size; casePagination.current = 1; void fetchCases() }
const onRecordPageChange = (page: number) => { recordPagination.current = page; void fetchRecords() }
const onRecordPageSizeChange = (size: number) => { recordPagination.pageSize = size; recordPagination.current = 1; void fetchRecords() }
const openCaseModal = (record?: UiAICase) => {
  caseModalPurpose.value = record ? 'edit' : 'create'
  if (record) Object.assign(caseForm, { project: record.project, name: record.name, description: record.description || '', task_description: record.task_description, default_execution_mode: record.default_execution_mode, enable_gif: record.enable_gif })
  else resetCaseForm()
  editingCaseId.value = record?.id ?? null
  caseModalVisible.value = true
}
const submitCase = async () => {
  if (!projectId.value) return Message.warning('请先选择项目'), false
  if (!caseForm.name.trim()) return Message.warning('请输入用例名称'), false
  if (!caseForm.task_description.trim()) return Message.warning('请输入任务描述'), false
  caseSubmitting.value = true
  caseForm.project = projectId.value
  const savingFromQuickRun = caseModalPurpose.value === 'quick-run'
  try {
    if (editingCaseId.value) { await aiCaseApi.update(editingCaseId.value, { ...caseForm }); Message.success('AI 用例已更新') }
    else { await aiCaseApi.create({ ...caseForm }); Message.success(savingFromQuickRun ? '已保存为 AI 用例' : 'AI 用例已创建') }
    caseModalVisible.value = false
    caseModalPurpose.value = 'create'
    if (savingFromQuickRun) activeView.value = 'cases'
    await fetchCases()
    return true
  } catch { Message.error(editingCaseId.value ? '更新 AI 用例失败' : '创建 AI 用例失败'); return false } finally { caseSubmitting.value = false }
}
const deleteCase = async (id: number) => {
  try {
    await aiCaseApi.delete(id)
    closeCaseModalForIds([id])
    selectedCaseIds.value = selectedCaseIds.value.filter(item => item !== id)
    adjustPaginationAfterDelete(casePagination, cases.value.length, 1)
    Message.success('AI 用例已删除')
    await fetchCases()
  } catch (error: unknown) { Message.error(extractErrorMessage(error, '删除 AI 用例失败')) }
}
const batchDeleteCases = () => {
  if (!selectedCaseIds.value.length) return
  const ids = [...selectedCaseIds.value]
  Modal.confirm({
    title: '批量删除 AI 用例',
    content: `已选择 ${ids.length} 条 AI 用例，确认继续删除吗？`,
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      caseBatchDeleting.value = true
      try {
        const result = extractResponseData<{ deleted_count?: number }>(await aiCaseApi.batchDelete(ids))
        closeCaseModalForIds(ids)
        selectedCaseIds.value = []
        adjustPaginationAfterDelete(casePagination, cases.value.length, result?.deleted_count ?? ids.length)
        Message.success(`已删除 ${result?.deleted_count ?? ids.length} 条 AI 用例`)
        await fetchCases()
      } catch (error: unknown) { Message.error(extractErrorMessage(error, '批量删除 AI 用例失败')) } finally { caseBatchDeleting.value = false }
    },
  })
}
const buildQuickRunCaseName = () => {
  const trimmedName = adhocForm.case_name.trim()
  if (trimmedName) return trimmedName
  const trimmedTask = adhocForm.task_description.trim()
  return trimmedTask.length > 24 ? `${trimmedTask.slice(0, 24)}...` : trimmedTask
}
const saveQuickRunAsCase = async () => {
  if (!projectId.value) return Message.warning('请先选择项目')
  if (!adhocForm.task_description.trim()) return Message.warning('请输入任务描述')
  caseModalPurpose.value = 'quick-run'
  editingCaseId.value = null
  Object.assign(caseForm, {
    project: projectId.value,
    name: buildQuickRunCaseName() || 'AI 快速调试任务',
    description: '由 AI 快速调试面板保存',
    task_description: adhocForm.task_description.trim(),
    default_execution_mode: adhocForm.execution_mode,
    enable_gif: adhocForm.enable_gif,
  })
  caseModalVisible.value = true
}
const runCase = async (record: UiAICase) => {
  try {
    if (!ensureExecutionModeReady(record.default_execution_mode, '该 AI 用例')) return
    const created = extractResponseData<UiAIExecutionRecord>(await aiCaseApi.run(record.id, record.default_execution_mode))
    if (created?.id) {
      liveExecutionRecordId.value = created.id
      liveExecutionRecord.value = created
      await loadLiveExecutionRecord(created.id, false)
    }
    activeView.value = 'records'
    await fetchRecords()
    if (created?.id) { await loadRecordDetail(created.id); recordDrawerVisible.value = true }
    Message.success('AI 用例已开始执行')
  } catch (error: unknown) { handleExecutionFailure(error, '运行 AI 用例失败', 'AI 用例') }
}
const openAdhocModal = (preserveCurrentInput = false) => {
  if (!preserveCurrentInput) resetAdhocForm()
  adhocModalVisible.value = true
}
const executeAdhocRun = async (options?: { closeModal?: boolean; openDrawer?: boolean; switchToRecords?: boolean; successMessage?: string; trackQuickRunCompletion?: boolean }) => {
  if (!projectId.value) return false
  if (!ensureExecutionModeReady(adhocForm.execution_mode, '当前 AI 任务')) return false
  adhocForm.project = projectId.value
  const created = extractResponseData<UiAIExecutionRecord>(await aiExecutionApi.runAdhoc({ ...adhocForm }))
  if (created?.id) {
    if (options?.trackQuickRunCompletion) {
      quickRunTrackedRecordIds.add(created.id)
      quickRunNotifiedRecordIds.delete(created.id)
    }
    liveExecutionRecordId.value = created.id
    liveExecutionRecord.value = created
    await loadLiveExecutionRecord(created.id, false)
  }
  if (options?.closeModal !== false) adhocModalVisible.value = false
  if (options?.switchToRecords !== false) activeView.value = 'records'
  await fetchRecords()
  if (created?.id && options?.openDrawer) { await loadRecordDetail(created.id); recordDrawerVisible.value = true }
  Message.success(options?.successMessage || '临时 AI 任务已开始执行')
  return true
}
const submitAdhoc = async () => {
  if (!projectId.value) return Message.warning('请先选择项目'), false
  if (!adhocForm.task_description.trim()) return Message.warning('请输入任务描述'), false
  adhocSubmitting.value = true
  try {
    return await executeAdhocRun({ closeModal: true, openDrawer: true, switchToRecords: true, successMessage: '临时 AI 任务已开始执行' })
  } catch (error: unknown) { handleExecutionFailure(error, '临时 AI 任务执行失败', '临时 AI 任务'); return false } finally { adhocSubmitting.value = false }
}
const submitQuickRun = async () => {
  if (!projectId.value) return Message.warning('请先选择项目')
  if (!adhocForm.task_description.trim()) return Message.warning('请输入任务描述')
  adhocSubmitting.value = true
  try {
    await executeAdhocRun({ closeModal: false, openDrawer: false, switchToRecords: false, successMessage: 'AI 快速调试任务已开始执行', trackQuickRunCompletion: true })
  } catch (error: unknown) { handleExecutionFailure(error, 'AI 快速调试任务执行失败', 'AI 快速调试任务') } finally { adhocSubmitting.value = false }
}
const viewRecord = async (id: number) => { recordDrawerVisible.value = true; await loadRecordDetail(id) }
const openReport = async (id: number) => {
  currentReportId.value = id
  currentReportType.value = 'summary'
  reportVisible.value = true
  await loadReport(id, true, 'summary')
}
const handleReportTypeChange = async (value: string | number | boolean) => {
  if (!currentReportId.value) return
  currentReportType.value = String(value) as UiAIReportType
  await loadReport(currentReportId.value, true, currentReportType.value)
}
const exportReportPdf = async () => {
  if (!currentReportId.value) return
  exportingReport.value = true
  try {
    const response = await aiExecutionApi.exportPdf(currentReportId.value, currentReportType.value)
    const blob = response.data
    if (!(blob instanceof Blob)) throw new Error('服务器返回的不是有效 PDF 文件')

    const contentDisposition = response.headers['content-disposition']
    let filename = `FlyTest_AI_Report_${currentReportType.value}.pdf`
    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
      const normalMatch = contentDisposition.match(/filename="?([^\";]+)"?/i)
      if (utf8Match?.[1]) filename = decodeURIComponent(utf8Match[1])
      else if (normalMatch?.[1]) filename = normalMatch[1]
    }

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('PDF 报告已开始下载')
  } catch (error: any) {
    let errorMessage = extractErrorMessage(error, '导出 PDF 失败')
    const errorBlob = error?.response?.data
    if (errorBlob instanceof Blob) {
      try {
        const text = await errorBlob.text()
        const payload = JSON.parse(text)
        errorMessage = payload?.error || payload?.message || errorMessage
      } catch {
        // ignore blob parse errors and keep fallback message
      }
    }
    Message.error(errorMessage)
  } finally {
    exportingReport.value = false
  }
}
const stopRecord = async (id: number) => {
  try {
    await aiExecutionApi.stop(id)
    Message.success('已发送停止信号')
    await Promise.all([
      fetchRecords(false),
      currentRecord.value?.id === id ? loadRecordDetail(id, false) : Promise.resolve(),
      currentReportId.value === id ? loadReport(id, false, currentReportType.value) : Promise.resolve(),
      liveExecutionRecordId.value === id ? loadLiveExecutionRecord(id, false) : Promise.resolve(),
    ])
  } catch (error: unknown) { Message.error(extractErrorMessage(error, '停止任务失败')) }
}
const stopLiveExecution = async () => {
  if (!liveExecutionRecordId.value) return
  await stopRecord(liveExecutionRecordId.value)
}
const batchStopRecords = () => {
  if (!selectedRunnableRecordIds.value.length) return
  const ids = [...selectedRunnableRecordIds.value]
  Modal.confirm({
    title: '批量停止 AI 执行任务',
    content: `已选择 ${ids.length} 条运行中的执行记录，确认发送停止信号吗？`,
    okButtonProps: { status: 'warning' },
    onOk: async () => {
      batchStopping.value = true
      try {
        const result = extractResponseData<{ stopped_count?: number; skipped_records?: Array<{ id: number }> }>(await aiExecutionApi.batchStop(ids))
        const currentRecordId = currentRecord.value?.id
        const currentOpenReportId = currentReportId.value
        const currentLiveRecordId = liveExecutionRecordId.value
        Message.success(`已停止 ${result?.stopped_count ?? ids.length} 条执行记录`)
        await Promise.all([
          fetchRecords(),
          currentRecordId && ids.includes(currentRecordId) ? loadRecordDetail(currentRecordId, false) : Promise.resolve(),
          currentOpenReportId && ids.includes(currentOpenReportId) ? loadReport(currentOpenReportId, false, currentReportType.value) : Promise.resolve(),
          currentLiveRecordId && ids.includes(currentLiveRecordId) ? loadLiveExecutionRecord(currentLiveRecordId, false) : Promise.resolve(),
        ])
      } catch (error: unknown) { Message.error(extractErrorMessage(error, '批量停止执行记录失败')) } finally { batchStopping.value = false }
    },
  })
}
const deleteRecord = async (id: number) => {
  try {
    await aiExecutionApi.delete(id)
    closePanelsForIds([id])
    selectedRecordIds.value = selectedRecordIds.value.filter(item => item !== id)
    adjustPaginationAfterDelete(recordPagination, records.value.length, 1)
    Message.success('执行记录已删除')
    await fetchRecords()
  } catch (error: unknown) { Message.error(extractErrorMessage(error, '删除执行记录失败')) }
}
const batchDeleteRecords = () => {
  if (!selectedRecordIds.value.length) return
  const ids = [...selectedRecordIds.value]
  Modal.confirm({
    title: '批量删除 AI 执行记录',
    content: `已选择 ${ids.length} 条执行记录。执行中的任务需要先停止，确认继续删除吗？`,
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      batchDeleting.value = true
      try {
        const result = extractResponseData<{ deleted_count?: number }>(await aiExecutionApi.batchDelete(ids))
        closePanelsForIds(ids)
        selectedRecordIds.value = []
        adjustPaginationAfterDelete(recordPagination, records.value.length, result?.deleted_count ?? ids.length)
        Message.success(`已删除 ${result?.deleted_count ?? ids.length} 条执行记录`)
        await fetchRecords()
      } catch (error: unknown) { Message.error(extractErrorMessage(error, '批量删除执行记录失败')) } finally { batchDeleting.value = false }
    },
  })
}
const startPolling = () => {
  if (pollingTimer != null) return
  pollingTimer = window.setInterval(() => {
    void fetchRecords(false)
    if (liveExecutionRecordId.value) void loadLiveExecutionRecord(liveExecutionRecordId.value, false)
    if (recordDrawerVisible.value && currentRecord.value?.id) void loadRecordDetail(currentRecord.value.id, false)
    if (reportVisible.value && currentReportId.value) void loadReport(currentReportId.value, false, currentReportType.value)
  }, 2500)
}
const stopPolling = () => { if (pollingTimer != null) { window.clearInterval(pollingTimer); pollingTimer = null } }
const refresh = () => { void Promise.all([fetchCases(), fetchRecords()]) }
defineExpose({ refresh })

watch(projectId, newValue => {
  quickRunTrackedRecordIds.clear(); quickRunNotifiedRecordIds.clear(); caseModalPurpose.value = 'create'; resetCaseForm(); resetAdhocForm(); cases.value = []; records.value = []; selectedCaseIds.value = []; selectedRecordIds.value = []; currentRecord.value = null; currentReport.value = null; currentReportId.value = null; currentReportType.value = 'summary'; liveExecutionRecord.value = null; liveExecutionRecordId.value = null; runtimeCapabilities.value = null
  if (newValue) { casePagination.current = 1; recordPagination.current = 1; void Promise.all([fetchRuntimeCapabilities(), fetchCases(), fetchRecords()]) }
}, { immediate: true })
watch(hasRunningRecords, value => value ? startPolling() : stopPolling(), { immediate: true })
watch(() => runtimeCapabilities.value?.vision_mode_ready, value => {
  if (value === false && adhocForm.execution_mode === 'vision') {
    adhocForm.execution_mode = 'text'
  }
})
watch(caseModalVisible, visible => {
  if (!visible) {
    editingCaseId.value = null
    caseModalPurpose.value = 'create'
  }
})
watch(() => liveExecutionRecord.value?.logs, (value, previousValue) => {
  if (value !== previousValue) scrollQuickRunLogToBottom()
})
watch(
  [
    () => liveExecutionRecord.value?.id,
    () => liveExecutionRecord.value?.status,
    () => liveExecutionRecord.value?.error_message,
  ],
  ([id, status]) => {
    if (!id || !status || !liveExecutionRecord.value) return
    notifyQuickRunCompletion(liveExecutionRecord.value)
  },
)
watch(recordDrawerVisible, visible => { if (!visible) currentRecord.value = null })
watch(reportVisible, visible => { if (!visible) { currentReport.value = null; currentReportId.value = null; currentReportType.value = 'summary' } })
onUnmounted(() => stopPolling())
</script>

<style scoped>
.ai-mode-view { padding: 16px; background: var(--color-bg-2); border-radius: 8px; }
.capability-card { margin-bottom: 16px; }
.capability-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.capability-detail { margin-top: 8px; color: var(--color-text-3); font-size: 12px; line-height: 1.6; word-break: break-word; }
.quick-run-layout { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr); gap: 16px; margin-bottom: 16px; }
.quick-run-card { padding: 18px; border-radius: 12px; background: var(--color-bg-1); border: 1px solid var(--color-border-2); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.section-heading h3 { margin: 0; font-size: 16px; color: var(--color-text-1); }
.section-heading p { margin: 6px 0 0; color: var(--color-text-3); font-size: 13px; line-height: 1.6; }
.switch-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.switch-tip { color: var(--color-text-3); font-size: 12px; line-height: 1.6; }
.quick-run-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.live-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 8px; }
.live-alert { margin-bottom: 16px; }
.status-alert { margin: 16px 0; }
.summary-text { display: block; margin-top: 6px; color: var(--color-text-1); font-size: 14px; line-height: 1.5; word-break: break-word; }
.live-list { max-height: 280px; overflow: auto; padding-right: 4px; }
.quick-run-log { min-height: 220px; max-height: 360px; }
.mode-tip, .drawer-actions, .report-toolbar { margin-bottom: 16px; }
.empty-state { min-height: 320px; display: flex; align-items: center; justify-content: center; }
.page-header { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.search-box, .action-buttons, .report-toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.report-toolbar { justify-content: space-between; }
.block-card, .summary-card, .metric-card { padding: 12px 14px; border-radius: 8px; background: var(--color-fill-2); }
.item-list, .timeline-list, .error-list, .distribution-list, .recommendation-list { display: flex; flex-direction: column; gap: 12px; }
.item-card, .timeline-card { padding: 14px; border-radius: 10px; background: var(--color-bg-2); border: 1px solid var(--color-border-2); }
.item-head { display: flex; justify-content: space-between; gap: 12px; }
.item-title { font-weight: 600; color: var(--color-text-1); }
.item-desc, .block-card { color: var(--color-text-1); line-height: 1.6; white-space: pre-wrap; }
.item-meta, .summary-label { margin-top: 8px; color: var(--color-text-3); font-size: 12px; }
.error-text { color: rgb(var(--danger-6)); }
.media-grid, .report-summary, .metric-grid { display: grid; gap: 12px; }
.media-grid { grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); }
.report-summary, .metric-grid { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); margin-bottom: 16px; }
.summary-card strong, .metric-card strong { display: block; margin-top: 6px; font-size: 22px; color: var(--color-text-1); }
.distribution-item { display: grid; grid-template-columns: 72px 1fr 40px; align-items: center; gap: 12px; }
.distribution-label, .distribution-count { color: var(--color-text-1); }
.distribution-bar { height: 8px; border-radius: 999px; background: var(--color-fill-2); overflow: hidden; }
.distribution-bar__fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #165dff, #36cfc9); }
.step-media { margin-top: 12px; }
.gif-preview { overflow: hidden; border-radius: 10px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.gif-preview img { display: block; width: 100%; max-height: 360px; object-fit: contain; }
.log-panel { margin: 0; padding: 14px; border-radius: 8px; background: var(--color-fill-2); color: var(--color-text-1); font-size: 12px; line-height: 1.6; max-height: 280px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1080px) { .quick-run-layout { grid-template-columns: 1fr; } }
@media (max-width: 768px) { .page-header, .report-toolbar, .section-heading { flex-direction: column; align-items: stretch; } .search-box, .action-buttons, .quick-run-actions { width: 100%; } .distribution-item { grid-template-columns: 1fr; } }
</style>

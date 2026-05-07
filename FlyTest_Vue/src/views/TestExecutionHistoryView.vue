<template>
  <div class="test-report-view">
    <div v-if="!currentProjectId" class="empty-state">
      <a-empty description="请先选择项目" />
    </div>

    <div v-else class="report-layout">
      <section class="report-sidebar">
        <div class="sidebar-header">
          <div>
            <div class="sidebar-title">测试报告</div>
            <div class="sidebar-subtitle">
              选择一个或多个根套件、子套件，基于测试用例、BUG 与执行记录生成当前迭代测试报告。
            </div>
          </div>
          <a-button size="small" @click="fetchSuites">刷新</a-button>
        </div>

        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索套件名称"
          allow-clear
          @search="fetchSuites"
          @clear="fetchSuites"
        />

        <div class="sidebar-toolbar">
          <a-space>
            <a-button size="mini" @click="checkAllSuites">全选</a-button>
            <a-button size="mini" @click="clearCheckedSuites">清空</a-button>
            <a-button size="mini" @click="expandAllSuites">展开</a-button>
          </a-space>
          <span class="checked-summary">已选 {{ checkedSuiteIds.length }} 个</span>
        </div>

        <div class="suite-tree-panel">
          <a-spin :loading="suiteLoading" style="width: 100%">
            <a-tree
              v-if="treeData.length > 0"
              checkable
              block-node
              show-line
              :data="treeData"
              :field-names="{ key: 'id', title: 'name' }"
              v-model:checked-keys="checkedKeys"
              v-model:expanded-keys="expandedKeys"
            >
              <template #title="nodeData">
                <div class="suite-node">
                  <span class="suite-node-name">{{ nodeData.name }}</span>
                  <span class="suite-node-count">{{ nodeData.testcase_count || 0 }}</span>
                </div>
              </template>
            </a-tree>
            <a-empty v-else description="暂无套件数据" />
          </a-spin>
        </div>

        <div class="sidebar-actions">
          <a-button
            type="primary"
            long
            :loading="reportLoading"
            :disabled="checkedSuiteIds.length === 0"
            @click="handleGenerateReport"
          >
            {{ currentGenerateButtonText }}
          </a-button>
          <div class="sidebar-note">
            生成时会带入所选套件及其子套件下的测试用例、BUG 列表和执行状态数据。
          </div>
        </div>

        <div v-if="latestGenerationRecord" class="generation-record-panel">
          <div class="generation-record-header">
            <span class="generation-record-title">最近一次生成</span>
            <a-tag
              size="small"
              :color="
                latestGenerationRecord.source === 'fallback'
                  ? 'orange'
                  : latestGenerationRecord.source === 'ai'
                    ? 'arcoblue'
                    : 'gold'
              "
            >
              {{ latestGenerationRecord.sourceLabel }}
            </a-tag>
          </div>
          <div class="generation-record-time">{{ latestGenerationRecord.generatedAtText }}</div>
          <div class="generation-record-grid">
            <div class="generation-record-item">
              <span class="generation-record-label">生成状态</span>
              <span class="generation-record-value">{{ latestGenerationRecord.statusText }}</span>
            </div>
            <div class="generation-record-item">
              <span class="generation-record-label">生成耗时</span>
              <span class="generation-record-value">{{ latestGenerationRecord.durationText }}</span>
            </div>
            <div class="generation-record-item">
              <span class="generation-record-label">选择套件</span>
              <span class="generation-record-value">{{ latestGenerationRecord.selectedSuiteCount }} 个</span>
            </div>
            <div class="generation-record-item">
              <span class="generation-record-label">覆盖套件</span>
              <span class="generation-record-value">{{ latestGenerationRecord.suiteCount }} 个</span>
            </div>
          </div>
          <div class="generation-record-note">{{ latestGenerationRecord.note }}</div>
        </div>

        <div v-if="snapshotCompareItems.length > 0" class="generation-record-panel compare-panel">
          <div class="generation-record-header">
            <span class="generation-record-title">快照变化</span>
            <div class="compare-panel-actions">
              <span class="compare-panel-note">当前报告 vs {{ compareSnapshotDescription }}</span>
              <a-select
                v-model="selectedCompareSnapshotId"
                size="small"
                class="compare-target-select"
              >
                <a-option value="auto">自动选择上一版</a-option>
                <a-option v-for="item in compareSnapshotOptions" :key="item.id" :value="item.id">
                  {{ item.title }}
                </a-option>
              </a-select>
            </div>
          </div>
          <div class="compare-list">
            <div v-for="item in snapshotCompareItems" :key="item.label" class="compare-item">
              <div class="compare-item-top">
                <span class="compare-item-label">{{ item.label }}</span>
                <span
                  class="compare-item-delta"
                  :class="{
                    up: item.trend === 'up',
                    down: item.trend === 'down',
                    flat: item.trend === 'flat',
                    positive: item.impact === 'positive',
                    negative: item.impact === 'negative',
                    neutral: item.impact === 'neutral',
                  }"
                >
                  {{ item.delta }}
                </span>
              </div>
              <div class="compare-item-values">
                <span>当前 {{ item.current }}</span>
                <span>对比 {{ item.previous }}</span>
              </div>
              <div class="compare-item-judgement">{{ item.judgement }}</div>
            </div>
          </div>
        </div>

        <div class="snapshot-panel">
          <div class="snapshot-header">
            <span class="snapshot-title">报告快照</span>
            <a-space>
              <a-button size="mini" :disabled="!reportData" @click="handleSaveSnapshot">保存</a-button>
              <a-button size="mini" @click="loadReportSnapshots">刷新</a-button>
              <a-button
                size="mini"
                status="danger"
                :disabled="reportSnapshots.length === 0"
                @click="clearReportSnapshots"
              >
                清空
              </a-button>
            </a-space>
          </div>

          <a-input-search
            v-model="snapshotKeyword"
            class="snapshot-search"
            placeholder="搜索快照标题或创建人"
            allow-clear
          />

          <a-radio-group
            v-model="snapshotSourceFilter"
            type="button"
            size="small"
            class="snapshot-filter-group"
          >
            <a-radio value="all">全部</a-radio>
            <a-radio value="ai">AI</a-radio>
            <a-radio value="fallback">回退</a-radio>
            <a-radio value="rule">规则</a-radio>
            <a-radio value="pinned">置顶</a-radio>
          </a-radio-group>

          <div class="snapshot-summary">
            <span>共 {{ reportSnapshots.length }} 条</span>
            <span v-if="snapshotKeyword.trim() || snapshotSourceFilter !== 'all'">
              筛选后 {{ filteredReportSnapshots.length }} 条
            </span>
          </div>

          <a-empty v-if="filteredReportSnapshots.length === 0" description="暂无报告快照" />
          <div v-else class="snapshot-list">
            <div
              v-for="item in filteredReportSnapshots"
              :key="item.id"
              class="snapshot-item"
              :class="{ active: activeSnapshotId === item.id, pinned: item.isPinned }"
            >
              <div class="snapshot-main" @click="applyReportSnapshot(item)">
                <div class="snapshot-name-row">
                  <template v-if="editingSnapshotId === item.id">
                    <a-input
                      v-model="editingSnapshotTitle"
                      size="small"
                      class="snapshot-title-input"
                      placeholder="请输入快照名称"
                      @click.stop
                      @press-enter="submitRenameSnapshot(item)"
                    />
                  </template>
                  <template v-else>
                    <div class="snapshot-name">{{ item.title }}</div>
                    <a-tag v-if="item.isPinned" size="small" color="gold">置顶</a-tag>
                  </template>
                </div>
                <div class="snapshot-meta">
                  <span>{{ item.generatedAtText }}</span>
                  <span>创建人：{{ item.creatorName }}</span>
                </div>
                <div class="snapshot-report-meta">
                  <a-tag size="small" :color="getGenerationSourceColor(item.report)">
                    {{ getSnapshotSummaryMeta(item).sourceLabel }}
                  </a-tag>
                  <span>{{ getSnapshotSummaryMeta(item).durationText }}</span>
                  <span>{{ getSnapshotSummaryMeta(item).statusText }}</span>
                </div>
              </div>

              <div class="snapshot-actions">
                <template v-if="editingSnapshotId === item.id">
                  <a-button size="mini" type="primary" @click.stop="submitRenameSnapshot(item)">保存</a-button>
                  <a-button size="mini" @click.stop="cancelRenameSnapshot">取消</a-button>
                </template>
                <template v-else>
                  <a-button size="mini" @click.stop="startRenameSnapshot(item)">重命名</a-button>
                  <a-button size="mini" @click.stop="handleTogglePinSnapshot(item)">
                    {{ item.isPinned ? '取消置顶' : '置顶' }}
                  </a-button>
                  <a-button size="mini" status="danger" @click.stop="removeReportSnapshot(item.id)">删除</a-button>
                </template>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="report-content">
        <div v-if="reportData" class="report-body">
          <div class="report-hero">
            <div class="hero-main">
              <div class="hero-kicker">QUALITY REPORT CENTER</div>
              <div class="report-title-row">
                <div class="report-title-block">
                  <div class="report-title">本轮测试报告</div>
                  <div class="report-meta">
                    {{ reportData.report_standard.test_overview.test_object }} /
                    {{ reportData.report_standard.test_overview.target_version }}
                  </div>
                </div>
                <div class="hero-tag-group">
                  <a-tag
                    :color="
                      getReleaseRecommendationColor(
                        reportData.report_standard.quality_conclusion.release_recommendation
                      )
                    "
                  >
                    {{ reportData.report_standard.quality_conclusion.release_recommendation }}
                  </a-tag>
                  <a-tag
                    :color="getQualityRatingColor(reportData.report_standard.quality_conclusion.rating)"
                  >
                    质量评级：{{ reportData.report_standard.quality_conclusion.rating }}
                  </a-tag>
                </div>
              </div>
              <div class="hero-description">{{ reportData.summary }}</div>
              <div class="hero-meta-grid">
                <div class="hero-meta-item">
                  <div class="hero-meta-label">报告编号</div>
                  <div class="hero-meta-value">{{ reportData.report_standard.basic_info.report_no }}</div>
                </div>
                <div class="hero-meta-item">
                  <div class="hero-meta-label">报告日期</div>
                  <div class="hero-meta-value">{{ reportData.report_standard.basic_info.report_date }}</div>
                </div>
                <div class="hero-meta-item">
                  <div class="hero-meta-label">编写人</div>
                  <div class="hero-meta-value">{{ reportData.report_standard.basic_info.author }}</div>
                </div>
                <div class="hero-meta-item">
                  <div class="hero-meta-label">审核人</div>
                  <div class="hero-meta-value">{{ reportData.report_standard.basic_info.reviewer }}</div>
                </div>
              </div>
            </div>
            <div class="hero-side">
              <div class="hero-status-card">
                <div class="hero-status-label">发布建议</div>
                <div class="hero-status-value">
                  {{ reportData.report_standard.quality_conclusion.release_recommendation }}
                </div>
                <div class="hero-status-footnote">{{ releaseDecisionFootnote }}</div>
              </div>
            </div>
          </div>

          <div class="report-toolbar">
            <a-space wrap>
              <a-button size="small" :disabled="!reportData" @click="handleSaveSnapshot">保存快照</a-button>
              <a-button size="small" :disabled="!activeSnapshotId || !reportData" @click="handleOverwriteSnapshot">
                覆盖当前快照
              </a-button>
              <a-button size="small" @click="handleCopyReportSummary">复制摘要</a-button>
              <a-button size="small" @click="handleExportReport">导出报告</a-button>
              <a-button size="small" :loading="reportLoading" @click="handleGenerateReport">重新生成</a-button>
            </a-space>
          </div>

          <div class="report-nav-panel">
            <div class="report-nav-title">报告导航</div>
            <div class="report-nav-list">
              <a-button
                v-for="item in reportSectionNavItems"
                :key="item.id"
                size="small"
                class="report-nav-button"
                @click="scrollToReportSection(item.id)"
              >
                {{ item.label }}
              </a-button>
            </div>
          </div>

          <a-alert v-if="generationInsight" class="generation-alert" :type="generationInsight.status">
            <template #title>{{ generationInsight.title }}</template>
            {{ generationInsight.description }}
          </a-alert>

          <div class="report-summary-grid">
            <div class="item-card">
              <div class="hero-kicker">SCOPE</div>
              <div class="decision-focus-label">已选套件</div>
              <div class="decision-focus-value">{{ reportData.selected_suite_count }}</div>
              <div class="decision-focus-footnote">实际汇总覆盖 {{ reportData.suite_count }} 个套件节点</div>
            </div>
            <div class="item-card">
              <div class="hero-kicker">CASE</div>
              <div class="decision-focus-label">测试用例</div>
              <div class="decision-focus-value">{{ reportData.testcase_count }}</div>
              <div class="decision-focus-footnote">
                已执行 {{ reportData.report_standard.activity_summary.workload.executed_cases }} 条
              </div>
            </div>
            <div class="item-card">
              <div class="hero-kicker">BUG</div>
              <div class="decision-focus-label">关联 BUG</div>
              <div class="decision-focus-value">{{ reportData.bug_count }}</div>
              <div class="decision-focus-footnote">
                未关闭 {{ reportData.report_standard.appendices.defect_list_summary.open_total }} 条
              </div>
            </div>
            <div class="item-card">
              <div class="hero-kicker">TRACE</div>
              <div class="decision-focus-label">需求追踪</div>
              <div class="decision-focus-value">
                {{ reportData.requirement_summary.traceable_testcase_count }}/{{ reportData.requirement_summary.testcase_count }}
              </div>
              <div class="decision-focus-footnote">
                未追踪 {{ reportData.requirement_summary.unlinked_testcase_count }} 条
              </div>
            </div>
          </div>

          <div class="report-summary-caption">
            以上摘要用于快速判断当前版本是否具备发布基础，详细证据以下方测试结果、缺陷闭环与风险说明为准。
          </div>

          <div class="decision-focus-grid">
            <div class="decision-focus-card">
              <div class="decision-focus-label">当前发布判断</div>
              <div class="decision-focus-value">
                {{ reportData.report_standard.quality_conclusion.release_recommendation }}
              </div>
              <div class="decision-focus-footnote">{{ releaseDecisionFootnote }}</div>
            </div>
            <div class="decision-focus-card">
              <div class="decision-focus-label">执行覆盖率</div>
              <div class="decision-focus-value">{{ executionCoverageRate }}</div>
              <div class="decision-focus-footnote">
                已执行 {{ reportData.report_standard.activity_summary.workload.executed_cases }} /
                {{ reportData.report_standard.activity_summary.workload.total_cases }} 条，当前通过率
                {{ reportData.report_standard.result_details.case_execution.pass_rate }}%。
              </div>
            </div>
            <div class="decision-focus-card">
              <div class="decision-focus-label">未关闭缺陷</div>
              <div class="decision-focus-value">
                {{ reportData.report_standard.appendices.defect_list_summary.open_total }}
              </div>
              <div class="decision-focus-footnote">
                当前复测失败 {{ reportData.report_standard.defect_summary.trend_summary.retest_failed_total }} 次。
              </div>
            </div>
            <div class="decision-focus-card">
              <div class="decision-focus-label">完成标准达成</div>
              <div class="decision-focus-value">{{ criteriaCompletionSummary.value }}</div>
              <div class="decision-focus-footnote">{{ criteriaCompletionSummary.footnote }}</div>
            </div>
          </div>

          <div id="report-basic-info" class="report-section">
            <div class="section-title">报告基本信息</div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">报告编号与版本</div>
                <p class="section-text">
                  编号：{{ reportData.report_standard.basic_info.report_no }}<br />
                  版本：{{ reportData.report_standard.basic_info.report_version }}
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">报告责任人</div>
                <p class="section-text">
                  报告日期：{{ reportData.report_standard.basic_info.report_date }}<br />
                  编写人：{{ reportData.report_standard.basic_info.author }}<br />
                  负责人：{{ reportData.report_standard.basic_info.owner }}<br />
                  审核人：{{ reportData.report_standard.basic_info.reviewer }}
                </p>
              </div>
            </div>
          </div>

          <div id="report-overview" class="report-section">
            <div class="section-title">测试概述</div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">测试对象</div>
                <p class="section-text">
                  测试对象：{{ reportData.report_standard.test_overview.test_object }}<br />
                  目标版本：{{ reportData.report_standard.test_overview.target_version }}
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">测试范围</div>
                <p class="section-text">
                  纳入范围：{{ reportData.report_standard.test_overview.scope_included }}<br />
                  不在范围：{{ reportData.report_standard.test_overview.scope_excluded }}
                </p>
              </div>
            </div>
            <div class="item-card">
              <div class="decision-focus-label">测试目标</div>
              <div class="item-list">
                <div
                  v-for="(item, index) in reportData.report_standard.test_overview.objectives"
                  :key="`objective-${index}`"
                  class="item-card"
                >
                  <div class="item-detail">{{ item }}</div>
                </div>
                <div v-if="reportData.report_standard.test_overview.objectives.length === 0" class="item-detail">
                  当前未记录测试目标
                </div>
              </div>
            </div>
          </div>

          <div id="report-environment" class="report-section">
            <div class="section-title">测试环境</div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">硬件与网络</div>
                <p class="section-text">{{ reportData.report_standard.environment.hardware_network }}</p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">软件环境</div>
                <p class="section-text">{{ reportData.report_standard.environment.software_environment }}</p>
              </div>
            </div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">测试工具</div>
                <p class="section-text">
                  {{ formatDisplayList(reportData.report_standard.environment.test_tools, '当前未记录测试工具') }}
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">第三方依赖</div>
                <p class="section-text">{{ reportData.report_standard.environment.third_party_services }}</p>
              </div>
            </div>
          </div>

          <div id="report-activity" class="report-section">
            <div class="section-title">测试活动摘要</div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">测试活动</div>
                <p class="section-text">
                  测试类型：{{ formatDisplayList(reportData.report_standard.activity_summary.test_types, '-') }}<br />
                  测试轮次：{{ reportData.report_standard.activity_summary.test_round }}<br />
                  时间跨度：{{ formatDateTime(reportData.report_standard.activity_summary.time_span.start) }} 至
                  {{ formatDateTime(reportData.report_standard.activity_summary.time_span.end) }}
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">工作量</div>
                <p class="section-text">
                  人日：{{ reportData.report_standard.activity_summary.workload.person_days }}<br />
                  总用例：{{ reportData.report_standard.activity_summary.workload.total_cases }}<br />
                  已执行：{{ reportData.report_standard.activity_summary.workload.executed_cases }}<br />
                  自动化占比：{{ reportData.report_standard.activity_summary.workload.automation_ratio }}<br />
                  缺陷数：{{ reportData.report_standard.activity_summary.workload.bug_count }}
                </p>
              </div>
            </div>
          </div>

          <div id="report-results" class="report-section">
            <div class="section-title">测试结果详情</div>
            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">用例执行统计</div>
                <p class="section-text">
                  总数：{{ reportData.report_standard.result_details.case_execution.total }}<br />
                  通过：{{ reportData.report_standard.result_details.case_execution.passed }}<br />
                  失败：{{ reportData.report_standard.result_details.case_execution.failed }}<br />
                  阻塞：{{ reportData.report_standard.result_details.case_execution.blocked }}<br />
                  未执行：{{ reportData.report_standard.result_details.case_execution.not_executed }}<br />
                  通过率：{{ reportData.report_standard.result_details.case_execution.pass_rate }}%
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">执行状态分布</div>
                <div class="item-list compact-item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.result_details.execution_breakdown"
                    :key="`execution-${index}`"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>{{ item.name }}</span>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                  <div v-if="reportData.report_standard.result_details.execution_breakdown.length === 0" class="item-detail">
                    当前没有执行状态分布数据
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div id="report-defects" class="report-section">
            <div class="section-title">缺陷统计</div>
            <div class="report-summary-grid-secondary">
              <div class="item-card">
                <div class="decision-focus-label">按严重程度</div>
                <div class="item-list compact-item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.defect_summary.by_severity"
                    :key="`severity-${index}`"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>{{ item.name }}</span>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                  <div v-if="reportData.report_standard.defect_summary.by_severity.length === 0" class="item-detail">
                    当前没有严重程度统计
                  </div>
                </div>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">按状态</div>
                <div class="item-list compact-item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.defect_summary.by_status"
                    :key="`status-${index}`"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>{{ item.name }}</span>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                  <div v-if="reportData.report_standard.defect_summary.by_status.length === 0" class="item-detail">
                    当前没有缺陷状态统计
                  </div>
                </div>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">按模块</div>
                <div class="item-list compact-item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.defect_summary.by_module"
                    :key="`module-${index}`"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>{{ item.name }}</span>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                  <div v-if="reportData.report_standard.defect_summary.by_module.length === 0" class="item-detail">
                    当前没有模块分布数据
                  </div>
                </div>
              </div>
            </div>

            <div class="report-two-column">
              <div class="item-card">
                <div class="decision-focus-label">缺陷趋势摘要</div>
                <p class="section-text">
                  新发现：{{ reportData.report_standard.defect_summary.trend_summary.discovered }}<br />
                  已关闭：{{ reportData.report_standard.defect_summary.trend_summary.closed }}<br />
                  重新激活：{{ reportData.report_standard.defect_summary.trend_summary.reactivated }}<br />
                  复测失败：{{ reportData.report_standard.defect_summary.trend_summary.retest_failed_total }}
                </p>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">遗留缺陷</div>
                <div class="item-list">
                  <div
                    v-for="item in reportData.report_standard.defect_summary.legacy_defects"
                    :key="`legacy-${item.id}`"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>#{{ item.id }} {{ item.title }}</span>
                      <a-tag size="small" color="red">{{ item.status }}</a-tag>
                    </div>
                    <div class="item-detail">
                      严重程度：{{ item.severity }}，模块：{{ item.module }}
                    </div>
                    <div class="item-detail">影响范围：{{ item.impact_scope }}</div>
                    <div class="item-detail">计划修复版本：{{ item.planned_fix_version }}</div>
                    <div class="item-detail">风险接受理由：{{ item.risk_acceptance }}</div>
                  </div>
                  <div v-if="reportData.report_standard.defect_summary.legacy_defects.length === 0" class="item-detail">
                    当前没有遗留缺陷
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div id="report-conclusion" class="report-section">
            <div class="section-title">测试结论</div>
            <div class="conclusion-overview-grid">
              <div v-for="item in conclusionOverviewCards" :key="item.label" class="conclusion-overview-card">
                <div class="conclusion-overview-label">{{ item.label }}</div>
                <div class="conclusion-overview-value">{{ item.value }}</div>
                <div class="conclusion-overview-footnote">{{ item.footnote }}</div>
              </div>
            </div>

            <div class="conclusion-reason-panel">
              <div class="conclusion-reason-header">
                <div class="conclusion-reason-title">结论依据</div>
                <div class="conclusion-reason-subtitle">直接说明哪些数据支撑了当前测试结论。</div>
              </div>
              <div class="conclusion-reason-list">
                <div
                  v-for="(item, index) in conclusionReasons"
                  :key="`reason-${index}`"
                  class="conclusion-reason-item"
                  :class="item.tone"
                >
                  <div class="conclusion-reason-item-top">
                    <span class="conclusion-reason-item-title">{{ item.title }}</span>
                    <a-tag size="small" :color="getCriteriaSectionColor(item.tone)">
                      {{ item.tone === 'danger' ? '高影响' : item.tone === 'warning' ? '需关注' : '已支撑' }}
                    </a-tag>
                  </div>
                  <div class="conclusion-reason-item-detail">{{ item.detail }}</div>
                </div>
                <div v-if="conclusionReasons.length === 0" class="item-detail">当前没有额外结论依据</div>
              </div>
            </div>

            <div class="report-summary-grid-secondary">
              <div class="item-card">
                <div class="decision-focus-label">完成标准判断</div>
                <div class="criteria-summary-grid">
                  <div
                    v-for="item in criteriaSummaryCards"
                    :key="item.key"
                    class="item-card"
                  >
                    <div class="item-header">
                      <span>{{ item.title }}</span>
                      <a-tag size="small" :color="getCriteriaSectionColor(item.tone)">{{ item.count }}</a-tag>
                    </div>
                    <div class="item-detail">{{ item.description }}</div>
                    <div class="item-list compact-item-list">
                      <div
                        v-for="(detail, index) in item.items"
                        :key="`${item.key}-${index}`"
                        class="item-card"
                      >
                        <div class="item-header">
                          <span>{{ detail.name }}</span>
                          <a-tag size="small" :color="getCriteriaSectionColor(detail.tone)">
                            {{ detail.toneLabel }}
                          </a-tag>
                        </div>
                        <div class="item-detail">{{ detail.detail }}</div>
                      </div>
                      <div v-if="item.items.length === 0" class="item-detail">{{ item.emptyText }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="item-card">
                <div class="decision-focus-label">发布前待办</div>
                <div class="report-section-intro">按优先级列出当前最值得先处理的事项。</div>
                <div class="item-list">
                  <div v-for="(item, index) in releaseChecklist" :key="`todo-${index}`" class="item-card">
                    <div class="item-header">
                      <span>{{ item.title }}</span>
                      <a-tag
                        size="small"
                        :color="item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'arcoblue'"
                      >
                        {{ getPriorityLabel(item.priority) }}
                      </a-tag>
                    </div>
                    <div class="item-detail">{{ item.detail }}</div>
                  </div>
                  <div v-if="releaseChecklist.length === 0" class="item-detail">当前没有额外待办事项</div>
                </div>
              </div>
            </div>

            <div class="item-card">
              <div class="decision-focus-label">结论陈述</div>
              <p class="section-text">{{ reportData.report_standard.quality_conclusion.conclusion }}</p>
            </div>
          </div>

          <div id="report-risk" class="report-section">
            <div class="section-title">风险与建议</div>
            <div class="report-section-intro">
              这里归纳当前测试阶段仍需关注的执行风险、发布剩余风险和后续闭环动作，供版本评审和上线决策参考。
            </div>

            <div class="risk-overview-grid">
              <div v-for="item in riskOverviewCards" :key="item.label" class="risk-overview-card">
                <div class="risk-overview-label">{{ item.label }}</div>
                <div class="risk-overview-value">{{ item.value }}</div>
                <div class="risk-overview-footnote">{{ item.footnote }}</div>
              </div>
            </div>

            <div class="report-summary-grid-secondary">
              <div class="item-card">
                <div class="decision-focus-label">测试过程风险</div>
                <div class="item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.risk_and_suggestions.process_risks"
                    :key="`process-risk-${index}`"
                    class="item-card"
                  >
                    <div class="item-detail">{{ item }}</div>
                  </div>
                  <div v-if="reportData.report_standard.risk_and_suggestions.process_risks.length === 0" class="item-detail">
                    当前没有额外测试过程风险
                  </div>
                </div>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">剩余风险</div>
                <div class="item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.risk_and_suggestions.residual_risks"
                    :key="`residual-risk-${index}`"
                    class="item-card"
                  >
                    <div class="item-detail">{{ item }}</div>
                  </div>
                  <div v-if="reportData.report_standard.risk_and_suggestions.residual_risks.length === 0" class="item-detail">
                    当前没有剩余风险项
                  </div>
                </div>
              </div>
              <div class="item-card">
                <div class="decision-focus-label">后续建议</div>
                <div class="item-list">
                  <div
                    v-for="(item, index) in reportData.report_standard.risk_and_suggestions.follow_up_actions"
                    :key="`follow-action-${index}`"
                    class="item-card"
                  >
                    <div class="item-detail">{{ item }}</div>
                  </div>
                  <div v-if="reportData.report_standard.risk_and_suggestions.follow_up_actions.length === 0" class="item-detail">
                    当前没有额外后续建议
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div id="report-appendix" class="report-section">
            <div class="section-title">补充分析</div>
            <div class="report-section-intro">
              这里补充展示需求覆盖、缺陷修复闭环和测试证据，用于说明当前发布结论背后的事实依据。
            </div>

            <div class="support-summary-strip">
              <div v-for="item in supportSummaryItems" :key="item.label" class="support-summary-item">
                <div class="support-summary-label">{{ item.label }}</div>
                <div class="support-summary-value">{{ item.value }}</div>
              </div>
            </div>

            <div class="support-analysis-grid">
              <div class="support-analysis-card">
                <div class="support-analysis-title">需求覆盖证据</div>
                <div class="support-analysis-metrics compact">
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">覆盖文档</span>
                    <span class="support-analysis-value">{{ reportData.requirement_summary.linked_document_count }}</span>
                  </div>
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">追踪用例</span>
                    <span class="support-analysis-value">{{ reportData.requirement_summary.traceable_testcase_count }}</span>
                  </div>
                </div>
                <div class="item-detail support-evidence-copy">
                  <template v-if="reportData.requirement_summary.linked_document_count > 0">
                    当前已建立 {{ reportData.requirement_summary.linked_module_count }} 个模块的需求追踪关系，仍有
                    {{ reportData.requirement_summary.unlinked_testcase_count }} 条测试用例未补齐来源需求。
                  </template>
                  <template v-else>当前未记录可追踪的需求文档</template>
                </div>
                <div class="item-detail">
                  {{ formatDisplayList(reportData.report_standard.appendices.requirement_documents.map((item) => `${item.title} ${item.version}`), '当前未记录需求文档') }}
                </div>
              </div>

              <div class="support-analysis-card">
                <div class="support-analysis-title">BUG 闭环证据</div>
                <div class="support-analysis-metrics compact">
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">已关闭</span>
                    <span class="support-analysis-value">{{ reportData.bug_workflow_summary.closed_bug_count }}</span>
                  </div>
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">复测失败</span>
                    <span class="support-analysis-value">{{ reportData.bug_workflow_summary.retest_failed_total_count }}</span>
                  </div>
                </div>
                <div class="item-detail support-evidence-copy">
                  已修复 {{ reportData.bug_workflow_summary.fixed_bug_count }} 个，待复测
                  {{ reportData.bug_workflow_summary.submitted_retest_bug_count }} 个，重新激活
                  {{ reportData.bug_workflow_summary.reactivated_bug_count }} 个，反映当前缺陷闭环稳定性。
                </div>
                <div class="item-detail">
                  <div
                    v-for="item in reportData.bug_workflow_summary.top_retest_failed_bugs.slice(0, 4)"
                    :key="`top-bug-${item.id}`"
                  >
                    #{{ item.id }} {{ item.title }}，复测失败 {{ item.failed_retest_count }} 次
                  </div>
                  <div v-if="reportData.bug_workflow_summary.top_retest_failed_bugs.length === 0">
                    当前没有高频复测失败的 BUG
                  </div>
                </div>
              </div>

              <div class="support-analysis-card">
                <div class="support-analysis-title">附录与证据</div>
                <div class="support-analysis-metrics compact">
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">关联缺陷</span>
                    <span class="support-analysis-value">{{ reportData.report_standard.appendices.defect_list_summary.total }}</span>
                  </div>
                  <div class="support-analysis-metric">
                    <span class="support-analysis-label">证据条目</span>
                    <span class="support-analysis-value">{{ reportData.evidence.length }}</span>
                  </div>
                </div>
                <div class="item-detail support-evidence-copy">
                  当前报告共引用缺陷 {{ reportData.report_standard.appendices.defect_list_summary.total }} 个，其中未关闭
                  {{ reportData.report_standard.appendices.defect_list_summary.open_total }} 个，补充证据
                  {{ reportData.evidence.length }} 条。
                </div>
                <div class="item-detail">
                  测试数据说明：{{ reportData.report_standard.appendices.test_data_note }}
                </div>
                <div class="item-detail">
                  <div v-for="item in reportData.evidence.slice(0, 4)" :key="`${item.label}-${item.detail}`">
                    {{ item.label }}：{{ item.detail }}
                  </div>
                  <div v-if="reportData.evidence.length === 0">当前未记录额外测试证据</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="report-placeholder">
          <a-empty description="请选择套件后生成测试报告" />
        </div>
      </section>
    </div>
  </div>
</template>


<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Message, Modal, type TreeNodeData } from '@arco-design/web-vue';
import { useRoute } from 'vue-router';
import {
  createTestReportSnapshot,
  deleteTestReportSnapshot,
  generateAiIterationTestReport,
  getTestReportSnapshots,
  updateTestReportSnapshot,
  type AiIterationTestReport,
} from '@/services/testExecutionService';
import { getTestSuiteList, type TestSuite } from '@/services/testSuiteService';
import { useProjectStore } from '@/store/projectStore';

type SuiteTreeNode = TreeNodeData & {
  id: number;
  name: string;
  testcase_count: number;
  children?: SuiteTreeNode[];
};

type ReportSnapshot = {
  id: number;
  title: string;
  projectId: number;
  suiteIds: number[];
  creatorName: string;
  isPinned: boolean;
  generatedAt: string;
  generatedAtText: string;
  sourcePriority: number;
  report: AiIterationTestReport;
};

type SnapshotSummaryMeta = {
  sourceLabel: string;
  statusText: string;
  durationText: string;
};

type GenerationRecordSummary = {
  generatedAtText: string;
  source: 'ai' | 'rule' | 'fallback';
  sourceLabel: string;
  statusText: string;
  durationText: string;
  selectedSuiteCount: number;
  suiteCount: number;
  note: string;
};

type SnapshotCompareItem = {
  label: string;
  current: string;
  previous: string;
  delta: string;
  trend: 'up' | 'down' | 'flat';
  impact: 'positive' | 'negative' | 'neutral';
  judgement: string;
};

type CriteriaSummaryItem = {
  name: string;
  detail: string;
  passed: boolean;
  tone: 'danger' | 'warning' | 'success';
  toneLabel: string;
};

type ConclusionReasonItem = {
  title: string;
  detail: string;
  tone: 'danger' | 'warning' | 'success';
};

type ReleaseChecklistItem = {
  title: string;
  detail: string;
  priority: 'high' | 'medium' | 'low';
};

type ReportSectionNavItem = {
  id: string;
  label: string;
};

const projectStore = useProjectStore();
const route = useRoute();
const currentProjectId = computed(() => projectStore.currentProjectId || null);

const suiteLoading = ref(false);
const reportLoading = ref(false);
const searchKeyword = ref('');
const snapshotKeyword = ref('');
const snapshotSourceFilter = ref<'all' | 'ai' | 'fallback' | 'rule' | 'pinned'>('all');
const selectedCompareSnapshotId = ref<number | 'auto'>('auto');
const suites = ref<TestSuite[]>([]);
const checkedKeys = ref<(number | string)[]>([]);
const expandedKeys = ref<(number | string)[]>([]);
const reportData = ref<AiIterationTestReport | null>(null);
const reportSnapshots = ref<ReportSnapshot[]>([]);
const activeSnapshotId = ref<number | null>(null);
const editingSnapshotId = ref<number | null>(null);
const editingSnapshotTitle = ref('');
const reportSectionNavItems: ReportSectionNavItem[] = [
  { id: 'report-basic-info', label: '基本信息' },
  { id: 'report-overview', label: '测试概述' },
  { id: 'report-environment', label: '测试环境' },
  { id: 'report-activity', label: '活动摘要' },
  { id: 'report-results', label: '结果详情' },
  { id: 'report-defects', label: '缺陷统计' },
  { id: 'report-conclusion', label: '测试结论' },
  { id: 'report-risk', label: '风险建议' },
  { id: 'report-appendix', label: '附录附件' },
];

const checkedSuiteIds = computed(() =>
  Array.from(
    new Set(checkedKeys.value.map((item) => Number(item)).filter((item) => Number.isFinite(item)))
  )
);

const filteredReportSnapshots = computed(() => {
  const keyword = snapshotKeyword.value.trim().toLowerCase();
  return reportSnapshots.value.filter((item) => {
    const matchedFilter = matchSnapshotSourceFilter(item, snapshotSourceFilter.value);
    if (!matchedFilter) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.generatedAtText.toLowerCase().includes(keyword) ||
      item.creatorName.toLowerCase().includes(keyword)
    );
  });
});

const currentGenerateButtonText = computed(() => {
  if (reportLoading.value) {
    return '正在生成测试报告...';
  }
  return 'AI生成测试报告';
});

const latestGenerationRecord = computed<GenerationRecordSummary | null>(() => {
  const report =
    reportData.value ||
    (reportSnapshots.value.length > 0 ? reportSnapshots.value[0].report : null);
  if (!report) {
    return null;
  }
  return {
    generatedAtText: formatDateTime(report.generated_at),
    source: report.generation_source || (report.used_ai ? 'ai' : 'rule'),
    sourceLabel: getGenerationSourceLabel(report),
    statusText: getGenerationStatusText(report),
    durationText: formatDuration(report.generation_duration_ms),
    selectedSuiteCount: Number(report.selected_suite_count || 0),
    suiteCount: Number(report.suite_count || 0),
    note: report.note || '当前未记录额外生成说明。',
  };
});

const compareSnapshotOptions = computed(() =>
  reportSnapshots.value.filter((item) => item.id !== activeSnapshotId.value)
);

const compareSnapshot = computed<ReportSnapshot | null>(() => {
  if (selectedCompareSnapshotId.value !== 'auto') {
    return (
      reportSnapshots.value.find((item) => item.id === selectedCompareSnapshotId.value) || null
    );
  }
  return findNearestComparableSnapshot();
});

const compareSnapshotDescription = computed(() => {
  if (!compareSnapshot.value) {
    return '暂无可对比快照';
  }
  if (selectedCompareSnapshotId.value === 'auto') {
    return `自动匹配上一版：${compareSnapshot.value.title}`;
  }
  return compareSnapshot.value.title;
});

const snapshotCompareItems = computed<SnapshotCompareItem[]>(() => {
  const current = reportData.value;
  if (!current) {
    return [];
  }

  const previous = compareSnapshot.value?.report;
  if (!previous) {
    return [];
  }

  const buildDelta = (
    currentValue: number,
    previousValue: number,
    suffix = '',
    higherIsBetter = true
  ) => {
    const diff = currentValue - previousValue;
    if (diff === 0) {
      return {
        delta: `0${suffix}`,
        trend: 'flat' as const,
        impact: 'neutral' as const,
        judgement: '与对比快照持平',
      };
    }
    const improved = higherIsBetter ? diff > 0 : diff < 0;
    return {
      delta: `${diff > 0 ? '+' : ''}${diff}${suffix}`,
      trend: diff > 0 ? ('up' as const) : ('down' as const),
      impact: improved ? ('positive' as const) : ('negative' as const),
      judgement: improved ? '较对比快照改善' : '较对比快照变差',
    };
  };

  const currentPassRate = Number(current.report_standard.result_details.case_execution.pass_rate || 0);
  const previousPassRate = Number(previous.report_standard.result_details.case_execution.pass_rate || 0);
  const currentOpenBug = Number(current.report_standard.appendices.defect_list_summary.open_total || 0);
  const previousOpenBug = Number(previous.report_standard.appendices.defect_list_summary.open_total || 0);
  const currentRetestFailed = Number(current.report_standard.defect_summary.trend_summary.retest_failed_total || 0);
  const previousRetestFailed = Number(previous.report_standard.defect_summary.trend_summary.retest_failed_total || 0);
  const currentNotExecuted = Number(current.report_standard.result_details.case_execution.not_executed || 0);
  const previousNotExecuted = Number(previous.report_standard.result_details.case_execution.not_executed || 0);

  const passRateDelta = buildDelta(currentPassRate, previousPassRate, '%', true);
  const openBugDelta = buildDelta(currentOpenBug, previousOpenBug, '', false);
  const retestDelta = buildDelta(currentRetestFailed, previousRetestFailed, '', false);
  const notExecutedDelta = buildDelta(currentNotExecuted, previousNotExecuted, '', false);

  return [
    {
      label: '执行通过率',
      current: `${currentPassRate}%`,
      previous: `${previousPassRate}%`,
      delta: passRateDelta.delta,
      trend: passRateDelta.trend,
      impact: passRateDelta.impact,
      judgement: passRateDelta.judgement,
    },
    {
      label: '遗留BUG',
      current: `${currentOpenBug}`,
      previous: `${previousOpenBug}`,
      delta: openBugDelta.delta,
      trend: openBugDelta.trend,
      impact: openBugDelta.impact,
      judgement: openBugDelta.judgement,
    },
    {
      label: '复测失败',
      current: `${currentRetestFailed}`,
      previous: `${previousRetestFailed}`,
      delta: retestDelta.delta,
      trend: retestDelta.trend,
      impact: retestDelta.impact,
      judgement: retestDelta.judgement,
    },
    {
      label: '未执行用例',
      current: `${currentNotExecuted}`,
      previous: `${previousNotExecuted}`,
      delta: notExecutedDelta.delta,
      trend: notExecutedDelta.trend,
      impact: notExecutedDelta.impact,
      judgement: notExecutedDelta.judgement,
    },
  ];
});

const normalizeSnapshots = (items: ReportSnapshot[]) =>
  [...items].sort((left, right) => {
    if (left.isPinned !== right.isPinned) {
      return left.isPinned ? -1 : 1;
    }
    if (left.sourcePriority !== right.sourcePriority) {
      return left.sourcePriority - right.sourcePriority;
    }
    return new Date(right.generatedAt).getTime() - new Date(left.generatedAt).getTime();
  });

const buildFallbackStandardReport = (report: any) => {
  const totalCases = Number(report?.testcase_count || 0);
  const passedCount = Number(report?.execution_status_distribution?.passed || 0);
  const failedCount = Number(report?.execution_status_distribution?.failed || 0);
  const blockedCount = Number(report?.execution_status_distribution?.not_applicable || 0);
  const notExecutedCount = Number(report?.execution_status_distribution?.not_executed || 0);
  const executedCases = Math.max(totalCases - notExecutedCount, 0);
  const passRate = executedCases > 0 ? Math.round((passedCount / executedCases) * 100) : 0;
  const traceableCount = Number(report?.requirement_summary?.traceable_testcase_count || 0);
  const unlinkedCount = Number(report?.requirement_summary?.unlinked_testcase_count || 0);

  const bugStatusDistribution = report?.bug_status_distribution || {};
  const openBugCount = Object.entries(bugStatusDistribution).reduce((sum, [key, value]) => {
    return key === 'closed' ? sum : sum + Number(value || 0);
  }, 0);
  const highRiskBugCount =
    Number(bugStatusDistribution.unassigned || 0) +
    Number(bugStatusDistribution.assigned || 0) +
    Number(bugStatusDistribution.confirmed || 0);
  const retestFailedTotal = Number(report?.bug_workflow_summary?.retest_failed_total_count || 0);

  let rating = '优';
  let releaseRecommendation = '建议发布';

  if (failedCount > 0 || highRiskBugCount > 0) {
    rating = '不合格';
    releaseRecommendation = '不建议发布';
  } else if (openBugCount > 0 || retestFailedTotal > 0) {
    rating = '良';
    releaseRecommendation = '有条件发布';
  } else if (notExecutedCount > 0 || unlinkedCount > 0) {
    rating = '合格';
    releaseRecommendation = '有条件发布';
  }

  const criteria = [
    {
      name: '测试用例已完成执行',
      passed: notExecutedCount === 0,
      detail: `未执行用例 ${notExecutedCount} 条`,
    },
    {
      name: '执行结果无失败',
      passed: failedCount === 0,
      detail: `失败用例 ${failedCount} 条`,
    },
    {
      name: '测试用例已完成需求追踪',
      passed: unlinkedCount === 0,
      detail: `已关联需求 ${traceableCount} 条，未关联需求 ${unlinkedCount} 条`,
    },
    {
      name: '未关闭 BUG 可控',
      passed: highRiskBugCount === 0,
      detail: `高风险未关闭 BUG ${highRiskBugCount} 个，未关闭 BUG 总数 ${openBugCount} 个`,
    },
    {
      name: 'BUG 复测结果稳定',
      passed: retestFailedTotal === 0,
      detail: `复测失败累计 ${retestFailedTotal} 次`,
    },
  ];

  const processRisks = ['当前报告来自历史快照兼容计算，部分环境类字段无法从旧数据中完全还原。'];
  if (unlinkedCount > 0) {
    processRisks.push(`仍有 ${unlinkedCount} 条测试用例未关联需求，历史快照的需求追踪完整性不足。`);
  }
  if (notExecutedCount > 0) {
    processRisks.push(`仍有 ${notExecutedCount} 条测试用例未执行，测试覆盖尚未完整闭环。`);
  }

  const residualRisks: string[] = [];
  if (openBugCount > 0) {
    residualRisks.push(`仍有 ${openBugCount} 个 BUG 未关闭，需要继续跟进修复与验证。`);
  }
  if (retestFailedTotal > 0) {
    residualRisks.push(`BUG 复测失败累计 ${retestFailedTotal} 次，修复稳定性仍需重点关注。`);
  }
  if (failedCount > 0) {
    residualRisks.push(`当前仍有 ${failedCount} 条失败用例，发布风险较高。`);
  }

  const suiteScope = (report?.suite_breakdown || []).map((item: any) => item.path || item.name).join('；') || '未记录';
  const latestDocument =
    (report?.requirement_summary?.documents || []).find((item: any) => item?.is_latest && item?.version) ||
    (report?.requirement_summary?.documents || []).find((item: any) => item?.version);
  const version = latestDocument?.version
    ? `V${String(latestDocument.version).replace(/^V/i, '')}`
    : 'V1.0';

  return {
    basic_info: {
      report_no: report?.generated_at ? `LEGACY-${String(report.generated_at).replace(/\D/g, '').slice(0, 14)}` : 'LEGACY',
      report_version: version,
      report_date: formatDateTime(report?.generated_at),
      author: '-',
      owner: '-',
      reviewer: '-',
    },
    test_overview: {
      test_object: '历史测试报告',
      target_version: version,
      scope_included: suiteScope,
      scope_excluded: '历史快照未记录明确的不在测试范围项。',
      objectives: ['该报告由历史快照兼容计算生成，核心质量结论已按现有执行与 BUG 数据重新推导。'],
    },
    environment: {
      hardware_network: '历史快照未记录',
      software_environment: '历史快照未记录',
      test_tools: ['FlyTest'],
      third_party_services: '历史快照未记录',
    },
    activity_summary: {
      test_types: ['未记录'],
      test_round: '历史快照兼容分析',
      time_span: {
        start: report?.generated_at || null,
        end: report?.generated_at || null,
      },
      workload: {
        person_days: '未统计',
        total_cases: totalCases,
        executed_cases: executedCases,
        automation_ratio: '未统计',
        bug_count: Number(report?.bug_count || 0),
      },
    },
    result_details: {
      case_execution: {
        total: totalCases,
        passed: passedCount,
        failed: failedCount,
        blocked: blockedCount,
        not_executed: notExecutedCount,
        pass_rate: passRate,
      },
      execution_breakdown: Object.entries(report?.execution_status_distribution || {}).map(([name, count]) => ({
        name,
        count: Number(count || 0),
      })),
    },
    defect_summary: {
      by_severity: [],
      by_status: Object.entries(bugStatusDistribution).map(([name, count]) => ({
        name,
        count: Number(count || 0),
      })),
      by_module: [],
      trend_summary: {
        discovered: Number(report?.bug_count || 0),
        closed: Number(report?.bug_workflow_summary?.closed_bug_count || 0),
        reactivated: Number(report?.bug_workflow_summary?.reactivated_bug_count || 0),
        retest_failed_total: retestFailedTotal,
      },
      legacy_defects: [],
    },
    quality_conclusion: {
      rating,
      release_recommendation: releaseRecommendation,
      criteria,
      conclusion:
        report?.summary ||
        `历史快照兼容分析结果：当前执行通过率 ${passRate}%，未关闭 BUG ${openBugCount} 个，失败用例 ${failedCount} 条，未关联需求用例 ${unlinkedCount} 条。`,
    },
    risk_and_suggestions: {
      process_risks: processRisks,
      residual_risks: residualRisks.length > 0 ? residualRisks : ['当前未识别额外剩余风险。'],
      follow_up_actions:
        (report?.recommendations || []).map((item: any) => item.detail).filter(Boolean).slice(0, 5).length > 0
          ? (report?.recommendations || []).map((item: any) => item.detail).filter(Boolean).slice(0, 5)
          : ['建议重新生成一次新版标准测试报告，以补齐环境、范围和附录字段。'],
    },
    appendices: {
      defect_list_summary: {
        total: Number(report?.bug_count || 0),
        open_total: openBugCount,
        items: [],
      },
      key_testcases: [],
      requirement_documents: (report?.requirement_summary?.documents || []).map((item: any) => ({
        title: item.title,
        version: item.version,
        status: item.status,
      })),
      test_data_note: '该报告为历史快照兼容分析结果，未补录额外测试数据。',
    },
  };
};

const normalizeArray = <T>(value: T[] | undefined | null): T[] => (Array.isArray(value) ? value : []);
const normalizeString = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;
const normalizeNumber = (value: unknown, fallback = 0): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};
const normalizeBoolean = (value: unknown, fallback = false): boolean =>
  typeof value === 'boolean' ? value : fallback;

const normalizeReportPayload = (payload: any): AiIterationTestReport => {
  let current = payload;
  while (
    current &&
    typeof current === 'object' &&
    ((current.status && current.data !== undefined) ||
      (current.success === true && current.data !== undefined))
  ) {
    current = current.data;
  }
  if (current && typeof current === 'object' && !current.report_standard) {
    current = {
      ...current,
      report_standard: buildFallbackStandardReport(current),
    };
  }
  if (current && typeof current === 'object') {
    const requirementSummary = current.requirement_summary || {};
    const bugWorkflowSummary = current.bug_workflow_summary || {};
    const standard = current.report_standard || {};
    const basicInfo = standard.basic_info || {};
    const testOverview = standard.test_overview || {};
    const environment = standard.environment || {};
    const activitySummary = standard.activity_summary || {};
    const activityTimeSpan = activitySummary.time_span || {};
    const activityWorkload = activitySummary.workload || {};
    const resultDetails = standard.result_details || {};
    const caseExecution = resultDetails.case_execution || {};
    const defectSummary = standard.defect_summary || {};
    const defectTrendSummary = defectSummary.trend_summary || {};
    const qualityConclusion = standard.quality_conclusion || {};
    const appendices = standard.appendices || {};
    const defectListSummary = appendices.defect_list_summary || {};
    const riskAndSuggestions = standard.risk_and_suggestions || {};
    current = {
      ...current,
      suite_ids: normalizeArray(current.suite_ids),
      suite_count: normalizeNumber(current.suite_count),
      selected_suite_count: normalizeNumber(current.selected_suite_count),
      testcase_count: normalizeNumber(current.testcase_count),
      bug_count: normalizeNumber(current.bug_count),
      generated_at: normalizeString(current.generated_at),
      used_ai: normalizeBoolean(current.used_ai),
      note: normalizeString(current.note),
      summary: normalizeString(current.summary),
      quality_overview: normalizeString(current.quality_overview),
      risk_overview: normalizeString(current.risk_overview),
      generation_source:
        current.generation_source || (current.used_ai ? 'ai' : 'rule'),
      generation_status: current.generation_status || 'completed',
      generation_duration_ms: normalizeNumber(current.generation_duration_ms),
      fallback_reason: normalizeString(current.fallback_reason),
      evidence: normalizeArray(current.evidence),
      findings: normalizeArray(current.findings),
      recommendations: normalizeArray(current.recommendations),
      suite_breakdown: normalizeArray(current.suite_breakdown),
      execution_status_distribution:
        current.execution_status_distribution && typeof current.execution_status_distribution === 'object'
          ? current.execution_status_distribution
          : {},
      bug_status_distribution:
        current.bug_status_distribution && typeof current.bug_status_distribution === 'object'
          ? current.bug_status_distribution
          : {},
      review_status_distribution:
        current.review_status_distribution && typeof current.review_status_distribution === 'object'
          ? current.review_status_distribution
          : {},
      requirement_summary: {
        testcase_count: Number(requirementSummary.testcase_count || 0),
        linked_document_count: Number(requirementSummary.linked_document_count || 0),
        linked_module_count: Number(requirementSummary.linked_module_count || 0),
        traceable_testcase_count: Number(requirementSummary.traceable_testcase_count || 0),
        unlinked_testcase_count: Number(requirementSummary.unlinked_testcase_count || 0),
        project_latest_document_count: Number(requirementSummary.project_latest_document_count || 0),
        documents: normalizeArray(requirementSummary.documents),
        modules: normalizeArray(requirementSummary.modules),
      },
      bug_workflow_summary: {
        bug_count: Number(bugWorkflowSummary.bug_count || 0),
        fixed_bug_count: Number(bugWorkflowSummary.fixed_bug_count || 0),
        submitted_retest_bug_count: Number(bugWorkflowSummary.submitted_retest_bug_count || 0),
        closed_bug_count: Number(bugWorkflowSummary.closed_bug_count || 0),
        confirmed_bug_count: Number(bugWorkflowSummary.confirmed_bug_count || 0),
        reactivated_bug_count: Number(bugWorkflowSummary.reactivated_bug_count || 0),
        retest_failed_total_count: Number(bugWorkflowSummary.retest_failed_total_count || 0),
        bugs_with_failed_retest: normalizeArray(bugWorkflowSummary.bugs_with_failed_retest),
        top_retest_failed_bugs: normalizeArray(bugWorkflowSummary.top_retest_failed_bugs),
      },
      report_standard: {
        ...standard,
        basic_info: {
          report_no: normalizeString(basicInfo.report_no, '-'),
          report_version: normalizeString(basicInfo.report_version, '-'),
          report_date: normalizeString(basicInfo.report_date, '-'),
          author: normalizeString(basicInfo.author, '-'),
          owner: normalizeString(basicInfo.owner, '-'),
          reviewer: normalizeString(basicInfo.reviewer, '-'),
        },
        test_overview: {
          test_object: normalizeString(testOverview.test_object, '-'),
          target_version: normalizeString(testOverview.target_version, '-'),
          scope_included: normalizeString(testOverview.scope_included, '-'),
          scope_excluded: normalizeString(testOverview.scope_excluded, '-'),
          objectives: normalizeArray(testOverview.objectives),
        },
        environment: {
          hardware_network: normalizeString(environment.hardware_network, '-'),
          software_environment: normalizeString(environment.software_environment, '-'),
          test_tools: normalizeArray(environment.test_tools),
          third_party_services: normalizeString(environment.third_party_services, '-'),
        },
        activity_summary: {
          test_types: normalizeArray(activitySummary.test_types),
          test_round: normalizeString(activitySummary.test_round, '-'),
          time_span: {
            start: activityTimeSpan.start || null,
            end: activityTimeSpan.end || null,
          },
          workload: {
            person_days: normalizeString(activityWorkload.person_days, '-'),
            total_cases: normalizeNumber(activityWorkload.total_cases),
            executed_cases: normalizeNumber(activityWorkload.executed_cases),
            automation_ratio: normalizeString(activityWorkload.automation_ratio, '-'),
            bug_count: normalizeNumber(activityWorkload.bug_count),
          },
        },
        result_details: {
          case_execution: {
            total: normalizeNumber(caseExecution.total),
            passed: normalizeNumber(caseExecution.passed),
            failed: normalizeNumber(caseExecution.failed),
            blocked: normalizeNumber(caseExecution.blocked),
            not_executed: normalizeNumber(caseExecution.not_executed),
            pass_rate: normalizeNumber(caseExecution.pass_rate),
          },
          execution_breakdown: normalizeArray(resultDetails.execution_breakdown),
        },
        defect_summary: {
          by_severity: normalizeArray(defectSummary.by_severity),
          by_status: normalizeArray(defectSummary.by_status),
          by_module: normalizeArray(defectSummary.by_module),
          trend_summary: {
            discovered: normalizeNumber(defectTrendSummary.discovered),
            closed: normalizeNumber(defectTrendSummary.closed),
            reactivated: normalizeNumber(defectTrendSummary.reactivated),
            retest_failed_total: normalizeNumber(defectTrendSummary.retest_failed_total),
          },
          legacy_defects: normalizeArray(defectSummary.legacy_defects),
        },
        quality_conclusion: {
          rating: normalizeString(qualityConclusion.rating, '-'),
          release_recommendation: normalizeString(qualityConclusion.release_recommendation, '-'),
          criteria: normalizeArray(qualityConclusion.criteria),
          conclusion: normalizeString(qualityConclusion.conclusion, '-'),
        },
        risk_and_suggestions: {
          process_risks: normalizeArray(riskAndSuggestions.process_risks),
          residual_risks: normalizeArray(riskAndSuggestions.residual_risks),
          follow_up_actions: normalizeArray(riskAndSuggestions.follow_up_actions),
        },
        appendices: {
          defect_list_summary: {
            total: normalizeNumber(defectListSummary.total),
            open_total: normalizeNumber(defectListSummary.open_total),
            items: normalizeArray(defectListSummary.items),
          },
          key_testcases: normalizeArray(appendices.key_testcases),
          requirement_documents: normalizeArray(appendices.requirement_documents),
          test_data_note: normalizeString(appendices.test_data_note, '-'),
        },
      },
    };
  }
  return current as AiIterationTestReport;
};

const toSnapshot = (item: {
  id: number;
  title: string;
  project: number;
  suite_ids?: number[];
  creator_name?: string;
  is_pinned?: boolean;
  report_data: AiIterationTestReport;
  created_at: string;
}) => {
  const report = normalizeReportPayload(item.report_data);
  return {
    id: item.id,
    title: item.title,
    projectId: item.project,
    suiteIds: item.suite_ids || [],
    creatorName: item.creator_name || '-',
    isPinned: Boolean(item.is_pinned),
    generatedAt: report?.generated_at || item.created_at,
    generatedAtText: formatDateTime(report?.generated_at || item.created_at),
    sourcePriority: getGenerationSourcePriority(report),
    report,
  };
};

const getSnapshotSummaryMeta = (snapshot: ReportSnapshot): SnapshotSummaryMeta => ({
  sourceLabel: getGenerationSourceLabel(snapshot.report),
  statusText: getGenerationStatusText(snapshot.report),
  durationText: formatDuration(snapshot.report.generation_duration_ms),
});

const buildTree = (parentId: number | null = null): SuiteTreeNode[] =>
  suites.value
    .filter((suite) => (suite.parent ?? suite.parent_id ?? null) === parentId)
    .map((suite) => ({
      id: suite.id,
      key: suite.id,
      name: suite.name,
      testcase_count: suite.testcase_count || 0,
      children: buildTree(suite.id),
    }));

const treeData = computed(() => buildTree());

const overviewCards = computed(() => {
  if (!reportData.value) {
    return [];
  }
  const standard = reportData.value.report_standard;
  const traceableCount = Number(reportData.value.requirement_summary.traceable_testcase_count || 0);
  const totalCases = Number(reportData.value.testcase_count || 0);
  const unlinkedCount = Number(reportData.value.requirement_summary.unlinked_testcase_count || 0);
  const closedBugCount = Number(reportData.value.bug_workflow_summary.closed_bug_count || 0);
  const totalBugCount = Number(reportData.value.bug_count || 0);
  const criteria = standard.quality_conclusion.criteria || [];
  const passedCriteria = criteria.filter((item: { passed: boolean }) => item.passed).length;
  const blockers = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && isBlockingCriteria(item.name)).length;
  const conditions = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && !isBlockingCriteria(item.name)).length;

  return [
    {
      kicker: 'GATE',
      label: '发布门槛',
      value: `${passedCriteria}/${criteria.length || 0}`,
      footnote:
        blockers > 0
          ? `当前仍有 ${blockers} 项阻断因素未消除`
          : conditions > 0
            ? `当前仍有 ${conditions} 项条件因素待跟进`
            : '当前关键完成标准已全部满足',
      compact: false,
    },
    {
      kicker: 'TRACEABILITY',
      label: '需求追踪',
      value: `${traceableCount}/${totalCases}`,
      footnote:
        unlinkedCount > 0 ? `仍有 ${unlinkedCount} 条用例未建立需求追踪` : '需求追踪关系已完整建立',
      compact: false,
    },
    {
      kicker: 'CLOSURE',
      label: '缺陷闭环',
      value: `${closedBugCount}/${totalBugCount}`,
      footnote:
        standard.appendices.defect_list_summary.open_total > 0
          ? `已关闭 ${closedBugCount} 个，仍有 ${standard.appendices.defect_list_summary.open_total} 个未关闭`
          : '当前缺陷已全部进入关闭状态',
      compact: false,
    },
    {
      kicker: 'SCOPE',
      label: '覆盖套件',
      value: `${reportData.value.suite_count}`,
      footnote: `由 ${reportData.value.selected_suite_count} 个根套件联动汇总本轮测试范围`,
      compact: false,
    },
  ];
});

const executionCoverageRate = computed(() => {
  if (!reportData.value) {
    return '0%';
  }
  const workload = reportData.value.report_standard.activity_summary.workload;
  const totalCases = Number(workload.total_cases || 0);
  const executedCases = Number(workload.executed_cases || 0);
  if (totalCases <= 0) {
    return '0%';
  }
  const coverage = (executedCases / totalCases) * 100;
  return Number.isInteger(coverage) ? `${coverage}%` : `${coverage.toFixed(1)}%`;
});

const criteriaCompletionSummary = computed(() => {
  if (!reportData.value) {
    return {
      value: '0/0',
      footnote: '当前暂无完成标准数据',
    };
  }
  const criteria = reportData.value.report_standard.quality_conclusion.criteria || [];
  const passed = criteria.filter((item: { passed: boolean }) => item.passed).length;
  const blockers = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && isBlockingCriteria(item.name)).length;
  const conditions = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && !isBlockingCriteria(item.name)).length;

  let footnote = '当前关键完成标准已全部满足';
  if (blockers > 0) {
    footnote = `仍有 ${blockers} 项阻断项需要先关闭`;
  } else if (conditions > 0) {
    footnote = `仍有 ${conditions} 项条件项需要同步跟进`;
  }

  return {
    value: `${passed}/${criteria.length}`,
    footnote,
  };
});

const releaseDecisionFootnote = computed(() => {
  if (!reportData.value) {
    return '';
  }
  const criteria = reportData.value.report_standard.quality_conclusion.criteria || [];
  const blockers = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && isBlockingCriteria(item.name)).length;
  const conditions = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && !isBlockingCriteria(item.name)).length;
  const rating = reportData.value.report_standard.quality_conclusion.rating;
  if (blockers > 0) {
    return `质量评级 ${rating}，当前仍有 ${blockers} 项阻断因素未消除。`;
  }
  if (conditions > 0) {
    return `质量评级 ${rating}，当前仍有 ${conditions} 项条件因素待跟进。`;
  }
  return `质量评级 ${rating}，当前关键完成标准已全部满足。`;
});

const generationInsight = computed(() => {
  if (!reportData.value) {
    return null;
  }
  const report = reportData.value;
  return {
    status: getGenerationAlertStatus(report),
    title: getGenerationAlertTitle(report),
    description:
      report.note ||
      `${getGenerationSourceLabel(report)}，耗时 ${formatDuration(report.generation_duration_ms)}。`,
  };
});

const criteriaSummary = computed(() => {
  if (!reportData.value) {
    return {
      blockers: [] as CriteriaSummaryItem[],
      conditions: [] as CriteriaSummaryItem[],
      passed: [] as CriteriaSummaryItem[],
    };
  }

  const criteria = reportData.value.report_standard.quality_conclusion.criteria || [];
  const blockers: CriteriaSummaryItem[] = [];
  const conditions: CriteriaSummaryItem[] = [];
  const passed: CriteriaSummaryItem[] = [];

  criteria.forEach((item: { name: string; detail: string; passed: boolean }) => {
    if (item.passed) {
      passed.push({ ...item, tone: 'success', toneLabel: '已达成' });
    } else if (isBlockingCriteria(item.name)) {
      blockers.push({ ...item, tone: 'danger', toneLabel: '阻断发布' });
    } else {
      conditions.push({ ...item, tone: 'warning', toneLabel: '需补齐' });
    }
  });

  return { blockers, conditions, passed };
});

const criteriaSummaryCards = computed(() => [
  {
    key: 'blockers',
    title: '阻断项',
    count: criteriaSummary.value.blockers.length,
    tone: 'danger' as const,
    description: '这些项未达成时，当前版本不应进入发布阶段。',
    items: criteriaSummary.value.blockers,
    emptyText: '当前没有阻断项',
  },
  {
    key: 'conditions',
    title: '条件项',
    count: criteriaSummary.value.conditions.length,
    tone: 'warning' as const,
    description: '这些项会影响发布条件与遗留风险说明。',
    items: criteriaSummary.value.conditions,
    emptyText: '当前没有条件项',
  },
  {
    key: 'passed',
    title: '已达成',
    count: criteriaSummary.value.passed.length,
    tone: 'success' as const,
    description: '这些项已满足，可作为当前测试结论的正向依据。',
    items: criteriaSummary.value.passed,
    emptyText: '当前没有已达成项',
  },
]);

const conclusionOverviewCards = computed(() => {
  if (!reportData.value) {
    return [];
  }
  const criteria = reportData.value.report_standard.quality_conclusion.criteria || [];
  const blockers = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && isBlockingCriteria(item.name));
  const conditions = criteria.filter((item: { name: string; passed: boolean }) => !item.passed && !isBlockingCriteria(item.name));
  const passed = criteria.filter((item: { passed: boolean }) => item.passed);
  const openBugTotal = Number(reportData.value.report_standard.appendices.defect_list_summary.open_total || 0);
  const retestFailedTotal = Number(reportData.value.report_standard.defect_summary.trend_summary.retest_failed_total || 0);
  const pendingCount = blockers.length + conditions.length;

  return [
    {
      label: '完成标准',
      value: `${passed.length}/${criteria.length}`,
      footnote: criteria.length > 0 ? `当前已达成 ${passed.length} 项完成标准` : '当前暂无完成标准数据',
    },
    {
      label: '待跟进项',
      value: `${pendingCount}`,
      footnote:
        blockers.length > 0
          ? `其中阻断项 ${blockers.length} 个，需优先关闭`
          : conditions.length > 0
            ? `当前有 ${conditions.length} 个条件项待补齐`
            : '当前无额外待跟进项',
    },
    {
      label: '遗留缺陷',
      value: `${openBugTotal}`,
      footnote: `未关闭 BUG ${openBugTotal} 个，复测失败 ${retestFailedTotal} 次`,
    },
  ];
});

const riskOverviewCards = computed(() => {
  if (!reportData.value) {
    return [];
  }
  const risk = reportData.value.report_standard.risk_and_suggestions;
  return [
    {
      label: '过程风险',
      value: `${risk.process_risks.length}`,
      footnote: risk.process_risks.length > 0 ? '测试执行过程中仍有不确定因素需要关注' : '当前测试过程已相对稳定',
    },
    {
      label: '剩余风险',
      value: `${risk.residual_risks.length}`,
      footnote: risk.residual_risks.length > 0 ? '上线后仍需接受或持续跟进的风险项' : '当前未识别额外剩余风险',
    },
    {
      label: '后续动作',
      value: `${risk.follow_up_actions.length}`,
      footnote: risk.follow_up_actions.length > 0 ? '建议按优先级推进后续闭环动作' : '当前暂无新增后续动作',
    },
  ];
});

const supportSummaryItems = computed(() => {
  if (!reportData.value) {
    return [];
  }
  return [
    { label: '需求文档覆盖', value: `${reportData.value.requirement_summary.linked_document_count}` },
    { label: '未追踪用例', value: `${reportData.value.requirement_summary.unlinked_testcase_count}` },
    { label: '复测失败 BUG', value: `${reportData.value.bug_workflow_summary.retest_failed_total_count}` },
  ];
});

const conclusionReasons = computed<ConclusionReasonItem[]>(() => {
  if (!reportData.value) {
    return [];
  }
  return buildConclusionReasonsSnapshot(reportData.value);
});

const releaseChecklist = computed<ReleaseChecklistItem[]>(() => {
  if (!reportData.value) {
    return [];
  }
  return buildExecutiveSummarySnapshot(reportData.value).releaseChecklist.map((item) => ({
    title: item.title,
    detail: item.detail,
    priority: item.priority,
  }));
});

function formatDateTime(value?: string | null) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatDuration(value?: number | null) {
  const durationMs = Number(value || 0);
  if (!Number.isFinite(durationMs) || durationMs <= 0) {
    return '耗时未记录';
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 0 : 1)} 秒`;
}

function formatDisplayList(items?: Array<string | null | undefined>, fallback = '-') {
  const normalized = normalizeArray(items).map((item) => `${item ?? ''}`.trim()).filter(Boolean);
  return normalized.length > 0 ? normalized.join('、') : fallback;
}

function getGenerationSourceLabel(report: AiIterationTestReport) {
  if (report.generation_source === 'fallback') return 'AI失败后回退';
  if (report.generation_source === 'ai' || report.used_ai) return 'AI生成';
  return '规则生成';
}

function getGenerationSourceColor(report: AiIterationTestReport) {
  if (report.generation_source === 'fallback') return 'orange';
  if (report.generation_source === 'ai' || report.used_ai) return 'arcoblue';
  return 'gold';
}

function getGenerationSourcePriority(report: AiIterationTestReport) {
  if (report.generation_source === 'ai' || report.used_ai) return 0;
  if (report.generation_source === 'fallback') return 1;
  return 2;
}

function matchSnapshotSourceFilter(
  snapshot: ReportSnapshot,
  filter: 'all' | 'ai' | 'fallback' | 'rule' | 'pinned'
) {
  if (filter === 'all') return true;
  if (filter === 'pinned') return snapshot.isPinned;
  if (filter === 'ai') return snapshot.report.generation_source === 'ai' || snapshot.report.used_ai;
  if (filter === 'fallback') return snapshot.report.generation_source === 'fallback';
  return snapshot.report.generation_source === 'rule' && !snapshot.report.used_ai;
}

function getSnapshotTimestamp(snapshot: ReportSnapshot) {
  const timestamp = new Date(snapshot.generatedAt).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function findNearestComparableSnapshot() {
  const candidates = reportSnapshots.value.filter((item) => item.id !== activeSnapshotId.value);
  if (candidates.length === 0) {
    return null;
  }

  const currentTimestamp = reportData.value ? new Date(reportData.value.generated_at).getTime() : NaN;
  if (!Number.isFinite(currentTimestamp)) {
    return candidates[0];
  }

  const olderCandidates = candidates
    .filter((item) => getSnapshotTimestamp(item) <= currentTimestamp)
    .sort((left, right) => getSnapshotTimestamp(right) - getSnapshotTimestamp(left));
  if (olderCandidates.length > 0) {
    return olderCandidates[0];
  }

  return [...candidates].sort((left, right) => {
    return Math.abs(getSnapshotTimestamp(left) - currentTimestamp) - Math.abs(getSnapshotTimestamp(right) - currentTimestamp);
  })[0];
}

function buildSnapshotTitle(report: AiIterationTestReport, suites: TestSuite[], mode: 'auto' | 'manual') {
  const selectedIds = Array.isArray(report.suite_ids) ? report.suite_ids : [];
  const selectedSuites = suites.filter((suite) => selectedIds.includes(suite.id));
  const suiteLabel =
    selectedSuites.length === 0
      ? `${Number(report.selected_suite_count || 0)}个套件`
      : selectedSuites.length === 1
        ? selectedSuites[0].name
        : `${selectedSuites[0].name}等${selectedSuites.length}个套件`;
  const sourceLabel = getGenerationSourceLabel(report);
  const generatedAt = formatDateTime(report.generated_at).replace(/\//g, '-');
  return mode === 'manual'
    ? `手动保存 ${suiteLabel} ${generatedAt}`
    : `${sourceLabel} ${suiteLabel} ${generatedAt}`;
}

function getGenerationStatusText(report: AiIterationTestReport) {
  if (report.generation_source === 'fallback') {
    return 'AI调用失败，已自动回退';
  }
  if (report.generation_source === 'ai' || report.used_ai) {
    return '已完成 AI 分析';
  }
  return report.model_name ? '未走 AI，直接按规则生成' : '当前未配置可用模型，按规则生成';
}

function getGenerationAlertStatus(report: AiIterationTestReport): 'success' | 'warning' | 'normal' {
  if (report.generation_source === 'fallback') return 'warning';
  if (report.generation_source === 'ai' || report.used_ai) return 'success';
  return 'normal';
}

function getGenerationAlertTitle(report: AiIterationTestReport) {
  if (report.generation_source === 'fallback') return '本次 AI 分析失败，已自动切换为规则生成';
  if (report.generation_source === 'ai' || report.used_ai) return '本次测试报告已通过 AI 分析生成';
  return report.model_name ? '本次测试报告未采用 AI 结果' : '当前未配置可用模型，已按规则生成报告';
}

function isBlockingCriteria(name: string) {
  return [
    '测试范围内至少已有有效执行结果',
    '无未关闭致命/严重缺陷',
    '核心测试执行失败数为 0',
    '测试用例均已审核通过',
  ].includes(name);
}

function getCriteriaSectionColor(tone: 'danger' | 'warning' | 'success'): 'danger' | 'warning' | 'success' {
  if (tone === 'danger') return 'danger';
  if (tone === 'warning') return 'warning';
  return 'success';
}

function scrollToReportSection(id: string) {
  if (typeof document === 'undefined') {
    return;
  }
  const target = document.getElementById(id);
  if (!target) {
    return;
  }
  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadReportSnapshots() {
  if (!currentProjectId.value) {
    reportSnapshots.value = [];
    activeSnapshotId.value = null;
    return;
  }

  const response = await getTestReportSnapshots(currentProjectId.value);
  if (!response.success) {
    Message.error(response.error || '加载报告快照失败');
    reportSnapshots.value = [];
    return;
  }

  reportSnapshots.value = normalizeSnapshots((response.data || []).map((item) => toSnapshot(item)));

  if (activeSnapshotId.value) {
    const matched = reportSnapshots.value.find((item) => item.id === activeSnapshotId.value);
    if (matched) {
      reportData.value = matched.report;
      return;
    }
    activeSnapshotId.value = null;
  }

  if (!reportData.value && reportSnapshots.value.length > 0) {
    applyReportSnapshot(reportSnapshots.value[0], false);
  }
}

async function createReportSnapshot(
  report: AiIterationTestReport,
  useCurrentTitle = true,
  options: {
    silent?: boolean;
  } = {}
) {
  if (!currentProjectId.value) {
    return null;
  }

  const title = buildSnapshotTitle(report, suites.value, useCurrentTitle ? 'auto' : 'manual');

  const response = await createTestReportSnapshot(currentProjectId.value, {
    title,
    suite_ids: [...checkedSuiteIds.value],
    report_data: JSON.parse(JSON.stringify(report)),
  });

  if (!response.success || !response.data) {
    if (!options.silent) {
      Message.error(response.error || '保存报告快照失败');
    }
    return null;
  }

  const snapshot = toSnapshot(response.data);
  reportSnapshots.value = normalizeSnapshots(
    [snapshot, ...reportSnapshots.value.filter((item) => item.id !== snapshot.id)].slice(0, 20)
  );
  activeSnapshotId.value = snapshot.id;
  return snapshot;
}

function persistReportSnapshotInBackground(report: AiIterationTestReport) {
  void createReportSnapshot(report, true, { silent: true }).catch((error) => {
    console.error('自动保存报告快照失败:', error);
    Message.warning('测试报告已生成，但自动保存快照失败，可手动点击保存');
  });
}
function applyReportSnapshot(snapshot: ReportSnapshot, showMessage = true) {
  cancelRenameSnapshot();
  reportData.value = snapshot.report;
  checkedKeys.value = [...snapshot.suiteIds];
  expandedKeys.value = Array.from(new Set([...expandedKeys.value, ...snapshot.suiteIds]));
  activeSnapshotId.value = snapshot.id;
  if (showMessage) {
    Message.success('报告快照已加载');
  }
}

async function patchSnapshot(
  snapshotId: number,
  payload: {
    title?: string;
    is_pinned?: boolean;
    suite_ids?: number[];
    report_data?: AiIterationTestReport;
  }
) {
  if (!currentProjectId.value) {
    return null;
  }

  const response = await updateTestReportSnapshot(currentProjectId.value, snapshotId, payload);
  if (!response.success || !response.data) {
    Message.error(response.error || '更新报告快照失败');
    return null;
  }

  const nextItem = toSnapshot(response.data);
  reportSnapshots.value = normalizeSnapshots(
    reportSnapshots.value.map((item) => (item.id === snapshotId ? nextItem : item))
  );

  if (activeSnapshotId.value === snapshotId) {
    reportData.value = nextItem.report;
  }

  return nextItem;
}

function startRenameSnapshot(snapshot: ReportSnapshot) {
  editingSnapshotId.value = snapshot.id;
  editingSnapshotTitle.value = snapshot.title;
}

function cancelRenameSnapshot() {
  editingSnapshotId.value = null;
  editingSnapshotTitle.value = '';
}

async function submitRenameSnapshot(snapshot: ReportSnapshot) {
  const nextTitle = editingSnapshotTitle.value.trim();
  if (!nextTitle) {
    Message.warning('快照标题不能为空');
    return;
  }

  const updated = await patchSnapshot(snapshot.id, { title: nextTitle });
  if (!updated) {
    return;
  }

  cancelRenameSnapshot();
  Message.success('快照名称已更新');
}

async function handleTogglePinSnapshot(snapshot: ReportSnapshot) {
  const updated = await patchSnapshot(snapshot.id, { is_pinned: !snapshot.isPinned });
  if (updated) {
    Message.success(updated.isPinned ? '快照已置顶' : '快照已取消置顶');
  }
}

async function removeReportSnapshot(snapshotId: number) {
  if (!currentProjectId.value) {
    return;
  }

  Modal.confirm({
    title: '确认删除',
    content: '删除后不可恢复，确定删除这条报告快照吗？',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      const response = await deleteTestReportSnapshot(currentProjectId.value!, snapshotId);
      if (!response.success) {
        Message.error(response.error || '删除报告快照失败');
        return;
      }

      reportSnapshots.value = reportSnapshots.value.filter((item) => item.id !== snapshotId);
      if (activeSnapshotId.value === snapshotId) {
        activeSnapshotId.value = null;
        reportData.value = null;
        if (reportSnapshots.value.length > 0) {
          applyReportSnapshot(reportSnapshots.value[0], false);
        }
      }
      Message.success('报告快照已删除');
    },
  });
}

async function clearReportSnapshots() {
  if (!currentProjectId.value || reportSnapshots.value.length === 0) {
    return;
  }

  Modal.confirm({
    title: '确认清空',
    content: '将清空当前项目下最近保存的报告快照，确定继续吗？',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      const snapshotIds = reportSnapshots.value.map((item) => item.id);
      for (const snapshotId of snapshotIds) {
        const response = await deleteTestReportSnapshot(currentProjectId.value!, snapshotId);
        if (!response.success) {
          Message.error(response.error || '清空报告快照失败');
          return;
        }
      }

      reportSnapshots.value = [];
      reportData.value = null;
      activeSnapshotId.value = null;
      cancelRenameSnapshot();
      Message.success('报告快照已清空');
    },
  });
}

async function handleSaveSnapshot() {
  if (!reportData.value) {
    Message.warning('当前没有可保存的测试报告');
    return;
  }

  const snapshot = await createReportSnapshot(reportData.value, false);
  if (snapshot) {
    Message.success('报告快照已保存');
  }
}

async function handleOverwriteSnapshot() {
  if (!reportData.value || !activeSnapshotId.value) {
    Message.warning('请先加载一个可覆盖的报告快照');
    return;
  }

  Modal.confirm({
    title: '确认覆盖',
    content: '将用当前报告内容覆盖这条快照，原内容会被更新，确定继续吗？',
    onOk: async () => {
      const updated = await patchSnapshot(activeSnapshotId.value!, {
        suite_ids: [...checkedSuiteIds.value],
        report_data: JSON.parse(JSON.stringify(reportData.value)),
      });
      if (!updated) {
        return;
      }
      activeSnapshotId.value = updated.id;
      reportData.value = updated.report;
      Message.success('当前快照已覆盖保存');
    },
  });
}

function applySuiteSelectionFromRoute() {
  const suiteId = Number(route.query.suiteId);
  if (!suiteId || !Number.isFinite(suiteId)) {
    return;
  }
  if (!suites.value.some((suite) => suite.id === suiteId)) {
    return;
  }
  checkedKeys.value = Array.from(new Set([suiteId, ...checkedSuiteIds.value]));
  expandedKeys.value = Array.from(new Set([suiteId, ...expandedKeys.value.map((item) => Number(item))]));
}

async function fetchSuites() {
  if (!currentProjectId.value) {
    suites.value = [];
    checkedKeys.value = [];
    expandedKeys.value = [];
    return;
  }

  suiteLoading.value = true;
  try {
    const response = await getTestSuiteList(currentProjectId.value, {
      search: searchKeyword.value.trim() || undefined,
    });
    if (response.success && response.data) {
      suites.value = response.data;
      expandedKeys.value = response.data.map((item) => item.id);
      applySuiteSelectionFromRoute();
      return;
    }
    Message.error(response.error || '获取套件列表失败');
    suites.value = [];
  } catch (error) {
    console.error('获取套件列表失败:', error);
    Message.error('获取套件列表失败');
    suites.value = [];
  } finally {
    suiteLoading.value = false;
  }
}

function checkAllSuites() {
  checkedKeys.value = suites.value.map((item) => item.id);
}

function clearCheckedSuites() {
  checkedKeys.value = [];
}

function expandAllSuites() {
  expandedKeys.value = suites.value.map((item) => item.id);
}

async function handleGenerateReport() {
  if (!currentProjectId.value) {
    Message.warning('请先选择项目');
    return;
  }

  if (checkedSuiteIds.value.length === 0) {
    Message.warning('请至少选择一个测试套件');
    return;
  }

  reportLoading.value = true;
  try {
    const response = await generateAiIterationTestReport(currentProjectId.value, checkedSuiteIds.value);
    if (response.success && response.data) {
      reportData.value = response.data;
      persistReportSnapshotInBackground(response.data);
      if (response.data.generation_source === 'fallback') {
        Message.warning('AI 分析失败，已自动回退为规则生成');
      } else if (response.data.generation_source === 'ai' || response.data.used_ai) {
        Message.success('AI 测试报告生成完成');
      } else {
        Message.success(
          response.data.model_name
            ? '未采用 AI 结果，已按规则生成测试报告'
            : '当前未配置可用模型，已按规则生成测试报告'
        );
      }
      return;
    }
    Message.error(response.error || '生成测试报告失败');
  } catch (error) {
    console.error('生成测试报告失败:', error);
    Message.error('生成测试报告失败');
  } finally {
    reportLoading.value = false;
  }
}

function getQualityRatingColor(value: string) {
  if (value === '优') return 'green';
  if (value === '良') return 'arcoblue';
  if (value === '合格') return 'orange';
  return 'red';
}

function getReleaseRecommendationColor(value: string) {
  if (value === '建议发布') return 'green';
  if (value === '有条件发布') return 'orange';
  return 'red';
}

function getSeverityLabel(value: string) {
  if (value === 'high') return '高';
  if (value === 'low') return '低';
  return '中';
}

function getPriorityLabel(value: string) {
  if (value === 'high') return '高优先级';
  if (value === 'low') return '低优先级';
  return '中优先级';
}

function buildExecutiveSummarySnapshot(report: AiIterationTestReport) {
  const standard = report.report_standard;
  const execution = standard.result_details.case_execution;
  const openBugTotal = Number(standard.appendices.defect_list_summary.open_total || 0);
  const retestFailedTotal = Number(standard.defect_summary.trend_summary.retest_failed_total || 0);
  const criteria = standard.quality_conclusion.criteria || [];
  const blockers = criteria.filter((item) => !item.passed && isBlockingCriteria(item.name));
  const conditions = criteria.filter((item) => !item.passed && !isBlockingCriteria(item.name));
  const actions = standard.risk_and_suggestions.follow_up_actions || [];
  const releaseRecommendation = standard.quality_conclusion.release_recommendation;
  const rating = standard.quality_conclusion.rating;
  const releaseChecklist: Array<{
    title: string;
    detail: string;
    priority: 'high' | 'medium' | 'low';
    priorityLabel: string;
  }> = [];

  blockers.slice(0, 3).forEach((item) => {
    releaseChecklist.push({
      title: item.name,
      detail: item.detail,
      priority: 'high',
      priorityLabel: '高优先级',
    });
  });

  conditions.slice(0, 2).forEach((item) => {
    releaseChecklist.push({
      title: item.name,
      detail: item.detail,
      priority: 'medium',
      priorityLabel: '中优先级',
    });
  });

  actions.forEach((item) => {
    if (releaseChecklist.length >= 5) return;
    if (releaseChecklist.some((existing) => existing.detail === item || existing.title === item)) return;
    const priority = blockers.length > 0 ? 'high' : conditions.length > 0 ? 'medium' : 'low';
    releaseChecklist.push({
      title: '跟进动作',
      detail: item,
      priority,
      priorityLabel: priority === 'high' ? '高优先级' : priority === 'medium' ? '中优先级' : '低优先级',
    });
  });

  if (releaseChecklist.length === 0) {
    releaseChecklist.push({
      title: '可以进入发布评审',
      detail: '当前没有阻断项或额外条件项，建议按正常发布流程继续推进。',
      priority: 'low',
      priorityLabel: '低优先级',
    });
  }

  const summaryText =
    releaseRecommendation === '不建议发布'
      ? `当前存在 ${blockers.length} 项阻断因素，建议优先处理高风险问题后再进入发布评审。`
      : releaseRecommendation === '有条件发布'
        ? `当前不存在硬性阻断，但仍有 ${conditions.length} 项条件因素需要跟进，建议在明确责任人与时间后再推进发布。`
        : '当前关键完成标准已满足，可按正常流程进入发布评审或上线验证。';

  return {
    releaseRecommendation,
    rating,
    summaryText,
    passRate: execution.pass_rate,
    openBugTotal,
    retestFailedTotal,
    notExecuted: execution.not_executed,
    releaseChecklist: releaseChecklist.slice(0, 5),
  };
}

function buildConclusionReasonsSnapshot(report: AiIterationTestReport) {
  const standard = report.report_standard;
  const reasons: ConclusionReasonItem[] = [];
  const caseExecution = standard.result_details.case_execution;
  const defectSummary = standard.defect_summary.trend_summary;
  const openBugTotal = standard.appendices.defect_list_summary.open_total;
  const rating = standard.quality_conclusion.rating;
  const recommendation = standard.quality_conclusion.release_recommendation;
  const criteria = standard.quality_conclusion.criteria || [];
  const blockers = criteria.filter((item) => !item.passed && isBlockingCriteria(item.name));
  const conditions = criteria.filter((item) => !item.passed && !isBlockingCriteria(item.name));
  const passed = criteria.filter((item) => item.passed);

  blockers.forEach((item) => {
    reasons.push({
      title: `阻断因素：${item.name}`,
      detail: item.detail,
      tone: 'danger',
    });
  });

  conditions.forEach((item) => {
    reasons.push({
      title: `条件因素：${item.name}`,
      detail: item.detail,
      tone: 'warning',
    });
  });

  if (reasons.length === 0) {
    reasons.push({
      title: '结论依据完整',
      detail: '当前完成标准已全部达成，测试结果、需求追踪和缺陷闭环均支持当前发布结论。',
      tone: 'success',
    });
  } else {
    reasons.unshift({
      title: `当前结论为 ${rating} / ${recommendation}`,
      detail: `执行通过率 ${caseExecution.pass_rate}%，未关闭 BUG ${openBugTotal} 个，复测失败累计 ${defectSummary.retest_failed_total} 次。`,
      tone: recommendation === '不建议发布' ? 'danger' : 'warning',
    });
  }

  if (passed.length > 0) {
    const passedNames = passed.slice(0, 3).map((item) => item.name).join('、');
    reasons.push({
      title: '正向依据',
      detail: `已达成 ${passed.length} 项完成标准，当前已满足：${passedNames}${passed.length > 3 ? ' 等' : ''}。`,
      tone: 'success',
    });
  }

  return reasons;
}

function buildReportMarkdown(report: AiIterationTestReport) {
  const summary = buildExecutiveSummarySnapshot(report);
  const conclusionReasons = buildConclusionReasonsSnapshot(report);
  const basicInfo = report.report_standard.basic_info;
  const overview = report.report_standard.test_overview;
  const execution = report.report_standard.result_details.case_execution;
  const pushPrefixedList = (items: string[], prefix: string) => {
    if (items.length === 0) {
      lines.push(`- ${prefix}：无`);
      return;
    }
    items.forEach((item) => {
      lines.push(`- ${prefix}：${item}`);
    });
  };
  const lines: string[] = [
    '# 测试报告',
    '',
    `> 报告编号：${basicInfo.report_no}`,
    `> 报告版本：${basicInfo.report_version}`,
    `> 测试对象：${overview.test_object}`,
    `> 目标版本：${overview.target_version}`,
    `> 报告日期：${basicInfo.report_date}`,
    '',
    '## 封面摘要',
    `- 编写人：${basicInfo.author}`,
    `- 负责人：${basicInfo.owner}`,
    `- 审核人：${basicInfo.reviewer}`,
    `- 测试范围：${overview.scope_included}`,
    `- 发布建议：${summary.releaseRecommendation}`,
    `- 质量评级：${summary.rating}`,
    '',
    '## 管理摘要',
    '| 指标 | 结果 |',
    '| --- | --- |',
    `| 发布建议 | ${summary.releaseRecommendation} |`,
    `| 质量评级 | ${summary.rating} |`,
    `| 执行通过率 | ${summary.passRate}% |`,
    `| 未关闭 BUG | ${summary.openBugTotal} |`,
    `| 复测失败 | ${summary.retestFailedTotal} |`,
    `| 未执行用例 | ${summary.notExecuted} |`,
    '',
    `- 摘要说明：${summary.summaryText}`,
    `- 一句话结论：本轮共执行 ${execution.total} 条测试用例，当前通过率 ${summary.passRate}%，未关闭 BUG ${summary.openBugTotal} 个。`,
    '',
    '## 报告基本信息',
    `- 报告编号：${basicInfo.report_no}`,
    `- 报告版本：${basicInfo.report_version}`,
    `- 报告日期：${basicInfo.report_date}`,
    `- 编写人：${basicInfo.author}`,
    `- 负责人：${basicInfo.owner}`,
    `- 审核人：${basicInfo.reviewer}`,
    '',
    '## 测试概述',
    `- 测试对象：${overview.test_object}`,
    `- 目标版本：${overview.target_version}`,
    `- 测试范围：${overview.scope_included}`,
    `- 不在范围：${overview.scope_excluded}`,
    ...(overview.objectives.length > 0 ? overview.objectives.map((item) => `- 测试目标：${item}`) : ['- 测试目标：无']),
    '',
    '## 测试环境',
    `- 硬件/网络：${report.report_standard.environment.hardware_network}`,
    `- 软件环境：${report.report_standard.environment.software_environment}`,
    `- 第三方依赖：${report.report_standard.environment.third_party_services}`,
    `- 测试工具：${formatDisplayList(report.report_standard.environment.test_tools)}`,
    '',
    '## 测试活动摘要',
    `- 测试类型：${formatDisplayList(report.report_standard.activity_summary.test_types)}`,
    `- 测试轮次：${report.report_standard.activity_summary.test_round}`,
    `- 时间跨度：${formatDateTime(report.report_standard.activity_summary.time_span.start)} 至 ${formatDateTime(report.report_standard.activity_summary.time_span.end)}`,
    `- 工作量（人日）：${report.report_standard.activity_summary.workload.person_days}`,
    `- 执行用例总数：${report.report_standard.activity_summary.workload.total_cases}`,
    `- 已执行用例数：${report.report_standard.activity_summary.workload.executed_cases}`,
    `- 自动化占比：${report.report_standard.activity_summary.workload.automation_ratio}`,
    '',
    '## 测试结果详情',
    `- 总用例数：${report.report_standard.result_details.case_execution.total}`,
    `- 通过数：${report.report_standard.result_details.case_execution.passed}`,
    `- 失败数：${report.report_standard.result_details.case_execution.failed}`,
    `- 阻塞/无需执行数：${report.report_standard.result_details.case_execution.blocked}`,
    `- 未执行数：${report.report_standard.result_details.case_execution.not_executed}`,
    `- 通过率：${report.report_standard.result_details.case_execution.pass_rate}%`,
    ...(
      report.report_standard.result_details.execution_breakdown.length > 0
        ? report.report_standard.result_details.execution_breakdown.map((item) => `- 执行状态 ${item.name}：${item.count}`)
        : ['- 执行状态明细：无']
    ),
    '',
    '## 缺陷统计',
    ...(report.report_standard.defect_summary.by_severity.length > 0
      ? report.report_standard.defect_summary.by_severity.map((item) => `- 按严重程度 ${item.name}：${item.count}`)
      : ['- 按严重程度：无']),
    ...(report.report_standard.defect_summary.by_status.length > 0
      ? report.report_standard.defect_summary.by_status.map((item) => `- 按状态 ${item.name}：${item.count}`)
      : ['- 按状态：无']),
    ...(report.report_standard.defect_summary.by_module.length > 0
      ? report.report_standard.defect_summary.by_module.map((item) => `- 按模块 ${item.name}：${item.count}`)
      : ['- 按模块：无']),
    `- 缺陷趋势摘要：发现 ${report.report_standard.defect_summary.trend_summary.discovered} / 已关闭 ${report.report_standard.defect_summary.trend_summary.closed} / 重新激活 ${report.report_standard.defect_summary.trend_summary.reactivated} / 复测失败 ${report.report_standard.defect_summary.trend_summary.retest_failed_total}`,
    '',
    '## 报告生成摘要',
    `- 生成时间：${formatDateTime(report.generated_at)}`,
    `- 生成方式：${getGenerationSourceLabel(report)}`,
    `- 生成状态：${getGenerationStatusText(report)}`,
    `- 生成耗时：${formatDuration(report.generation_duration_ms)}`,
    ...(report.fallback_reason ? [`- 回退原因：${report.fallback_reason}`] : []),
    `- 套件总数：${report.suite_count}`,
    `- 测试用例总数：${report.testcase_count}`,
    `- BUG 总数：${report.bug_count}`,
    `- 本次选择套件数：${report.selected_suite_count}`,
    '',
    '## 执行摘要',
    report.summary || '-',
    '',
    '## 质量概览',
    report.quality_overview || '-',
    '',
    '## 风险概览',
    report.risk_overview || '-',
    '',
    '## 结论依据',
  ];

  if (conclusionReasons.length === 0) {
    lines.push('- 无');
  } else {
    conclusionReasons.forEach((item) => {
      lines.push(`- ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 关键发现');
  if (report.findings.length === 0) {
    lines.push('- 无');
  } else {
    report.findings.forEach((item) => {
      lines.push(`- [${getSeverityLabel(item.severity)}] ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 遗留缺陷');
  if (report.report_standard.defect_summary.legacy_defects.length === 0) {
    lines.push('- 当前无遗留缺陷');
  } else {
    report.report_standard.defect_summary.legacy_defects.forEach((item) => {
      lines.push(`- BUG#${item.id} ${item.title}：${item.severity} / ${item.status} / 模块 ${item.module} / 计划修复 ${item.planned_fix_version} / 风险接受理由 ${item.risk_acceptance}`);
      lines.push(`  - 影响范围：${item.impact_scope}`);
      lines.push(`  - 复现步骤：${item.repro_steps}`);
    });
  }

  lines.push('', '## 改进建议');
  if (report.recommendations.length === 0) {
    lines.push('- 无');
  } else {
    report.recommendations.forEach((item) => {
      lines.push(`- [${getPriorityLabel(item.priority)}] ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 发布前待办');
  if (summary.releaseChecklist.length === 0) {
    lines.push('- 无');
  } else {
    summary.releaseChecklist.forEach((item, index) => {
      lines.push(`${index + 1}. [${item.priorityLabel}] ${item.title}：${item.detail}`);
    });
  }

  lines.push('', '## 需求覆盖情况');
  lines.push(
    `- 关联需求文档数：${report.requirement_summary.linked_document_count}`,
    `- 关联需求模块数：${report.requirement_summary.linked_module_count}`,
    `- 可追踪测试用例数：${report.requirement_summary.traceable_testcase_count}`,
    `- 未关联测试用例数：${report.requirement_summary.unlinked_testcase_count}`
  );
  if (report.requirement_summary.documents.length > 0) {
    report.requirement_summary.documents.forEach((item) => {
      lines.push(`- 文档 ${item.title}：版本 ${item.version || '-'} / 状态 ${item.status || '-'} / 关联用例 ${item.linked_testcase_count} / 模块 ${item.module_count}`);
    });
  } else {
    lines.push('- 需求文档明细：无');
  }
  if (report.requirement_summary.modules.length > 0) {
    lines.push('', '### 需求模块');
    report.requirement_summary.modules.forEach((item) => {
      lines.push(`- ${item.document_title} / ${item.title}：关联用例 ${item.matched_testcase_count}${item.content_excerpt ? ` / 摘要 ${item.content_excerpt}` : ''}`);
    });
  } else {
    lines.push('- 需求模块明细：无');
  }

  lines.push('', '## BUG 流程摘要');
  lines.push(
    `- 已修复 BUG 数：${report.bug_workflow_summary.fixed_bug_count}`,
    `- 待复测 BUG 数：${report.bug_workflow_summary.submitted_retest_bug_count}`,
    `- 已关闭 BUG 数：${report.bug_workflow_summary.closed_bug_count}`,
    `- 已确认 BUG 数：${report.bug_workflow_summary.confirmed_bug_count}`,
    `- 已激活 BUG 数：${report.bug_workflow_summary.reactivated_bug_count}`,
    `- 复测失败总次数：${report.bug_workflow_summary.retest_failed_total_count}`
  );
  if (report.bug_workflow_summary.top_retest_failed_bugs.length > 0) {
    lines.push('', '### 复测失败 TOP BUG');
    report.bug_workflow_summary.top_retest_failed_bugs.forEach((item) => {
      lines.push(`- ${item.title}：复测失败 ${item.failed_retest_count} 次 / 当前状态 ${item.status} / 套件 ${item.suite || '-'} / 修复次数 ${item.fix_count} / 解决次数 ${item.resolve_count}`);
    });
  } else {
    lines.push('- 复测失败 TOP BUG：无');
  }

  lines.push('', '## 测试结论');
  lines.push(`- 质量评级：${report.report_standard.quality_conclusion.rating}`);
  lines.push(`- 发布建议：${report.report_standard.quality_conclusion.release_recommendation}`);
  lines.push(`- 结论陈述：${report.report_standard.quality_conclusion.conclusion}`);
  if (report.report_standard.quality_conclusion.criteria.length === 0) {
    lines.push('- 完成标准：无');
  } else {
    report.report_standard.quality_conclusion.criteria.forEach((item) => {
      lines.push(`- 完成标准 ${item.name}：${item.passed ? '达成' : '未达成'}，${item.detail}`);
    });
  }

  lines.push('', '## 风险与建议');
  pushPrefixedList(report.report_standard.risk_and_suggestions.process_risks, '测试过程风险');
  pushPrefixedList(report.report_standard.risk_and_suggestions.residual_risks, '剩余风险');
  pushPrefixedList(report.report_standard.risk_and_suggestions.follow_up_actions, '后续行动建议');

  lines.push('', '## 套件覆盖详情');
  if (report.suite_breakdown.length === 0) {
    lines.push('- 当前无套件覆盖详情');
  } else {
    report.suite_breakdown.forEach((item) => {
      lines.push(`- ${item.path}：测试用例 ${item.testcase_count} / 已审核 ${item.approved_testcase_count} / 失败 ${item.failed_testcase_count} / 未执行 ${item.not_executed_testcase_count} / BUG ${item.bug_count} / 待复测 ${item.pending_retest_bug_count}`);
    });
  }

  lines.push('', '## 附录与附件');
  lines.push(`- 缺陷清单摘要：总数 ${report.report_standard.appendices.defect_list_summary.total} / 未关闭 ${report.report_standard.appendices.defect_list_summary.open_total}`);
  if (report.report_standard.appendices.key_testcases.length === 0) {
    lines.push('- 关键测试用例：无');
  } else {
    report.report_standard.appendices.key_testcases.forEach((item) => {
      lines.push(`- 关键测试用例 ${item.name}：${item.module || '-'} / ${item.test_type} / ${item.execution_status}`);
    });
  }
  if (report.report_standard.appendices.requirement_documents.length === 0) {
    lines.push('- 需求文档：无');
  } else {
    report.report_standard.appendices.requirement_documents.forEach((item) => {
      lines.push(`- 需求文档 ${item.title}：${item.version || '-'} / ${item.status || '-'}`);
    });
  }
  lines.push(`- 测试数据说明：${report.report_standard.appendices.test_data_note}`);

  lines.push('', '## 证据与附件');
  if (report.evidence.length === 0) {
    lines.push('- 无');
  } else {
    report.evidence.forEach((item) => {
      lines.push(`- ${item.label}：${item.detail}`);
    });
  }

  lines.push('', '## 报告结语');
  lines.push(`- 最终发布建议：${summary.releaseRecommendation}`);
  lines.push(`- 最终质量评级：${summary.rating}`);
  lines.push(`- 结论摘要：${summary.summaryText}`);
  lines.push('- 评审说明：建议结合发布前待办、未关闭 BUG、复测失败记录与剩余风险说明，完成本轮版本发布评审。');

  return lines.join('\n');
}

async function handleCopyReportSummary() {
  if (!reportData.value) {
    Message.warning('当前没有可复制的测试报告');
    return;
  }

  const summaryText = buildReportMarkdown(reportData.value);
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(summaryText);
    } else {
      const textArea = document.createElement('textarea');
      textArea.value = summaryText;
      textArea.style.position = 'fixed';
      textArea.style.opacity = '0';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
    Message.success('测试报告摘要已复制');
  } catch (error) {
    console.error('复制测试报告失败:', error);
    Message.error('复制测试报告失败');
  }
}

function handleExportReport() {
  if (!reportData.value) {
    Message.warning('当前没有可导出的测试报告');
    return;
  }

  const blob = new Blob([buildReportMarkdown(reportData.value)], {
    type: 'text/markdown;charset=utf-8',
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  const date = new Date();
  const fileName = `测试报告_${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}_${String(date.getHours()).padStart(2, '0')}${String(date.getMinutes()).padStart(2, '0')}.md`;
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
  Message.success('测试报告已导出');
}

onMounted(() => {
  fetchSuites();
  void loadReportSnapshots();
});

watch(
  () => currentProjectId.value,
  (projectId) => {
    if (!projectId) {
      suites.value = [];
      checkedKeys.value = [];
      expandedKeys.value = [];
      reportData.value = null;
      reportSnapshots.value = [];
      activeSnapshotId.value = null;
      cancelRenameSnapshot();
      return;
    }
    fetchSuites();
    void loadReportSnapshots();
  }
);

watch(
  () => route.query.suiteId,
  () => {
    applySuiteSelectionFromRoute();
  }
);

watch(
  () => [reportSnapshots.value.map((item) => item.id).join(','), activeSnapshotId.value],
  () => {
    if (
      selectedCompareSnapshotId.value !== 'auto' &&
      !reportSnapshots.value.some((item) => item.id === selectedCompareSnapshotId.value) 
    ) {
      selectedCompareSnapshotId.value = 'auto';
    }
    if (selectedCompareSnapshotId.value === activeSnapshotId.value) {
      selectedCompareSnapshotId.value = 'auto';
    }
  }
);
</script>

<style scoped>
.test-report-view {
  height: 100%;
  background:
    linear-gradient(180deg, #f5f7ff 0%, #f7f8fa 240px, #f2f3f5 100%);
}

.empty-state,
.report-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 420px;
  background: #fff;
  border-radius: 8px;
}

.report-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 20px;
  min-height: calc(100vh - 180px);
}

.report-sidebar,
.report-content {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(229, 230, 235, 0.9);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 14px 40px rgba(17, 24, 39, 0.06);
  backdrop-filter: blur(12px);
}

.report-sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-header,
.report-header-card,
.item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-toolbar {
  display: flex;
  justify-content: flex-end;
  position: sticky;
  top: 0;
  z-index: 2;
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(229, 230, 235, 0.9);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
}

.sidebar-title,
.report-title {
  font-size: 22px;
  font-weight: 600;
  color: #1d2129;
  letter-spacing: 0;
}

.sidebar-subtitle,
.report-meta,
.sidebar-note,
.section-note,
.summary-inline,
.checked-summary {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
}

.sidebar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.suite-tree-panel {
  flex: 1;
  min-height: 260px;
  overflow: auto;
  border: 1px solid #e5e6eb;
  border-radius: 14px;
  padding: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
}

.suite-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.suite-node-name,
.item-title {
  color: #1d2129;
  font-weight: 500;
}

.suite-node-count {
  min-width: 28px;
  text-align: center;
  padding: 0 8px;
  border-radius: 999px;
  background: #f2f3f5;
  color: #4e5969;
  font-size: 12px;
  line-height: 22px;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.generation-record-panel {
  border: 1px solid #e5e6eb;
  border-radius: 14px;
  padding: 12px;
  background: linear-gradient(180deg, #fbfcff 0%, #ffffff 100%);
}

.generation-record-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.generation-record-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.generation-record-time {
  margin-top: 6px;
  font-size: 12px;
  color: #86909c;
}

.generation-record-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.generation-record-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(247, 248, 250, 0.9);
}

.generation-record-label {
  font-size: 12px;
  color: #86909c;
}

.generation-record-value {
  font-size: 13px;
  color: #1d2129;
  line-height: 1.6;
  word-break: break-word;
}

.generation-record-note {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
  white-space: pre-wrap;
  word-break: break-word;
}

.compare-panel-note {
  font-size: 12px;
  color: #86909c;
}

.compare-panel-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.compare-target-select {
  width: 220px;
}

.compare-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.compare-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(247, 248, 250, 0.9);
}

.compare-item-top,
.compare-item-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.compare-item-label {
  font-size: 13px;
  font-weight: 500;
  color: #1d2129;
}

.compare-item-delta {
  font-size: 12px;
  font-weight: 600;
}

.compare-item-delta.up {
  color: #165dff;
}

.compare-item-delta.down {
  color: #f53f3f;
}

.compare-item-delta.flat {
  color: #86909c;
}

.compare-item-values {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.compare-item-judgement {
  margin-top: 6px;
  font-size: 12px;
  color: #4e5969;
}

.compare-item-delta.positive {
  color: #00b42a;
}

.compare-item-delta.negative {
  color: #f53f3f;
}

.compare-item-delta.neutral {
  color: #86909c;
}

.snapshot-panel {
  border: 1px solid #e5e6eb;
  border-radius: 14px;
  padding: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #fafbff 100%);
}

.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.snapshot-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.snapshot-search {
  margin-bottom: 8px;
}

.snapshot-filter-group {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.snapshot-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #86909c;
  font-size: 12px;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}

.snapshot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #eef0f4;
  background: rgba(247, 248, 250, 0.9);
  transition: all 0.2s ease;
}

.snapshot-item.active {
  border-color: #165dff;
  background: #eff4ff;
  box-shadow: 0 10px 24px rgba(22, 93, 255, 0.12);
}

.snapshot-item.pinned {
  border-color: #f7c244;
}

.snapshot-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.snapshot-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.snapshot-name {
  color: #1d2129;
  font-size: 13px;
  font-weight: 500;
}

.snapshot-title-input {
  width: 220px;
}

.snapshot-meta {
  margin-top: 4px;
  color: #86909c;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.snapshot-report-meta {
  margin-top: 8px;
  color: #6b7280;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.snapshot-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.report-content {
  overflow: auto;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
}

.report-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.generation-alert {
  border-radius: 14px;
}

.report-nav-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.report-nav-title {
  flex: 0 0 auto;
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}

.report-nav-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.report-nav-button {
  border-radius: 999px;
}

.report-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(320px, 1fr);
  gap: 16px;
  padding: 20px;
  border-radius: 18px;
  border: 1px solid rgba(199, 210, 254, 0.7);
  background:
    linear-gradient(135deg, rgba(236, 242, 255, 0.96) 0%, rgba(255, 255, 255, 0.96) 42%, rgba(238, 244, 255, 0.96) 100%);
  box-shadow: 0 14px 32px rgba(59, 130, 246, 0.07);
}

.hero-main,
.hero-side {
  display: flex;
  flex-direction: column;
}

.hero-main {
  gap: 14px;
}

.hero-kicker,
.summary-topline {
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 1.2px;
  color: #165dff;
}

.report-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-title-block {
  min-width: 0;
}

.hero-tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-description {
  color: #334155;
  font-size: 14px;
  line-height: 1.9;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(219, 234, 254, 0.9);
}

.hero-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.hero-meta-item,
.hero-status-card {
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.88);
}

.hero-meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
}

.hero-meta-label,
.hero-highlight-label,
.hero-status-label {
  font-size: 12px;
  color: #64748b;
}

.hero-meta-value,
.hero-status-footnote {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.hero-side {
  gap: 14px;
}

.hero-status-card {
  padding: 14px;
}

.hero-status-value {
  margin-top: 10px;
}

.hero-status-footnote {
  margin-top: 10px;
}

.report-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.report-summary-caption {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.criteria-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 14px 0;
}

.conclusion-overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 14px 0;
}

.conclusion-overview-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(229, 230, 235, 0.95);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.conclusion-overview-label {
  font-size: 12px;
  color: #6b7280;
}

.conclusion-overview-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.15;
  color: #111827;
}

.conclusion-overview-footnote {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
}

.risk-overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 14px 0;
}

.risk-overview-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(229, 230, 235, 0.95);
  background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
}

.risk-overview-label {
  font-size: 12px;
  color: #6b7280;
}

.risk-overview-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.15;
  color: #111827;
}

.risk-overview-footnote {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
}

.conclusion-reason-panel {
  margin: 12px 0;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(229, 230, 235, 0.95);
  background: linear-gradient(180deg, #fbfcff 0%, #ffffff 100%);
}

.conclusion-reason-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conclusion-reason-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.conclusion-reason-subtitle {
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.conclusion-reason-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.conclusion-reason-item {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(229, 230, 235, 0.9);
  background: rgba(255, 255, 255, 0.88);
}

.conclusion-reason-item.danger {
  background: rgba(255, 247, 247, 0.92);
  border-color: rgba(245, 63, 63, 0.2);
}

.conclusion-reason-item.warning {
  background: rgba(255, 250, 240, 0.92);
  border-color: rgba(255, 125, 0, 0.2);
}

.conclusion-reason-item.success {
  background: rgba(243, 255, 247, 0.92);
  border-color: rgba(0, 180, 42, 0.16);
}

.conclusion-reason-item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.conclusion-reason-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}

.conclusion-reason-item-detail {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
}

.release-checklist-panel {
  margin: 12px 0;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(229, 230, 235, 0.95);
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
}

.release-checklist-header,
.release-checklist-item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.release-checklist-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.release-checklist-subtitle,
.release-checklist-item-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.release-checklist-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.release-checklist-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 230, 235, 0.85);
}

.release-checklist-index {
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #eff4ff;
  color: #165dff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.release-checklist-content {
  min-width: 0;
  flex: 1;
}

.release-checklist-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}

.criteria-summary-card {
  border: 1px solid rgba(229, 230, 235, 0.95);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 16px;
}

.criteria-summary-card.danger {
  background: linear-gradient(180deg, rgba(255, 247, 247, 0.96) 0%, #ffffff 100%);
  border-color: rgba(245, 63, 63, 0.2);
}

.criteria-summary-card.warning {
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.96) 0%, #ffffff 100%);
  border-color: rgba(255, 125, 0, 0.2);
}

.criteria-summary-card.success {
  background: linear-gradient(180deg, rgba(243, 255, 247, 0.96) 0%, #ffffff 100%);
  border-color: rgba(0, 180, 42, 0.18);
}

.criteria-summary-header,
.criteria-summary-item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.criteria-summary-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.criteria-summary-description,
.criteria-summary-item-detail {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.criteria-summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.criteria-summary-item {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(229, 230, 235, 0.8);
}

.criteria-summary-item-name {
  font-size: 13px;
  font-weight: 500;
  color: #1d2129;
}

.report-summary-grid-secondary {
  margin-top: -2px;
}

.summary-card,
.report-section,
.item-card,
.report-header-card {
  border: 1px solid rgba(229, 230, 235, 0.95);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.summary-card {
  padding: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.summary-card-soft {
  background: linear-gradient(180deg, #fbfcff 0%, #ffffff 100%);
}

.decision-focus-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.decision-focus-card {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(229, 230, 235, 0.95);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.decision-focus-label {
  font-size: 12px;
  color: #6b7280;
}

.decision-focus-value {
  margin-top: 10px;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: #111827;
  word-break: break-word;
}

.decision-focus-footnote {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
}

.summary-label {
  margin-top: 8px;
  font-size: 13px;
  color: #64748b;
}

.summary-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1;
}

.summary-value-small {
  font-size: 17px;
  line-height: 1.5;
  word-break: break-word;
}

.summary-footnote {
  margin-top: 10px;
  min-height: 38px;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

.report-header-card,
.report-section,
.item-card {
  padding: 16px;
}

.support-section-intro {
  margin-bottom: 14px;
}

.support-summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.support-summary-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(247, 248, 250, 0.92);
  border: 1px solid rgba(229, 230, 235, 0.85);
}

.support-summary-label {
  font-size: 12px;
  color: #6b7280;
}

.support-summary-value {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
  color: #111827;
}

.support-analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.support-analysis-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(229, 230, 235, 0.88);
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.03);
}

.report-section-intro {
  margin-bottom: 12px;
  font-size: 13px;
  color: #64748b;
}

.support-evidence-copy {
  color: var(--color-text-2);
  line-height: 1.7;
}

.support-analysis-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.support-analysis-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0;
}

.support-analysis-metrics.compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.support-analysis-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(247, 248, 250, 0.9);
}

.support-analysis-label {
  font-size: 12px;
  color: #6b7280;
}

.support-analysis-value {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.report-two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.section-title {
  position: relative;
  margin-bottom: 14px;
  padding-left: 14px;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  width: 4px;
  height: 18px;
  border-radius: 999px;
  background: linear-gradient(180deg, #165dff 0%, #36a9ff 100%);
}

.section-text,
.item-detail {
  margin: 0;
  color: #4b5563;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  text-align: left;
}

.tag-flow,
.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.compact-item-list .item-card {
  padding: 12px 14px;
}

.tag-flow {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8px;
}

.item-card {
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
}

.item-header + .item-detail,
.item-detail + .item-detail {
  margin-top: 6px;
}

:deep(.arco-tag) {
  border-radius: 999px;
  font-weight: 500;
}

:deep(.arco-table) {
  border-radius: 14px;
  overflow: hidden;
}

:deep(.arco-table-th) {
  background: #f8fafc;
  color: #475569;
}

:deep(.arco-tree-node-title) {
  padding-right: 0;
}

:deep(.arco-btn-size-small) {
  border-radius: 10px;
}

:deep(.arco-input-wrapper),
:deep(.arco-textarea-wrapper) {
  border-radius: 12px;
}

@media (max-width: 1200px) {
  .report-layout {
    grid-template-columns: 1fr;
  }

  .report-hero,
  .decision-focus-grid,
  .report-summary-grid,
  .conclusion-overview-grid,
  .risk-overview-grid,
  .support-summary-strip,
  .support-analysis-grid,
  .criteria-summary-grid,
  .report-two-column {
    grid-template-columns: 1fr;
  }

  .hero-meta-grid {
    grid-template-columns: 1fr 1fr;
  }

  .snapshot-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .snapshot-actions {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .snapshot-title-input {
    width: 100%;
  }

  .report-nav-panel {
    flex-direction: column;
    align-items: flex-start;
  }

  .report-nav-list {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .report-sidebar,
  .report-content {
    padding: 14px;
    border-radius: 14px;
  }

  .report-hero {
    padding: 16px;
  }

  .report-title-row,
  .snapshot-header,
  .sidebar-header,
  .sidebar-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-meta-grid {
    grid-template-columns: 1fr;
  }

  .report-toolbar {
    position: static;
    padding: 0;
    border: 0;
    background: transparent;
    backdrop-filter: none;
  }
}
</style>

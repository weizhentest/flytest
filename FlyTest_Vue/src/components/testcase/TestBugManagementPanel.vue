<template>
  <div class="bug-panel">
    <template v-if="viewMode === 'list'">
      <div class="bug-panel-header">
        <div class="bug-panel-heading">
          <div class="bug-panel-title">BUG 管理</div>
          <div class="bug-panel-subtitle">围绕当前测试套件查看、筛选、处理和追踪缺陷。</div>
        </div>
        <div class="bug-panel-actions">
          <a-button @click="fetchBugs">刷新</a-button>
          <a-button type="primary" @click="openCreateDetail">提 BUG</a-button>
        </div>
      </div>

      <div class="bug-status-grid">
        <button
          v-for="item in statusCards"
          :key="item.key"
          type="button"
          class="status-card"
          :class="{ 'status-card--active': activeStatusView === item.key }"
          @click="activeStatusView = item.key"
        >
          <span class="status-card-label">{{ item.label }}</span>
          <span class="status-card-value">{{ item.count }}</span>
        </button>
      </div>

      <div class="bug-toolbar">
        <div class="quick-view-list">
          <button
            v-for="item in quickViews"
            :key="item.key"
            type="button"
            class="quick-view-item"
            :class="{ 'quick-view-item--active': activeQuickView === item.key }"
            @click="activeQuickView = item.key"
          >
            {{ item.label }}
          </button>
        </div>

        <div class="bug-filter-grid">
          <a-input-search
            v-model="filters.search"
            class="bug-filter-search"
            placeholder="搜索 BUG 标题、重现步骤、期望结果、实际结果"
            allow-clear
            @search="fetchBugs"
            @clear="fetchBugs"
          />

          <a-select v-model="filters.bug_type" placeholder="BUG类型" allow-clear @change="handleFilterChange" @clear="handleFilterChange">
            <a-option v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-option>
          </a-select>

          <a-select v-model="filters.severity" placeholder="严重程度" allow-clear @change="handleFilterChange" @clear="handleFilterChange">
            <a-option v-for="item in levelOptions" :key="item" :value="item">S{{ item }}</a-option>
          </a-select>

          <a-select v-model="filters.priority" placeholder="优先级" allow-clear @change="handleFilterChange" @clear="handleFilterChange">
            <a-option v-for="item in levelOptions" :key="item" :value="item">P{{ item }}</a-option>
          </a-select>

          <a-select v-model="filters.assigned_to" placeholder="指派给" allow-clear @change="handleFilterChange" @clear="handleFilterChange">
            <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
              {{ member.user_detail.username }}
            </a-option>
          </a-select>

          <a-button type="outline" @click="resetFilters">重置筛选</a-button>
        </div>

        <div class="bug-toolbar-footer">
          <div class="bug-toolbar-sort">
            <span class="bug-toolbar-sort-label">排序</span>
            <a-select v-model="sortBy" size="small" class="bug-sort-select">
              <a-option v-for="item in bugSortOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </div>

          <div class="bug-toolbar-footer-actions">
            <a-button size="small" type="outline" @click="openSaveFilterViewModal">保存常用视图</a-button>
            <a-button size="small" type="outline" @click="exportSavedFilterViews">导出视图</a-button>
            <a-button size="small" type="outline" @click="triggerImportFilterViews">导入视图</a-button>
            <input
              ref="filterViewImportRef"
              type="file"
              accept="application/json"
              class="bug-hidden-file-input"
              @change="handleImportFilterViews"
            />
            <a-dropdown trigger="click" position="br">
              <a-button size="small" type="outline">
                <template #icon><icon-settings /></template>
                显示列
              </a-button>
              <template #content>
                <div class="bug-column-dropdown">
                  <div class="bug-column-dropdown-header">
                    <span>选择列表字段</span>
                    <a-button type="text" size="mini" @click="resetVisibleColumns">恢复默认</a-button>
                  </div>
                  <a-checkbox-group
                    v-model="visibleColumns"
                    direction="vertical"
                    class="bug-column-checkbox-group"
                    @change="handleVisibleColumnsChange"
                  >
                    <a-checkbox v-for="column in tableColumnOptions" :key="column.key" :value="column.key">
                      {{ column.label }}
                    </a-checkbox>
                  </a-checkbox-group>
                </div>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div v-if="savedFilterViews.length" class="bug-saved-view-list">
          <button
            v-for="item in savedFilterViews"
            :key="item.id"
            type="button"
            class="bug-saved-view-chip"
            :class="{ 'bug-saved-view-chip--active': currentAppliedFilterViewId === item.id }"
            :title="getSavedFilterViewMetaLabel(item)"
            @click="applySavedFilterView(item.id)"
          >
            <icon-up v-if="item.pinned" class="bug-saved-view-chip-pin" />
            <span class="bug-saved-view-chip-name">{{ item.name }}</span>
            <icon-edit class="bug-saved-view-chip-action" @click.stop="openEditFilterViewModal(item)" />
            <icon-up class="bug-saved-view-chip-action" @click.stop="togglePinFilterView(item.id)" />
            <icon-close class="bug-saved-view-chip-action" @click.stop="removeSavedFilterView(item.id)" />
          </button>
        </div>
      </div>

      <div class="bug-summary-pills">
        <button
          v-if="activeStatusView !== 'all'"
          type="button"
          class="bug-summary-pill bug-summary-pill--clearable"
          @click="clearSummaryFilter('status')"
        >
          <span>状态：{{ getStatusViewLabel(activeStatusView) }}</span>
          <icon-close class="bug-summary-pill-close" />
        </button>
        <button
          v-if="activeQuickView !== 'all'"
          type="button"
          class="bug-summary-pill bug-summary-pill--clearable"
          @click="clearSummaryFilter('quickView')"
        >
          <span>视图：{{ getQuickViewLabel(activeQuickView) }}</span>
          <icon-close class="bug-summary-pill-close" />
        </button>
        <button
          v-if="filters.search"
          type="button"
          class="bug-summary-pill bug-summary-pill--clearable bug-summary-pill--search"
          :title="filters.search"
          @click="clearSummaryFilter('search')"
        >
          <span>搜索：{{ filters.search }}</span>
          <icon-close class="bug-summary-pill-close" />
        </button>
      </div>

      <div v-if="updateSummary" class="bug-update-summary">
        <div class="bug-update-summary-content">
          <span class="bug-update-summary-title">{{ updateSummary.text }}</span>
          <span class="bug-update-summary-time">{{ updateSummary.timeLabel }}</span>
        </div>
        <div class="bug-update-summary-actions">
          <a-button v-if="lastSelectionSnapshot.length" type="text" size="mini" @click="restoreLastSelection">恢复选择</a-button>
          <a-button type="text" size="mini" @click="clearUpdateSummary">关闭</a-button>
        </div>
      </div>

      <div v-if="filteredBugList.length > 0" class="bug-batch-toolbar">
        <div class="bug-batch-toolbar-left">
          <span class="bug-batch-toolbar-count">已选 {{ selectedBugCount }} 条 BUG</span>
          <a-button type="text" size="small" @click="toggleSelectCurrentPage">
            {{ isCurrentPageSelected ? '取消本页选择' : '选择本页' }}
          </a-button>
          <a-button type="text" size="small" @click="toggleSelectFiltered">
            {{ isAllFilteredSelected ? '取消当前筛选' : '全选当前筛选结果' }}
          </a-button>
          <a-button v-if="selectedBugCount > 0" type="text" size="small" @click="selectedBugIds = []">清空选择</a-button>
        </div>
        <div class="bug-batch-toolbar-right">
          <a-dropdown trigger="click" :popup-visible="selectedBugCount === 0 ? false : undefined">
            <a-button type="primary" size="small" :disabled="selectedBugCount === 0">批量操作</a-button>
            <template #content>
              <a-doption @click="openBatchModal('assign')">批量指派</a-doption>
              <a-doption @click="openBatchModal('status')">批量修改状态</a-doption>
              <a-doption @click="openBatchModal('priority')">批量修改优先级</a-doption>
              <a-doption @click="openBatchModal('severity')">批量修改严重程度</a-doption>
              <a-doption @click="openBatchModal('bug_type')">批量修改BUG类型</a-doption>
              <a-doption @click="openBatchModal('resolution')">批量修改解决方案</a-doption>
              <a-doption class="bug-batch-toolbar-danger-option" @click="openBatchModal('delete')">批量删除</a-doption>
            </template>
          </a-dropdown>
        </div>
      </div>

      <a-table
        v-if="filteredBugList.length > 0"
        :data="pagedBugList"
        :loading="loading"
        :pagination="false"
        row-key="id"
        class="bug-table"
        :scroll="{ x: 1560, y: 420 }"
        :row-class="getBugRowClass"
        :row-selection="rowSelection"
        column-resizable
      >
        <a-table-column v-if="isColumnVisible('id')" title="ID" data-index="id" :width="72" align="center" />

        <a-table-column v-if="isColumnVisible('title')" title="BUG标题" :width="280">
          <template #cell="{ record }">
            <a-link @click="openDetail(record)">{{ record.title }}</a-link>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('status')" title="状态" :width="120" align="center">
          <template #cell="{ record }">
            <a-dropdown trigger="click" @select="(value) => handleStatusQuickSelect(record, String(value))">
              <a-tag :color="getStatusColor(record.status)" class="bug-selectable-tag">
                {{ record.status_display || record.status }}
                <icon-down class="bug-selectable-tag-icon" />
              </a-tag>
              <template #content>
                <a-doption v-for="item in getStatusActionOptions(record)" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('related_testcases')" title="关联用例" :width="220">
          <template #cell="{ record }">
            <div class="bug-related-cell" :title="getRelatedTestcaseSummary(record)">
              <template v-if="getRelatedTestcaseNames(record).length">
                <a-tag v-for="name in getRelatedTestcaseNames(record).slice(0, 2)" :key="name" size="small">
                  {{ name }}
                </a-tag>
                <a-tag v-if="getRelatedTestcaseNames(record).length > 2" size="small" color="arcoblue">
                  +{{ getRelatedTestcaseNames(record).length - 2 }}
                </a-tag>
              </template>
              <span v-else>-</span>
            </div>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('bug_type')" title="BUG类型" :width="120" align="center">
          <template #cell="{ record }">
            <a-dropdown trigger="click" @select="(value) => handleBugTypeChange(record, String(value) as TestBugType)">
              <a-tag :color="getBugTypeColor(record.bug_type)" class="bug-selectable-tag">
                {{ getBugTypeLabel(record.bug_type) }}
                <icon-down class="bug-selectable-tag-icon" />
              </a-tag>
              <template #content>
                <a-doption v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('severity')" title="严重程度" :width="96" align="center">
          <template #cell="{ record }">
            <a-dropdown trigger="click" @select="(value) => handleSeverityChange(record, String(value))">
              <a-tag :color="getSeverityColor(record.severity)" class="bug-selectable-tag">
                S{{ record.severity }}
                <icon-down class="bug-selectable-tag-icon" />
              </a-tag>
              <template #content>
                <a-doption v-for="item in levelOptions" :key="item" :value="item">S{{ item }}</a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('priority')" title="优先级" :width="96" align="center">
          <template #cell="{ record }">
            <a-dropdown trigger="click" @select="(value) => handlePriorityChange(record, String(value))">
              <a-tag :color="getPriorityColor(record.priority)" class="bug-selectable-tag">
                P{{ record.priority }}
                <icon-down class="bug-selectable-tag-icon" />
              </a-tag>
              <template #content>
                <a-doption v-for="item in levelOptions" :key="item" :value="item">P{{ item }}</a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('resolution')" title="解决方案" :width="120" align="center">
          <template #cell="{ record }">
            <a-tag v-if="record.resolution" :color="getResolutionColor(record.resolution)">
              {{ record.resolution_display || getResolutionLabel(record.resolution) }}
            </a-tag>
            <span v-else>-</span>
          </template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('assigned_to')" title="指派给" :width="160" align="center">
          <template #cell="{ record }">{{ getAssignedUserName(record) }}</template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('opened_by')" title="创建人" :width="120" align="center">
          <template #cell="{ record }">{{ record.opened_by_name || record.opened_by || '-' }}</template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('opened_at')" title="创建时间" :width="166" align="center">
          <template #cell="{ record }">{{ record.opened_at ? formatDate(record.opened_at) : '-' }}</template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('resolved_at')" title="解决时间" :width="166" align="center">
          <template #cell="{ record }">{{ record.resolved_at ? formatDate(record.resolved_at) : '-' }}</template>
        </a-table-column>

        <a-table-column v-if="isColumnVisible('actions')" title="操作" :width="260" fixed="right" align="center">
          <template #cell="{ record }">
            <a-space>
              <a-button size="mini" @click="openDetail(record)">查看</a-button>
              <a-button size="mini" type="primary" @click="openDetail(record, true)">编辑</a-button>
              <a-dropdown trigger="click">
                <a-button size="mini" type="outline">更多</a-button>
                <template #content>
                  <a-doption @click="handleActionSelect(record, 'assign')">指派</a-doption>
                  <a-doption v-if="record.status === 'assigned'" @click="handleActionSelect(record, 'confirm')">确认</a-doption>
                  <a-doption v-if="record.status === 'confirmed'" @click="handleActionSelect(record, 'fix')">修复</a-doption>
                  <a-doption v-if="record.status === 'fixed'" @click="handleActionSelect(record, 'resolve')">提交复测</a-doption>
                  <a-doption v-if="['pending_retest', 'closed', 'expired'].includes(record.status)" @click="handleActionSelect(record, 'activate')">激活</a-doption>
                  <a-doption :disabled="record.status === 'closed'" @click="handleActionSelect(record, 'close')">关闭</a-doption>
                  <a-doption @click="handleActionSelect(record, 'delete')">删除</a-doption>
                </template>
              </a-dropdown>
            </a-space>
          </template>
        </a-table-column>
      </a-table>

      <a-empty v-else-if="!loading" class="bug-empty-state">
        <div class="bug-empty-content">
          <div class="bug-empty-title">{{ hasActiveFilters ? '当前筛选条件下没有找到 BUG' : '当前套件下还没有 BUG' }}</div>
          <div class="bug-empty-description">
            {{ hasActiveFilters ? '可以清空部分筛选条件后再查看。' : '可以先提交一个 BUG，或切换到其他测试套件查看。' }}
          </div>
          <div v-if="hasActiveFilters" class="bug-empty-actions">
            <a-button size="small" @click="resetFilters">清空全部筛选</a-button>
          </div>
        </div>
      </a-empty>

      <div class="bug-pagination">
        <a-pagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="filteredBugList.length"
          :page-size-options="[10, 20, 50, 100]"
          show-total
          show-page-size
        />
      </div>
    </template>

    <template v-else>
      <div class="bug-detail-page">
        <div class="bug-detail-page-header">
          <div class="bug-detail-page-title-wrap">
            <a-button type="text" size="small" @click="backToList">返回列表</a-button>
            <h2>{{ detailDraftType === 'create' ? '新建 BUG' : detailDraftType === 'copy' ? '复制 BUG' : 'BUG 详情' }}</h2>
          </div>
          <div class="bug-detail-page-actions">
            <template v-if="detailEditMode">
              <a-button @click="cancelDetailEdit">取消</a-button>
              <a-button type="primary" :loading="detailSaving" @click="saveDetailEdit">保存</a-button>
            </template>
            <template v-else-if="detailBug">
              <a-button type="primary" @click="startDetailEdit(detailBug)">编辑</a-button>
              <a-button @click="openCopyDetail(detailBug)">复制</a-button>
            </template>
          </div>
        </div>

        <div class="bug-detail-page-title">
          <a-input
            v-if="detailEditMode"
            v-model="detailForm.title"
            size="large"
            placeholder="请输入 BUG 标题"
          />
          <template v-else>{{ detailBug?.title || '-' }}</template>
        </div>

        <div class="bug-detail-status-row">
          <div class="bug-detail-status-main">
            <span class="bug-detail-status-label">BUG状态</span>
            <a-dropdown v-if="detailBug && !detailDraftType" trigger="click" @select="(value) => handleActionSelect(detailBug!, String(value))">
              <a-tag :color="getStatusColor(detailBug?.status)" class="bug-selectable-tag">
                {{ detailBug?.status_display || detailBug?.status || '未指派' }}
                <icon-down class="bug-selectable-tag-icon" />
              </a-tag>
              <template #content>
                <a-doption v-for="item in getStatusActionOptions(detailBug)" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
            <a-tag v-else color="gray">未指派</a-tag>
          </div>
          <div v-if="detailBug && !detailDraftType && !detailEditMode" class="bug-detail-toolbar">
            <a-button type="outline" class="bug-detail-toolbar-button" @click="handleActionSelect(detailBug, 'assign')">
              <template #icon><icon-user /></template>
              指派给
            </a-button>
            <a-dropdown trigger="click" @select="(value) => handleActionSelect(detailBug, String(value))">
              <a-button type="outline" class="bug-detail-toolbar-button">
                <template #icon><icon-check-circle /></template>
                处理状态
              </a-button>
              <template #content>
                <a-doption v-for="item in getStatusActionOptions(detailBug)" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-doption>
              </template>
            </a-dropdown>
            <a-button type="outline" class="bug-detail-toolbar-button" @click="openCopyDetail(detailBug)">
              <template #icon><icon-copy /></template>
              复制
            </a-button>
            <a-button type="outline" status="danger" class="bug-detail-toolbar-button" @click="handleActionSelect(detailBug, 'delete')">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </div>
        </div>

        <div class="bug-detail-section">
          <div class="bug-detail-section-title">基础信息</div>
          <div class="bug-detail-grid">
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">所属套件</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.suite_name || '-') }}</div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">关联用例</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-select v-model="detailForm.testcase_ids" multiple allow-clear placeholder="请选择关联用例" style="width: 100%;">
                    <a-option v-for="item in suiteTestCases" :key="item.id" :value="item.id">{{ item.name }}</a-option>
                  </a-select>
                </template>
                <div v-else class="bug-related-field">
                  <template v-if="getRelatedTestcaseNames(detailBug).length">
                    <a-tag v-for="name in getRelatedTestcaseNames(detailBug)" :key="name" size="small">
                      {{ name }}
                    </a-tag>
                  </template>
                  <span v-else>-</span>
                </div>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">指派给</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-select v-model="detailForm.assigned_to" multiple allow-clear placeholder="请选择指派人员" style="width: 100%;">
                    <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
                      {{ member.user_detail.username }}
                    </a-option>
                  </a-select>
                </template>
                <template v-else>{{ detailBug ? getAssignedUserName(detailBug) : '-' }}</template>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">创建人</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.opened_by_name || detailBug?.opened_by || '-') }}</div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">BUG类型</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-dropdown trigger="click" @select="(value) => (detailForm.bug_type = String(value) as TestBugType)">
                    <a-tag :color="getBugTypeColor(detailForm.bug_type)" class="bug-selectable-tag">
                      {{ getBugTypeLabel(detailForm.bug_type) }}
                      <icon-down class="bug-selectable-tag-icon" />
                    </a-tag>
                    <template #content>
                      <a-doption v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
                        {{ item.label }}
                      </a-doption>
                    </template>
                  </a-dropdown>
                </template>
                <a-tag v-else :color="getBugTypeColor(detailBug?.bug_type)">{{ getBugTypeLabel(detailBug?.bug_type) }}</a-tag>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">严重程度</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-dropdown trigger="click" @select="(value) => (detailForm.severity = String(value))">
                    <a-tag :color="getSeverityColor(detailForm.severity)" class="bug-selectable-tag">
                      S{{ detailForm.severity }}
                      <icon-down class="bug-selectable-tag-icon" />
                    </a-tag>
                    <template #content>
                      <a-doption v-for="item in levelOptions" :key="item" :value="item">S{{ item }}</a-doption>
                    </template>
                  </a-dropdown>
                </template>
                <a-tag v-else :color="getSeverityColor(detailBug?.severity)">S{{ detailBug?.severity || '-' }}</a-tag>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">优先级</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-dropdown trigger="click" @select="(value) => (detailForm.priority = String(value))">
                    <a-tag :color="getPriorityColor(detailForm.priority)" class="bug-selectable-tag">
                      P{{ detailForm.priority }}
                      <icon-down class="bug-selectable-tag-icon" />
                    </a-tag>
                    <template #content>
                      <a-doption v-for="item in levelOptions" :key="item" :value="item">P{{ item }}</a-doption>
                    </template>
                  </a-dropdown>
                </template>
                <a-tag v-else :color="getPriorityColor(detailBug?.priority)">P{{ detailBug?.priority || '-' }}</a-tag>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">解决方案</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-dropdown trigger="click" @select="(value) => (detailForm.resolution = String(value) as TestBugResolution)">
                    <a-tag :color="getResolutionColor(detailForm.resolution)" class="bug-selectable-tag">
                      {{ getResolutionLabel(detailForm.resolution) }}
                      <icon-down class="bug-selectable-tag-icon" />
                    </a-tag>
                    <template #content>
                      <a-doption v-for="item in TEST_BUG_RESOLUTION_OPTIONS" :key="item.value" :value="item.value">
                        {{ item.label }}
                      </a-doption>
                    </template>
                  </a-dropdown>
                </template>
                <template v-else>{{ detailDraftType ? '-' : (detailBug?.resolution_display || '-') }}</template>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">截止时间</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-date-picker v-model="detailForm.deadline" value-format="YYYY-MM-DD" style="width: 100%;" />
                </template>
                <template v-else>{{ detailDraftType ? '-' : (detailBug?.deadline || '-') }}</template>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">关键词</div>
              <div class="bug-detail-field-value">
                <template v-if="detailEditMode">
                  <a-input v-model="detailForm.keywords" placeholder="多个关键词可用空格分隔" />
                </template>
                <template v-else>{{ detailDraftType ? '-' : (detailBug?.keywords || '-') }}</template>
              </div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">创建时间</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.opened_at ? formatDate(detailBug.opened_at) : '-') }}</div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">指派时间</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.assigned_at ? formatDate(detailBug.assigned_at) : '-') }}</div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">解决时间</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.resolved_at ? formatDate(detailBug.resolved_at) : '-') }}</div>
            </div>
            <div class="bug-detail-field">
              <div class="bug-detail-field-label">关闭时间</div>
              <div class="bug-detail-field-value">{{ detailDraftType ? '-' : (detailBug?.closed_at ? formatDate(detailBug.closed_at) : '-') }}</div>
            </div>
          </div>
        </div>

        <div class="bug-detail-section">
          <div class="bug-detail-section-title">重现步骤</div>
          <BugRichTextEditor
            v-if="detailEditMode"
            v-model="detailForm.steps"
            placeholder="请输入重现步骤"
            :attachments="getSectionAttachments('steps')"
            :pending-files="pendingAttachmentFiles.steps"
            @upload-files="(files) => handleDetailAttachmentUpload('steps', files)"
            @remove-attachment="(attachment) => removeDetailAttachment('steps', attachment)"
            @remove-pending-file="(id) => removePendingAttachment('steps', id)"
          />
          <template v-else>
            <div class="bug-detail-content" v-html="renderBugContent(detailBug?.steps)"></div>
            <div v-if="getSectionAttachments('steps').length" class="bug-detail-attachment-list">
              <div v-for="attachment in getSectionAttachments('steps')" :key="attachment.id" class="bug-detail-attachment-item">
                <a v-if="attachment.file_type === 'image'" :href="attachment.url" target="_blank" rel="noreferrer">
                  <img :src="attachment.url" :alt="attachment.original_name" class="bug-detail-attachment-image" />
                </a>
                <video v-else-if="attachment.file_type === 'video'" class="bug-detail-attachment-video" controls :src="attachment.url" />
                <a v-else :href="attachment.url" target="_blank" rel="noreferrer" class="bug-detail-attachment-file">
                  {{ attachment.original_name }}
                </a>
              </div>
            </div>
          </template>
        </div>

        <div class="bug-detail-section">
          <div class="bug-detail-section-title">期望结果</div>
          <BugRichTextEditor
            v-if="detailEditMode"
            v-model="detailForm.expected_result"
            placeholder="请输入期望结果"
            :attachments="getSectionAttachments('expected_result')"
            :pending-files="pendingAttachmentFiles.expected_result"
            @upload-files="(files) => handleDetailAttachmentUpload('expected_result', files)"
            @remove-attachment="(attachment) => removeDetailAttachment('expected_result', attachment)"
            @remove-pending-file="(id) => removePendingAttachment('expected_result', id)"
          />
          <template v-else>
            <div class="bug-detail-content" v-html="renderBugContent(detailBug?.expected_result)"></div>
            <div v-if="getSectionAttachments('expected_result').length" class="bug-detail-attachment-list">
              <div v-for="attachment in getSectionAttachments('expected_result')" :key="attachment.id" class="bug-detail-attachment-item">
                <a v-if="attachment.file_type === 'image'" :href="attachment.url" target="_blank" rel="noreferrer">
                  <img :src="attachment.url" :alt="attachment.original_name" class="bug-detail-attachment-image" />
                </a>
                <video v-else-if="attachment.file_type === 'video'" class="bug-detail-attachment-video" controls :src="attachment.url" />
                <a v-else :href="attachment.url" target="_blank" rel="noreferrer" class="bug-detail-attachment-file">
                  {{ attachment.original_name }}
                </a>
              </div>
            </div>
          </template>
        </div>

        <div class="bug-detail-section">
          <div class="bug-detail-section-title">实际结果</div>
          <BugRichTextEditor
            v-if="detailEditMode"
            v-model="detailForm.actual_result"
            placeholder="请输入实际结果"
            :attachments="getSectionAttachments('actual_result')"
            :pending-files="pendingAttachmentFiles.actual_result"
            @upload-files="(files) => handleDetailAttachmentUpload('actual_result', files)"
            @remove-attachment="(attachment) => removeDetailAttachment('actual_result', attachment)"
            @remove-pending-file="(id) => removePendingAttachment('actual_result', id)"
          />
          <template v-else>
            <div class="bug-detail-content" v-html="renderBugContent(detailBug?.actual_result)"></div>
            <div v-if="getSectionAttachments('actual_result').length" class="bug-detail-attachment-list">
              <div v-for="attachment in getSectionAttachments('actual_result')" :key="attachment.id" class="bug-detail-attachment-item">
                <a v-if="attachment.file_type === 'image'" :href="attachment.url" target="_blank" rel="noreferrer">
                  <img :src="attachment.url" :alt="attachment.original_name" class="bug-detail-attachment-image" />
                </a>
                <video v-else-if="attachment.file_type === 'video'" class="bug-detail-attachment-video" controls :src="attachment.url" />
                <a v-else :href="attachment.url" target="_blank" rel="noreferrer" class="bug-detail-attachment-file">
                  {{ attachment.original_name }}
                </a>
              </div>
            </div>
          </template>
        </div>

        <div class="bug-detail-section">
          <div class="bug-detail-section-title">处理备注</div>
          <template v-if="detailEditMode">
            <a-textarea v-model="detailForm.solution" :auto-size="{ minRows: 4, maxRows: 8 }" placeholder="请输入处理备注" />
          </template>
          <div v-else class="bug-detail-content" v-html="renderBugContent(detailDraftType ? '' : detailBug?.solution)"></div>
        </div>
      </div>
    </template>

    <a-modal
      v-model:visible="actionVisible"
      :title="actionModalTitle"
      width="560px"
      :ok-loading="actionSubmitting"
      @ok="submitAction"
      @cancel="resetActionState"
    >
      <a-form :model="actionForm" layout="vertical">
        <template v-if="actionType === 'assign'">
          <a-form-item field="assigned_to" label="指派给" required>
            <a-select v-model="actionForm.assigned_to" multiple allow-clear placeholder="请选择指派人员">
              <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
                {{ member.user_detail.username }}
              </a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="actionType === 'fix' || actionType === 'resolve' || actionType === 'close'">
          <a-form-item field="resolution" label="解决方案" required>
            <a-select v-model="actionForm.resolution" placeholder="请选择解决方案">
              <a-option v-for="item in TEST_BUG_RESOLUTION_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="solution" label="处理备注">
            <a-textarea
              v-model="actionForm.solution"
              :auto-size="{ minRows: 4, maxRows: 8 }"
              placeholder="请输入处理备注"
            />
          </a-form-item>
        </template>
        <template v-else-if="actionType === 'delete'">
          <div class="action-confirm-tip">确定删除当前 BUG 吗？删除后不可恢复。</div>
        </template>
        <template v-else-if="actionType === 'activate'">
          <div class="action-confirm-tip">重新激活后，BUG 会回到待处理流程。</div>
        </template>
        <template v-else>
          <div class="action-confirm-tip">确认继续当前操作。</div>
        </template>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="batchVisible"
      :title="batchModalTitle"
      width="560px"
      :ok-loading="batchSubmitting"
      @ok="submitBatchAction"
      @cancel="resetBatchState"
    >
      <a-form :model="batchForm" layout="vertical">
        <div class="bug-batch-preview">
          <div class="bug-batch-preview-title">本次将处理 {{ selectedBugCount }} 条 BUG</div>
          <div class="bug-batch-preview-summary">{{ batchPreviewSummary }}</div>
          <div class="bug-batch-preview-impact">
            <span class="bug-batch-preview-impact-item bug-batch-preview-impact-item--active">实际变更 {{ batchAffectedCount }} 条</span>
            <span v-if="batchUnchangedCount > 0" class="bug-batch-preview-impact-item">保持不变 {{ batchUnchangedCount }} 条</span>
          </div>
          <div v-if="batchAffectedDiffs.length" class="bug-batch-preview-diffs">
            <div v-for="item in batchAffectedDiffs" :key="item" class="bug-batch-preview-diff">{{ item }}</div>
          </div>
          <div v-if="batchPreviewTitles.length" class="bug-batch-preview-tags">
            <a-tag v-for="item in batchPreviewTitles" :key="item">{{ item }}</a-tag>
            <a-tag v-if="batchAffectedCount > batchPreviewTitles.length" color="arcoblue">
              +{{ batchAffectedCount - batchPreviewTitles.length }}
            </a-tag>
          </div>
        </div>

        <template v-if="batchActionType === 'assign'">
          <a-form-item field="assigned_to" label="指派给" required>
            <a-select v-model="batchForm.assigned_to" multiple allow-clear placeholder="请选择项目成员">
              <a-option v-for="member in projectMembers" :key="member.user" :value="member.user">
                {{ member.user_detail.username }}
              </a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'status'">
          <a-form-item field="status" label="BUG状态" required>
            <a-select v-model="batchForm.status">
              <a-option
                v-for="item in TEST_BUG_STATUS_OPTIONS.filter((option) => option.value !== 'expired')"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'priority'">
          <a-form-item field="priority" label="优先级" required>
            <a-select v-model="batchForm.priority">
              <a-option v-for="item in levelOptions" :key="item" :value="item">P{{ item }}</a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'severity'">
          <a-form-item field="severity" label="严重程度" required>
            <a-select v-model="batchForm.severity">
              <a-option v-for="item in levelOptions" :key="item" :value="item">S{{ item }}</a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'bug_type'">
          <a-form-item field="bug_type" label="BUG类型" required>
            <a-select v-model="batchForm.bug_type">
              <a-option v-for="item in TEST_BUG_TYPE_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'resolution'">
          <a-form-item field="resolution" label="解决方案" required>
            <a-select v-model="batchForm.resolution" placeholder="请选择解决方案">
              <a-option v-for="item in TEST_BUG_RESOLUTION_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="solution" label="处理备注">
            <a-textarea v-model="batchForm.solution" :auto-size="{ minRows: 4, maxRows: 8 }" placeholder="请输入处理备注" />
          </a-form-item>
        </template>
        <template v-else-if="batchActionType === 'delete'">
          <div class="action-confirm-tip">确定删除当前选中的 {{ selectedBugCount }} 条 BUG 吗？删除后不可恢复。</div>
        </template>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="saveFilterViewVisible"
      :title="editingFilterViewId ? '编辑常用视图' : '保存常用视图'"
      width="420px"
      @ok="submitSaveFilterView"
      @cancel="resetSaveFilterViewState"
    >
      <a-form layout="vertical">
        <a-form-item field="name" label="视图名称" required>
          <a-input v-model="saveFilterViewName" :max-length="20" placeholder="请输入视图名称" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>


<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconCheckCircle, IconClose, IconCopy, IconDelete, IconDown, IconEdit, IconSettings, IconUp, IconUser } from '@arco-design/web-vue/es/icon';
import { useAuthStore } from '@/store/authStore';
import { formatDate } from '@/utils/formatters';
import BugRichTextEditor, { type PendingBugAttachmentFile } from './BugRichTextEditor.vue';
import {
  TEST_BUG_RESOLUTION_OPTIONS,
  TEST_BUG_STATUS_OPTIONS,
  TEST_BUG_TYPE_OPTIONS,
  activateTestBug,
  assignTestBug,
  batchAssignTestBugs,
  batchChangeTestBugStatus,
  batchDeleteTestBugs,
  batchUpdateTestBugPriority,
  batchUpdateTestBugResolution,
  batchUpdateTestBugSeverity,
  batchUpdateTestBugType,
  closeTestBug,
  confirmTestBug,
  createTestBug,
  deleteTestBug,
  deleteTestBugAttachment,
  fixTestBug,
  getTestBugDetail,
  getTestBugList,
  resolveTestBug,
  uploadTestBugAttachments,
  updateTestBug,
  type TestBugAttachment,
  type TestBug,
  type TestBugAttachmentSection,
  type TestBugResolution,
  type TestBugStatus,
  type TestBugType,
} from '@/services/testBugService';
import { getProjectMembers, type ProjectMember } from '@/services/projectService';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';

type ActionType = 'assign' | 'confirm' | 'fix' | 'resolve' | 'activate' | 'close' | 'delete' | null;
type StatusView = 'all' | TestBugStatus;
type QuickView = 'all' | 'assigned_to_me' | 'opened_by_me' | 'unassigned' | 'unresolved';
type BugSortValue =
  | 'priority_desc'
  | 'severity_desc'
  | 'opened_at_desc'
  | 'opened_at_asc'
  | 'resolved_at_desc'
  | 'activated_desc';
type BugUpdateSummary = {
  text: string;
  timeLabel: string;
};
type LocalPendingBugAttachmentFile = PendingBugAttachmentFile & { file: File };
type SavedBugFilterView = {
  id: string;
  name: string;
  pinned?: boolean;
  created_at?: string;
  updated_at?: string;
  last_applied_at?: string;
  filters: {
    search: string;
    bug_type?: string;
    severity?: string;
    priority?: string;
    assigned_to?: number;
    activeStatusView: StatusView;
    activeQuickView: QuickView;
    sortBy: BugSortValue;
  };
};
type BugTableColumnKey =
  | 'id'
  | 'title'
  | 'status'
  | 'related_testcases'
  | 'bug_type'
  | 'severity'
  | 'priority'
  | 'resolution'
  | 'assigned_to'
  | 'opened_by'
  | 'opened_at'
  | 'resolved_at'
  | 'actions';

const props = defineProps<{
  currentProjectId: number | null;
  selectedSuiteId: number | null;
}>();

const BUG_COLUMN_STORAGE_KEY_PREFIX = 'flytest_bug_management_visible_columns';
const BUG_FILTER_STORAGE_KEY_PREFIX = 'flytest_bug_management_filters';
const BUG_FILTER_VIEWS_STORAGE_KEY_PREFIX = 'flytest_bug_management_filter_views';
const DEFAULT_VISIBLE_COLUMNS: BugTableColumnKey[] = [
  'id',
  'title',
  'status',
  'related_testcases',
  'bug_type',
  'severity',
  'priority',
  'resolution',
  'assigned_to',
  'opened_by',
  'opened_at',
  'resolved_at',
  'actions',
];
const tableColumnOptions: Array<{ key: BugTableColumnKey; label: string }> = [
  { key: 'id', label: 'ID' },
  { key: 'title', label: 'BUG标题' },
  { key: 'status', label: '状态' },
  { key: 'related_testcases', label: '关联用例' },
  { key: 'bug_type', label: 'BUG类型' },
  { key: 'severity', label: '严重程度' },
  { key: 'priority', label: '优先级' },
  { key: 'resolution', label: '解决方案' },
  { key: 'assigned_to', label: '指派给' },
  { key: 'opened_by', label: '创建人' },
  { key: 'opened_at', label: '创建时间' },
  { key: 'resolved_at', label: '解决时间' },
  { key: 'actions', label: '操作' },
];

const getBugColumnStorageKey = (projectId?: number | null) =>
  `${BUG_COLUMN_STORAGE_KEY_PREFIX}:${projectId || 'global'}`;
const getBugFilterStorageKey = (projectId?: number | null) =>
  `${BUG_FILTER_STORAGE_KEY_PREFIX}:${projectId || 'global'}`;
const getBugFilterViewsStorageKey = (projectId?: number | null) =>
  `${BUG_FILTER_VIEWS_STORAGE_KEY_PREFIX}:${projectId || 'global'}`;

const authStore = useAuthStore();
const currentUserId = computed(() => authStore.user?.id ?? null);

const loading = ref(false);
const detailLoading = ref(false);
const detailSaving = ref(false);
const detailEditMode = ref(false);
const actionSubmitting = ref(false);
const actionVisible = ref(false);
const batchSubmitting = ref(false);
const batchVisible = ref(false);
const saveFilterViewVisible = ref(false);
const viewMode = ref<'list' | 'detail'>('list');
const detailDraftType = ref<'create' | 'copy' | null>(null);
const filterViewImportRef = ref<HTMLInputElement | null>(null);
const bugList = ref<TestBug[]>([]);
const projectMembers = ref<ProjectMember[]>([]);
const suiteTestCases = ref<TestCase[]>([]);
const detailBug = ref<TestBug | null>(null);
const actionBug = ref<TestBug | null>(null);
const actionType = ref<ActionType>(null);
const activeStatusView = ref<StatusView>('all');
const activeQuickView = ref<QuickView>('all');
const sortBy = ref<BugSortValue>('priority_desc');
const selectedBugIds = ref<number[]>([]);
const visibleColumns = ref<BugTableColumnKey[]>(DEFAULT_VISIBLE_COLUMNS.slice());
const savedFilterViews = ref<SavedBugFilterView[]>([]);
const recentlyUpdatedBugIds = ref<number[]>([]);
const updateSummary = ref<BugUpdateSummary | null>(null);
const batchActionType = ref<'assign' | 'status' | 'priority' | 'severity' | 'bug_type' | 'resolution' | 'delete' | null>(null);
const saveFilterViewName = ref('');
const editingFilterViewId = ref<string | null>(null);
const lastSelectionSnapshot = ref<number[]>([]);
const levelOptions = ['1', '2', '3', '4'];
let rowHighlightTimer: ReturnType<typeof setTimeout> | null = null;
let updateSummaryTimer: ReturnType<typeof setTimeout> | null = null;
const hasActiveFilters = computed(
  () =>
    Boolean(
      filters.search ||
      filters.bug_type ||
      filters.severity ||
      filters.priority ||
      filters.assigned_to ||
      activeStatusView.value !== 'all' ||
      activeQuickView.value !== 'all'
    )
);

const filters = reactive({
  search: '',
  bug_type: undefined as string | undefined,
  severity: undefined as string | undefined,
  priority: undefined as string | undefined,
  assigned_to: undefined as number | undefined,
});

const buildCurrentFilterSnapshot = () => ({
  search: filters.search || '',
  bug_type: filters.bug_type,
  severity: filters.severity,
  priority: filters.priority,
  assigned_to: filters.assigned_to,
  activeStatusView: activeStatusView.value,
  activeQuickView: activeQuickView.value,
  sortBy: sortBy.value,
});

const pagination = reactive({
  current: 1,
  pageSize: 10,
});

const actionForm = reactive({
  assigned_to: [] as number[],
  resolution: 'fixed' as TestBugResolution,
  solution: '',
});

const batchForm = reactive({
  assigned_to: [] as number[],
  status: 'assigned' as Exclude<TestBugStatus, 'expired'>,
  priority: '3',
  severity: '3',
  bug_type: 'codeerror' as TestBugType,
  resolution: 'fixed' as TestBugResolution,
  solution: '',
});

const detailForm = reactive({
  title: '',
  testcase_ids: [] as number[],
  assigned_to: [] as number[],
  bug_type: 'codeerror' as TestBugType,
  resolution: '' as TestBugResolution,
  severity: '3',
  priority: '3',
  deadline: undefined as string | undefined,
  keywords: '',
  steps: '',
  expected_result: '',
  actual_result: '',
  solution: '',
});

const createEmptyPendingAttachmentState = () => ({
  steps: [] as LocalPendingBugAttachmentFile[],
  expected_result: [] as LocalPendingBugAttachmentFile[],
  actual_result: [] as LocalPendingBugAttachmentFile[],
});

const pendingAttachmentFiles = reactive(createEmptyPendingAttachmentState());

const statusCards = computed(() => [
  { key: 'all' as const, label: '全部', count: bugList.value.length },
  { key: 'unassigned' as const, label: '未指派', count: bugList.value.filter((item) => item.status === 'unassigned').length },
  { key: 'assigned' as const, label: '未确认', count: bugList.value.filter((item) => item.status === 'assigned').length },
  { key: 'confirmed' as const, label: '已确认', count: bugList.value.filter((item) => item.status === 'confirmed').length },
  { key: 'fixed' as const, label: '已修复', count: bugList.value.filter((item) => item.status === 'fixed').length },
  { key: 'pending_retest' as const, label: '待复测', count: bugList.value.filter((item) => item.status === 'pending_retest').length },
  { key: 'closed' as const, label: '已关闭', count: bugList.value.filter((item) => item.status === 'closed').length },
  { key: 'expired' as const, label: '已过期', count: bugList.value.filter((item) => item.status === 'expired').length },
]);

const quickViews = [
  { key: 'all' as const, label: '全部视图' },
  { key: 'assigned_to_me' as const, label: '指派给我' },
  { key: 'opened_by_me' as const, label: '我创建的' },
  { key: 'unassigned' as const, label: '未指派' },
  { key: 'unresolved' as const, label: '未解决' },
];

const bugSortOptions = [
  { value: 'priority_desc' as const, label: '优先级从高到低' },
  { value: 'severity_desc' as const, label: '严重程度从高到低' },
  { value: 'opened_at_desc' as const, label: '创建时间最新' },
  { value: 'opened_at_asc' as const, label: '创建时间最早' },
  { value: 'resolved_at_desc' as const, label: '解决时间最新' },
  { value: 'activated_desc' as const, label: '激活次数最多' },
];

const getBugTimeValue = (value?: string | null) => {
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
};

const sortBugList = (list: TestBug[]) =>
  [...list].sort((left, right) => {
    const priorityDiff = Number(left.priority || 9) - Number(right.priority || 9);
    const severityDiff = Number(left.severity || 9) - Number(right.severity || 9);
    const openedDiff = getBugTimeValue(left.opened_at) - getBugTimeValue(right.opened_at);
    const resolvedDiff = getBugTimeValue(left.resolved_at) - getBugTimeValue(right.resolved_at);
    const activatedDiff = Number(left.activated_count || 0) - Number(right.activated_count || 0);

    if (sortBy.value === 'priority_desc') return priorityDiff || severityDiff || openedDiff * -1;
    if (sortBy.value === 'severity_desc') return severityDiff || priorityDiff || openedDiff * -1;
    if (sortBy.value === 'opened_at_desc') return openedDiff * -1 || priorityDiff || severityDiff;
    if (sortBy.value === 'opened_at_asc') return openedDiff || priorityDiff || severityDiff;
    if (sortBy.value === 'resolved_at_desc') return resolvedDiff * -1 || openedDiff * -1 || priorityDiff;
    return activatedDiff * -1 || priorityDiff || severityDiff || openedDiff * -1;
  });


const filteredBugList = computed(() =>
  sortBugList(bugList.value.filter((bug) => {
    if (activeStatusView.value !== 'all' && bug.status !== activeStatusView.value) {
      return false;
    }

    if (activeQuickView.value === 'assigned_to_me' && !getAssignedUserIds(bug).includes(currentUserId.value || -1)) {
      return false;
    }
    if (activeQuickView.value === 'opened_by_me' && bug.opened_by !== currentUserId.value) {
      return false;
    }
    if (activeQuickView.value === 'unassigned' && getAssignedUserIds(bug).length > 0) {
      return false;
    }
    if (activeQuickView.value === 'unresolved' && bug.status === 'closed') {
      return false;
    }

    return true;
  }))
);

const pagedBugList = computed(() => {
  const total = filteredBugList.value.length;
  const pageSize = Number(pagination.pageSize) > 0 ? Number(pagination.pageSize) : 10;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(Number(pagination.current) || 1, 1), maxPage);

  if (current !== pagination.current) {
    pagination.current = current;
  }

  const start = (current - 1) * pageSize;
  return filteredBugList.value.slice(start, start + pageSize);
});

const filteredBugIds = computed(() => filteredBugList.value.map((bug) => bug.id));
const pagedBugIds = computed(() => pagedBugList.value.map((bug) => bug.id));
const selectedBugCount = computed(() => selectedBugIds.value.length);
const selectedBugRecords = computed(() =>
  bugList.value.filter((bug) => selectedBugIds.value.includes(bug.id))
);
const isAllFilteredSelected = computed(
  () => filteredBugIds.value.length > 0 && filteredBugIds.value.every((id) => selectedBugIds.value.includes(id))
);
const isCurrentPageSelected = computed(
  () => pagedBugIds.value.length > 0 && pagedBugIds.value.every((id) => selectedBugIds.value.includes(id))
);
const batchModalTitle = computed(() => {
  if (batchActionType.value === 'assign') return '批量指派';
  if (batchActionType.value === 'status') return '批量修改状态';
  if (batchActionType.value === 'priority') return '批量修改优先级';
  if (batchActionType.value === 'severity') return '批量修改严重程度';
  if (batchActionType.value === 'bug_type') return '批量修改 BUG 类型';
  if (batchActionType.value === 'resolution') return '批量修改解决方案';
  if (batchActionType.value === 'delete') return '批量删除';
  return '批量操作';
});

const hasSameAssignedUsers = (bug: TestBug, targetUserIds: number[]) => {
  const source = [...getAssignedUserIds(bug)].sort((left, right) => left - right);
  const target = [...targetUserIds].sort((left, right) => left - right);
  if (source.length !== target.length) {
    return false;
  }
  return source.every((value, index) => value === target[index]);
};

const doesBatchActionAffectBug = (bug: TestBug) => {
  if (!batchActionType.value) {
    return true;
  }
  if (batchActionType.value === 'assign') {
    return !hasSameAssignedUsers(bug, batchForm.assigned_to);
  }
  if (batchActionType.value === 'status') {
    return bug.status !== batchForm.status;
  }
  if (batchActionType.value === 'priority') {
    return String(bug.priority || '') !== String(batchForm.priority || '');
  }
  if (batchActionType.value === 'severity') {
    return String(bug.severity || '') !== String(batchForm.severity || '');
  }
  if (batchActionType.value === 'bug_type') {
    return String(bug.bug_type || '') !== String(batchForm.bug_type || '');
  }
  if (batchActionType.value === 'resolution') {
    return (
      String(bug.resolution || '') !== String(batchForm.resolution || '') ||
      String(bug.solution || '').trim() !== String(batchForm.solution || '').trim()
    );
  }
  return true;
};

const batchPreviewTitles = computed(() =>
  selectedBugRecords.value
    .filter((bug) => doesBatchActionAffectBug(bug))
    .map((bug) => String(bug.title || '').trim())
    .filter((title) => Boolean(title))
    .slice(0, 3)
);

const batchAffectedCount = computed(() =>
  batchActionType.value
    ? selectedBugRecords.value.filter((bug) => doesBatchActionAffectBug(bug)).length
    : selectedBugRecords.value.length
);

const batchUnchangedCount = computed(() => Math.max(0, selectedBugCount.value - batchAffectedCount.value));

const batchAffectedDiffs = computed(() => {
  if (!batchActionType.value) {
    return [];
  }
  if (batchActionType.value === 'assign') {
    const names = batchForm.assigned_to.map((userId) => getMemberName(userId)).filter((name) => name && name !== '-');
    return [`指派给 -> ${names.join('、') || '未选择'}`];
  }
  if (batchActionType.value === 'status') {
    return [`BUG状态 -> ${getStatusViewLabel(batchForm.status)}`];
  }
  if (batchActionType.value === 'priority') {
    return [`优先级 -> P${batchForm.priority}`];
  }
  if (batchActionType.value === 'severity') {
    return [`严重程度 -> S${batchForm.severity}`];
  }
  if (batchActionType.value === 'bug_type') {
    return [`BUG类型 -> ${getBugTypeLabel(batchForm.bug_type)}`];
  }
  if (batchActionType.value === 'resolution') {
    return [
      `解决方案 -> ${getResolutionLabel(batchForm.resolution)}`,
      ...(batchForm.solution.trim() ? [`处理备注 -> ${batchForm.solution.trim()}`] : []),
    ];
  }
  return ['删除所选 BUG'];
});

const batchPreviewSummary = computed(() => {
  if (!batchActionType.value) {
    return '将按当前筛选与勾选结果执行批量操作。';
  }
  if (batchActionType.value === 'assign') {
    const names = batchForm.assigned_to.map((userId) => getMemberName(userId)).filter((name) => name && name !== '-');
    return names.length ? `目标指派人：${names.join('、')}` : '将统一修改所选 BUG 的指派人。';
  }
  if (batchActionType.value === 'status') {
    return `目标状态：${getStatusViewLabel(batchForm.status)}`;
  }
  if (batchActionType.value === 'priority') {
    return `目标优先级：P${batchForm.priority}`;
  }
  if (batchActionType.value === 'severity') {
    return `目标严重程度：S${batchForm.severity}`;
  }
  if (batchActionType.value === 'bug_type') {
    return `目标 BUG 类型：${getBugTypeLabel(batchForm.bug_type)}`;
  }
  if (batchActionType.value === 'resolution') {
    return `目标解决方案：${getResolutionLabel(batchForm.resolution)}`;
  }
  return '删除后不可恢复，请确认本次批量删除范围。';
});

const getBatchActionSummary = (type: NonNullable<typeof batchActionType.value>, count: number) => {
  if (type === 'assign') {
    const memberNames = batchForm.assigned_to
      .map((userId) => getMemberName(userId))
      .filter((name) => name && name !== '-');
    return `已将 ${count} 条 BUG 指派给 ${memberNames.length ? memberNames.join('、') : '指定成员'}`;
  }
  if (type === 'status') {
    return `已将 ${count} 条 BUG 的状态改为 ${getStatusViewLabel(batchForm.status)}`;
  }
  if (type === 'priority') {
    return `已将 ${count} 条 BUG 的优先级改为 P${batchForm.priority}`;
  }
  if (type === 'severity') {
    return `已将 ${count} 条 BUG 的严重程度改为 S${batchForm.severity}`;
  }
  if (type === 'bug_type') {
    return `已将 ${count} 条 BUG 的类型改为 ${getBugTypeLabel(batchForm.bug_type)}`;
  }
  if (type === 'resolution') {
    return `已将 ${count} 条 BUG 的解决方案改为 ${getResolutionLabel(batchForm.resolution)}`;
  }
  return `已删除 ${count} 条 BUG`;
};

const normalizePaginationCurrent = () => {
  const total = filteredBugList.value.length;
  const pageSize = Number(pagination.pageSize) > 0 ? Number(pagination.pageSize) : 10;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const current = Number(pagination.current) || 1;

  if (current > maxPage) {
    pagination.current = maxPage;
  }
  if (current < 1) {
    pagination.current = 1;
  }
};

const getSectionAttachments = (section: TestBugAttachmentSection): TestBugAttachment[] => {
  if (!detailBug.value?.attachments?.length) {
    return [];
  }
  return detailBug.value.attachments.filter((attachment) => attachment.section === section);
};

const mapPendingAttachmentFile = (file: File): LocalPendingBugAttachmentFile => {
  const mimeType = String(file.type || '').toLowerCase();
  const fileType = mimeType.startsWith('image/')
    ? 'image'
    : mimeType.startsWith('video/')
      ? 'video'
      : 'file';

  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    original_name: file.name,
    file_type: fileType,
    url: URL.createObjectURL(file),
    file,
  };
};

const removePendingAttachment = (section: TestBugAttachmentSection, id: string) => {
  const nextFiles = pendingAttachmentFiles[section].filter((item) => item.id !== id);
  const removedFile = pendingAttachmentFiles[section].find((item) => item.id === id);
  if (removedFile?.url?.startsWith('blob:')) {
    URL.revokeObjectURL(removedFile.url);
  }
  pendingAttachmentFiles[section] = nextFiles;
};

const appendPendingAttachments = (section: TestBugAttachmentSection, files: File[]) => {
  pendingAttachmentFiles[section] = [
    ...pendingAttachmentFiles[section],
    ...files.map((file) => mapPendingAttachmentFile(file)),
  ];
};

const flushPendingAttachments = async (bugId: number) => {
  if (!props.currentProjectId) {
    return;
  }

  const sections: TestBugAttachmentSection[] = ['steps', 'expected_result', 'actual_result'];
  for (const section of sections) {
    const pendingItems = pendingAttachmentFiles[section];
    if (!pendingItems.length) {
      continue;
    }
    const response = await uploadTestBugAttachments(
      props.currentProjectId,
      bugId,
      section,
      pendingItems.map((item) => item.file)
    );
    if (!response.success) {
      Message.error(response.error || '上传 BUG 附件失败');
      continue;
    }
    pendingItems.forEach((item) => {
      if (item.url.startsWith('blob:')) {
        URL.revokeObjectURL(item.url);
      }
    });
    pendingAttachmentFiles[section] = [];
  }
};

const actionModalTitle = computed(() => {
  if (actionType.value === 'assign') return '指派 BUG';
  if (actionType.value === 'confirm') return '确认 BUG';
  if (actionType.value === 'fix') return '修复 BUG';
  if (actionType.value === 'resolve') return '提交复测';
  if (actionType.value === 'activate') return '激活 BUG';
  if (actionType.value === 'close') return '关闭 BUG';
  return '处理 BUG';
});

const resetActionState = () => {
  actionBug.value = null;
  actionType.value = null;
  actionForm.assigned_to = [];
  actionForm.resolution = 'fixed';
  actionForm.solution = '';
};

const resetPendingAttachments = () => {
  [...pendingAttachmentFiles.steps, ...pendingAttachmentFiles.expected_result, ...pendingAttachmentFiles.actual_result].forEach((item) => {
    if (item.url.startsWith('blob:')) {
      URL.revokeObjectURL(item.url);
    }
  });
  pendingAttachmentFiles.steps = [];
  pendingAttachmentFiles.expected_result = [];
  pendingAttachmentFiles.actual_result = [];
};

const resetDetailForm = () => {
  detailForm.title = '';
  detailForm.testcase_ids = [];
  detailForm.assigned_to = [];
  detailForm.bug_type = 'codeerror';
  detailForm.resolution = '';
  detailForm.severity = '3';
  detailForm.priority = '3';
  detailForm.deadline = undefined;
  detailForm.keywords = '';
  detailForm.steps = '';
  detailForm.expected_result = '';
  detailForm.actual_result = '';
  detailForm.solution = '';
  resetPendingAttachments();
};

const fillDetailForm = (bug: TestBug) => {
  detailForm.title = bug.title || '';
  detailForm.testcase_ids = Array.isArray(bug.testcase_ids)
    ? bug.testcase_ids.map((item) => Number(item))
    : bug.testcase
      ? [Number(bug.testcase)]
      : [];
  detailForm.assigned_to = getAssignedUserIds(bug);
  detailForm.bug_type = bug.bug_type;
  detailForm.resolution = bug.resolution || '';
  detailForm.severity = bug.severity || '3';
  detailForm.priority = bug.priority || '3';
  detailForm.deadline = bug.deadline || undefined;
  detailForm.keywords = bug.keywords || '';
  detailForm.steps = bug.steps || '';
  detailForm.expected_result = bug.expected_result || '';
  detailForm.actual_result = bug.actual_result || '';
  detailForm.solution = bug.solution || '';
};

const startDetailEdit = async (bug: TestBug) => {
  await fetchSuiteTestCases();
  if (detailBug.value?.id !== bug.id) {
    const detail = await fetchBugDetail(bug.id);
    if (!detail) {
      return;
    }
    detailBug.value = detail;
  }
  if (!detailBug.value) {
    return;
  }
  fillDetailForm(detailBug.value);
  detailDraftType.value = null;
  detailEditMode.value = true;
  resetPendingAttachments();
};

const cancelDetailEdit = () => {
  const isCreateDraft = detailDraftType.value === 'create' && !detailBug.value;
  detailDraftType.value = null;
  detailEditMode.value = false;
  if (isCreateDraft) {
    resetDetailForm();
    viewMode.value = 'list';
    return;
  }
  if (detailBug.value) {
    fillDetailForm(detailBug.value);
  } else {
    resetDetailForm();
  }
  resetPendingAttachments();
};

const openCopyDetail = async (bug: TestBug) => {
  detailDraftType.value = 'copy';
  viewMode.value = 'detail';
  await fetchSuiteTestCases();
  if (detailBug.value?.id !== bug.id) {
    const detail = await fetchBugDetail(bug.id);
    if (!detail) {
      return;
    }
    detailBug.value = detail;
  }
  if (!detailBug.value) {
    return;
  }
  fillDetailForm(detailBug.value);
  detailForm.title = '';
  detailForm.steps = '';
  detailForm.expected_result = '';
  detailForm.actual_result = '';
  detailEditMode.value = true;
  resetPendingAttachments();
};

const resetFilters = async () => {
  filters.search = '';
  filters.bug_type = undefined;
  filters.severity = undefined;
  filters.priority = undefined;
  filters.assigned_to = undefined;
  activeStatusView.value = 'all';
  activeQuickView.value = 'all';
  pagination.current = 1;
  await fetchBugs();
};

const persistBugFilters = () => {
  localStorage.setItem(
    getBugFilterStorageKey(props.currentProjectId),
    JSON.stringify({
      search: filters.search || '',
      bug_type: filters.bug_type || null,
      severity: filters.severity || null,
      priority: filters.priority || null,
      assigned_to: filters.assigned_to || null,
      activeStatusView: activeStatusView.value,
      activeQuickView: activeQuickView.value,
      sortBy: sortBy.value,
    })
  );
};

const persistSavedFilterViews = () => {
  localStorage.setItem(getBugFilterViewsStorageKey(props.currentProjectId), JSON.stringify(savedFilterViews.value));
};

const isSameFilterSnapshot = (
  left: SavedBugFilterView['filters'],
  right: SavedBugFilterView['filters']
) => (
  String(left.search || '') === String(right.search || '') &&
  String(left.bug_type || '') === String(right.bug_type || '') &&
  String(left.severity || '') === String(right.severity || '') &&
  String(left.priority || '') === String(right.priority || '') &&
  Number(left.assigned_to || 0) === Number(right.assigned_to || 0) &&
  left.activeStatusView === right.activeStatusView &&
  left.activeQuickView === right.activeQuickView &&
  left.sortBy === right.sortBy
);

const currentAppliedFilterViewId = computed(() => {
  const snapshot = buildCurrentFilterSnapshot();
  return savedFilterViews.value.find((item) => isSameFilterSnapshot(item.filters, snapshot))?.id || null;
});

const getSavedFilterViewMetaLabel = (view: SavedBugFilterView) => {
  const parts: string[] = [];
  if (view.updated_at) {
    parts.push(`最近保存：${formatDate(view.updated_at)}`);
  } else if (view.created_at) {
    parts.push(`创建时间：${formatDate(view.created_at)}`);
  }
  if (view.last_applied_at) {
    parts.push(`最近使用：${formatDate(view.last_applied_at)}`);
  }
  return parts.join(' | ') || '点击应用该视图';
};

const applySavedFilterView = async (id: string) => {
  const view = savedFilterViews.value.find((item) => item.id === id);
  if (!view) {
    return;
  }

  filters.search = view.filters.search || '';
  filters.bug_type = view.filters.bug_type || undefined;
  filters.severity = view.filters.severity || undefined;
  filters.priority = view.filters.priority || undefined;
  filters.assigned_to = view.filters.assigned_to ? Number(view.filters.assigned_to) : undefined;
  activeStatusView.value = view.filters.activeStatusView || 'all';
  activeQuickView.value = view.filters.activeQuickView || 'all';
  sortBy.value = view.filters.sortBy || 'priority_desc';
  pagination.current = 1;

  const now = new Date().toISOString();
  savedFilterViews.value = savedFilterViews.value.map((item) =>
    item.id === id ? { ...item, last_applied_at: now } : item
  );
  sortSavedFilterViews();
  persistSavedFilterViews();
  await fetchBugs();
};

const applySavedBugFilters = (projectId?: number | null) => {
  const resetState = () => {
    filters.search = '';
    filters.bug_type = undefined;
    filters.severity = undefined;
    filters.priority = undefined;
    filters.assigned_to = undefined;
    activeStatusView.value = 'all';
    activeQuickView.value = 'all';
    sortBy.value = 'priority_desc';
  };

  const savedFilters = localStorage.getItem(getBugFilterStorageKey(projectId));
  if (!savedFilters) {
    resetState();
    return;
  }

  try {
    const parsed = JSON.parse(savedFilters);
    filters.search = typeof parsed?.search === 'string' ? parsed.search : '';
    filters.bug_type = parsed?.bug_type || undefined;
    filters.severity = parsed?.severity || undefined;
    filters.priority = parsed?.priority || undefined;
    filters.assigned_to = parsed?.assigned_to ? Number(parsed.assigned_to) : undefined;
    activeStatusView.value = parsed?.activeStatusView || 'all';
    activeQuickView.value = parsed?.activeQuickView || 'all';
    sortBy.value = parsed?.sortBy || 'priority_desc';
  } catch (error) {
    localStorage.removeItem(getBugFilterStorageKey(projectId));
    resetState();
  }
};

const loadSavedFilterViews = (projectId?: number | null) => {
  const saved = localStorage.getItem(getBugFilterViewsStorageKey(projectId));
  if (!saved) {
    savedFilterViews.value = [];
    return;
  }
  try {
    const parsed = JSON.parse(saved);
    savedFilterViews.value = Array.isArray(parsed)
      ? parsed
          .filter((item) => item && typeof item.name === 'string' && item.filters)
          .map((item) => ({
            ...item,
            created_at: item.created_at || item.updated_at || undefined,
            updated_at: item.updated_at || item.created_at || undefined,
            last_applied_at: item.last_applied_at || undefined,
          }))
      : [];
    sortSavedFilterViews();
  } catch (error) {
    localStorage.removeItem(getBugFilterViewsStorageKey(projectId));
    savedFilterViews.value = [];
  }
};

const openSaveFilterViewModal = () => {
  saveFilterViewName.value = '';
  editingFilterViewId.value = null;
  saveFilterViewVisible.value = true;
};

const resetSaveFilterViewState = () => {
  saveFilterViewVisible.value = false;
  saveFilterViewName.value = '';
  editingFilterViewId.value = null;
};

const exportSavedFilterViews = () => {
  const payload = {
    exported_at: new Date().toISOString(),
    project_id: props.currentProjectId,
    views: savedFilterViews.value,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `flytest_bug_views_${props.currentProjectId || 'global'}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
  Message.success('å¸¸ç¨è§å¾å·²å¯¼åº');
};

const triggerImportFilterViews = () => {
  filterViewImportRef.value?.click();
};

const handleImportFilterViews = async (event: Event) => {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (!file) {
    return;
  }

  try {
    const text = await file.text();
    const parsed = JSON.parse(text);
    const importedViews = Array.isArray(parsed?.views) ? parsed.views : Array.isArray(parsed) ? parsed : [];
    if (!importedViews.length) {
      Message.warning('导入文件中没有可用的常用视图');
      return;
    }

    const now = new Date().toISOString();
    const normalizedViews = importedViews
      .filter((item) => item && typeof item.name === 'string' && item.filters)
      .map((item: any) => ({
        id: String(item.id || `view_${Date.now()}_${Math.random().toString(16).slice(2)}`),
        name: String(item.name).trim(),
        pinned: Boolean(item.pinned),
        created_at: item.created_at || item.updated_at || now,
        updated_at: item.updated_at || item.created_at || now,
        last_applied_at: item.last_applied_at || undefined,
        filters: {
          search: String(item.filters.search || ''),
          bug_type: item.filters.bug_type || undefined,
          severity: item.filters.severity || undefined,
          priority: item.filters.priority || undefined,
          assigned_to: item.filters.assigned_to ? Number(item.filters.assigned_to) : undefined,
          activeStatusView: item.filters.activeStatusView || 'all',
          activeQuickView: item.filters.activeQuickView || 'all',
          sortBy: item.filters.sortBy || 'priority_desc',
        },
      }))
      .filter((item) => item.name);

    if (!normalizedViews.length) {
      Message.warning('导入文件中没有有效的常用视图');
      return;
    }

    const conflictViews = normalizedViews.filter((view) =>
      savedFilterViews.value.some((item) => item.name === view.name || item.id === view.id)
    );
    const shouldOverwrite = conflictViews.length
      ? await new Promise<boolean>((resolve) => {
          Modal.warning({
            title: '检测到冲突视图',
            content: `发现 ${conflictViews.length} 个同名或同 ID 视图，是否使用导入内容覆盖现有视图？`,
            okText: '覆盖导入',
            cancelText: '仅导入新增',
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          });
        })
      : true;

    const mergedViews = [...savedFilterViews.value];
    let importedCount = 0;
    let skippedCount = 0;

    normalizedViews.forEach((view) => {
      const existingIndex = mergedViews.findIndex((item) => item.name === view.name || item.id === view.id);
      if (existingIndex >= 0) {
        if (!shouldOverwrite) {
          skippedCount += 1;
          return;
        }
        mergedViews.splice(existingIndex, 1, {
          ...mergedViews[existingIndex],
          ...view,
          id: mergedViews[existingIndex].id,
          created_at: mergedViews[existingIndex].created_at || view.created_at,
          updated_at: now,
        });
        importedCount += 1;
        return;
      }

      mergedViews.push(view);
      importedCount += 1;
    });

    savedFilterViews.value = mergedViews.slice(0, 20);
    sortSavedFilterViews();
    persistSavedFilterViews();
    Message.success(
      skippedCount > 0
        ? `已导入 ${importedCount} 个常用视图，跳过 ${skippedCount} 个重复视图`
        : `已导入 ${importedCount} 个常用视图`
    );
  } catch (error) {
    Message.error('导入失败，请检查文件格式是否为有效的 JSON');
  } finally {
    if (input) {
      input.value = '';
    }
  }
};

const submitSaveFilterView = () => {
  const name = saveFilterViewName.value.trim();
  const isEditing = Boolean(editingFilterViewId.value);
  if (!name) {
    Message.warning('请输入常用视图名称');
    return;
  }
  const previousView = editingFilterViewId.value
    ? savedFilterViews.value.find((item) => item.id === editingFilterViewId.value)
    : null;
  const now = new Date().toISOString();
  const nextView: SavedBugFilterView = {
    id: previousView?.id || `view_${Date.now()}`,
    name,
    pinned: previousView?.pinned || false,
    created_at: previousView?.created_at || now,
    updated_at: now,
    last_applied_at: previousView?.last_applied_at,
    filters: {
      ...buildCurrentFilterSnapshot(),
    },
  };
  const targetIndex = editingFilterViewId.value
    ? savedFilterViews.value.findIndex((item) => item.id === editingFilterViewId.value)
    : savedFilterViews.value.findIndex((item) => item.name === name);
  if (targetIndex >= 0) {
    savedFilterViews.value.splice(targetIndex, 1, {
      ...savedFilterViews.value[targetIndex],
      ...nextView,
      id: savedFilterViews.value[targetIndex].id,
    });
  } else {
    savedFilterViews.value = [nextView, ...savedFilterViews.value].slice(0, 8);
  }
  sortSavedFilterViews();
  persistSavedFilterViews();
  resetSaveFilterViewState();
  Message.success(isEditing ? '常用视图已更新' : '常用视图已保存');
};

const removeSavedFilterView = (id: string) => {
  savedFilterViews.value = savedFilterViews.value.filter((item) => item.id !== id);
  persistSavedFilterViews();
  Message.success('å¸¸ç¨è§å¾å·²å é¤');
};

const sortSavedFilterViews = () => {
  savedFilterViews.value = [...savedFilterViews.value].sort((left, right) => {
    const pinDiff = Number(Boolean(right.pinned)) - Number(Boolean(left.pinned));
    if (pinDiff !== 0) {
      return pinDiff;
    }
    const appliedDiff = getBugTimeValue(right.last_applied_at) - getBugTimeValue(left.last_applied_at);
    if (appliedDiff !== 0) {
      return appliedDiff;
    }
    const updatedDiff = getBugTimeValue(right.updated_at) - getBugTimeValue(left.updated_at);
    if (updatedDiff !== 0) {
      return updatedDiff;
    }
    return right.id.localeCompare(left.id);
  });
};

const openEditFilterViewModal = (view: SavedBugFilterView) => {
  editingFilterViewId.value = view.id;
  saveFilterViewName.value = view.name;
  saveFilterViewVisible.value = true;
};

const togglePinFilterView = (id: string) => {
  savedFilterViews.value = savedFilterViews.value.map((item) =>
    item.id === id ? { ...item, pinned: !item.pinned } : item
  );
  sortSavedFilterViews();
  persistSavedFilterViews();
  Message.success('常用视图置顶状态已更新');
};

const restoreLastSelection = () => {
  if (!lastSelectionSnapshot.value.length) {
    return;
  }
  selectedBugIds.value = lastSelectionSnapshot.value.filter((id) => bugList.value.some((bug) => bug.id === id));
  Message.success(`已恢复 ${selectedBugIds.value.length} 条 BUG 的勾选状态`);
};

const getStatusViewLabel = (value: StatusView) => {
  if (value === 'all') return '全部';
  return TEST_BUG_STATUS_OPTIONS.find((item) => item.value === value)?.label || value;
};

const getQuickViewLabel = (value: QuickView) => quickViews.find((item) => item.key === value)?.label || value;

const getSortLabel = (value: BugSortValue) => bugSortOptions.find((item) => item.value === value)?.label || value;

const getMemberName = (userId?: number) => {
  if (!userId) return '-';
  const member = projectMembers.value.find((item) => Number(item.user) === Number(userId));
  return member?.user_detail?.username || '-';
};

const clearSummaryFilter = async (
  key: 'status' | 'quickView' | 'search' | 'bug_type' | 'severity' | 'priority' | 'assigned_to'
) => {
  if (key === 'status') {
    activeStatusView.value = 'all';
    pagination.current = 1;
    await fetchBugs();
    return;
  }
  if (key === 'quickView') {
    activeQuickView.value = 'all';
    pagination.current = 1;
    await fetchBugs();
    return;
  }
  if (key === 'search') filters.search = '';
  if (key === 'bug_type') filters.bug_type = undefined;
  if (key === 'severity') filters.severity = undefined;
  if (key === 'priority') filters.priority = undefined;
  if (key === 'assigned_to') filters.assigned_to = undefined;
  pagination.current = 1;
  await fetchBugs();
};

const markUpdatedRows = (ids: number[]) => {
  const nextIds = Array.from(new Set(ids.map((item) => Number(item)).filter((item) => item > 0)));
  recentlyUpdatedBugIds.value = nextIds;
  if (rowHighlightTimer) {
    clearTimeout(rowHighlightTimer);
  }
  if (!nextIds.length) {
    rowHighlightTimer = null;
    return;
  }
  rowHighlightTimer = setTimeout(() => {
    recentlyUpdatedBugIds.value = [];
    rowHighlightTimer = null;
  }, 2600);
};

const getBugRowClass = (record: TestBug) =>
  recentlyUpdatedBugIds.value.includes(record.id) ? 'bug-row-highlight' : '';

const clearUpdateSummary = () => {
  updateSummary.value = null;
  if (updateSummaryTimer) {
    clearTimeout(updateSummaryTimer);
    updateSummaryTimer = null;
  }
};

const setUpdateSummary = (text: string) => {
  clearUpdateSummary();
  updateSummary.value = {
    text,
    timeLabel: formatDate(new Date().toISOString()),
  };
  updateSummaryTimer = setTimeout(() => {
    updateSummary.value = null;
    updateSummaryTimer = null;
  }, 5000);
};

const effectiveVisibleColumns = computed<BugTableColumnKey[]>(() =>
  visibleColumns.value.length ? visibleColumns.value : DEFAULT_VISIBLE_COLUMNS.slice()
);

const isColumnVisible = (key: BugTableColumnKey) => effectiveVisibleColumns.value.includes(key);

const handleVisibleColumnsChange = (values: Array<string | number>) => {
  const nextValues = values.map((item) => String(item) as BugTableColumnKey);
  if (!nextValues.length) {
    visibleColumns.value = DEFAULT_VISIBLE_COLUMNS.slice();
    Message.warning('至少保留一列显示，已恢复默认列');
    return;
  }
  visibleColumns.value = nextValues;
};

const resetVisibleColumns = () => {
  visibleColumns.value = DEFAULT_VISIBLE_COLUMNS.slice();
};

const mergeSelectedBugIds = (ids: number[]) => {
  selectedBugIds.value = Array.from(
    new Set([...selectedBugIds.value, ...ids.map((item) => Number(item)).filter((item) => item > 0)])
  );
};

const removeSelectedBugIds = (ids: number[]) => {
  const removeSet = new Set(ids.map((item) => Number(item)).filter((item) => item > 0));
  selectedBugIds.value = selectedBugIds.value.filter((id) => !removeSet.has(id));
};

const toggleSelectCurrentPage = () => {
  if (!pagedBugIds.value.length) {
    return;
  }
  if (isCurrentPageSelected.value) {
    removeSelectedBugIds(pagedBugIds.value);
    return;
  }
  mergeSelectedBugIds(pagedBugIds.value);
};

const toggleSelectFiltered = () => {
  if (!filteredBugIds.value.length) {
    return;
  }
  if (isAllFilteredSelected.value) {
    removeSelectedBugIds(filteredBugIds.value);
    return;
  }
  selectedBugIds.value = filteredBugIds.value.slice();
};

const rowSelection = computed(() => ({
  type: 'checkbox' as const,
  showCheckedAll: true,
  selectedRowKeys: selectedBugIds.value,
  onChange: (keys: (string | number)[]) => {
    selectedBugIds.value = keys.map((item) => Number(item)).filter((item) => item > 0);
  },
}));

const syncBugRecord = (updatedBug: TestBug) => {
  const existingIndex = bugList.value.findIndex((item) => item.id === updatedBug.id);
  if (existingIndex >= 0) {
    bugList.value = bugList.value.map((item) => (item.id === updatedBug.id ? updatedBug : item));
  } else {
    bugList.value = [updatedBug, ...bugList.value];
  }
  if (detailBug.value?.id === updatedBug.id) {
    detailBug.value = updatedBug;
  }
};

const removeBugRecord = (bugId: number) => {
  bugList.value = bugList.value.filter((item) => item.id !== bugId);
  selectedBugIds.value = selectedBugIds.value.filter((item) => item !== bugId);
  normalizePaginationCurrent();
};

const resetBatchState = () => {
  batchVisible.value = false;
  batchActionType.value = null;
  batchForm.assigned_to = [];
  batchForm.status = 'assigned';
  batchForm.priority = '3';
  batchForm.severity = '3';
  batchForm.bug_type = 'codeerror';
  batchForm.resolution = 'fixed';
  batchForm.solution = '';
};

const getCommonScalarValue = <T,>(values: T[]) => {
  if (!values.length) {
    return null;
  }
  const firstValue = values[0];
  return values.every((item) => item === firstValue) ? firstValue : null;
};

const getCombinedAssignedUserIds = (bugs: TestBug[]) =>
  Array.from(new Set(bugs.flatMap((bug) => getAssignedUserIds(bug)).filter((id) => id > 0)));

const presetBatchForm = (type: 'assign' | 'status' | 'priority' | 'severity' | 'bug_type' | 'resolution' | 'delete') => {
  const selectedBugs = selectedBugRecords.value;
  batchForm.assigned_to = [];
  batchForm.status = 'assigned';
  batchForm.priority = '3';
  batchForm.severity = '3';
  batchForm.bug_type = 'codeerror';
  batchForm.resolution = 'fixed';
  batchForm.solution = '';

  if (!selectedBugs.length) {
    return;
  }

  if (type === 'assign') {
    batchForm.assigned_to = getCombinedAssignedUserIds(selectedBugs);
    return;
  }
  if (type === 'status') {
    const commonStatus = getCommonScalarValue(
      selectedBugs.map((bug) => bug.status).filter((status): status is Exclude<TestBugStatus, 'expired'> => status !== 'expired')
    );
    batchForm.status = commonStatus || 'assigned';
    return;
  }
  if (type === 'priority') {
    batchForm.priority = getCommonScalarValue(selectedBugs.map((bug) => String(bug.priority || '3'))) || '3';
    return;
  }
  if (type === 'severity') {
    batchForm.severity = getCommonScalarValue(selectedBugs.map((bug) => String(bug.severity || '3'))) || '3';
    return;
  }
  if (type === 'bug_type') {
    batchForm.bug_type = getCommonScalarValue(selectedBugs.map((bug) => bug.bug_type || 'codeerror')) || 'codeerror';
    return;
  }
  if (type === 'resolution') {
    batchForm.resolution =
      getCommonScalarValue(
        selectedBugs.map((bug) => bug.resolution).filter((value): value is TestBugResolution => Boolean(value))
      ) || 'fixed';
    batchForm.solution =
      getCommonScalarValue(selectedBugs.map((bug) => String(bug.solution || '').trim()).filter((value) => Boolean(value))) || '';
  }
};

const openBatchModal = (type: 'assign' | 'status' | 'priority' | 'severity' | 'bug_type' | 'resolution' | 'delete') => {
  if (!selectedBugCount.value) {
    Message.warning('请先选择 BUG');
    return;
  }
  presetBatchForm(type);
  batchActionType.value = type;
  batchVisible.value = true;
};

const submitBatchAction = async () => {
  if (!props.currentProjectId || !selectedBugIds.value.length || !batchActionType.value) {
    return;
  }
  const currentBatchType = batchActionType.value;
  if (batchActionType.value === 'assign' && batchForm.assigned_to.length === 0) {
    Message.warning('请选择指派人员');
    return;
  }
  if (batchActionType.value === 'resolution' && !batchForm.resolution) {
    Message.warning('请选择解决方案');
    return;
  }

  batchSubmitting.value = true;
  try {
    let response;
    if (batchActionType.value === 'assign') {
      response = await batchAssignTestBugs(props.currentProjectId, selectedBugIds.value, batchForm.assigned_to);
    } else if (batchActionType.value === 'status') {
      response = await batchChangeTestBugStatus(props.currentProjectId, selectedBugIds.value, batchForm.status);
    } else if (batchActionType.value === 'priority') {
      response = await batchUpdateTestBugPriority(props.currentProjectId, selectedBugIds.value, batchForm.priority);
    } else if (batchActionType.value === 'severity') {
      response = await batchUpdateTestBugSeverity(props.currentProjectId, selectedBugIds.value, batchForm.severity);
    } else if (batchActionType.value === 'bug_type') {
      response = await batchUpdateTestBugType(props.currentProjectId, selectedBugIds.value, batchForm.bug_type);
    } else if (batchActionType.value === 'resolution') {
      response = await batchUpdateTestBugResolution(
        props.currentProjectId,
        selectedBugIds.value,
        batchForm.resolution,
        batchForm.solution.trim() || undefined
      );
    } else {
      response = await batchDeleteTestBugs(props.currentProjectId, selectedBugIds.value);
    }

    if (!response.success) {
      Message.error(response.error || '批量操作失败');
      return;
    }

    const selectedCount = selectedBugIds.value.length;
    const summaryText = getBatchActionSummary(currentBatchType, selectedCount);

    lastSelectionSnapshot.value = [...selectedBugIds.value];
    resetBatchState();
    selectedBugIds.value = [];
    await fetchBugs();
    markUpdatedRows(response.updated_ids || []);
    setUpdateSummary(summaryText);
    Message.success(response.message || summaryText);

    if (detailBug.value && currentBatchType !== 'delete') {
      const detailStillExists = bugList.value.some((item) => item.id === detailBug.value?.id);
      if (detailStillExists) {
        detailBug.value = await fetchBugDetail(detailBug.value.id);
      }
    }
    if (detailBug.value && currentBatchType === 'delete') {
      viewMode.value = 'list';
      detailBug.value = null;
    }
  } finally {
    batchSubmitting.value = false;
  }
};

const updateBugField = async (bug: TestBug, payload: Partial<TestBug>, successMessage: string) => {
  if (!props.currentProjectId) return;
  const response = await updateTestBug(props.currentProjectId, bug.id, payload);
  if (!response.success || !response.data) {
    Message.error(response.error || '更新 BUG 失败');
    return;
  }
  syncBugRecord(response.data);
  markUpdatedRows([response.data.id]);
  setUpdateSummary('刚刚更新了 BUG #' + response.data.id);
  Message.success(successMessage);
};

const getStatusActionOptions = (bug: TestBug) => {
  const items: Array<{ value: Exclude<ActionType, null>; label: string }> = [];
  items.push({ value: 'assign', label: '指派' });
  if (bug.status === 'assigned') items.push({ value: 'confirm', label: '确认' });
  if (bug.status === 'confirmed') items.push({ value: 'fix', label: '修复' });
  if (bug.status === 'fixed') items.push({ value: 'resolve', label: '提交复测' });
  if (['pending_retest', 'closed', 'expired'].includes(bug.status)) items.push({ value: 'activate', label: '激活' });
  if (bug.status !== 'closed') items.push({ value: 'close', label: '关闭' });
  return items;
};

const handleStatusQuickSelect = async (bug: TestBug, action: string) => {
  await handleActionSelect(bug, action);
};

const getAssignedUserIds = (bug: TestBug) => {
  if (Array.isArray(bug.assigned_to_ids) && bug.assigned_to_ids.length > 0) {
    return bug.assigned_to_ids.map((item) => Number(item));
  }
  if (bug.assigned_to) {
    return [Number(bug.assigned_to)];
  }
  return [];
};

const getAssignedUserName = (bug: TestBug) => {
  if (Array.isArray(bug.assigned_to_names) && bug.assigned_to_names.length > 0) {
    return bug.assigned_to_names.join('、');
  }
  if (Array.isArray(bug.assigned_to_details) && bug.assigned_to_details.length > 0) {
    return bug.assigned_to_details.map((item) => item.username).join('、');
  }
  return bug.assigned_to_detail?.username || bug.assigned_to_name || '-';
};

const getCreatorName = (bug: TestBug) => bug.creator_detail?.username || bug.opened_by_name || '-';

const getRelatedTestcaseNames = (bug?: TestBug | null) => {
  if (!bug) {
    return [];
  }
  if (Array.isArray(bug.testcase_names) && bug.testcase_names.length > 0) {
    return bug.testcase_names.filter((item) => String(item || '').trim());
  }
  if (bug.testcase_name) {
    return [bug.testcase_name];
  }
  return [];
};

const getRelatedTestcaseSummary = (bug?: TestBug | null) => {
  const names = getRelatedTestcaseNames(bug);
  return names.length ? names.join('、') : '-';
};

const fetchMembers = async () => {
  if (!props.currentProjectId) {
    projectMembers.value = [];
    return;
  }

  const response = await getProjectMembers(props.currentProjectId);
  projectMembers.value = response.success && response.data ? response.data : [];
};

const fetchSuiteTestCases = async () => {
  if (!props.currentProjectId || !props.selectedSuiteId) {
    suiteTestCases.value = [];
    return;
  }

  const response = await getTestCaseList(props.currentProjectId, {
    page: 1,
    pageSize: 500,
    suite_id: props.selectedSuiteId,
  });

  suiteTestCases.value = response.success && response.data ? response.data : [];
};

const fetchBugs = async () => {
  if (!props.currentProjectId || !props.selectedSuiteId) {
    bugList.value = [];
    return;
  }

  loading.value = true;
  try {
    const response = await getTestBugList(props.currentProjectId, {
      suite_id: props.selectedSuiteId,
      search: filters.search || undefined,
      bug_type: filters.bug_type,
      severity: filters.severity,
      priority: filters.priority,
      assigned_to: filters.assigned_to,
    });

    if (!response.success) {
      bugList.value = [];
      Message.error(response.error || '获取 BUG 列表失败');
      return;
    }

    bugList.value = response.data || [];
    normalizePaginationCurrent();
  } finally {
    loading.value = false;
  }
};

const fetchBugDetail = async (bugId: number) => {
  if (!props.currentProjectId) {
    return null;
  }

  const response = await getTestBugDetail(props.currentProjectId, bugId);
  if (!response.success || !response.data) {
    Message.error(response.error || '获取 BUG 详情失败');
    return null;
  }
  return response.data;
};

const handleDetailAttachmentUpload = async (section: TestBugAttachmentSection, files: File[]) => {
  if (!files.length) {
    return;
  }

  if (!props.currentProjectId || !detailBug.value?.id || detailDraftType.value) {
    appendPendingAttachments(section, files);
    return;
  }

  const response = await uploadTestBugAttachments(props.currentProjectId, detailBug.value.id, section, files);
  if (!response.success) {
    Message.error(response.error || '上传 BUG 附件失败');
    return;
  }

  const detail = await fetchBugDetail(detailBug.value.id);
  if (detail) {
    detailBug.value = detail;
    syncBugRecord(detail);
  }
  Message.success('附件上传成功');
};

const removeDetailAttachment = async (section: TestBugAttachmentSection, attachment: TestBugAttachment) => {
  if (!props.currentProjectId || !detailBug.value?.id) {
    return;
  }
  const response = await deleteTestBugAttachment(props.currentProjectId, detailBug.value.id, attachment.id);
  if (!response.success) {
    Message.error(response.error || '删除 BUG 附件失败');
    return;
  }
  detailBug.value = {
    ...detailBug.value,
    attachments: (detailBug.value.attachments || []).filter((item) => item.id !== attachment.id),
  };
  syncBugRecord(detailBug.value);
  Message.success(`${section === 'steps' ? '重现步骤' : section === 'expected_result' ? '期望结果' : '实际结果'}附件已删除`);
};

const openCreateDetail = async () => {
  detailBug.value = null;
  detailDraftType.value = 'create';
  detailEditMode.value = true;
  viewMode.value = 'detail';
  resetDetailForm();
  await fetchSuiteTestCases();
};

const openDetail = async (bug: TestBug, startEdit = false) => {
  detailLoading.value = true;
  detailDraftType.value = null;
  detailEditMode.value = false;
  viewMode.value = 'detail';
  resetPendingAttachments();
  try {
    detailBug.value = await fetchBugDetail(bug.id);
    if (detailBug.value) {
      fillDetailForm(detailBug.value);
    }
  } finally {
    detailLoading.value = false;
  }

  if (startEdit && detailBug.value) {
    detailEditMode.value = true;
    await fetchSuiteTestCases();
  }
};

const backToList = () => {
  detailDraftType.value = null;
  detailEditMode.value = false;
  viewMode.value = 'list';
  resetPendingAttachments();
};

const saveDetailEdit = async () => {
  if (!props.currentProjectId) return;
  if (!detailForm.title.trim()) {
    Message.warning('请填写 BUG 标题');
    return;
  }

  detailSaving.value = true;
  try {
    const payload = {
      title: detailForm.title.trim(),
      testcase_ids: detailForm.testcase_ids,
      assigned_to_ids: detailForm.assigned_to,
      bug_type: detailForm.bug_type,
      resolution: detailForm.resolution,
      severity: detailForm.severity,
      priority: detailForm.priority,
      deadline: detailForm.deadline,
      keywords: detailForm.keywords.trim(),
      steps: detailForm.steps,
      expected_result: detailForm.expected_result,
      actual_result: detailForm.actual_result,
      solution: detailForm.solution.trim(),
    };

    const isDraftCreate = detailDraftType.value === 'create' || detailDraftType.value === 'copy';
    const response = isDraftCreate
      ? await createTestBug(props.currentProjectId, {
          ...payload,
          suite: props.selectedSuiteId || undefined,
        })
      : detailBug.value
        ? await updateTestBug(props.currentProjectId, detailBug.value.id, payload)
        : { success: false, error: '未找到当前 BUG' };
    if (!response.success || !response.data) {
      Message.error(response.error || '保存 BUG 失败');
      return;
    }

    await flushPendingAttachments(response.data.id);
    const latestDetail = await fetchBugDetail(response.data.id);
    const nextBug = latestDetail || response.data;
    syncBugRecord(nextBug);
    fillDetailForm(nextBug);
    detailBug.value = nextBug;
    detailDraftType.value = null;
    detailEditMode.value = false;
    markUpdatedRows([nextBug.id]);
    setUpdateSummary((isDraftCreate ? '刚刚新增了 BUG #' : '刚刚更新了 BUG #') + nextBug.id);
    Message.success(isDraftCreate ? 'BUG 创建成功' : 'BUG 更新成功');
    await fetchBugs();
  } finally {
    detailSaving.value = false;
  }
};

const openActionModal = (bug: TestBug, type: Exclude<ActionType, null>) => {
  actionBug.value = bug;
  actionType.value = type;
  actionForm.assigned_to = getAssignedUserIds(bug);
  actionForm.resolution = bug.resolution || 'fixed';
  actionForm.solution = bug.solution || '';
  actionVisible.value = true;
};

const submitAction = async () => {
  if (!props.currentProjectId || !actionBug.value || !actionType.value) {
    return;
  }

  if (actionType.value === 'assign' && actionForm.assigned_to.length === 0) {
    Message.warning('请选择指派人员');
    return;
  }

  if ((actionType.value === 'fix' || actionType.value === 'resolve' || actionType.value === 'close') && !actionForm.resolution) {
    Message.warning('请选择解决方案');
    return;
  }

  actionSubmitting.value = true;
  try {
    let response;
    if (actionType.value === 'assign') {
      response = await assignTestBug(props.currentProjectId, actionBug.value.id, actionForm.assigned_to);
    } else if (actionType.value === 'confirm') {
      response = await confirmTestBug(props.currentProjectId, actionBug.value.id);
    } else if (actionType.value === 'fix') {
      response = await fixTestBug(
        props.currentProjectId,
        actionBug.value.id,
        actionForm.resolution,
        actionForm.solution.trim()
      );
    } else if (actionType.value === 'resolve') {
      response = await resolveTestBug(
        props.currentProjectId,
        actionBug.value.id,
        actionForm.resolution,
        actionForm.solution.trim()
      );
    } else if (actionType.value === 'activate') {
      response = await activateTestBug(props.currentProjectId, actionBug.value.id);
    } else {
      response = await closeTestBug(
        props.currentProjectId,
        actionBug.value.id,
        actionForm.resolution,
        actionForm.solution.trim()
      );
    }

    if (!response.success) {
      Message.error(response.error || 'BUG 操作失败');
      return;
    }

    if (response.data) {
      syncBugRecord(response.data);
    }
    Message.success(getActionSuccessMessage(actionType.value));
    markUpdatedRows(response.data ? [response.data.id] : [actionBug.value.id]);
    setUpdateSummary(getActionSuccessMessage(actionType.value));
    actionVisible.value = false;
    await fetchBugs();

    if (viewMode.value === 'detail' && detailBug.value?.id === actionBug.value.id) {
      detailBug.value = await fetchBugDetail(actionBug.value.id);
    }

    resetActionState();
  } finally {
    actionSubmitting.value = false;
  }
};

const getActionSuccessMessage = (type: Exclude<ActionType, null>) => {
  if (type === 'assign') return 'BUG 指派成功';
  if (type === 'confirm') return 'BUG 已确认';
  if (type === 'fix') return 'BUG 已修复';
  if (type === 'resolve') return 'BUG 已提交复测';
  if (type === 'activate') return 'BUG 已激活';
  return 'BUG 已关闭';
};

const handleActionSelect = async (bug: TestBug, action: string) => {
  if (!props.currentProjectId) {
    return;
  }

  if (action === 'delete') {
    Modal.warning({
      title: '删除 BUG',
      content: '确定删除 BUG「' + bug.title + '」吗？',
      onOk: async () => {
        const response = await deleteTestBug(props.currentProjectId, bug.id);
        if (!response.success) {
          Message.error(response.error || '删除 BUG 失败');
          return false;
        }

        if (detailBug.value?.id === bug.id) {
          viewMode.value = 'list';
          detailBug.value = null;
        }

        removeBugRecord(bug.id);
        Message.success('BUG 已删除');
        setUpdateSummary('刚刚删除了 BUG #' + bug.id);
        await fetchBugs();
        return true;
      },
    });
    return;
  }

  if (
    action === 'assign' ||
    action === 'confirm' ||
    action === 'fix' ||
    action === 'resolve' ||
    action === 'activate' ||
    action === 'close'
  ) {
    openActionModal(bug, action);
  }
};

const handleFilterChange = async () => {
  pagination.current = 1;
  await fetchBugs();
};

const getStatusColor = (status?: string) => {
  if (status === 'unassigned') return 'gray';
  if (status === 'assigned') return 'arcoblue';
  if (status === 'confirmed') return 'blue';
  if (status === 'fixed') return 'green';
  if (status === 'pending_retest') return 'gold';
  if (status === 'closed') return 'gray';
  if (status === 'expired') return 'red';
  return 'arcoblue';
};

const getSeverityColor = (severity?: string) => {
  if (severity === '1') return 'red';
  if (severity === '2') return 'orangered';
  if (severity === '3') return 'orange';
  return 'gold';
};

const getPriorityColor = (priority?: string) => {
  if (priority === '1') return 'red';
  if (priority === '2') return 'orange';
  if (priority === '3') return 'gold';
  return 'gray';
};

const escapeBugHtml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#39;');

const renderBugContent = (value?: string | null) => {
  const content = String(value || '').trim();
  if (!content) {
    return '<span class="bug-detail-empty">-</span>';
  }
  if (/<\/?[a-z][\s\S]*>/i.test(content)) {
    return content;
  }
  return '<div>' + escapeBugHtml(content).replace(/\r?\n/g, '<br />') + '</div>';
};

const getBugTypeLabel = (bugType?: TestBugType | string) => {
  return TEST_BUG_TYPE_OPTIONS.find((item) => item.value === bugType)?.label || '-';
};

const getResolutionLabel = (resolution?: TestBugResolution | string) => {
  if (!resolution) return '-';
  return TEST_BUG_RESOLUTION_OPTIONS.find((item) => item.value === resolution)?.label || String(resolution);
};

const getBugTypeColor = (bugType?: TestBugType | string) => {
  if (bugType === 'codeerror') return 'orangered';
  if (bugType === 'design') return 'purple';
  if (bugType === 'standard') return 'arcoblue';
  if (bugType === 'performance') return 'gold';
  if (bugType === 'config') return 'lime';
  if (bugType === 'install') return 'cyan';
  if (bugType === 'security') return 'red';
  return 'gray';
};

const getResolutionColor = (resolution?: TestBugResolution | string) => {
  if (!resolution) return 'gray';
  if (resolution === 'fixed') return 'green';
  if (resolution === 'postponed') return 'gold';
  if (resolution === 'notrepro') return 'gray';
  if (resolution === 'external') return 'arcoblue';
  if (resolution === 'duplicate') return 'purple';
  if (resolution === 'wontfix') return 'red';
  if (resolution === 'bydesign') return 'lime';
  return 'gray';
};

const handleBugTypeChange = async (bug: TestBug, bugType: TestBugType) => {
  if (bug.bug_type === bugType) return;
  await updateBugField(bug, { bug_type: bugType }, 'BUG 类型已更新');
};

const handleSeverityChange = async (bug: TestBug, severity: string) => {
  if (bug.severity === severity) return;
  await updateBugField(bug, { severity }, '严重程度已更新');
};

const handlePriorityChange = async (bug: TestBug, priority: string) => {
  if (bug.priority === priority) return;
  await updateBugField(bug, { priority }, '优先级已更新');
};

watch([activeStatusView, activeQuickView], () => {
  pagination.current = 1;
  persistBugFilters();
});

watch(
  () => [filters.search, filters.bug_type, filters.severity, filters.priority, filters.assigned_to, sortBy.value],
  () => {
    persistBugFilters();
  }
);

watch(
  () => filteredBugList.value.length,
  () => {
    normalizePaginationCurrent();
    selectedBugIds.value = selectedBugIds.value.filter((id) => bugList.value.some((bug) => bug.id === id));
  }
);

watch(
  visibleColumns,
  (value) => {
    const nextColumns = tableColumnOptions
      .map((item) => item.key)
      .filter((key) => value.includes(key));
    if (!nextColumns.length) {
      visibleColumns.value = DEFAULT_VISIBLE_COLUMNS.slice();
      return;
    }
    localStorage.setItem(getBugColumnStorageKey(props.currentProjectId), JSON.stringify(nextColumns));
  },
  { deep: true }
);

watch(
  () => [props.currentProjectId, props.selectedSuiteId],
  async ([projectId, suiteId]) => {
    if (!projectId || !suiteId) {
      bugList.value = [];
      suiteTestCases.value = [];
      detailBug.value = null;
      viewMode.value = 'list';
      pagination.current = 1;
      applySavedBugFilters(projectId);
      return;
    }

    pagination.current = 1;
    applySavedBugFilters(projectId);
    await fetchMembers();
    await fetchSuiteTestCases();
    await fetchBugs();
  },
  { immediate: true }
);

watch(
  () => pagination.pageSize,
  () => {
    normalizePaginationCurrent();
  }
);

onMounted(async () => {
  applySavedBugFilters(props.currentProjectId);
  loadSavedFilterViews(props.currentProjectId);
  const savedColumns = localStorage.getItem(getBugColumnStorageKey(props.currentProjectId));
  if (savedColumns) {
    try {
      const parsed = JSON.parse(savedColumns);
      if (Array.isArray(parsed)) {
        const nextColumns = tableColumnOptions
          .map((item) => item.key)
          .filter((key) => parsed.includes(key));
        if (nextColumns.length) {
          visibleColumns.value = nextColumns;
        }
      }
    } catch (error) {
      localStorage.removeItem(getBugColumnStorageKey(props.currentProjectId));
    }
  }
  if (props.currentProjectId && props.selectedSuiteId) {
    await fetchMembers();
    await fetchSuiteTestCases();
    await fetchBugs();
  }
});

watch(
  () => props.currentProjectId,
  (projectId) => {
    applySavedBugFilters(projectId);
    loadSavedFilterViews(projectId);
    const savedColumns = localStorage.getItem(getBugColumnStorageKey(projectId));
    if (!savedColumns) {
      visibleColumns.value = DEFAULT_VISIBLE_COLUMNS.slice();
      return;
    }
    try {
      const parsed = JSON.parse(savedColumns);
      if (Array.isArray(parsed)) {
        const nextColumns = tableColumnOptions.map((item) => item.key).filter((key) => parsed.includes(key));
        visibleColumns.value = nextColumns.length ? nextColumns : DEFAULT_VISIBLE_COLUMNS.slice();
        return;
      }
    } catch (error) {
      localStorage.removeItem(getBugColumnStorageKey(projectId));
    }
    visibleColumns.value = DEFAULT_VISIBLE_COLUMNS.slice();
  }
);

onUnmounted(() => {
  if (rowHighlightTimer) {
    clearTimeout(rowHighlightTimer);
    rowHighlightTimer = null;
  }
  if (updateSummaryTimer) {
    clearTimeout(updateSummaryTimer);
    updateSummaryTimer = null;
  }
  resetPendingAttachments();
});

defineExpose({
  refresh: fetchBugs,
});
</script>

<style scoped>
.bug-panel {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  padding: 16px;
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.bug-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.bug-panel-heading {
  min-width: 0;
}

.bug-panel-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-1);
}

.bug-panel-subtitle {
  margin-top: 6px;
  color: var(--color-text-3);
  line-height: 1.6;
}

.bug-panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.bug-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px 16px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  cursor: pointer;
  transition: 0.2s ease;
}

.status-card:hover,
.status-card--active {
  border-color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.06);
}

.status-card-label {
  font-size: 13px;
  color: var(--color-text-3);
}

.status-card-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-1);
  line-height: 1;
}

.bug-toolbar {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.quick-view-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.quick-view-item {
  height: 32px;
  padding: 0 12px;
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 6px;
  color: var(--color-text-2);
  cursor: pointer;
  transition: 0.2s ease;
}

.quick-view-item:hover,
.quick-view-item--active {
  color: rgb(var(--arcoblue-6));
  border-color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.05);
}

.bug-filter-grid {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(120px, 1fr)) auto;
  gap: 8px;
  align-items: center;
}

.bug-filter-search {
  min-width: 0;
}

.bug-toolbar-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
}

.bug-toolbar-footer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.bug-hidden-file-input {
  display: none;
}

.bug-saved-views {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.bug-saved-views-label {
  color: var(--color-text-3);
  font-size: 13px;
}

.bug-saved-view-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  height: 30px;
  padding: 0 10px;
  color: var(--color-text-2);
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 999px;
  cursor: pointer;
}

.bug-saved-view-chip--pinned {
  border-color: rgba(var(--arcoblue-6), 0.35);
  background: rgba(var(--arcoblue-6), 0.06);
}

.bug-saved-view-chip--active {
  color: rgb(var(--arcoblue-6));
  border-color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.12);
  box-shadow: 0 0 0 1px rgba(var(--arcoblue-6), 0.08);
}

.bug-saved-view-chip:hover {
  color: rgb(var(--arcoblue-6));
  border-color: rgb(var(--arcoblue-6));
}

.bug-saved-view-chip-pin {
  flex-shrink: 0;
  font-size: 11px;
}

.bug-saved-view-chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bug-saved-view-chip-action {
  flex-shrink: 0;
  font-size: 11px;
  opacity: 0.72;
}

.bug-saved-view-chip-action:hover {
  opacity: 1;
}

.bug-column-dropdown {
  min-width: 220px;
  padding: 8px 10px 10px;
}

.bug-column-dropdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--color-text-2);
  font-size: 13px;
}

.bug-column-checkbox-group {
  width: 100%;
}

.bug-toolbar-sort {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bug-toolbar-sort-label {
  color: var(--color-text-3);
  font-size: 13px;
}

.bug-sort-select {
  width: 180px;
}

.bug-summary-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.bug-debug-panel {
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px dashed var(--color-neutral-4);
  border-radius: 8px;
  background: var(--color-fill-1);
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}

.bug-summary-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-height: 28px;
  padding: 0 10px;
  color: var(--color-text-2);
  font-size: 13px;
  background: var(--color-fill-2);
  border: 1px solid var(--color-neutral-3);
  border-radius: 999px;
}

.bug-summary-pill--primary {
  color: rgb(var(--arcoblue-6));
  background: rgba(var(--arcoblue-6), 0.08);
  border-color: rgba(var(--arcoblue-6), 0.2);
}

.bug-summary-pill--clearable {
  cursor: pointer;
}

.bug-summary-pill--clearable span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.bug-summary-pill-close {
  flex-shrink: 0;
  font-size: 11px;
}

.bug-summary-pill--search {
  max-width: 320px;
}

.bug-selectable-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.bug-selectable-tag-icon {
  font-size: 11px;
}

.bug-update-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: rgba(var(--arcoblue-1), 0.96);
  border: 1px solid rgba(var(--arcoblue-4), 0.35);
  border-radius: 8px;
}

.bug-update-summary-content {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  min-width: 0;
}

.bug-update-summary-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.bug-update-summary-title {
  color: rgb(var(--arcoblue-6));
  font-weight: 600;
  line-height: 1.6;
}

.bug-update-summary-time {
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.bug-batch-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.bug-batch-toolbar-info,
.bug-batch-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.bug-batch-toolbar-count {
  color: var(--color-text-2);
  font-size: 13px;
}

.bug-batch-toolbar-trigger-icon {
  margin-left: 6px;
  font-size: 11px;
}

.bug-batch-toolbar-danger-option :deep(.arco-dropdown-option-content) {
  color: rgb(var(--danger-6));
}

.bug-batch-preview {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.bug-batch-preview-title {
  color: var(--color-text-1);
  font-weight: 600;
  line-height: 1.6;
}

.bug-batch-preview-summary {
  margin-top: 4px;
  color: var(--color-text-2);
  line-height: 1.6;
}

.bug-batch-preview-impact {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.bug-batch-preview-impact-item {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  color: var(--color-text-2);
  font-size: 12px;
  background: #fff;
  border: 1px solid var(--color-neutral-3);
  border-radius: 999px;
}

.bug-batch-preview-impact-item--active {
  color: rgb(var(--arcoblue-6));
  border-color: rgba(var(--arcoblue-6), 0.35);
  background: rgba(var(--arcoblue-6), 0.06);
}

.bug-batch-preview-diffs {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.bug-batch-preview-diff {
  color: var(--color-text-2);
  font-size: 12px;
  line-height: 1.6;
}

.bug-batch-preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.bug-table :deep(.bug-row-highlight > .arco-table-td) {
  background: rgba(var(--arcoblue-6), 0.08);
}

.bug-empty-state {
  padding: 28px 0 20px;
}

.bug-empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.bug-empty-title {
  color: var(--color-text-1);
  font-size: 16px;
  font-weight: 600;
}

.bug-empty-description {
  color: var(--color-text-3);
  line-height: 1.6;
  text-align: center;
}

.bug-table {
  flex: 1;
}

.bug-related-cell,
.bug-related-field {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  min-height: 24px;
}

.bug-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.bug-form-section + .bug-form-section {
  margin-top: 12px;
}

.bug-detail-page {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.bug-detail-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.bug-detail-page-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.bug-detail-page-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-1);
}

.bug-detail-page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bug-detail-spin {
  width: 100%;
}

.bug-form-section-title,
.bug-detail-section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
}

.bug-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.bug-form-full {
  grid-column: 1 / -1;
}

.action-confirm-tip {
  padding: 12px;
  line-height: 1.7;
  color: var(--color-text-2);
  background: var(--color-fill-2);
  border-radius: 6px;
}

.bug-detail-header {
  margin-bottom: 16px;
}

.bug-detail-toolbar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 18px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  backdrop-filter: blur(8px);
}

.bug-detail-toolbar-button {
  min-width: 108px;
}

.bug-detail-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
}

.bug-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.bug-detail-section + .bug-detail-section {
  margin-top: 18px;
}

.bug-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.bug-detail-field {
  padding: 12px 14px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  min-width: 0;
}

.bug-detail-field--full {
  grid-column: 1 / -1;
}

.bug-detail-field-label {
  margin-bottom: 8px;
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.4;
}

.bug-detail-field-value {
  color: var(--color-text-1);
  line-height: 1.7;
  word-break: break-word;
}

.bug-detail-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: var(--color-text-2);
  text-align: left;
}

.bug-detail-attachment-list {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.bug-detail-attachment-item {
  padding: 12px;
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
  background: var(--color-fill-1);
}

.bug-detail-attachment-image,
.bug-detail-attachment-video {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border-radius: 6px;
  background: #000;
}

.bug-detail-attachment-file {
  color: rgb(var(--arcoblue-6));
  word-break: break-all;
}

.bug-activity-list {
  display: grid;
  gap: 14px;
}

.bug-activity-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.bug-activity-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 999px;
  background: rgb(var(--arcoblue-6));
  box-shadow: 0 0 0 4px rgba(var(--arcoblue-6), 0.12);
}

.bug-activity-main {
  padding: 12px 14px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-neutral-3);
  border-radius: 8px;
}

.bug-activity-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
}

.bug-activity-action {
  color: var(--color-text-1);
  font-weight: 600;
}

.bug-activity-meta {
  color: var(--color-text-3);
  font-size: 12px;
}

.bug-activity-content {
  margin-top: 8px;
  color: var(--color-text-2);
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 1280px) {
  .bug-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .bug-panel-header,
  .bug-detail-page-header,
  .bug-form-grid,
  .bug-detail-grid,
  .bug-status-grid,
  .bug-filter-grid {
    grid-template-columns: 1fr;
  }

  .bug-panel-header,
  .bug-detail-page-header {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .bug-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>











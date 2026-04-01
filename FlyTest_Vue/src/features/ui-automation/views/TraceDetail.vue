<template>
  <div class="trace-viewer">
    <!-- 顶部标题栏 -->
    <div class="trace-header">
      <a-button type="text" size="small" @click="handleBack">
        <template #icon><icon-left /></template>
      </a-button>
      <span class="trace-title">{{ recordInfo?.test_case_name ?? `执行记录 #${recordId}` }}</span>
      <a-tag v-if="recordInfo?.status !== undefined" :color="statusColors[recordInfo.status]" size="small">
        {{ STATUS_LABELS[recordInfo.status] ?? '未知' }}
      </a-tag>
      <span class="trace-time">{{ recordInfo?.start_time ? formatTime(recordInfo.start_time) : '' }}</span>
      <div class="header-actions">
        <a-button type="text" size="small" @click="refreshTraceData" :loading="loading">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </div>
    </div>

    <!-- 加载/错误状态 -->
    <div v-if="loading" class="loading-state">
      <a-spin dot tip="正在加载 Trace 数据..." />
    </div>
    <div v-else-if="error" class="error-state">
      <a-result status="warning" :title="error">
        <template #extra>
          <a-button type="primary" @click="loadData">重试</a-button>
        </template>
      </a-result>
    </div>

    <!-- 主内容区域 -->
    <template v-else-if="traceData">
      <!-- 时间线标尺 -->
      <div class="timeline-ruler">
        <div
          ref="timelineTrackRef"
          class="timeline-track"
          @mousedown="startRangeSelect"
        >
          <template v-for="(tick, idx) in timelineTicks" :key="idx">
            <div class="timeline-tick" :style="{ left: tick.position + '%' }">
              <span class="tick-label">{{ tick.label }}</span>
            </div>
          </template>
          <!-- 时间范围选区 -->
          <div
            v-if="rangeSelection"
            class="time-range-selection"
            :style="{ left: rangeSelection.left + '%', width: rangeSelection.width + '%' }"
          />
        </div>
        <!-- 清除选区按钮 -->
        <a-button
          v-if="rangeSelection"
          type="text"
          size="mini"
          class="clear-range-btn"
          @click="clearTimeRange"
        >
          <template #icon><icon-close /></template>
          清除选区
        </a-button>
        <!-- 快照缩略图平铺 -->
        <div ref="snapshotsStripRef" class="snapshots-strip">
          <div
            v-for="snap in sampledSnapshots"
            :key="'snap-' + snap.originalIndex"
            class="snapshot-thumb"
            :class="{ active: selectedSnapshotIndex === snap.originalIndex }"
            @click="selectSnapshot(snap.originalIndex)"
            @mouseenter="hoveredSnapshotIndex = snap.originalIndex"
            @mouseleave="hoveredSnapshotIndex = null"
          >
            <img v-if="snap.screenshot" :src="snap.screenshot" alt="" />
          </div>
        </div>
      </div>

      <div class="trace-main">
        <!-- 左侧：操作列表 -->
        <div class="actions-panel" :style="{ width: actionsPanelWidth + 'px' }">
          <div class="panel-header">
            <span>Actions</span>
            <a-badge :count="filteredActions.length" />
          </div>
          <div class="actions-list">
            <div
              v-for="(action, idx) in filteredActions"
              :key="action.action_id || idx"
              class="action-item"
              :class="{ active: selectedAction?.action_id === action.action_id, error: action.error }"
              @click="selectActionByItem(action)"
            >
              <div class="action-icon">
                <IconLink v-if="action.type === 'goto'" />
                <IconThunderbolt v-else-if="action.type === 'click'" />
                <IconEdit v-else-if="action.type === 'type' || action.type === 'fill'" />
                <IconEye v-else-if="action.type === 'waitForSelector'" />
                <IconCommand v-else />
              </div>
              <div class="action-content">
                <div class="action-name">
                  {{ getActionLabel(action) }}
                </div>
                <div class="action-selector" v-if="action.selector">
                  {{ truncateText(action.selector, 40) }}
                </div>
              </div>
              <div class="action-duration">{{ formatDuration(action.duration) }}</div>
            </div>
            <a-empty v-if="!filteredActions.length" description="暂无操作记录" :image-size="60" />
          </div>
        </div>
        <!-- 左侧分隔条 -->
        <div class="resizer resizer-h" @mousedown="startResizeActions"></div>

        <!-- 右侧：快照预览 -->
        <div class="snapshot-panel">
          <div class="panel-header">
            <span>Snapshot</span>
          </div>
          <div class="snapshot-preview">
            <img
              v-if="currentSnapshot?.screenshot"
              :src="currentSnapshot.screenshot"
              alt="Page Snapshot"
              class="snapshot-image"
            />
            <div v-else class="no-snapshot">
              <icon-image :size="48" />
              <p>暂无快照</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部：详情面板 -->
      <!-- 底部分隔条 -->
      <div class="resizer resizer-v" @mousedown="startResizeDetails"></div>
      <div class="details-panel" :style="{ height: detailsPanelHeight + 'px' }">
        <a-tabs v-model:active-key="activeTab" size="small">
          <!-- Network -->
          <a-tab-pane key="network">
            <template #title>
              <span>Network</span>
              <a-badge :count="traceData.network_requests?.length || 0" :offset="[6, -2]" />
            </template>
            <div class="tab-content network-content">
              <!-- 顶部过滤器 -->
              <div class="network-filters">
                <a-input-search
                  v-model="networkFilter"
                  placeholder="Filter network"
                  size="mini"
                  allow-clear
                  class="filter-input"
                />
                <div class="filter-types">
                  <span
                    v-for="t in networkTypeOptions"
                    :key="t.value"
                    class="filter-type-btn"
                    :class="{ active: networkTypeFilter === t.value }"
                    @click="networkTypeFilter = t.value"
                  >{{ t.label }}</span>
                </div>
              </div>
              <!-- 左右分栏 -->
              <div class="network-split">
                <!-- 左侧：请求列表 -->
                <div class="network-sidebar">
                  <div class="network-list-header">Name</div>
                  <div class="network-list">
                    <div
                      v-for="(req, idx) in filteredNetworkRequests"
                      :key="idx"
                      class="network-list-item"
                      :class="{ active: selectedNetworkRequest?.request_id === req.request_id, error: req.status >= 400 }"
                      @click="selectNetworkRequest(req)"
                    >
                      <span class="request-name" :title="req.url">{{ getUrlName(req.url) }}</span>
                    </div>
                    <a-empty v-if="!filteredNetworkRequests.length" description="No requests" :image-size="36" />
                  </div>
                </div>
                <!-- 右侧：请求详情 -->
                <div class="network-main" v-if="selectedNetworkRequest">
                  <div class="detail-header">
                    <span class="close-btn" @click="selectedNetworkRequest = null">×</span>
                    <div class="detail-tabs">
                      <span
                        v-for="tab in ['Headers', 'Payload', 'Response']"
                        :key="tab"
                        class="detail-tab"
                        :class="{ active: networkDetailTab === tab.toLowerCase() }"
                        @click="networkDetailTab = tab.toLowerCase()"
                      >{{ tab }}</span>
                    </div>
                  </div>
                  <div class="detail-body">
                    <!-- Headers -->
                    <template v-if="networkDetailTab === 'headers'">
                      <div class="detail-scroll">
                        <div class="collapse-section">
                          <div class="collapse-header" @click="toggleSection('general')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.general }">›</span>
                            <span class="collapse-title">General</span>
                          </div>
                          <table class="headers-table" v-show="expandedSections.general">
                            <tbody>
                              <tr><td class="header-key">URL:</td><td class="header-value">{{ selectedNetworkRequest.url }}</td></tr>
                              <tr><td class="header-key">Method:</td><td class="header-value">{{ selectedNetworkRequest.method }}</td></tr>
                              <tr>
                                <td class="header-key">Status Code:</td>
                                <td class="header-value">
                                  {{ selectedNetworkRequest.status }} {{ selectedNetworkRequest.status_text }}
                                  <span class="status-dot" :class="getStatusDotClass(selectedNetworkRequest.status)"></span>
                                </td>
                              </tr>
                              <tr><td class="header-key">Duration:</td><td class="header-value">{{ formatDuration(selectedNetworkRequest.duration) }}</td></tr>
                            </tbody>
                          </table>
                        </div>
                        <div class="collapse-section" v-if="Object.keys(selectedNetworkRequest.request_headers || {}).length">
                          <div class="collapse-header" @click="toggleSection('reqHeaders')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.reqHeaders }">›</span>
                            <span class="collapse-title">Request Headers</span>
                            <span class="collapse-count">× {{ Object.keys(selectedNetworkRequest.request_headers).length }}</span>
                          </div>
                          <table class="headers-table" v-show="expandedSections.reqHeaders">
                            <tbody>
                              <tr v-for="(v, k) in selectedNetworkRequest.request_headers" :key="k">
                                <td class="header-key">{{ k }}:</td>
                                <td class="header-value">{{ v }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div class="collapse-section" v-if="Object.keys(selectedNetworkRequest.response_headers || {}).length">
                          <div class="collapse-header" @click="toggleSection('respHeaders')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.respHeaders }">›</span>
                            <span class="collapse-title">Response Headers</span>
                            <span class="collapse-count">× {{ Object.keys(selectedNetworkRequest.response_headers).length }}</span>
                          </div>
                          <table class="headers-table" v-show="expandedSections.respHeaders">
                            <tbody>
                              <tr v-for="(v, k) in selectedNetworkRequest.response_headers" :key="k">
                                <td class="header-key">{{ k }}:</td>
                                <td class="header-value">{{ v }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </template>
                    <!-- Payload -->
                    <template v-else-if="networkDetailTab === 'payload'">
                      <div class="detail-scroll">
                        <div class="collapse-section">
                          <div class="collapse-header" @click="toggleSection('queryParams')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.queryParams }">›</span>
                            <span class="collapse-title">Query String Parameters</span>
                            <span class="collapse-count" v-if="getQueryParams(selectedNetworkRequest.url).length">× {{ getQueryParams(selectedNetworkRequest.url).length }}</span>
                          </div>
                          <table class="headers-table" v-show="expandedSections.queryParams">
                            <tbody>
                              <tr v-for="(param, idx) in getQueryParams(selectedNetworkRequest.url)" :key="idx">
                                <td class="header-key">{{ param.key }}:</td>
                                <td class="header-value">{{ param.value }}</td>
                              </tr>
                              <tr v-if="!getQueryParams(selectedNetworkRequest.url).length">
                                <td class="no-data" colspan="2">No query parameters</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div class="collapse-section">
                          <div class="collapse-header" @click="toggleSection('requestBody')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.requestBody }">›</span>
                            <span class="collapse-title">Request Payload</span>
                          </div>
                          <div class="payload-content" v-show="expandedSections.requestBody">
                            <pre class="response-body" v-if="selectedNetworkRequest.request_body">{{ formatResponseBody(selectedNetworkRequest.request_body, selectedNetworkRequest.mime_type) }}</pre>
                            <div v-else class="no-data">No request body</div>
                          </div>
                        </div>
                      </div>
                    </template>
                    <!-- Response -->
                    <template v-else>
                      <div class="detail-scroll">
                        <div class="collapse-section">
                          <div class="collapse-header" @click="toggleSection('responseBody')">
                            <span class="collapse-arrow" :class="{ expanded: expandedSections.responseBody }">›</span>
                            <span class="collapse-title">Response Body</span>
                            <span class="collapse-count" v-if="selectedNetworkRequest.response_size">{{ formatSize(selectedNetworkRequest.response_size) }}</span>
                          </div>
                          <div class="payload-content" v-show="expandedSections.responseBody">
                            <pre class="response-body" v-if="selectedNetworkRequest.response_body">{{ formatResponseBody(selectedNetworkRequest.response_body, selectedNetworkRequest.mime_type) }}</pre>
                            <div v-else class="no-data">No response body or non-text content type</div>
                          </div>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
                <div class="network-main network-empty" v-else>
                  <icon-code-sandbox :size="32" />
                  <p>Select a request to view details</p>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <!-- Console -->
          <a-tab-pane key="console">
            <template #title>
              <span>Console</span>
              <a-badge :count="traceData.console_messages?.length || 0" :offset="[6, -2]" />
            </template>
            <div class="tab-content console-content">
              <div
                v-for="(msg, idx) in traceData.console_messages"
                :key="idx"
                class="console-item"
                :class="'console-' + msg.type"
              >
                <span class="console-type">{{ msg.type }}</span>
                <span class="console-text">{{ msg.text }}</span>
              </div>
              <a-empty v-if="!traceData.console_messages?.length" description="暂无控制台消息" :image-size="40" />
            </div>
          </a-tab-pane>

          <!-- Call -->
          <a-tab-pane key="call" title="Call">
            <div class="tab-content" v-if="selectedAction">
              <div class="detail-section">
                <div class="detail-title">Action Details</div>
                <div class="detail-item"><span>Type:</span> {{ selectedAction.type }}</div>
                <div class="detail-item" v-if="selectedAction.selector"><span>Selector:</span> <code>{{ selectedAction.selector }}</code></div>
                <div class="detail-item" v-if="selectedAction.value"><span>Value:</span> {{ selectedAction.value }}</div>
                <div class="detail-item" v-if="selectedAction.url"><span>URL:</span> {{ selectedAction.url }}</div>
                <div class="detail-item"><span>Duration:</span> {{ formatDuration(selectedAction.duration) }}</div>
                <div class="detail-item error-text" v-if="selectedAction.error"><span>Error:</span> {{ selectedAction.error }}</div>
              </div>
            </div>
            <a-empty v-else description="选择一个操作查看详情" :image-size="40" />
          </a-tab-pane>

          <!-- Attachments (Screenshots) -->
          <a-tab-pane key="attachments">
            <template #title>
              <span>Attachments</span>
              <a-badge :count="traceData.snapshots?.length || 0" :offset="[6, -2]" />
            </template>
            <div class="tab-content attachments-content">
              <a-image-preview-group infinite>
                <div class="attachments-grid">
                  <div
                    v-for="(snap, idx) in traceData.snapshots"
                    :key="idx"
                    class="attachment-item"
                    :class="{ active: selectedSnapshotIndex === idx }"
                    @click="selectSnapshot(idx)"
                  >
                    <a-image
                      v-if="snap.screenshot"
                      :src="snap.screenshot"
                      width="120"
                      height="68"
                      fit="cover"
                      :preview="true"
                    />
                  </div>
                </div>
              </a-image-preview-group>
              <a-empty v-if="!traceData.snapshots?.length" description="暂无快照" :image-size="40" />
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { executionRecordApi } from '../api'
import type { TraceData, UiExecutionRecord, TraceAction, TraceNetworkRequest, TraceSnapshot } from '../types'
import dayjs from 'dayjs'
import {
  IconLeft, IconLink, IconEdit, IconEye, IconCommand, IconImage, IconThunderbolt, IconClose, IconCodeSandbox, IconRefresh
} from '@arco-design/web-vue/es/icon'

const route = useRoute()
const router = useRouter()

const recordId = Number(route.params.id)
const loading = ref(false)
const error = ref('')
const traceData = ref<TraceData | null>(null)
const recordInfo = ref<Partial<UiExecutionRecord> | null>(null)
const snapshotsStripRef = ref<HTMLElement | null>(null)
const stripWidth = ref(0)

// UI 状态
const activeTab = ref('network')
const selectedActionIndex = ref(0)
const selectedSnapshotIndex = ref(0)
const hoveredSnapshotIndex = ref<number | null>(null)
const networkFilter = ref('')
const networkTypeFilter = ref('all')
const networkDetailTab = ref('headers')
const selectedNetworkRequest = ref<TraceNetworkRequest | null>(null)
const expandedSections = reactive({
  general: true,
  reqHeaders: true,
  respHeaders: true,
  queryParams: true,
  requestBody: true,
  responseBody: true
})

const networkTypeOptions = [
  { value: 'all', label: 'All' },
  { value: 'fetch', label: 'Fetch' },
  { value: 'document', label: 'HTML' },
  { value: 'script', label: 'JS' },
  { value: 'stylesheet', label: 'CSS' },
  { value: 'image', label: 'Image' },
]

type SectionKey = 'general' | 'reqHeaders' | 'respHeaders' | 'queryParams' | 'requestBody' | 'responseBody'

const toggleSection = (key: SectionKey) => {
  expandedSections[key] = !expandedSections[key]
}

const getQueryParams = (url: string): { key: string; value: string }[] => {
  try {
    const u = new URL(url)
    const params: { key: string; value: string }[] = []
    u.searchParams.forEach((value, key) => {
      params.push({ key, value })
    })
    return params
  } catch {
    return []
  }
}

const getStatusDotClass = (status: number) => {
  if (status >= 200 && status < 300) return 'dot-success'
  if (status >= 300 && status < 400) return 'dot-redirect'
  if (status >= 400) return 'dot-error'
  return ''
}

// 时间范围选择
const timelineTrackRef = ref<HTMLElement | null>(null)
const timeRangeStart = ref<number | null>(null) // 百分比 0-100
const timeRangeEnd = ref<number | null>(null)
let isSelectingRange = false

// 可拖拽面板尺寸
const actionsPanelWidth = ref(280)
const detailsPanelHeight = ref(240)
let isResizing = false
let resizeType: 'actions' | 'details' | null = null
let startX = 0
let startY = 0
let startSize = 0

const startResizeActions = (e: MouseEvent) => {
  isResizing = true
  resizeType = 'actions'
  startX = e.clientX
  startSize = actionsPanelWidth.value
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const startResizeDetails = (e: MouseEvent) => {
  isResizing = true
  resizeType = 'details'
  startY = e.clientY
  startSize = detailsPanelHeight.value
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

const handleResize = (e: MouseEvent) => {
  if (!isResizing) return
  if (resizeType === 'actions') {
    const diff = e.clientX - startX
    actionsPanelWidth.value = Math.max(180, Math.min(600, startSize + diff))
  } else if (resizeType === 'details') {
    const diff = startY - e.clientY
    detailsPanelHeight.value = Math.max(120, Math.min(500, startSize + diff))
  }
}

const stopResize = () => {
  isResizing = false
  resizeType = null
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 时间范围选择处理
const startRangeSelect = (e: MouseEvent) => {
  if (!timelineTrackRef.value) return
  isSelectingRange = true
  const rect = timelineTrackRef.value.getBoundingClientRect()
  const percent = ((e.clientX - rect.left) / rect.width) * 100
  timeRangeStart.value = Math.max(0, Math.min(100, percent))
  timeRangeEnd.value = timeRangeStart.value
  document.addEventListener('mousemove', handleRangeSelect)
  document.addEventListener('mouseup', stopRangeSelect)
  document.body.style.userSelect = 'none'
}

const handleRangeSelect = (e: MouseEvent) => {
  if (!isSelectingRange || !timelineTrackRef.value) return
  const rect = timelineTrackRef.value.getBoundingClientRect()
  const percent = ((e.clientX - rect.left) / rect.width) * 100
  timeRangeEnd.value = Math.max(0, Math.min(100, percent))
}

const stopRangeSelect = () => {
  isSelectingRange = false
  document.removeEventListener('mousemove', handleRangeSelect)
  document.removeEventListener('mouseup', stopRangeSelect)
  document.body.style.userSelect = ''
  // 如果选区太小，清除选择
  if (timeRangeStart.value !== null && timeRangeEnd.value !== null) {
    if (Math.abs(timeRangeEnd.value - timeRangeStart.value) < 2) {
      clearTimeRange()
    }
  }
}

const clearTimeRange = () => {
  timeRangeStart.value = null
  timeRangeEnd.value = null
}

// 计算选区的左边界和宽度
const rangeSelection = computed(() => {
  if (timeRangeStart.value === null || timeRangeEnd.value === null) return null
  const left = Math.min(timeRangeStart.value, timeRangeEnd.value)
  const right = Math.max(timeRangeStart.value, timeRangeEnd.value)
  return { left, width: right - left }
})

// 根据时间范围过滤后的数据
const filteredActions = computed(() => {
  const actions = traceData.value?.actions
  if (!actions?.length || !rangeSelection.value) return actions ?? []
  const { min, duration } = snapshotTimeRange.value
  const startTime = min + (rangeSelection.value.left / 100) * duration
  const endTime = min + ((rangeSelection.value.left + rangeSelection.value.width) / 100) * duration
  return actions.filter(a => a.start_time >= startTime && a.start_time <= endTime)
})

const filteredSnapshots = computed(() => {
  const snapshots = traceData.value?.snapshots
  if (!snapshots?.length || !rangeSelection.value) return snapshots ?? []
  const { min, duration } = snapshotTimeRange.value
  const startTime = min + (rangeSelection.value.left / 100) * duration
  const endTime = min + ((rangeSelection.value.left + rangeSelection.value.width) / 100) * duration
  return snapshots.filter(s => s.timestamp >= startTime && s.timestamp <= endTime)
})

const STATUS_LABELS: Record<number, string> = { 0: '待执行', 1: '执行中', 2: '成功', 3: '失败', 4: '已取消' }
const statusColors: Record<number, string> = { 0: 'gray', 1: 'arcoblue', 2: 'green', 3: 'red', 4: 'orange' }

// 计算属性
const selectedAction = computed<TraceAction | null>(() => traceData.value?.actions?.[selectedActionIndex.value] ?? null)
// hover 时临时显示悬停的快照，否则显示选中的
const currentSnapshot = computed<TraceSnapshot | null>(() => {
  const idx = hoveredSnapshotIndex.value ?? selectedSnapshotIndex.value
  return traceData.value?.snapshots?.[idx] ?? null
})

// Network 过滤
const filteredNetworkRequests = computed(() => {
  const requests = traceData.value?.network_requests
  if (!requests?.length) return []
  return requests.filter(req => {
    // 类型过滤
    if (networkTypeFilter.value !== 'all') {
      const mimeType = req.mime_type || ''
      const typeMap: Record<string, (m: string) => boolean> = {
        fetch: m => m.includes('json') || m.includes('xml'),
        document: m => m.includes('html'),
        script: m => m.includes('javascript'),
        stylesheet: m => m.includes('css'),
        image: m => m.includes('image'),
      }
      const checker = typeMap[networkTypeFilter.value]
      if (checker && !checker(mimeType)) return false
    }
    // 关键词过滤
    if (networkFilter.value) {
      const keyword = networkFilter.value.toLowerCase()
      return req.url.toLowerCase().includes(keyword)
    }
    return true
  })
})

// 采样后的快照（根据容器宽度动态计算数量，使用过滤后的快照）
const THUMB_WIDTH = 72 // 每张缩略图宽度 + 间距
const sampledSnapshots = computed(() => {
  const snapshots = filteredSnapshots.value
  if (!snapshots?.length) return []
  // 根据容器宽度计算最多显示多少张
  const maxCount = Math.max(5, Math.floor(stripWidth.value / THUMB_WIDTH) || 20)
  if (snapshots.length <= maxCount) {
    return snapshots.map((s, i) => {
      const originalIndex = traceData.value?.snapshots?.findIndex(orig => orig.snapshot_id === s.snapshot_id) ?? i
      return { ...s, originalIndex }
    })
  }
  // 均匀采样
  const step = (snapshots.length - 1) / (maxCount - 1)
  const result = []
  for (let i = 0; i < maxCount; i++) {
    const idx = Math.round(i * step)
    const snap = snapshots[idx]
    const originalIndex = traceData.value?.snapshots?.findIndex(orig => orig.snapshot_id === snap.snapshot_id) ?? idx
    result.push({ ...snap, originalIndex })
  }
  return result
})

// 监听容器宽度变化
let resizeObserver: ResizeObserver | null = null

const initResizeObserver = () => {
  if (snapshotsStripRef.value && !resizeObserver) {
    stripWidth.value = snapshotsStripRef.value.clientWidth
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        stripWidth.value = entry.contentRect.width
      }
    })
    resizeObserver.observe(snapshotsStripRef.value)
  }
}

// 数据加载后初始化 ResizeObserver
watch(traceData, (val) => {
  if (val) {
    nextTick(() => initResizeObserver())
  }
})

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.removeEventListener('mousemove', handleRangeSelect)
  document.removeEventListener('mouseup', stopRangeSelect)
  resizeObserver?.disconnect()
})

// 快照时间范围
const snapshotTimeRange = computed(() => {
  const snapshots = traceData.value?.snapshots
  if (!snapshots?.length) return { min: 0, max: 1000, duration: 1000 }
  const timestamps = snapshots.map(s => s.timestamp).filter(t => t > 0)
  if (!timestamps.length) return { min: 0, max: 1000, duration: 1000 }
  const min = Math.min(...timestamps)
  const max = Math.max(...timestamps)
  return { min, max, duration: max - min || 1000 }
})

const timelineTicks = computed(() => {
  const { duration } = snapshotTimeRange.value
  const ticks = []
  const step = duration > 5000 ? 1000 : duration > 2000 ? 500 : 200
  for (let t = 0; t <= duration; t += step) {
    ticks.push({
      position: (t / duration) * 100,
      label: t >= 1000 ? `${(t / 1000).toFixed(1)}s` : `${t}ms`
    })
  }
  return ticks
})

// 方法
const handleBack = () => router.back()
const formatTime = (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss')
const formatDuration = (ms: number | undefined) => {
  if (!ms) return '-'
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`
}
const formatSize = (bytes: number | undefined) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes}`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}K`
  return `${(bytes / (1024 * 1024)).toFixed(1)}M`
}
const truncateText = (text: string, maxLen = 50) => text?.length > maxLen ? text.substring(0, maxLen) + '...' : text

const getUrlName = (url: string) => {
  try {
    const u = new URL(url)
    const path = u.pathname.split('/').pop() || u.hostname
    return path || u.hostname
  } catch {
    return url.split('/').pop() || url
  }
}

const getActionLabel = (action: TraceAction) => {
  const labels: Record<string, string> = {
    goto: 'Navigate to',
    click: 'Click',
    type: 'Type',
    fill: 'Fill',
    waitForSelector: 'Wait for selector',
    press: 'Press',
    hover: 'Hover'
  }
  const label = labels[action.type] || action.type
  if (action.type === 'goto') return `${label} "${action.url?.split('/').pop() || '/'}"`
  if (action.value) return `${label} "${truncateText(action.value, 20)}"`
  return label
}

const selectAction = (idx: number) => {
  selectedActionIndex.value = idx
  // 根据 action 的结束时间，找到最接近的 snapshot
  const action = traceData.value?.actions?.[idx]
  const snapshots = traceData.value?.snapshots
  if (!action || !snapshots?.length) return

  const targetTime = action.end_time || action.start_time
  if (!targetTime) {
    // 如果没有时间信息，按索引比例选择
    const actions = traceData.value?.actions
    if (actions?.length) {
      selectedSnapshotIndex.value = Math.round((idx / (actions.length - 1)) * (snapshots.length - 1)) || 0
    }
    return
  }

  // 找到时间最接近的 snapshot
  let closestIdx = 0
  let closestDiff = Infinity
  snapshots.forEach((snap, i) => {
    const diff = Math.abs(snap.timestamp - targetTime)
    if (diff < closestDiff) {
      closestDiff = diff
      closestIdx = i
    }
  })
  selectedSnapshotIndex.value = closestIdx
}

const selectActionByItem = (action: TraceAction) => {
  // 找到原始索引
  const idx = traceData.value?.actions?.findIndex(a => a.action_id === action.action_id) ?? -1
  if (idx >= 0) selectAction(idx)
}

const selectSnapshot = (idx: number) => {
  selectedSnapshotIndex.value = idx
}

const selectNetworkRequest = (req: TraceNetworkRequest) => {
  selectedNetworkRequest.value = req
}

const formatResponseBody = (body: string, mimeType?: string) => {
  if (!body) return ''
  const trimmed = body.trim()
  // 自动检测 JSON：以 { 或 [ 开头，或 mimeType 包含 json
  const isJson = mimeType?.includes('json') || trimmed.startsWith('{') || trimmed.startsWith('[')
  if (isJson) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2)
    } catch {
      // 解析失败则返回原内容
    }
  }
  return body.length > 5000 ? body.substring(0, 5000) + '\n\n... (内容已截断)' : body
}

const loadData = async () => {
  loading.value = true
  error.value = ''
  try {
    const recordRes = await executionRecordApi.get(recordId) as any
    const recordData = recordRes?.data
    if (recordData?.success && recordData.data) {
      recordInfo.value = recordData.data
      if (!recordData.data.trace_path) {
        error.value = '此执行记录没有 Trace 数据'
        return
      }
    }
    const traceRes = await executionRecordApi.getTrace(recordId) as any
    const traceResponse = traceRes?.data
    if (traceResponse?.success && traceResponse.data) {
      let data = traceResponse.data
      if (data.status === 'success' && data.data) data = data.data
      traceData.value = data
    } else {
      error.value = traceResponse?.message || '加载 Trace 数据失败'
    }
  } catch (e) {
    console.error('加载 Trace 失败:', e)
    error.value = '加载 Trace 数据失败'
  } finally {
    loading.value = false
  }
}

const refreshTraceData = async () => {
  loading.value = true
  error.value = ''
  try {
    const traceRes = await executionRecordApi.getTrace(recordId, true) as any
    const traceResponse = traceRes?.data
    if (traceResponse?.success && traceResponse.data) {
      let data = traceResponse.data
      if (data.status === 'success' && data.data) data = data.data
      traceData.value = data
    } else {
      error.value = traceResponse?.message || '刷新 Trace 数据失败'
    }
  } catch (e) {
    console.error('刷新 Trace 失败:', e)
    error.value = '刷新 Trace 数据失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 全局禁止滚动 - 仅在此页面生效 */
:global(html),
:global(body),
:global(#app),
:global(.arco-layout),
:global(.arco-layout-content) {
  overflow: hidden !important;
}

.trace-viewer {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-height: 100vh;
  background: var(--color-bg-1);
  overflow: hidden;
}

.trace-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-bg-2);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.trace-title {
  font-weight: 600;
  font-size: 14px;
}

.trace-time {
  color: var(--color-text-3);
  font-size: 12px;
}

.header-actions {
  margin-left: auto;
}

.loading-state, .error-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 0;
}

/* 时间线 */
.timeline-ruler {
  position: relative;
  padding: 8px 16px;
  background: var(--color-bg-2);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.timeline-track {
  position: relative;
  height: 20px;
  background: var(--color-fill-2);
  border-radius: 4px;
  margin-bottom: 8px;
  cursor: crosshair;
}

.time-range-selection {
  position: absolute;
  top: 0;
  height: 100%;
  background: rgba(var(--primary-6), 0.3);
  border-left: 2px solid rgb(var(--primary-6));
  border-right: 2px solid rgb(var(--primary-6));
  pointer-events: none;
}

.clear-range-btn {
  position: absolute;
  right: 16px;
  top: 4px;
  font-size: 11px;
}

.timeline-tick {
  position: absolute;
  top: 0;
  height: 100%;
  border-left: 1px solid var(--color-border-2);
}

.tick-label {
  position: absolute;
  top: 2px;
  left: 4px;
  font-size: 10px;
  color: var(--color-text-3);
}

.snapshots-strip {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.snapshot-thumb {
  flex: 1;
  min-width: 48px;
  max-width: 120px;
  height: 36px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  background: var(--color-bg-3);
  transition: all 0.15s;
}

.snapshot-thumb:last-child {
  flex-shrink: 0;
}

.snapshot-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.snapshot-thumb:hover {
  border-color: var(--color-primary-4);
  transform: scale(1.05);
}

.snapshot-thumb.active {
  border-color: var(--color-primary-6);
  box-shadow: 0 0 0 2px rgba(var(--primary-6), 0.3);
}

/* 主内容区 */
.trace-main {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 可拖拽分隔条 */
.resizer {
  background: var(--color-border);
  flex-shrink: 0;
  transition: background 0.15s;
}

.resizer:hover {
  background: var(--color-primary-4);
}

.resizer-h {
  width: 4px;
  cursor: col-resize;
}

.resizer-v {
  height: 4px;
  cursor: row-resize;
}

/* 左侧操作列表 */
.actions-panel {
  min-width: 180px;
  max-width: 600px;
  border-right: none;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-2);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-2);
  border-bottom: 1px solid var(--color-border);
}

.actions-list {
  flex: 1;
  overflow-y: auto;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border);
  transition: background 0.15s;
}

.action-item:hover {
  background: var(--color-fill-2);
}

.action-item.active {
  background: var(--color-primary-1);
  border-left: 3px solid var(--color-primary-6);
}

.action-item.error {
  background: rgba(var(--red-1), 0.5);
}

.action-icon {
  width: 20px;
  color: var(--color-text-3);
}

.action-content {
  flex: 1;
  min-width: 0;
}

.action-name {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-selector {
  font-size: 10px;
  color: var(--color-text-3);
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-duration {
  font-size: 10px;
  color: var(--color-text-3);
  white-space: nowrap;
}

/* 右侧快照预览 */
.snapshot-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-fill-1);
}

.snapshot-preview {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px;
  overflow: hidden;
}

.snapshot-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.no-snapshot {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--color-text-3);
}

.snapshot-url {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 11px;
  color: var(--color-text-3);
  background: var(--color-bg-2);
  border-top: 1px solid var(--color-border);
}

/* 底部详情面板 */
.details-panel {
  min-height: 120px;
  max-height: 500px;
  border-top: none;
  background: var(--color-bg-2);
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.details-panel :deep(.arco-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.details-panel :deep(.arco-tabs-content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.details-panel :deep(.arco-tabs-content-list),
.details-panel :deep(.arco-tabs-pane),
.details-panel :deep(.arco-tabs-content-item) {
  height: 100%;
}

.details-panel :deep(.arco-tabs-nav) {
  padding: 0 12px;
  flex-shrink: 0;
  height: 40px;
}

.tab-content {
  height: calc(100% - 110px);
  overflow: auto;
  padding: 8px 12px;
}

/* Network 面板 - 顶部过滤器 + 左右分栏布局 */
.network-content {
  display: flex;
  flex-direction: column;
  padding: 0 !important;
  height: calc(100% - 100px);
  overflow: hidden;
}

.network-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.filter-input {
  width: 140px;
}

.filter-types {
  display: flex;
  gap: 4px;
}

.filter-type-btn {
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  color: var(--color-text-2);
  border-radius: 2px;
  transition: all 0.15s;
}

.filter-type-btn:hover {
  background: var(--color-fill-2);
}

.filter-type-btn.active {
  color: var(--color-primary-6);
  background: var(--color-primary-1);
}

.network-split {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.network-sidebar {
  width: 200px;
  min-width: 150px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
  min-height: 0;
}

.network-list-header {
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-3);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.network-list {
  flex: 1;
  overflow-y: auto;
}

.network-list-item {
  padding: 5px 10px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-2);
  transition: background 0.1s;
}

.network-list-item:hover {
  background: var(--color-fill-2);
}

.network-list-item.active {
  background: var(--color-primary-1);
}

.network-list-item.error {
  color: var(--color-danger-6);
}

.request-name {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.network-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.network-main.network-empty {
  justify-content: center;
  align-items: center;
  color: var(--color-text-3);
}

.network-main.network-empty p {
  margin-top: 8px;
  font-size: 12px;
}

.detail-header {
  display: flex;
  align-items: center;
  padding: 0 8px;
  height: 36px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.close-btn {
  font-size: 18px;
  color: var(--color-text-3);
  cursor: pointer;
  padding: 4px 8px;
  line-height: 1;
}

.close-btn:hover {
  color: var(--color-text-1);
}

.detail-tabs {
  display: flex;
  gap: 4px;
}

.detail-tab {
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
  color: var(--color-text-2);
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}

.detail-tab:hover {
  color: var(--color-text-1);
}

.detail-tab.active {
  color: var(--color-primary-6);
  border-bottom-color: var(--color-primary-6);
}

.detail-body {
  height: calc(100% - 36px);
  overflow: hidden;
}

.detail-scroll {
  height: 100%;
  overflow-y: auto;
  padding: 8px 0;
}

/* 可折叠区块 */
.collapse-section {
  margin-bottom: 4px;
}

.collapse-header {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
}

.collapse-header:hover {
  background: var(--color-fill-1);
}

.collapse-arrow {
  width: 16px;
  font-size: 12px;
  color: var(--color-text-3);
  transition: transform 0.15s;
}

.collapse-arrow.expanded {
  transform: rotate(90deg);
}

.collapse-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-1);
}

.collapse-count {
  margin-left: 6px;
  font-size: 11px;
  color: var(--color-text-3);
}

.collapse-content {
  padding-left: 28px;
}

/* Headers 表格样式 - 左对齐 */
.headers-table {
  width: 100%;
  border-collapse: collapse;
  margin-left: 28px;
  font-size: 11px;
}

.headers-table td {
  padding: 2px 8px 2px 0;
  vertical-align: top;
  text-align: left;
}

.header-key {
  color: var(--color-primary-6);
  white-space: nowrap;
  width: 140px;
  min-width: 140px;
  padding-right: 12px !important;
}

.header-value {
  color: var(--color-text-1);
  word-break: break-all;
}

.detail-row {
  display: flex;
  padding: 3px 12px;
  font-size: 11px;
  line-height: 1.5;
}

.detail-key {
  width: 140px;
  flex-shrink: 0;
  color: var(--color-primary-6);
}

.detail-value {
  flex: 1;
  word-break: break-all;
  color: var(--color-text-1);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 6px;
  vertical-align: middle;
}

.dot-success { background: var(--color-success-6); }
.dot-redirect { background: var(--color-warning-6); }
.dot-error { background: var(--color-danger-6); }

.detail-section {
  margin-bottom: 12px;
}

.detail-title {
  font-weight: 600;
  font-size: 11px;
  color: var(--color-text-2);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border);
}

.detail-item {
  font-size: 11px;
  line-height: 1.6;
  font-family: monospace;
  word-break: break-all;
}

.detail-item span {
  color: var(--color-primary-6);
  margin-right: 4px;
}

.error-text {
  color: var(--color-danger-6);
}

.response-body {
  margin: 0;
  padding: 8px 12px;
  font-size: 11px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-fill-1);
  border-radius: 4px;
  text-align: left;
}

.payload-content {
  margin-left: 28px;
  padding: 4px 0;
  text-align: left;
}

.no-data {
  color: var(--color-text-3);
  font-size: 11px;
  padding: 8px 12px;
}

.no-response {
  color: var(--color-text-3);
  font-size: 12px;
  text-align: center;
  padding: 20px;
}

/* 控制台 */
.console-content {
  font-family: monospace;
  font-size: 11px;
  overflow-y: auto;
}

.console-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--color-border);
}

.console-type {
  width: 40px;
  font-weight: 500;
}

.console-text {
  flex: 1;
  word-break: break-all;
}

.console-log { color: var(--color-text-2); }
.console-info { color: var(--color-primary-6); }
.console-warn { color: var(--color-warning-6); }
.console-error { color: var(--color-danger-6); }

/* 附件 */
.attachments-content {
  padding: 8px !important;
  overflow-y: auto;
}

.attachments-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-item {
  border: 2px solid transparent;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.2s;
}

.attachment-item:hover {
  border-color: var(--color-primary-4);
}

.attachment-item.active {
  border-color: var(--color-primary-6);
}
</style>

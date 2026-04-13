<template>
  <a-drawer
    :visible="visible"
    width="1100px"
    title="数据工厂记录与统计"
    @update:visible="emit('update:visible', $event)"
  >
    <a-tabs :active-key="historyTab" @update:active-key="emit('update:history-tab', String($event))">
      <a-tab-pane key="records" title="使用记录">
        <div class="history-filters">
          <a-input-search
            v-model="recordFilters.search"
            allow-clear
            placeholder="搜索工具、标签或结果预览"
            :disabled="!projectReady"
            @search="searchRecords"
            @clear="searchRecords"
          />
          <a-select v-model="recordFilters.category" :disabled="!projectReady" @change="searchRecords">
            <a-option value="all" label="全部分类" />
            <a-option
              v-for="category in catalog.categories"
              :key="category.category"
              :value="category.category"
              :label="category.name"
            />
          </a-select>
          <a-select v-model="recordFilters.scenario" :disabled="!projectReady" @change="searchRecords">
            <a-option value="all" label="全部场景" />
            <a-option
              v-for="scenario in catalog.scenarios"
              :key="scenario.scenario"
              :value="scenario.scenario"
              :label="scenario.name"
            />
          </a-select>
          <a-select v-model="recordFilters.saved" :disabled="!projectReady" @change="searchRecords">
            <a-option value="all" label="全部记录" />
            <a-option value="saved" label="仅已保存" />
            <a-option value="temp" label="仅临时结果" />
          </a-select>
        </div>
        <a-table
          :data="projectReady ? records : []"
          :loading="projectReady ? loadingRecords : false"
          :pagination="projectReady ? recordPagination : false"
          row-key="id"
          @page-change="handleRecordPageChange"
          @page-size-change="handleRecordPageSizeChange"
        >
          <template #columns>
            <a-table-column title="ID" data-index="id" :width="80" />
            <a-table-column title="工具" :width="220">
              <template #cell="{ record }">
                <div class="record-tool">
                  <strong>{{ record.tool_display_name }}</strong>
                  <span>{{ record.category_display }} / {{ record.scenario_display }}</span>
                </div>
              </template>
            </a-table-column>
            <a-table-column title="标签" :width="220">
              <template #cell="{ record }">
                <a-space wrap size="mini">
                  <a-tag v-for="tag in record.tags" :key="tag.id" :color="tag.color || 'arcoblue'">{{ tag.name }}</a-tag>
                </a-space>
              </template>
            </a-table-column>
            <a-table-column title="结果预览" data-index="preview" ellipsis tooltip />
            <a-table-column title="创建时间" :width="180">
              <template #cell="{ record }">{{ formatDate(record.created_at) }}</template>
            </a-table-column>
            <a-table-column title="操作" :width="280">
              <template #cell="{ record }">
                <a-space wrap>
                  <a-button size="mini" :disabled="!projectReady" @click="showRecordResult(record)">查看</a-button>
                  <a-button
                    size="mini"
                    :disabled="!projectReady"
                    @click="copyText(record.reference_placeholder_api, '已复制 API 记录引用')"
                  >
                    API
                  </a-button>
                  <a-button
                    size="mini"
                    :disabled="!projectReady"
                    @click="copyText(record.reference_placeholder_ui, '已复制 UI 记录引用')"
                  >
                    UI
                  </a-button>
                  <a-popconfirm content="确定删除这条记录吗？" @ok="deleteRecord(record.id)">
                    <a-button size="mini" status="danger" :disabled="!projectReady">删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-tab-pane>
      <a-tab-pane key="stats" title="统计概览">
        <div class="insight-grid insight-grid--drawer">
          <div class="panel">
            <div class="section-title">分类使用统计</div>
            <div class="metric-list">
              <div v-for="item in categoryBreakdown" :key="item.key" class="metric">
                <div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div>
                <div class="metric__track"><span class="metric__bar" :style="{ width: `${item.percent}%` }"></span></div>
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="section-title">场景使用统计</div>
            <div class="metric-list">
              <div v-for="item in scenarioBreakdown" :key="item.key" class="metric">
                <div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div>
                <div class="metric__track"><span class="metric__bar metric__bar--soft" :style="{ width: `${item.percent}%` }"></span></div>
              </div>
            </div>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-drawer>
</template>

<script setup lang="ts">
import type {
  DataFactoryCatalog,
  DataFactoryCategoryKey,
  DataFactoryRecord,
  DataFactoryScenarioKey,
} from '../types'

type SavedFilter = 'all' | 'saved' | 'temp'

type MetricItem = {
  key: string
  name: string
  total: number
  percent: number
}

const props = defineProps<{
  visible: boolean
  historyTab: string
  projectReady: boolean
  loadingRecords: boolean
  records: DataFactoryRecord[]
  recordFilters: {
    search: string
    saved: SavedFilter
    category: DataFactoryCategoryKey | 'all'
    scenario: DataFactoryScenarioKey | 'all'
  }
  catalog: DataFactoryCatalog
  recordPagination: Record<string, unknown> | false
  categoryBreakdown: MetricItem[]
  scenarioBreakdown: MetricItem[]
  formatDate: (value?: string) => string
  copyText: (value: string, message?: string) => void
  showRecordResult: (record: DataFactoryRecord) => void
  deleteRecord: (id: number) => void
  searchRecords: () => void
  handleRecordPageChange: (page: number) => void
  handleRecordPageSizeChange: (pageSize: number) => void
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'update:history-tab', value: string): void
}>()

const {
  projectReady,
  loadingRecords,
  records,
  recordFilters,
  catalog,
  recordPagination,
  categoryBreakdown,
  scenarioBreakdown,
  formatDate,
  copyText,
  showRecordResult,
  deleteRecord,
  searchRecords,
  handleRecordPageChange,
  handleRecordPageSizeChange,
} = props
</script>

<style scoped>
.history-filters {
  display: grid;
  grid-template-columns: minmax(220px, 1.3fr) repeat(3, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.record-tool {
  display: grid;
  gap: 10px;
}

.record-tool span {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-text-3);
}

.insight-grid--drawer {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-1);
}

.section-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--color-text-1);
}

.metric-list {
  display: grid;
  gap: 12px;
}

.metric__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.metric__track {
  height: 8px;
  border-radius: 999px;
  background: rgba(var(--primary-6), 0.08);
  overflow: hidden;
}

.metric__bar {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(var(--primary-6), 0.55), rgb(var(--primary-6)));
}

.metric__bar--soft {
  background: linear-gradient(90deg, rgba(54, 127, 255, 0.35), rgba(54, 127, 255, 0.9));
}

@media (max-width: 1320px) {
  .insight-grid--drawer {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1180px) {
  .history-filters {
    grid-template-columns: 1fr;
  }
}
</style>

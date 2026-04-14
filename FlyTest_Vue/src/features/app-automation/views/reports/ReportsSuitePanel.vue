<template>
  <div class="panel-shell">
    <a-card class="filter-card">
      <div class="filter-grid">
        <a-input-search
          v-model="filters.search"
          allow-clear
          placeholder="搜索套件名称、描述或创建人"
          @search="emit('search')"
        />
        <a-select v-model="filters.status" placeholder="执行状态" allow-clear>
          <a-option value="not_run">未执行</a-option>
          <a-option value="running">执行中</a-option>
          <a-option value="passed">执行通过</a-option>
          <a-option value="failed">执行失败</a-option>
          <a-option value="stopped">已停止</a-option>
        </a-select>
        <div class="filter-actions">
          <a-button @click="emit('reset')">重置</a-button>
          <a-button type="primary" @click="emit('search')">查询</a-button>
        </div>
      </div>
    </a-card>

    <div class="stats-grid">
      <a-card class="stat-card">
        <span class="stat-label">套件总数</span>
        <strong>{{ statistics.total }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">执行中</span>
        <strong>{{ statistics.running }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">通过套件</span>
        <strong>{{ statistics.passed }}</strong>
      </a-card>
      <a-card class="stat-card">
        <span class="stat-label">平均健康度</span>
        <strong>{{ statistics.health }}%</strong>
      </a-card>
    </div>

    <a-card class="table-card">
      <a-table :data="suites" :loading="loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="套件 / 描述" :width="280">
            <template #cell="{ record }">
              <div class="stack">
                <strong>{{ record.name }}</strong>
                <span>{{ record.description || '暂无套件描述' }}</span>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="状态 / 健康度" :width="220">
            <template #cell="{ record }">
              <div class="stack">
                <a-tag :color="getSuiteStatus(record).color">{{ getSuiteStatus(record).label }}</a-tag>
                <small>健康度 {{ getSuiteHealthRate(record) }}%</small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="用例 / 结果" :width="220">
            <template #cell="{ record }">
              <div class="stack">
                <span>用例数 {{ record.test_case_count || 0 }}</span>
                <small>
                  通过 {{ record.passed_count || 0 }} / 失败 {{ record.failed_count || 0 }} / 停止
                  {{ record.stopped_count || 0 }}
                </small>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="最近执行" :width="180">
            <template #cell="{ record }">
              {{ formatDateTime(record.last_run_at) }}
            </template>
          </a-table-column>

          <a-table-column title="操作" :width="240" fixed="right">
            <template #cell="{ record }">
              <a-space wrap>
                <a-button type="text" @click="emit('open-detail', record)">详情</a-button>
                <a-button type="text" @click="emit('open-executions', record)">执行记录</a-button>
                <a-button type="text" @click="emit('open-report', record)">最新报告</a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>

      <div class="pagination-row">
        <a-pagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :show-total="true"
          :show-jumper="true"
          :show-page-size="true"
          :page-size-options="['10', '20', '50']"
        />
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import type { ReportsSuitePanelEmits } from './reportEventModels'
import type { ReportsSuitePanelProps } from './reportViewModels'

defineProps<ReportsSuitePanelProps>()

const emit = defineEmits<ReportsSuitePanelEmits>()
</script>

<style scoped>
.panel-shell,
.stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stack span,
.stack small {
  color: var(--theme-text-secondary);
}

.stack strong,
.stat-card strong {
  color: var(--theme-text);
}

.filter-card,
.table-card,
.stat-card {
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.6fr 180px auto;
  gap: 12px;
  align-items: center;
}

.filter-actions,
.pagination-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.stat-card strong {
  font-size: 30px;
  line-height: 1;
}

@media (max-width: 1280px) {
  .filter-grid,
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .filter-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>

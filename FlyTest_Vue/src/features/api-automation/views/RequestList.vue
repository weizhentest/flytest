<template>
  <div class="request-list">
    <div class="page-header api-page-header">
      <div class="page-summary">
        <div class="page-summary__eyebrow">项目 / 接口 / 用例</div>
        <div class="page-summary__title">接口管理</div>
        <div class="page-summary__meta">
          <span>{{ projectName }}</span>
          <span>{{ selectedCollectionName || '未选择接口集合' }}</span>
          <span>共 {{ requests.length }} 个接口</span>
          <span>共 {{ requestCaseTotal }} 条测试用例</span>
        </div>
      </div>
      <div class="page-toolbar">
        <a-input-search
          v-model="searchKeyword"
          class="toolbar-search"
          placeholder="搜索接口名称或 URL"
          allow-clear
          @search="loadRequests"
          @clear="loadRequests"
        />
        <div class="toolbar-group toolbar-group--filter">
          <a-select
            v-model="selectedEnvironmentId"
            class="toolbar-select"
            :loading="environmentLoading"
            allow-clear
            placeholder="执行环境"
          >
            <a-option v-for="item in environments" :key="item.id" :value="item.id" :label="item.name" />
          </a-select>
        </div>
        <div class="toolbar-group toolbar-group--actions">
          <a-button :disabled="!selectedRequestIds.length" @click="executeSelectedRequests">
            执行选中
          </a-button>
          <a-button :disabled="!selectedCollectionId" @click="executeCollectionRequests">
            执行当前集合
          </a-button>
          <a-button :disabled="!projectId" @click="executeProjectRequests">
            执行当前项目
          </a-button>
          <a-dropdown trigger="click" @select="handleSelectedCaseGenerationAction">
            <a-button :disabled="!selectedRequestIds.length">
              AI生成用例
            </a-button>
            <template #content>
              <a-doption value="generate" :disabled="!selectedRequestIds.length">批量生成</a-doption>
              <a-doption value="regenerate" :disabled="!selectedRequestIds.length">重新生成</a-doption>
              <a-doption value="append" :disabled="!selectedRequestIds.length">追加生成</a-doption>
            </template>
          </a-dropdown>
          <a-button type="primary" :disabled="!selectedCollectionId" @click="openCreateModal">
            新增接口
          </a-button>
        </div>
      </div>
    </div>

    <div v-if="!selectedCollectionId" class="empty-tip-card">
      <a-empty description="请先在左侧选择一个接口集合" />
    </div>

    <div v-else class="content-section">
      <a-table
        v-model:selectedKeys="selectedRequestIds"
        v-model:expanded-keys="expandedRequestKeys"
        :data="filteredRequests"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="large"
        :scroll="{ x: 1240 }"
        :row-selection="requestRowSelection"
        :expandable="{ width: 48 }"
        @expand="handleRequestExpand"
      >
        <template #columns>
          <a-table-column title="方法" :width="90">
            <template #cell="{ record }">
              <a-tag :color="methodColorMap[record.method] || 'arcoblue'">{{ record.method }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="接口名称" data-index="name" :width="220" ellipsis tooltip />
          <a-table-column title="请求地址" data-index="url" ellipsis tooltip />
          <a-table-column title="断言" :width="90" align="center">
            <template #cell="{ record }">
              <a-tag color="cyan">{{ record.assertions?.length || 0 }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="测试用例" :width="110" align="center">
            <template #cell="{ record }">
              <a-tag color="purple">{{ record.test_case_count || 0 }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="更新时间" :width="180">
            <template #cell="{ record }">{{ formatDate(record.updated_at) }}</template>
          </a-table-column>
          <a-table-column title="操作" :width="330" align="center" fixed="right">
            <template #cell="{ record }">
              <a-space :size="4">
                <a-button type="text" size="small" @click="executeRequest(record)">执行</a-button>
                <a-dropdown trigger="click" @select="value => handleSingleCaseGenerationAction(record, value)">
                  <a-button type="text" size="small">AI用例</a-button>
                  <template #content>
                    <a-doption value="generate">生成</a-doption>
                    <a-doption value="regenerate">重生成</a-doption>
                    <a-doption value="append">追加生成</a-doption>
                  </template>
                </a-dropdown>
                <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
                <a-button type="text" size="small" @click="viewRequest(record)">详情</a-button>
                <a-popconfirm content="确认删除该接口吗？" @ok="deleteRequest(record.id)">
                  <a-button type="text" size="small" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>

        <template #expand-row="{ record }">
          <div class="request-case-panel">
            <div class="request-case-panel__header">
              <div>
                <div class="request-case-panel__title">接口测试用例</div>
                <div class="request-case-panel__subtitle">
                  当前接口下的测试用例会直接绑定到该接口，可在这里查看和继续生成。
                </div>
              </div>
              <div class="request-case-panel__actions">
                <a-button size="small" @click="generateCasesForRequest(record, 'generate')">AI生成</a-button>
                <a-button size="small" @click="generateCasesForRequest(record, 'regenerate')">重新生成</a-button>
                <a-button size="small" @click="generateCasesForRequest(record, 'append')">追加生成</a-button>
              </div>
            </div>

            <div v-if="requestTestCaseLoadingMap[record.id]" class="request-case-panel__loading">
              <a-spin />
            </div>
            <a-empty
              v-else-if="!(requestTestCaseMap[record.id]?.length)"
              description="当前接口下还没有测试用例，可直接使用 AI 生成。"
            />
            <div v-else class="request-case-list">
              <div v-for="testCase in requestTestCaseMap[record.id]" :key="testCase.id" class="request-case-card">
                <div class="request-case-card__main">
                  <div class="request-case-card__name">{{ testCase.name }}</div>
                  <div class="request-case-card__desc">{{ testCase.description || '暂无描述' }}</div>
                  <a-space wrap>
                    <a-tag :color="statusTagColorMap[testCase.status]">{{ statusLabelMap[testCase.status] }}</a-tag>
                    <a-tag v-for="tag in testCase.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
                  </a-space>
                </div>
                <div class="request-case-card__meta">
                  <span>{{ formatDate(testCase.updated_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:visible="editorVisible"
      :title="editingRequest ? '编辑接口' : '新增接口'"
      width="900px"
      :ok-loading="submitLoading"
      :mask-closable="!submitLoading"
      :closable="!submitLoading"
      @before-ok="submitRequest"
      @cancel="resetEditor"
    >
      <div v-if="!editingRequest" class="create-mode-switch">
        <a-radio-group v-model="createMode" type="button">
          <a-radio value="manual">手动创建</a-radio>
          <a-radio value="document">文档导入</a-radio>
        </a-radio-group>
      </div>

      <a-form v-if="editingRequest || createMode === 'manual'" :model="formState" layout="vertical">
        <div v-if="!editingRequest && createMode === 'manual' && hasRequestDrafts" class="import-prefill-banner">
          <div class="prefill-copy">
            <div class="prefill-title">已同步最近一次文档解析结果</div>
            <div class="prefill-description">
              {{ draftSummary || '可以直接把解析结果回填到手动创建表单。' }}
            </div>
          </div>
          <div class="prefill-actions">
            <a-select
              v-model="selectedRequestDraftIndex"
              style="width: 260px"
              @change="applySelectedRequestDraft"
            >
              <a-option
                v-for="(draft, index) in requestDrafts"
                :key="`${draft.label}-${index}`"
                :value="index"
                :label="draft.label"
              />
            </a-select>
            <a-button @click="applySelectedRequestDraft()">回填字段</a-button>
            <a-button type="text" @click="clearDraftsAndReset">清除草稿</a-button>
          </div>
        </div>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="name" label="接口名称" :rules="[{ required: true, message: '请输入接口名称' }]">
              <a-input v-model="formState.name" placeholder="例如：获取用户信息" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="method" label="请求方法">
              <a-select v-model="formState.method">
                <a-option v-for="method in methods" :key="method" :value="method" :label="method" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item field="timeout_ms" label="超时(ms)">
              <a-input-number v-model="formState.timeout_ms" :min="1000" :step="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="url" label="请求地址" :rules="[{ required: true, message: '请输入请求地址' }]">
          <a-input
            v-model="formState.url"
            placeholder="支持完整 URL 或相对路径，例如 /api/users 或 {{base_url}}/users"
          />
        </a-form-item>

        <a-form-item field="description" label="描述">
          <a-textarea v-model="formState.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="headersText" label="请求头(JSON)">
              <a-textarea
                v-model="formState.headersText"
                :auto-size="{ minRows: 6, maxRows: 12 }"
                placeholder='例如：{"Authorization":"Bearer {{token}}"}'
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="paramsText" label="查询参数(JSON)">
              <a-textarea
                v-model="formState.paramsText"
                :auto-size="{ minRows: 6, maxRows: 12 }"
                placeholder='例如：{"page":1,"size":20}'
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="body_type" label="请求体类型">
              <a-select v-model="formState.body_type">
                <a-option value="none" label="none" />
                <a-option value="json" label="json" />
                <a-option value="form" label="form" />
                <a-option value="raw" label="raw" />
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item v-if="formState.body_type !== 'none'" field="bodyText" label="请求体">
          <a-textarea
            v-model="formState.bodyText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            :placeholder="formState.body_type === 'raw' ? '请输入原始文本' : '请输入 JSON 对象'"
          />
        </a-form-item>

        <a-form-item field="assertionsText" label="断言规则(JSON数组)">
          <a-textarea
            v-model="formState.assertionsText"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            placeholder='例如：[{"type":"status_code","expected":200},{"type":"body_contains","expected":"success"}]'
          />
        </a-form-item>
      </a-form>

      <div v-else-if="importProgressActive" class="document-import-panel import-progress-panel">
        <div class="import-progress-hero">
          <div class="import-progress-badge">
            {{
              importProgressStatus === 'error'
                ? '解析失败'
                : importProgressStatus === 'success'
                  ? '解析完成'
                  : '智能解析中'
            }}
          </div>
          <div class="import-progress-title">{{ importProgressFileName || '接口文档' }}</div>
          <div class="import-progress-description">{{ importProgressMessage }}</div>
        </div>

        <div class="import-progress-bar">
          <a-progress
            :percent="importProgressRatio"
            :show-text="false"
            :status="
              importProgressStatus === 'error'
                ? 'danger'
                : importProgressStatus === 'success'
                  ? 'success'
                  : undefined
            "
          />
          <span class="import-progress-percent">{{ importProgressPercent }}%</span>
        </div>

        <div class="import-progress-step-list">
          <div
            v-for="(step, index) in importProgressSteps"
            :key="step.title"
            class="import-progress-step"
            :class="getImportStepClass(index)"
          >
            <div class="import-progress-step-marker">{{ index + 1 }}</div>
            <div class="import-progress-step-copy">
              <div class="import-progress-step-title">{{ step.title }}</div>
              <div class="import-progress-step-description">{{ step.description }}</div>
            </div>
          </div>
        </div>

        <a-alert v-if="importProgressStatus === 'error'" type="error" class="import-progress-alert">
          <template #title>本次导入没有成功</template>
          {{ importProgressError || '请检查文档是否包含接口名称、请求方式、请求地址、参数说明和成功响应描述。' }}
        </a-alert>

        <div class="import-progress-actions" :class="{ 'is-error-only': importProgressStatus === 'error' }">
          <a-button
            v-if="currentImportJob && canCancelImportJob(currentImportJob)"
            status="danger"
            @click="handleCancelImportJob(currentImportJob)"
          >
            停止解析
          </a-button>
          <a-button @click="resetImportProgress">返回重新导入</a-button>
        </div>
      </div>

      <div v-else class="document-import-panel">
        <div class="import-hero-card">
          <div class="import-hero-badge">AI增强解析</div>
          <div class="import-hero-title">接口文档导入与自动化生成</div>
          <div class="import-hero-description">
            支持 Swagger / OpenAPI / Postman，以及 PDF、图片、PPTX、DOCX、XLSX、HTML、EPUB 等格式。
            导入时会先做规则解析，再按需调用系统设置中的当前激活模型进行 AI 增强解析，自动补全接口定义、断言，并批量生成脚本与测试用例。
          </div>
          <div class="import-hero-meta">
            <span class="hero-pill">系统设置 &gt; LLM配置</span>
            <span class="hero-pill">提示词管理 &gt; API自动化解析</span>
            <span class="hero-pill">失败自动回退规则解析</span>
          </div>
        </div>

        <div
          class="document-dropzone"
          :class="{ 'is-dragging': documentDragging, 'has-file': !!documentFile }"
          @click="triggerDocumentSelect"
          @dragenter.prevent="documentDragging = true"
          @dragover.prevent="documentDragging = true"
          @dragleave.prevent="documentDragging = false"
          @drop="handleDocumentDrop"
        >
          <input
            ref="documentInputRef"
            class="file-input-hidden"
            type="file"
            accept=".json,.yaml,.yml,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.html,.htm,.epub"
            @change="handleDocumentChange"
          />
          <div class="dropzone-icon">AI</div>
          <div class="dropzone-title">
            {{ documentFile ? '已选择接口文档，导入时将自动解析' : '拖拽接口文档到这里，或点击选择文件' }}
          </div>
          <div class="dropzone-subtitle">
            推荐优先上传 OpenAPI / Swagger / Postman。非结构化文档将结合规则解析与 AI 增强解析提取接口信息。
          </div>

          <div v-if="documentFile" class="selected-file-card" @click.stop>
            <div class="selected-file-main">
              <div class="selected-file-name">{{ documentFile.name }}</div>
              <div class="selected-file-meta">{{ documentFileSummary }}</div>
            </div>
            <a-button type="text" size="small" @click="clearDocumentFile">重新选择</a-button>
          </div>
        </div>

        <div class="import-option-grid">
          <div class="import-option-card import-option-card-primary">
            <div class="option-copy">
              <div class="option-title">AI增强解析</div>
              <div class="option-description">
                使用系统设置中当前激活的 AI 接口，并读取“提示词管理”中的 API 自动化解析提示词；若 AI 不可用，会自动回退到规则解析。
              </div>
            </div>
            <a-switch v-model="enableAiParse" />
          </div>
          <div class="import-option-card">
            <div class="option-copy">
              <div class="option-title">批量生成测试用例</div>
              <div class="option-description">
                基于解析出的接口请求自动生成接口自动化脚本和测试用例，适合导入后直接进入回归设计。
              </div>
            </div>
            <a-switch v-model="generateTestCases" />
          </div>
        </div>

        <a-alert type="info" class="import-alert">
          <template #title>导入说明</template>
          文档导入完成后，结果面板会显示本次是否启用了 AI 增强解析、采用了哪个模型、提示词来源，以及是否回退到了规则解析。
        </a-alert>
      </div>
    </a-modal>

    <a-modal
      v-model:visible="resultVisible"
      class="detail-modal detail-modal--wide"
      :title="currentResult?.id ? '执行结果详情' : '接口详情'"
      width="1120px"
      :footer="false"
      :mask-closable="true"
      :body-style="{ maxHeight: '78vh', overflowY: 'auto' }"
    >
      <div v-if="currentResult" class="result-drawer">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="接口名称">{{ currentResult.request_name }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="currentResult.passed ? 'green' : currentResult.status === 'error' ? 'red' : 'orange'">
              {{ currentResult.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态码">{{ currentResult.status_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="响应时间">{{ formatDuration(currentResult.response_time) }}</a-descriptions-item>
          <a-descriptions-item label="最终地址" :span="2">{{ currentResult.url }}</a-descriptions-item>
          <a-descriptions-item label="错误信息" :span="2">
            {{ currentResult.error_message || '-' }}
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>断言结果</a-divider>
        <a-table :data="currentResult.assertions_results || []" :pagination="false" row-key="index">
          <template #columns>
            <a-table-column title="#" data-index="index" :width="60" />
            <a-table-column title="类型" data-index="type" :width="120" />
            <a-table-column title="期望值" data-index="expected" ellipsis tooltip />
            <a-table-column title="实际值" data-index="actual" ellipsis tooltip />
            <a-table-column title="结果" :width="90">
              <template #cell="{ record }">
                <a-tag :color="record.passed ? 'green' : 'red'">{{ record.passed ? '通过' : '失败' }}</a-tag>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <a-divider>请求快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentResult.request_snapshot) }}</pre>

        <template v-if="currentResult.request_snapshot?.generated_script">
          <a-divider>接口脚本</a-divider>
          <pre class="json-block">{{ stringifyBlock(currentResult.request_snapshot.generated_script) }}</pre>
        </template>

        <a-divider>响应快照</a-divider>
        <pre class="json-block">{{ stringifyBlock(currentResult.response_snapshot) }}</pre>
      </div>
    </a-modal>

    <a-drawer v-model:visible="importResultVisible" width="920px" title="文档导入结果" :footer="false">
      <div v-if="importResult" class="import-result-drawer">
        <a-alert
          :type="importResult.ai_requested ? (importResult.ai_used ? 'success' : 'warning') : 'info'"
          class="import-result-alert"
        >
          <template #title>
            {{
              importResult.ai_requested
                ? importResult.ai_used
                  ? 'AI增强解析已生效'
                  : 'AI增强解析未生效，已回退到规则解析'
                : '本次未启用 AI 增强解析'
            }}
          </template>
          {{ importResult.ai_note || '本次导入未返回额外的 AI 解析说明。' }}
        </a-alert>

        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="导入来源">{{ importResult.source_type || '-' }}</a-descriptions-item>
          <a-descriptions-item label="使用 Marker">
            <a-tag :color="importResult.marker_used ? 'arcoblue' : 'gray'">
              {{ importResult.marker_used ? '是' : '否' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="AI增强解析">
            <a-tag :color="importResult.ai_requested ? (importResult.ai_used ? 'green' : 'orange') : 'gray'">
              {{
                importResult.ai_requested
                  ? importResult.ai_used
                    ? '已启用'
                    : '已回退'
                  : '未开启'
              }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="AI模型">{{ importResult.ai_model_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="生成接口">{{ importResult.created_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="生成脚本">{{ importResult.generated_script_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="生成测试用例">{{ importResult.created_testcase_count || 0 }}</a-descriptions-item>
          <a-descriptions-item label="提示词来源">
            {{ importResult.ai_prompt_name || importResult.ai_prompt_source || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="解析说明" :span="2">{{ importResult.note || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-tabs type="rounded">
          <a-tab-pane key="scripts" title="接口脚本">
            <a-empty v-if="!importResult.generated_scripts?.length" description="暂无生成脚本" />
            <a-collapse v-else>
              <a-collapse-item
                v-for="item in importResult.generated_scripts"
                :key="item.request_id"
                :header="`${item.request_name}${item.collection_name ? ` · ${item.collection_name}` : ''}`"
              >
                <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
              </a-collapse-item>
            </a-collapse>
          </a-tab-pane>
          <a-tab-pane key="test-cases" title="测试用例">
            <a-empty v-if="!importResult.test_cases?.length" description="本次未生成测试用例" />
            <a-collapse v-else>
              <a-collapse-item
                v-for="item in importResult.test_cases"
                :key="item.id"
                :header="`${item.name}${item.request_name ? ` · ${item.request_name}` : ''}`"
              >
                <a-space wrap class="import-tags">
                  <a-tag v-for="tag in item.tags || []" :key="tag" color="arcoblue">{{ tag }}</a-tag>
                </a-space>
                <pre class="json-block">{{ stringifyBlock(item.script) }}</pre>
                <a-divider>断言规则</a-divider>
                <pre class="json-block">{{ stringifyBlock(item.assertions) }}</pre>
              </a-collapse-item>
            </a-collapse>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { apiRequestApi, environmentApi, testCaseApi } from '../api'
import { useApiImportDrafts } from '../state/importDraft'
import { useApiImportJobs } from '../state/importJobs'
import type {
  ApiEnvironment,
  ApiExecutionBatchResult,
  ApiExecutionRecord,
  ApiImportJob,
  ApiImportResult,
  ApiRequest,
  ApiRequestForm,
  ApiTestCase,
  ApiTestCaseGenerationResult,
} from '../types'

const props = defineProps<{
  selectedCollectionId?: number
  selectedCollectionName?: string
}>()

const emit = defineEmits<{
  (e: 'executed'): void
  (e: 'updated'): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const projectName = computed(() => projectStore.currentProject?.name || '未选择项目')
const {
  requestDrafts,
  draftSummary,
  hasRequestDrafts,
  saveDraftsFromImport,
  getRequestDraft,
  clearDrafts,
} = useApiImportDrafts()

const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const methodColorMap: Record<string, string> = {
  GET: 'green',
  POST: 'arcoblue',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'gray',
  OPTIONS: 'cyan',
}

const statusLabelMap: Record<ApiTestCase['status'], string> = {
  draft: '草稿',
  ready: '就绪',
  disabled: '停用',
}

const statusTagColorMap: Record<ApiTestCase['status'], string> = {
  draft: 'gray',
  ready: 'green',
  disabled: 'red',
}

const loading = ref(false)
const environmentLoading = ref(false)
const submitLoading = ref(false)
const searchKeyword = ref('')
const requests = ref<ApiRequest[]>([])
const environments = ref<ApiEnvironment[]>([])
const selectedEnvironmentId = ref<number | undefined>(undefined)
const selectedRequestIds = ref<number[]>([])
const expandedRequestKeys = ref<number[]>([])
const requestTestCaseMap = ref<Record<number, ApiTestCase[]>>({})
const requestTestCaseLoadingMap = ref<Record<number, boolean>>({})
const editorVisible = ref(false)
const resultVisible = ref(false)
const importResultVisible = ref(false)
const editingRequest = ref<ApiRequest | null>(null)
const currentResult = ref<ApiExecutionRecord | null>(null)
const importResult = ref<ApiImportResult | null>(null)
const documentFile = ref<File | null>(null)
const documentInputRef = ref<HTMLInputElement | null>(null)
const documentDragging = ref(false)
const createMode = ref<'manual' | 'document'>('manual')
const generateTestCases = ref(true)
const enableAiParse = ref(true)
const selectedRequestDraftIndex = ref(0)
const importProgressActive = ref(false)
const importProgressPercent = ref(0)
const importProgressStage = ref(0)
const importProgressStatus = ref<'idle' | 'uploading' | 'processing' | 'success' | 'error'>('idle')
const importProgressMessage = ref('')
const importProgressError = ref('')
const importProgressFileName = ref('')

const { activeImportJobs, syncProject, trackImportJob, registerFinishedHandler, cancelImportJob } = useApiImportJobs()

const importProgressSteps = [
  { title: '上传接口文档', description: '将 Word、PDF、Swagger 等接口文档上传到 FlyTest。' },
  { title: '提取文档文本', description: '转换文档内容并抽取接口结构线索。' },
  { title: '识别接口定义', description: '结合规则与 AI 解析请求方式、路径、参数和断言。' },
  { title: '生成脚本与用例', description: '为识别出的接口批量生成可执行脚本和测试用例。' },
  { title: '写入 FlyTest', description: '把接口、脚本和测试用例保存到当前集合。' },
]

let importProgressTimer: ReturnType<typeof window.setInterval> | null = null

const formState = ref({
  name: '',
  description: '',
  method: 'GET',
  url: '',
  headersText: '{}',
  paramsText: '{}',
  body_type: 'none' as 'none' | 'json' | 'form' | 'raw',
  bodyText: '{}',
  assertionsText: '[]',
  timeout_ms: 30000,
})

const filteredRequests = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return requests.value
  return requests.value.filter(item => {
    return item.name.toLowerCase().includes(keyword) || item.url.toLowerCase().includes(keyword)
  })
})

const requestCaseTotal = computed(() =>
  requests.value.reduce((sum, item) => sum + Number(item.test_case_count || 0), 0)
)

type CaseGenerationMode = 'generate' | 'append' | 'regenerate'

const requestRowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
}

const documentFileSummary = computed(() => {
  if (!documentFile.value) return ''
  const size = documentFile.value.size
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
})

const importProgressRatio = computed(() => {
  const clamped = Math.max(0, Math.min(importProgressPercent.value, 100))
  return clamped / 100
})

const currentImportJob = computed(() => {
  if (!projectId.value) return null
  return activeImportJobs.value.find(job => job.project === projectId.value) || null
})

const canCancelImportJob = (job: ApiImportJob) => {
  return (job.status === 'pending' || job.status === 'running') && !job.cancel_requested
}

const getImportStepClass = (index: number) => {
  if (importProgressStatus.value === 'error') {
    if (index < importProgressStage.value) return 'is-finished'
    if (index === importProgressStage.value) return 'is-error'
    return 'is-pending'
  }
  if (importProgressStatus.value === 'success') {
    return 'is-finished'
  }
  if (index < importProgressStage.value) return 'is-finished'
  if (index === importProgressStage.value) return 'is-active'
  return 'is-pending'
}

const clearImportProgressTimer = () => {
  if (importProgressTimer) {
    window.clearInterval(importProgressTimer)
    importProgressTimer = null
  }
}

const resetImportProgress = () => {
  clearImportProgressTimer()
  importProgressActive.value = false
  importProgressPercent.value = 0
  importProgressStage.value = 0
  importProgressStatus.value = 'idle'
  importProgressMessage.value = ''
  importProgressError.value = ''
  importProgressFileName.value = ''
}

const syncProcessingStage = () => {
  const milestones = [28, 50, 74, 90, 97]

  if (importProgressPercent.value < milestones[1]) {
    importProgressStage.value = 1
    importProgressMessage.value = '文档上传完成，正在抽取正文与接口结构。'
    return
  }
  if (importProgressPercent.value < milestones[2]) {
    importProgressStage.value = 2
    importProgressMessage.value = '正在识别接口名称、请求方式、路径、参数与断言。'
    return
  }
  if (importProgressPercent.value < milestones[3]) {
    importProgressStage.value = 3
    importProgressMessage.value = '正在生成前端可执行的接口脚本和测试用例。'
    return
  }
  importProgressStage.value = 4
  importProgressMessage.value = '正在把解析结果写入当前接口集合。'
}

const startImportProgress = (fileName: string) => {
  resetImportProgress()
  importProgressActive.value = true
  importProgressFileName.value = fileName
  importProgressStatus.value = 'uploading'
  importProgressStage.value = 0
  importProgressPercent.value = 6
  importProgressMessage.value = `正在上传 ${fileName}，并校验文档格式。`

  clearImportProgressTimer()
  importProgressTimer = window.setInterval(() => {
    if (importProgressStatus.value === 'uploading') {
      importProgressPercent.value = Math.min(importProgressPercent.value + 3, 24)
      return
    }
    if (importProgressStatus.value !== 'processing') return

    importProgressPercent.value = Math.min(importProgressPercent.value + 4, 97)
    syncProcessingStage()
  }, 700)
}

const handleImportUploadProgress = (event: { loaded?: number; total?: number }) => {
  if (!importProgressActive.value) return

  const total = event.total || 0
  if (total > 0) {
    const percent = Math.max(6, Math.min(28, Math.round((event.loaded || 0) / total * 28)))
    importProgressPercent.value = Math.max(importProgressPercent.value, percent)
  }

  if (total > 0 && (event.loaded || 0) >= total) {
    importProgressStatus.value = 'processing'
    importProgressPercent.value = Math.max(importProgressPercent.value, 34)
    syncProcessingStage()
  }
}

const completeImportProgress = async (createdCount: number, testcaseCount: number) => {
  clearImportProgressTimer()
  importProgressActive.value = true
  importProgressStatus.value = 'success'
  importProgressStage.value = importProgressSteps.length - 1
  importProgressPercent.value = 100
  importProgressMessage.value = `解析完成，已生成 ${createdCount} 个接口和 ${testcaseCount} 个测试用例。`
  await new Promise(resolve => window.setTimeout(resolve, 360))
}

const failImportProgress = (message: string) => {
  clearImportProgressTimer()
  importProgressActive.value = true
  importProgressStatus.value = 'error'
  importProgressError.value = message
  importProgressPercent.value = Math.max(importProgressPercent.value, 20)
  syncProcessingStage()
}

const handleCancelImportJob = async (job: ApiImportJob) => {
  try {
    await cancelImportJob(job.id)
    importProgressActive.value = true
    importProgressStatus.value = 'processing'
    importProgressMessage.value = '已发送停止解析请求，正在等待后台终止任务。'
    Message.success('已发送停止解析请求')
  } catch (error) {
    console.error('[RequestList] 停止解析失败:', error)
    Message.error('停止解析失败')
  }
}

const stringifyJson = (value: any, fallback = '{}') => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const stringifyBlock = (value: any) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const parseJsonText = (text: string, fallback: any) => {
  if (!text.trim()) return fallback
  return JSON.parse(text)
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)} ms`
}

const loadEnvironments = async () => {
  if (!projectId.value) {
    environments.value = []
    return
  }
  environmentLoading.value = true
  try {
    const res = await environmentApi.list({ project: projectId.value })
    const data = res.data?.data || []
    environments.value = Array.isArray(data) ? data : []
    if (!selectedEnvironmentId.value) {
      const defaultEnv = environments.value.find(item => item.is_default)
      if (defaultEnv) selectedEnvironmentId.value = defaultEnv.id
    }
  } catch (error) {
    console.error('[RequestList] 获取环境失败:', error)
    environments.value = []
  } finally {
    environmentLoading.value = false
  }
}

const loadRequests = async () => {
  if (!projectId.value || !props.selectedCollectionId) {
    requests.value = []
    selectedRequestIds.value = []
    expandedRequestKeys.value = []
    requestTestCaseMap.value = {}
    return
  }
  loading.value = true
  try {
    const res = await apiRequestApi.list({
      project: projectId.value,
      collection: props.selectedCollectionId,
    })
    const data = res.data?.data || []
    requests.value = Array.isArray(data) ? data : []
    const availableIds = new Set(requests.value.map(item => item.id))
    selectedRequestIds.value = selectedRequestIds.value.filter(id => availableIds.has(id))
    expandedRequestKeys.value = expandedRequestKeys.value.filter(id => availableIds.has(id))
  } catch (error) {
    console.error('[RequestList] 获取接口失败:', error)
    Message.error(getErrorMessage(error))
    requests.value = []
    selectedRequestIds.value = []
    expandedRequestKeys.value = []
    requestTestCaseMap.value = {}
  } finally {
    loading.value = false
  }
}

const loadRequestTestCases = async (requestId: number, force = false) => {
  if (!projectId.value) return
  if (!force && requestTestCaseMap.value[requestId]) return

  requestTestCaseLoadingMap.value = {
    ...requestTestCaseLoadingMap.value,
    [requestId]: true,
  }
  try {
    const res = await testCaseApi.list({
      project: projectId.value,
      request: requestId,
    })
    const data = res.data?.data || []
    requestTestCaseMap.value = {
      ...requestTestCaseMap.value,
      [requestId]: Array.isArray(data) ? data : [],
    }
  } catch (error) {
    console.error('[RequestList] 获取接口下测试用例失败:', error)
    Message.error('获取接口下测试用例失败')
    requestTestCaseMap.value = {
      ...requestTestCaseMap.value,
      [requestId]: [],
    }
  } finally {
    requestTestCaseLoadingMap.value = {
      ...requestTestCaseLoadingMap.value,
      [requestId]: false,
    }
  }
}

const handleRequestExpand = async (rowKey: string | number) => {
  const requestId = Number(rowKey)
  if (!Number.isFinite(requestId)) return
  if (expandedRequestKeys.value.includes(requestId)) {
    await loadRequestTestCases(requestId)
  }
}

const unregisterImportFinishedHandler = registerFinishedHandler(async job => {
  if (job.project !== projectId.value) return
  if (job.status === 'canceled') {
    clearImportProgressTimer()
    importProgressActive.value = true
    importProgressStatus.value = 'error'
    importProgressError.value = job.error_message || job.progress_message || '文档解析已手动停止'
    importProgressMessage.value = job.progress_message || '文档解析任务已取消'
    return
  }
  const result = job.result_payload
  if (!result) return

  importResult.value = result
  importResultVisible.value = true
  saveDraftsFromImport(result, projectId.value || job.project, job.collection)
  await loadRequests()
  emit('updated')
})

const resetEditor = () => {
  editingRequest.value = null
  documentFile.value = null
  documentDragging.value = false
  createMode.value = 'manual'
  generateTestCases.value = true
  enableAiParse.value = true
  selectedRequestDraftIndex.value = 0
  resetImportProgress()
  if (documentInputRef.value) {
    documentInputRef.value.value = ''
  }
  formState.value = {
    name: '',
    description: '',
    method: 'GET',
    url: '',
    headersText: '{}',
    paramsText: '{}',
    body_type: 'none',
    bodyText: '{}',
    assertionsText: '[]',
    timeout_ms: 30000,
  }
}

const fillFormFromRequestDraft = (draftIndex = selectedRequestDraftIndex.value) => {
  const draft = getRequestDraft(draftIndex)
  if (!draft) return

  selectedRequestDraftIndex.value = draftIndex
  formState.value = {
    name: draft.form.name,
    description: draft.form.description || '',
    method: draft.form.method,
    url: draft.form.url,
    headersText: stringifyJson(draft.form.headers),
    paramsText: stringifyJson(draft.form.params),
    body_type: draft.form.body_type,
    bodyText:
      draft.form.body_type === 'raw'
        ? stringifyJson(draft.form.body, '')
        : stringifyJson(draft.form.body, '{}'),
    assertionsText: stringifyJson(draft.form.assertions, '[]'),
    timeout_ms: draft.form.timeout_ms || 30000,
  }
}

const openCreateModal = () => {
  resetEditor()
  if (hasRequestDrafts.value) {
    fillFormFromRequestDraft(0)
  }
  editorVisible.value = true
}

const openEditModal = (record: ApiRequest) => {
  editingRequest.value = record
  createMode.value = 'manual'
  formState.value = {
    name: record.name,
    description: record.description || '',
    method: record.method,
    url: record.url,
    headersText: stringifyJson(record.headers),
    paramsText: stringifyJson(record.params),
    body_type: record.body_type,
    bodyText: record.body_type === 'raw' ? stringifyJson(record.body, '') : stringifyJson(record.body, '{}'),
    assertionsText: stringifyJson(record.assertions, '[]'),
    timeout_ms: record.timeout_ms,
  }
  editorVisible.value = true
}

const applySelectedRequestDraft = (value?: string | number | boolean) => {
  const index = typeof value === 'number' ? value : selectedRequestDraftIndex.value
  fillFormFromRequestDraft(index)
}

const clearDraftsAndReset = () => {
  clearDrafts()
  resetEditor()
}

const handleDocumentChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  documentFile.value = input.files?.[0] || null
  documentDragging.value = false
}

const triggerDocumentSelect = () => {
  documentInputRef.value?.click()
}

const clearDocumentFile = () => {
  documentFile.value = null
  documentDragging.value = false
  if (documentInputRef.value) {
    documentInputRef.value.value = ''
  }
}

const handleDocumentDrop = (event: DragEvent) => {
  event.preventDefault()
  documentDragging.value = false
  const file = event.dataTransfer?.files?.[0] || null
  if (file) {
    documentFile.value = file
    if (documentInputRef.value) {
      documentInputRef.value.value = ''
    }
  }
}

const viewRequest = (record: ApiRequest) => {
  currentResult.value = {
    id: 0,
    project: record.project_id || projectId.value || 0,
    request: record.id,
    environment: null,
    request_name: record.name,
    method: record.method,
    url: record.url,
    status: 'success',
    passed: false,
    status_code: null,
    response_time: null,
    request_snapshot: {
      headers: record.headers,
      params: record.params,
      body_type: record.body_type,
      body: record.body,
      assertions: record.assertions,
      generated_script: record.generated_script,
    },
    response_snapshot: {},
    assertions_results: [],
    created_at: record.updated_at,
    executor: null,
  }
  resultVisible.value = true
}

const submitManualRequest = async () => {
  const payload: ApiRequestForm = {
    collection: props.selectedCollectionId!,
    name: formState.value.name.trim(),
    description: formState.value.description.trim(),
    method: formState.value.method,
    url: formState.value.url.trim(),
    headers: parseJsonText(formState.value.headersText, {}),
    params: parseJsonText(formState.value.paramsText, {}),
    body_type: formState.value.body_type,
    body:
      formState.value.body_type === 'none'
        ? {}
        : formState.value.body_type === 'raw'
          ? formState.value.bodyText
          : parseJsonText(formState.value.bodyText, {}),
    assertions: parseJsonText(formState.value.assertionsText, []),
    timeout_ms: formState.value.timeout_ms,
  }

  if (editingRequest.value) {
    await apiRequestApi.update(editingRequest.value.id, payload)
    Message.success('接口更新成功')
  } else {
    await apiRequestApi.create(payload)
    Message.success('接口创建成功')
  }
}

const getErrorMessage = (error: any) => {
  const rawMessage = error?.error || error?.data?.error || error?.message || '处理接口失败'
  if (error?.status === 408 || /timeout/i.test(String(rawMessage))) {
    return '接口文档解析超时，请稍后重试；如果文档较大，建议先关闭 AI 增强解析后再导入。'
  }
  if (String(rawMessage).includes('服务器无响应')) {
    return '接口文档解析等待时间过长，请稍后重试；如果文档较大，建议先关闭 AI 增强解析后再导入。'
  }
  return rawMessage
}

const submitDocumentImport = async () => {
  if (!documentFile.value) {
    throw new Error('请先选择接口文档')
  }

  startImportProgress(documentFile.value.name)
  try {
    const res = await apiRequestApi.importDocument(props.selectedCollectionId!, documentFile.value, {
      generateTestCases: generateTestCases.value,
      enableAiParse: enableAiParse.value,
      onUploadProgress: handleImportUploadProgress,
      asyncMode: true,
    })
    const job = res.data.data as ApiImportJob
    clearImportProgressTimer()
    resetImportProgress()
    trackImportJob(job)
    Message.success('接口文档解析任务已提交，后台会继续执行，完成后会自动提示你。')
  } catch (error: any) {
    failImportProgress(getErrorMessage(error))
    throw error
  }
}

const submitRequest = async (done: (closed: boolean) => void) => {
  if (!projectId.value || !props.selectedCollectionId) {
    Message.warning('请先选择接口集合')
    done(false)
    return
  }

  submitLoading.value = true
  try {
    if (editingRequest.value || createMode.value === 'manual') {
      await submitManualRequest()
      done(true)
      editorVisible.value = false
      resetEditor()
      emit('updated')
      loadRequests()
    } else {
      await submitDocumentImport()
      done(true)
      editorVisible.value = false
      resetEditor()
    }
  } catch (error: any) {
    console.error('[RequestList] 保存接口失败:', error)
    Message.error(getErrorMessage(error))
    done(false)
  } finally {
    submitLoading.value = false
  }
}

const deleteRequest = async (id: number) => {
  try {
    await apiRequestApi.delete(id)
    Message.success('接口删除成功')
    emit('updated')
    loadRequests()
  } catch (error: any) {
    Message.error(error?.error || '删除接口失败')
  }
}

const showBatchExecutionMessage = (label: string, summary: ApiExecutionBatchResult) => {
  const text = `${label}完成：共 ${summary.total_count} 条，成功 ${summary.success_count} 条，断言失败 ${summary.failed_count} 条，异常 ${summary.error_count} 条。`
  if (summary.failed_count || summary.error_count) {
    Message.warning(text)
    return
  }
  Message.success(text)
}

const executeRequestBatch = async (payload: {
  scope: 'selected' | 'collection' | 'project'
  ids?: number[]
  collection_id?: number
  project_id?: number
  environment_id?: number
}, label: string) => {
  try {
    const res = await apiRequestApi.executeBatch(payload)
    const summary = res.data.data
    showBatchExecutionMessage(label, summary)
    emit('executed')
  } catch (error: any) {
    console.error('[RequestList] 批量执行接口失败:', error)
    Message.error(error?.error || '批量执行接口失败')
  }
}

const showCaseGenerationMessage = (summary: ApiTestCaseGenerationResult, mode: CaseGenerationMode) => {
  const modeLabelMap: Record<CaseGenerationMode, string> = {
    generate: '生成',
    append: '追加生成',
    regenerate: '重新生成',
  }
  const text = `${modeLabelMap[mode]}完成：处理 ${summary.processed_requests}/${summary.total_requests} 个接口，新增 ${summary.created_testcase_count} 条测试用例。`
  if (summary.skipped_requests) {
    Message.warning(`${text} 跳过 ${summary.skipped_requests} 个已有用例的接口。`)
    return
  }
  Message.success(text)
}

const generateCasesByScope = async (
  payload: {
    scope: 'selected' | 'collection' | 'project'
    ids?: number[]
    collection_id?: number
    project_id?: number
    mode: CaseGenerationMode
    count_per_request?: number
  },
  targetRequestIds: number[] = []
) => {
  try {
    const res = await apiRequestApi.generateTestCases(payload)
    const summary = res.data.data
    showCaseGenerationMessage(summary, payload.mode)
    await loadRequests()
    const requestIdsToRefresh = targetRequestIds.length
      ? targetRequestIds
      : summary.items.map(item => item.request_id)
    for (const requestId of requestIdsToRefresh) {
      if (expandedRequestKeys.value.includes(requestId)) {
        await loadRequestTestCases(requestId, true)
      }
    }
    emit('updated')
  } catch (error: any) {
    console.error('[RequestList] AI 生成测试用例失败:', error)
    Message.error(error?.error || 'AI 生成测试用例失败')
  }
}

const executeRequest = async (record: ApiRequest) => {
  try {
    const res = await apiRequestApi.execute(record.id, selectedEnvironmentId.value)
    currentResult.value = res.data.data
    resultVisible.value = true
    if (currentResult.value.passed) {
      Message.success('接口执行通过')
    } else if (currentResult.value.status === 'error') {
      Message.error(currentResult.value.error_message || '接口执行失败，请检查环境变量或请求配置')
    } else {
      Message.warning('接口执行未通过，请检查断言或响应内容')
    }
    emit('executed')
  } catch (error: any) {
    console.error('[RequestList] 执行接口失败:', error)
    Message.error(error?.error || '执行接口失败')
  }
}

const generateCasesForRequest = async (record: ApiRequest, mode: CaseGenerationMode) => {
  await generateCasesByScope(
    {
      scope: 'selected',
      ids: [record.id],
      mode,
      count_per_request: 3,
    },
    [record.id]
  )
}

const handleSingleCaseGenerationAction = async (record: ApiRequest, value: string | number | boolean) => {
  const mode = String(value) as CaseGenerationMode
  if (!['generate', 'append', 'regenerate'].includes(mode)) return
  await generateCasesForRequest(record, mode)
}

const handleSelectedCaseGenerationAction = async (value: string | number | boolean) => {
  const mode = String(value) as CaseGenerationMode
  if (!['generate', 'append', 'regenerate'].includes(mode)) return
  if (!selectedRequestIds.value.length) {
    Message.warning('请先选择要生成测试用例的接口')
    return
  }
  await generateCasesByScope(
    {
      scope: 'selected',
      ids: selectedRequestIds.value,
      mode,
      count_per_request: 3,
    },
    selectedRequestIds.value
  )
}

const executeSelectedRequests = async () => {
  if (!selectedRequestIds.value.length) {
    Message.warning('请先选择要执行的接口')
    return
  }
  await executeRequestBatch(
    {
      scope: 'selected',
      ids: selectedRequestIds.value,
      environment_id: selectedEnvironmentId.value,
    },
    '选中接口执行'
  )
}

const executeCollectionRequests = async () => {
  if (!props.selectedCollectionId) {
    Message.warning('请先选择接口集合')
    return
  }
  await executeRequestBatch(
    {
      scope: 'collection',
      collection_id: props.selectedCollectionId,
      environment_id: selectedEnvironmentId.value,
    },
    '当前集合执行'
  )
}

const executeProjectRequests = async () => {
  if (!projectId.value) {
    Message.warning('请先选择项目')
    return
  }
  await executeRequestBatch(
    {
      scope: 'project',
      project_id: projectId.value,
      environment_id: selectedEnvironmentId.value,
    },
    '项目接口执行'
  )
}

watch(
  () => projectId.value,
  value => {
    syncProject(value)
    selectedRequestIds.value = []
    loadEnvironments()
    loadRequests()
  },
  { immediate: true }
)

watch(
  () => props.selectedCollectionId,
  () => {
    selectedRequestIds.value = []
    expandedRequestKeys.value = []
    requestTestCaseMap.value = {}
    loadRequests()
  },
  { immediate: true }
)

onUnmounted(() => {
  clearImportProgressTimer()
  unregisterImportFinishedHandler()
})

defineExpose({
  refresh: loadRequests,
})
</script>

<style scoped>
.request-list {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.api-page-header {
  display: grid;
  grid-template-columns: minmax(260px, 1.1fr) minmax(520px, 1.6fr);
  align-items: end;
  justify-content: space-between;
  gap: 22px;
  padding: 24px 26px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.9));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.06);
}

.page-summary,
.page-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.page-summary {
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.page-summary__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #2563eb;
}

.page-summary__title {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.08;
  color: #0f172a;
}

.page-summary__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.page-summary__meta span {
  position: relative;
  padding-right: 12px;
}

.page-summary__meta span:not(:last-child)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.9);
  transform: translateY(-50%);
}

.page-toolbar {
  justify-content: flex-end;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-group--filter {
  flex: 0 1 auto;
}

.toolbar-group--actions {
  justify-content: flex-end;
}

.toolbar-select {
  width: 240px;
}

.toolbar-search {
  width: 320px;
  max-width: 100%;
}

.page-toolbar :deep(.arco-input-wrapper),
.toolbar-group :deep(.arco-select-view),
.toolbar-group :deep(.arco-btn) {
  min-height: 42px;
}

.toolbar-group :deep(.arco-btn) {
  padding-inline: 16px;
  border-radius: 14px;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.content-section :deep(.arco-table-container) {
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
}

.content-section :deep(.arco-table-th) {
  padding-top: 16px;
  padding-bottom: 16px;
}

.content-section :deep(.arco-table-td) {
  padding-top: 15px;
  padding-bottom: 15px;
}

.request-case-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px 26px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.96));
}

.request-case-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.request-case-panel__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.request-case-panel__subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.request-case-panel__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.request-case-panel__loading {
  padding: 18px 0;
  display: flex;
  justify-content: center;
}

.request-case-list {
  display: grid;
  gap: 12px;
}

.request-case-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
}

.request-case-card__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.request-case-card__name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.request-case-card__desc {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-word;
}

.request-case-card__meta {
  flex: 0 0 auto;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .api-page-header {
    grid-template-columns: 1fr;
  }

  .page-toolbar {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .api-page-header {
    align-items: stretch;
    padding: 20px;
  }

  .page-summary,
  .page-toolbar,
  .toolbar-group,
  .toolbar-search,
  .toolbar-select {
    width: 100%;
  }

  .page-summary__title {
    font-size: 24px;
  }

  .toolbar-select {
    min-width: 0;
  }

  .request-case-card {
    flex-direction: column;
  }

  .request-case-card__meta {
    white-space: normal;
  }
}

.create-mode-switch {
  margin-bottom: 16px;
}

.import-prefill-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(59, 130, 246, 0.14);
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(20, 184, 166, 0.08)),
    rgba(255, 255, 255, 0.92);
}

.prefill-copy {
  min-width: 0;
}

.prefill-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.prefill-description {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.prefill-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.document-import-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-alert {
  margin-bottom: 0;
}

.import-progress-panel {
  gap: 18px;
}

.import-progress-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-progress-percent {
  min-width: 52px;
  text-align: right;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.import-progress-hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(15, 118, 110, 0.12)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 252, 0.92));
  border: 1px solid rgba(59, 130, 246, 0.14);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.import-progress-badge {
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.import-progress-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.import-progress-description {
  font-size: 14px;
  line-height: 1.7;
  color: #475569;
}

.import-progress-step-list {
  display: grid;
  gap: 12px;
}

.import-progress-step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.86);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.import-progress-step.is-active {
  border-color: rgba(59, 130, 246, 0.26);
  box-shadow: 0 16px 34px rgba(59, 130, 246, 0.12);
  transform: translateY(-1px);
}

.import-progress-step.is-finished {
  border-color: rgba(20, 184, 166, 0.22);
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.08), rgba(255, 255, 255, 0.96)),
    rgba(255, 255, 255, 0.92);
}

.import-progress-step.is-error {
  border-color: rgba(239, 68, 68, 0.24);
  background:
    linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(255, 255, 255, 0.96)),
    rgba(255, 255, 255, 0.92);
}

.import-progress-step-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.import-progress-step.is-active .import-progress-step-marker {
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  color: #fff;
}

.import-progress-step.is-finished .import-progress-step-marker {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
}

.import-progress-step.is-error .import-progress-step-marker {
  background: linear-gradient(135deg, #dc2626, #f97316);
  color: #fff;
}

.import-progress-step-copy {
  min-width: 0;
}

.import-progress-step-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.import-progress-step-description {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.import-progress-alert {
  margin-bottom: 0;
}

.import-progress-actions {
  display: flex;
  justify-content: flex-end;
}

.import-hero-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(13, 148, 136, 0.14), rgba(15, 23, 42, 0.06)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 252, 0.92));
  border: 1px solid rgba(13, 148, 136, 0.16);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.08);
}

.import-hero-badge {
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(13, 148, 136, 0.12);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.import-hero-title {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.import-hero-description {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
}

.import-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.document-dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 24px;
  border-radius: 26px;
  border: 1.5px dashed rgba(15, 118, 110, 0.26);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(244, 250, 249, 0.88));
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.document-dropzone:hover,
.document-dropzone.is-dragging {
  transform: translateY(-1px);
  border-color: rgba(13, 148, 136, 0.5);
  box-shadow: 0 18px 40px rgba(15, 118, 110, 0.12);
}

.document-dropzone.has-file {
  border-style: solid;
  border-color: rgba(13, 148, 136, 0.24);
}

.file-input-hidden {
  display: none;
}

.dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 68px;
  height: 68px;
  border-radius: 20px;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 18px 36px rgba(15, 118, 110, 0.2);
}

.dropzone-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.dropzone-subtitle {
  max-width: 640px;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.selected-file-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  max-width: 680px;
  margin-top: 8px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.selected-file-main {
  min-width: 0;
}

.selected-file-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-all;
}

.selected-file-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.import-option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-option-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.import-option-card-primary {
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(59, 130, 246, 0.08)),
    rgba(255, 255, 255, 0.92);
}

.option-copy {
  min-width: 0;
}

.option-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.option-description {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.empty-tip-card {
  padding: 44px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.result-drawer,
.import-result-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-result-alert {
  margin-bottom: 4px;
}

.import-task-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.import-task-alert {
  margin-bottom: 0;
}

.import-task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.import-task-card {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.import-task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.import-task-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.import-task-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.import-task-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.import-task-progress-text {
  min-width: 44px;
  text-align: right;
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.import-task-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 14px;
}

.import-task-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.import-task-step-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.5);
  flex-shrink: 0;
}

.import-task-step.is-finished {
  color: #0f766e;
}

.import-task-step.is-finished .import-task-step-dot {
  background: #14b8a6;
}

.import-task-step.is-active {
  color: #2563eb;
}

.import-task-step.is-active .import-task-step-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.14);
}

.import-task-step.is-failed {
  color: #dc2626;
}

.import-task-step.is-failed .import-task-step-dot {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.12);
}

.import-task-error {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(254, 242, 242, 0.96);
  border: 1px solid rgba(248, 113, 113, 0.22);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-word;
}

.import-task-float {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 1200;
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 280px;
  padding: 14px 16px;
  border: 1px solid rgba(59, 130, 246, 0.16);
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(20, 184, 166, 0.1)),
    rgba(255, 255, 255, 0.94);
  box-shadow: 0 22px 40px rgba(15, 23, 42, 0.14);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.import-task-float:hover {
  transform: translateY(-2px);
  box-shadow: 0 26px 44px rgba(15, 23, 42, 0.18);
}

.import-task-float-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.import-task-float-copy {
  min-width: 0;
  flex: 1;
}

.import-task-float-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.import-task-float-desc {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.import-task-float-progress {
  width: 96px;
  flex-shrink: 0;
}

.import-tags {
  margin-bottom: 12px;
}

.json-block {
  margin: 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.95);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-modal :deep(.arco-modal) {
  max-width: min(1120px, calc(100vw - 32px));
}

.detail-modal :deep(.arco-modal-body) {
  padding: 20px 24px 24px;
}

@media (max-width: 900px) {
  .import-option-grid {
    grid-template-columns: 1fr;
  }

  .import-prefill-banner,
  .selected-file-card,
  .import-option-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .import-task-float {
    right: 16px;
    bottom: 16px;
    left: 16px;
    min-width: 0;
  }
}
</style>

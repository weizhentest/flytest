<template>
<a-card class="config-panel">
          <template #title>步骤配置</template>
          <div v-if="!selectedSceneStep" class="config-empty">请选择一个步骤进行配置</div>

          <div v-else-if="selectedCustomParentSummary" class="config-summary">
            <a-form layout="vertical">
              <a-form-item label="组件名称">
                <a-input v-model="selectedParentStep!.name" />
              </a-form-item>
              <a-form-item label="组件类型">
                <a-input :model-value="selectedParentStep!.component_type || selectedParentStep!.type || 'custom'" disabled />
              </a-form-item>
              <a-form-item label="子步骤数量">
                <a-input :model-value="String(countChildSteps(selectedParentStep))" disabled />
              </a-form-item>
            </a-form>
            <a-alert>
              当前选中的是自定义组件父步骤，请展开后编辑子步骤；这里可以直接修改组件在当前场景中的显示名称。
            </a-alert>
          </div>

          <div v-else class="config-form">
            <a-alert v-if="selectedSceneStep && isFlowContainerStep(selectedSceneStep)" class="config-flow-alert">
              流程容器步骤的 JSON 同时支持维护 `steps`、`else_steps`、`catch_steps`、`finally_steps`。
            </a-alert>

            <a-form layout="vertical">
              <a-form-item label="步骤名称">
                <a-input v-model="selectedSceneStep.name" placeholder="请输入步骤名称" />
              </a-form-item>
              <a-form-item label="步骤类型">
                <a-input :model-value="resolveStepMeta(selectedSceneStep)" disabled />
              </a-form-item>
              <div class="config-toolbar">
                <a-button
                  type="outline"
                  size="small"
                  :disabled="!selectedSceneStep || !!selectedCustomParentSummary"
                  :loading="aiStepSuggesting"
                  @click="emit('open-ai-step-dialog')"
                >
                  AI 补全当前步骤
                </a-button>
              </div>

              <a-alert
                v-if="
                  usesBasicSelectorQuickConfig(selectedStepActionType) ||
                  usesSwipeToQuickConfig(selectedStepActionType) ||
                  usesSwipeQuickConfig(selectedStepActionType) ||
                  usesDragQuickConfig(selectedStepActionType) ||
                  usesVariableMutationQuickConfig(selectedStepActionType) ||
                  usesExtractOutputQuickConfig(selectedStepActionType) ||
                  usesApiRequestQuickConfig(selectedStepActionType) ||
                  usesDeviceActionQuickConfig(selectedStepActionType) ||
                  usesImageBranchQuickConfig(selectedStepActionType) ||
                  usesAssertQuickConfig(selectedStepActionType) ||
                  usesForeachAssertQuickConfig(selectedStepActionType)
                "
                class="config-helper-alert"
              >
                常用图片、OCR 和断言参数可以直接在下方快捷配置；更复杂的字段仍然可以继续在 JSON 中补充。
              </a-alert>

              <div v-if="usesBasicSelectorQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">基础动作配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="选择器类型">
                      <a-select
                        :model-value="selectedPrimarySelectorType"
                        @change="value => updateSelectedStepConfig('selector_type', value || 'element')"
                      >
                        <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="选择器内容">
                      <a-input
                        :model-value="readSelectedConfigString('selector')"
                        placeholder="元素名称、文本、XPath、图片路径或区域坐标"
                        @input="value => updateSelectedStepConfig('selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row v-if="selectedPrimarySelectorType === 'image'" :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="图片阈值">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('threshold', 0.7)"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('threshold', value ?? 0.7)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="全屏找图">
                      <a-switch
                        :model-value="readSelectedConfigBoolean('search_full_screen', true)"
                        @change="value => updateSelectedStepConfig('search_full_screen', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col v-if="selectedStepActionType === 'text'" :span="24">
                    <a-form-item label="输入内容">
                      <a-input
                        :model-value="readSelectedConfigString('text')"
                        placeholder="输入文本，支持变量表达式"
                        @input="value => updateSelectedStepConfig('text', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col v-if="selectedStepActionType === 'wait' || selectedStepActionType === 'assert_exists'" :span="8">
                    <a-form-item label="等待超时（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('timeout', 10)"
                        :min="0"
                        :max="300"
                        :step="0.5"
                        @change="value => updateSelectedStepConfig('timeout', value ?? 10)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col v-if="selectedStepActionType === 'double_click'" :span="8">
                    <a-form-item label="双击间隔（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('interval', 0.12)"
                        :min="0"
                        :max="5"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('interval', value ?? 0.12)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col v-if="selectedStepActionType === 'long_press'" :span="8">
                    <a-form-item label="长按时长（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('duration', 1)"
                        :min="0.1"
                        :max="20"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('duration', value ?? 1)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesSwipeToQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">滑动查找配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="目标选择器类型">
                      <a-select
                        :model-value="selectedTargetSelectorType"
                        @change="value => updateSelectedStepConfig('target_selector_type', value || 'text')"
                      >
                        <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="目标选择器">
                      <a-input
                        :model-value="readSelectedConfigString('target_selector')"
                        placeholder="目标元素、文本或图片路径"
                        @input="value => updateSelectedStepConfig('target_selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="6">
                    <a-form-item label="滑动方向">
                      <a-select
                        :model-value="readSelectedConfigString('direction', 'up')"
                        @change="value => updateSelectedStepConfig('direction', value || 'up')"
                      >
                        <a-option v-for="item in swipeDirectionOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="6">
                    <a-form-item label="最大滑动次数">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('max_swipes', 5)"
                        :min="1"
                        :max="100"
                        @change="value => updateSelectedStepConfig('max_swipes', value ?? 5)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="6">
                    <a-form-item label="每次间隔（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('interval', 0.5)"
                        :min="0"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="6">
                    <a-form-item label="滑动时长（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('duration', 0.4)"
                        :min="0.1"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('duration', value ?? 0.4)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="起点坐标（可选）">
                      <a-input
                        :model-value="readSelectedConfigString('start')"
                        placeholder="例如：540,1600"
                        @input="value => updateSelectedStepConfig('start', value || undefined)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="终点坐标（可选）">
                      <a-input
                        :model-value="readSelectedConfigString('end')"
                        placeholder="例如：540,600"
                        @input="value => updateSelectedStepConfig('end', value || undefined)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row v-if="selectedTargetSelectorType === 'image'" :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="目标阈值">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('target_threshold', 0.7)"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('target_threshold', value ?? 0.7)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="目标全屏找图">
                      <a-switch
                        :model-value="readSelectedConfigBoolean('target_search_full_screen', true)"
                        @change="value => updateSelectedStepConfig('target_search_full_screen', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesSwipeQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">滑动配置</div>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="起点坐标">
                      <a-input
                        :model-value="readSelectedConfigString('start')"
                        placeholder="例如：540,1600"
                        @input="value => updateSelectedStepConfig('start', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="终点坐标">
                      <a-input
                        :model-value="readSelectedConfigString('end')"
                        placeholder="例如：540,600"
                        @input="value => updateSelectedStepConfig('end', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="滑动时长（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('duration', 0.4)"
                        :min="0.1"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('duration', value ?? 0.4)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesDragQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">拖拽配置</div>
                <a-alert class="quick-config-subtle-alert">
                  当前快捷配置按坐标拖拽；如果需要按元素、图片或 OCR 区域定位拖拽起终点，可继续在下方 JSON 中补充
                  `start_selector_type`、`start_selector`、`end_selector_type`、`end_selector` 等高级字段。
                </a-alert>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="起点坐标">
                      <a-input
                        :model-value="readSelectedConfigString('start')"
                        placeholder="例如：200,800"
                        @input="value => updateSelectedStepConfig('start', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="终点坐标">
                      <a-input
                        :model-value="readSelectedConfigString('end')"
                        placeholder="例如：800,800"
                        @input="value => updateSelectedStepConfig('end', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="拖拽时长（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('duration', 0.6)"
                        :min="0.1"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('duration', value ?? 0.6)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesVariableMutationQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">
                  {{ selectedStepActionType === 'set_variable' ? '设置变量配置' : '删除变量配置' }}
                </div>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="变量名">
                      <a-input
                        :model-value="readSelectedConfigString('variable_name')"
                        placeholder="例如：token"
                        @input="value => updateSelectedStepConfig('variable_name', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="作用域">
                      <a-select
                        :model-value="selectedVariableScope"
                        @change="value => updateSelectedStepConfig('scope', value || 'local')"
                      >
                        <a-option v-for="item in variableScopeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-form-item v-if="selectedStepActionType === 'set_variable'" label="变量值">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('value'))"
                    :auto-size="{ minRows: 4, maxRows: 8 }"
                    placeholder="支持普通文本、数字、布尔值，或 JSON 对象/数组"
                    @change="value => handleLooseConfigTextChange('value', String(value || ''))"
                  />
                </a-form-item>
              </div>

              <div v-if="usesExtractOutputQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">提取输出配置</div>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="来源变量">
                      <a-input
                        :model-value="readSelectedConfigString('source')"
                        placeholder="例如：response 或 response.body"
                        @input="value => updateSelectedStepConfig('source', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="提取路径">
                      <a-input
                        :model-value="readSelectedConfigString('path')"
                        placeholder="例如：body.data.token"
                        @input="value => updateSelectedStepConfig('path', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="保存变量名">
                      <a-input
                        :model-value="readSelectedConfigString('variable_name')"
                        placeholder="例如：token"
                        @input="value => updateSelectedStepConfig('variable_name', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="保存作用域">
                      <a-select
                        :model-value="selectedVariableScope"
                        @change="value => updateSelectedStepConfig('scope', value || 'local')"
                      >
                        <a-option v-for="item in variableScopeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesApiRequestQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">接口请求配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="请求方法">
                      <a-select
                        :model-value="readSelectedConfigString('method', 'GET')"
                        @change="value => updateSelectedStepConfig('method', value || 'GET')"
                      >
                        <a-option v-for="item in httpMethodOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="请求地址">
                      <a-input
                        :model-value="readSelectedConfigString('url')"
                        placeholder="例如：https://example.com/api/health"
                        @input="value => updateSelectedStepConfig('url', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="超时（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('timeout', 10)"
                        :min="0.1"
                        :max="300"
                        :step="0.5"
                        @change="value => updateSelectedStepConfig('timeout', value ?? 10)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="响应类型">
                      <a-select
                        :model-value="readSelectedConfigString('response_type', 'auto')"
                        @change="value => updateSelectedStepConfig('response_type', value || 'auto')"
                      >
                        <a-option v-for="item in responseTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="期望状态码">
                      <a-input
                        :model-value="readSelectedConfigString('expected_status')"
                        placeholder="可留空，例如：200"
                        @input="value => handleLooseConfigTextChange('expected_status', String(value || ''))"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="完整响应保存名">
                      <a-input
                        :model-value="readSelectedConfigString('save_as')"
                        placeholder="例如：response"
                        @input="value => updateSelectedStepConfig('save_as', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="保存作用域">
                      <a-select
                        :model-value="selectedVariableScope"
                        @change="value => updateSelectedStepConfig('scope', value || 'local')"
                      >
                        <a-option v-for="item in variableScopeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-form-item label="请求头 JSON">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('headers', {}))"
                    :auto-size="{ minRows: 4, maxRows: 8 }"
                    placeholder='例如：{"Authorization":"Bearer {{token}}"}'
                    @change="value => handleJsonConfigTextChange('headers', String(value || ''), {})"
                  />
                </a-form-item>
                <a-form-item label="查询参数 JSON">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('params', {}))"
                    :auto-size="{ minRows: 4, maxRows: 8 }"
                    placeholder='例如：{"page":1,"size":20}'
                    @change="value => handleJsonConfigTextChange('params', String(value || ''), {})"
                  />
                </a-form-item>
                <a-form-item label="JSON 请求体">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('json'))"
                    :auto-size="{ minRows: 4, maxRows: 10 }"
                    placeholder='留空则不发送 JSON 请求体，例如：{"username":"admin"}'
                    @change="value => handleJsonConfigTextChange('json', String(value || ''), undefined)"
                  />
                </a-form-item>
                <a-form-item label="表单/原始请求体">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('data'))"
                    :auto-size="{ minRows: 3, maxRows: 8 }"
                    placeholder="可填写文本、数字，或 JSON 对象"
                    @change="value => handleLooseConfigTextChange('data', String(value || ''))"
                  />
                </a-form-item>
                <a-form-item label="字段提取 JSON 数组">
                  <a-textarea
                    :model-value="formatQuickConfigValue(readSelectedConfigValue('extracts', []))"
                    :auto-size="{ minRows: 4, maxRows: 10 }"
                    placeholder='例如：[{"path":"body.data.token","name":"token","scope":"local"}]'
                    @change="value => handleJsonConfigTextChange('extracts', String(value || ''), [])"
                  />
                </a-form-item>
              </div>

              <div v-if="usesDeviceActionQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">设备动作配置</div>
                <a-form-item v-if="selectedStepActionType === 'snapshot'" label="截图标签">
                  <a-input
                    :model-value="readSelectedConfigString('label')"
                    placeholder="可选，不填时默认使用步骤名称"
                    @input="value => updateSelectedStepConfig('label', value || undefined)"
                  />
                </a-form-item>

                <template v-if="selectedStepActionType === 'launch_app' || selectedStepActionType === 'stop_app'">
                  <a-row :gutter="12">
                    <a-col :span="selectedStepActionType === 'launch_app' ? 12 : 24">
                      <a-form-item label="应用包名">
                        <a-input
                          :model-value="readSelectedConfigString('package_name')"
                          placeholder="例如：com.example.demo"
                          @input="value => updateSelectedStepConfig('package_name', value)"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col v-if="selectedStepActionType === 'launch_app'" :span="12">
                      <a-form-item label="启动 Activity">
                        <a-input
                          :model-value="readSelectedConfigString('activity_name')"
                          placeholder="可选，例如：.MainActivity"
                          @input="value => updateSelectedStepConfig('activity_name', value || undefined)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </template>

                <a-form-item v-if="selectedStepActionType === 'keyevent'" label="Android Keyevent">
                  <a-input
                    :model-value="readSelectedConfigString('keycode', 'KEYCODE_ENTER')"
                    placeholder="例如：KEYCODE_BACK / KEYCODE_HOME / KEYCODE_ENTER"
                    @input="value => updateSelectedStepConfig('keycode', value || 'KEYCODE_ENTER')"
                  />
                </a-form-item>
              </div>

              <div v-if="usesAssertQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">断言快捷配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="断言类型">
                      <a-select :model-value="selectedAssertType" @change="value => handleAssertTypeChange(String(value || 'condition'))">
                        <a-option v-for="item in assertTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="超时重试（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('timeout', 0)"
                        :min="0"
                        :max="300"
                        :step="0.5"
                        @change="value => updateSelectedStepConfig('timeout', value ?? 0)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="重试间隔（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('retry_interval', 0.5)"
                        :min="0.1"
                        :max="30"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('retry_interval', value ?? 0.5)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <template v-if="selectedAssertQuickMode === 'ocr'">
                  <a-row :gutter="12">
                    <a-col :span="8">
                      <a-form-item label="OCR 区域类型">
                        <a-input :model-value="'region'" disabled />
                      </a-form-item>
                    </a-col>
                    <a-col :span="16">
                      <a-form-item label="OCR 区域">
                        <a-input
                          :model-value="readSelectedConfigString('selector')"
                          placeholder="格式：x1,y1,x2,y2"
                          @input="value => updateSelectedStepConfig('selector', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-row v-if="selectedAssertType === 'text' || selectedAssertType === 'regex'" :gutter="12">
                    <a-col v-if="selectedAssertType === 'text'" :span="8">
                      <a-form-item label="匹配方式">
                        <a-select
                          :model-value="readSelectedConfigString('match_mode', 'contains')"
                          @change="value => updateSelectedStepConfig('match_mode', value || 'contains')"
                        >
                          <a-option v-for="item in matchModeOptions" :key="item.value" :value="item.value">
                            {{ item.label }}
                          </a-option>
                        </a-select>
                      </a-form-item>
                    </a-col>
                    <a-col :span="selectedAssertType === 'text' ? 16 : 24">
                      <a-form-item :label="selectedAssertType === 'regex' ? '正则表达式' : '期望文本'">
                        <a-input
                          :model-value="readSelectedConfigString('expected')"
                          :placeholder="selectedAssertType === 'regex' ? '请输入 OCR 正则表达式' : '请输入期望文本'"
                          @input="value => updateSelectedStepConfig('expected', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-row v-else-if="selectedAssertType === 'number'" :gutter="12">
                    <a-col :span="12">
                      <a-form-item label="期望数字">
                        <a-input
                          :model-value="readSelectedConfigString('expected')"
                          placeholder="例如：100 或 3,000"
                          @input="value => updateSelectedStepConfig('expected', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-row v-else-if="selectedAssertType === 'range'" :gutter="12">
                    <a-col :span="12">
                      <a-form-item label="最小值">
                        <a-input
                          :model-value="readSelectedConfigString('min')"
                          placeholder="可留空"
                          @input="value => updateSelectedStepConfig('min', value)"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="最大值">
                        <a-input
                          :model-value="readSelectedConfigString('max')"
                          placeholder="可留空"
                          @input="value => updateSelectedStepConfig('max', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </template>

                <template v-else-if="selectedAssertQuickMode === 'image'">
                  <a-row :gutter="12">
                    <a-col :span="16">
                      <a-form-item label="期望图片路径">
                        <a-input
                          :model-value="readSelectedConfigString('expected')"
                          placeholder="例如：common/login-button.png"
                          @input="value => updateSelectedStepConfig('expected', value)"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="图片阈值">
                        <a-input-number
                          :model-value="readSelectedConfigNumber('threshold', 0.7)"
                          :min="0.1"
                          :max="1"
                          :step="0.05"
                          @change="value => updateSelectedStepConfig('threshold', value ?? 0.7)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-row :gutter="12">
                    <a-col :span="8">
                      <a-form-item label="全屏找图">
                        <a-switch
                          :model-value="readSelectedConfigBoolean('search_full_screen', true)"
                          @change="value => updateSelectedStepConfig('search_full_screen', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </template>

                <template v-else-if="selectedAssertQuickMode === 'exists'">
                  <a-row :gutter="12">
                    <a-col :span="8">
                      <a-form-item label="选择器类型">
                        <a-select
                          :model-value="selectedPrimarySelectorType"
                          @change="value => updateSelectedStepConfig('selector_type', value || 'element')"
                        >
                          <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                            {{ item.label }}
                          </a-option>
                        </a-select>
                      </a-form-item>
                    </a-col>
                    <a-col :span="16">
                      <a-form-item label="选择器内容">
                        <a-input
                          :model-value="readSelectedConfigString('selector')"
                          placeholder="元素名、文本或图片路径"
                          @input="value => updateSelectedStepConfig('selector', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </template>

                <template v-else>
                  <a-row :gutter="12">
                    <a-col :span="10">
                      <a-form-item label="断言来源">
                        <a-input
                          :model-value="readSelectedConfigString('source')"
                          placeholder="例如：response.body.code"
                          @input="value => updateSelectedStepConfig('source', value)"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col :span="6">
                      <a-form-item label="操作符">
                        <a-select
                          :model-value="readSelectedConfigString('operator', '==')"
                          @change="value => updateSelectedStepConfig('operator', value || '==')"
                        >
                          <a-option v-for="item in assertOperatorOptions" :key="item.value" :value="item.value">
                            {{ item.label }}
                          </a-option>
                        </a-select>
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="期望值">
                        <a-input
                          :model-value="readSelectedConfigString('expected')"
                          placeholder="期望值或变量表达式"
                          @input="value => updateSelectedStepConfig('expected', value)"
                        />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </template>
              </div>

              <div v-if="usesImageBranchQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">图片分支点击配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="主选择器类型">
                      <a-select
                        :model-value="selectedPrimarySelectorType"
                        @change="value => updateSelectedStepConfig('selector_type', value || 'image')"
                      >
                        <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="主选择器">
                      <a-input
                        :model-value="readSelectedConfigString('selector')"
                        placeholder="主定位元素或图片路径"
                        @input="value => updateSelectedStepConfig('selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row v-if="selectedPrimarySelectorType === 'image'" :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="主阈值">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('threshold', 0.7)"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('threshold', value ?? 0.7)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="主全屏找图">
                      <a-switch
                        :model-value="readSelectedConfigBoolean('search_full_screen', true)"
                        @change="value => updateSelectedStepConfig('search_full_screen', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="备用选择器类型">
                      <a-select
                        :model-value="selectedFallbackSelectorType"
                        @change="value => updateSelectedStepConfig('fallback_selector_type', value || 'element')"
                      >
                        <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="备用选择器">
                      <a-input
                        :model-value="readSelectedConfigString('fallback_selector')"
                        placeholder="备用元素或图片路径"
                        @input="value => updateSelectedStepConfig('fallback_selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col v-if="selectedFallbackSelectorType === 'image'" :span="8">
                    <a-form-item label="备用阈值">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('fallback_threshold', 0.7)"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('fallback_threshold', value ?? 0.7)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col v-if="selectedFallbackSelectorType === 'image'" :span="8">
                    <a-form-item label="备用全屏找图">
                      <a-switch
                        :model-value="readSelectedConfigBoolean('fallback_search_full_screen', true)"
                        @change="value => updateSelectedStepConfig('fallback_search_full_screen', value)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col v-if="selectedStepActionType === 'image_exists_click_chain'" :span="8">
                    <a-form-item label="主备间隔（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('interval', 0.5)"
                        :min="0"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <div v-if="usesForeachAssertQuickConfig(selectedStepActionType)" class="quick-config-panel">
                <div class="quick-config-title">循环点击断言配置</div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="点击选择器类型">
                      <a-select
                        :model-value="selectedClickSelectorType"
                        @change="value => updateSelectedStepConfig('click_selector_type', value || 'element')"
                      >
                        <a-option v-for="item in selectorTypeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="点击选择器">
                      <a-input
                        :model-value="readSelectedConfigString('click_selector')"
                        placeholder="点击按钮元素、文本或图片路径"
                        @input="value => updateSelectedStepConfig('click_selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row v-if="selectedClickSelectorType === 'image'" :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="点击阈值">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('click_threshold', 0.7)"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        @change="value => updateSelectedStepConfig('click_threshold', value ?? 0.7)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="点击全屏找图">
                      <a-switch
                        :model-value="readSelectedConfigBoolean('click_search_full_screen', true)"
                        @change="value => updateSelectedStepConfig('click_search_full_screen', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="断言类型">
                      <a-select
                        :model-value="readSelectedConfigString('assert_type', 'text')"
                        @change="value => updateSelectedStepConfig('assert_type', value || 'text')"
                      >
                        <a-option value="text">OCR 文本</a-option>
                        <a-option value="number">OCR 数字</a-option>
                        <a-option value="regex">OCR 正则</a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="16">
                    <a-form-item label="OCR 区域">
                      <a-input
                        :model-value="readSelectedConfigString('ocr_selector')"
                        placeholder="格式：x1,y1,x2,y2"
                        @input="value => updateSelectedStepConfig('ocr_selector', value)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="匹配方式">
                      <a-select
                        :model-value="readSelectedConfigString('match_mode', 'contains')"
                        @change="value => updateSelectedStepConfig('match_mode', value || 'contains')"
                      >
                        <a-option v-for="item in matchModeOptions" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </a-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="最大循环次数">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('max_loops', 3)"
                        :min="1"
                        :max="100"
                        @change="value => updateSelectedStepConfig('max_loops', value ?? 3)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="最少命中次数">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('min_match', 1)"
                        :min="0"
                        :max="100"
                        @change="value => updateSelectedStepConfig('min_match', value ?? 1)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="点击后等待（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('interval', 0.5)"
                        :min="0"
                        :max="10"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('interval', value ?? 0.5)"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="单次 OCR 超时（秒）">
                      <a-input-number
                        :model-value="readSelectedConfigNumber('timeout', 1.5)"
                        :min="0"
                        :max="30"
                        :step="0.1"
                        @change="value => updateSelectedStepConfig('timeout', value ?? 1.5)"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-form-item label="期望列表">
                  <a-textarea
                    :model-value="expectedListText"
                    :auto-size="{ minRows: 4, maxRows: 8 }"
                    placeholder="每行一个期望值，也可以直接填写 JSON 数组"
                    @input="value => handleExpectedListTextChange(String(value || ''))"
                  />
                </a-form-item>
              </div>
              <a-form-item label="配置字段">
                <div class="config-keys">
                  <a-tag v-for="item in configKeys" :key="item" size="small">{{ item }}</a-tag>
                  <span v-if="!configKeys.length" class="config-empty-text">当前步骤还没有配置字段</span>
                </div>
              </a-form-item>
              <a-form-item label="配置 JSON">
                <a-textarea
                  v-model="stepConfigTextModel"
                  :auto-size="{ minRows: 10, maxRows: 18 }"
                  placeholder="请输入步骤配置 JSON"
                />
              </a-form-item>
            </a-form>

            <div class="config-actions">
              <a-button @click="emit('reset-selected-step-config')">恢复默认配置</a-button>
              <a-button type="primary" @click="emit('apply-step-config')">应用到当前步骤</a-button>
            </div>
          </div>
        </a-card>
</template>


<script setup lang="ts">
import type { AppSceneStep } from '../../types'

interface QuickOption {
  label: string
  value: string
}

interface Props {
  selectedSceneStep: AppSceneStep | null
  selectedCustomParentSummary: boolean
  selectedParentStep: AppSceneStep | null
  countChildSteps: (step?: Partial<AppSceneStep> | null) => number
  isFlowContainerStep: (step?: Partial<AppSceneStep> | null) => boolean
  resolveStepMeta: (step?: Partial<AppSceneStep>) => string
  aiStepSuggesting: boolean
  selectedStepActionType: string
  usesBasicSelectorQuickConfig: (action?: string | null) => boolean
  usesSwipeToQuickConfig: (action?: string | null) => boolean
  usesSwipeQuickConfig: (action?: string | null) => boolean
  usesDragQuickConfig: (action?: string | null) => boolean
  usesVariableMutationQuickConfig: (action?: string | null) => boolean
  usesExtractOutputQuickConfig: (action?: string | null) => boolean
  usesApiRequestQuickConfig: (action?: string | null) => boolean
  usesDeviceActionQuickConfig: (action?: string | null) => boolean
  usesImageBranchQuickConfig: (action?: string | null) => boolean
  usesAssertQuickConfig: (action?: string | null) => boolean
  usesForeachAssertQuickConfig: (action?: string | null) => boolean
  selectedAssertType: string
  selectedAssertQuickMode: string
  selectedPrimarySelectorType: string
  selectedFallbackSelectorType: string
  selectedClickSelectorType: string
  selectedTargetSelectorType: string
  selectedVariableScope: string
  expectedListText: string
  configKeys: string[]
  readSelectedConfigValue: (key: string, fallback?: unknown) => unknown
  readSelectedConfigString: (key: string, fallback?: string) => string
  readSelectedConfigNumber: (key: string, fallback?: number) => number
  readSelectedConfigBoolean: (key: string, fallback?: boolean) => boolean
  updateSelectedStepConfig: (key: string, value: unknown) => void
  formatQuickConfigValue: (value: unknown) => string
  handleLooseConfigTextChange: (key: string, value: string) => void
  handleJsonConfigTextChange: (key: string, value: string, emptyValue?: unknown) => void
  handleExpectedListTextChange: (value: string) => void
  handleAssertTypeChange: (value: string) => void
}

defineProps<Props>()

const stepConfigTextModel = defineModel<string>('stepConfigText', { required: true })

const emit = defineEmits<{
  'open-ai-step-dialog': []
  'reset-selected-step-config': []
  'apply-step-config': []
}>()

const selectorTypeOptions: QuickOption[] = [
  { label: '???', value: 'element' },
  { label: '??', value: 'text' },
  { label: '?? ID', value: 'id' },
  { label: '??', value: 'desc' },
  { label: 'XPath', value: 'xpath' },
  { label: '??', value: 'image' },
  { label: '??', value: 'region' },
  { label: '??', value: 'pos' },
]

const matchModeOptions: QuickOption[] = [
  { label: '??', value: 'contains' },
  { label: '????', value: 'exact' },
  { label: '????', value: 'regex' },
]

const assertTypeOptions: QuickOption[] = [
  { label: '????', value: 'condition' },
  { label: '????', value: 'exists' },
  { label: '?????', value: 'not_exists' },
  { label: '????', value: 'image' },
  { label: 'OCR ??', value: 'text' },
  { label: 'OCR ??', value: 'number' },
  { label: 'OCR ??', value: 'regex' },
  { label: 'OCR ??', value: 'range' },
]

const assertOperatorOptions: QuickOption[] = [
  { label: '??', value: '==' },
  { label: '???', value: '!=' },
  { label: '??', value: '>' },
  { label: '????', value: '>=' },
  { label: '??', value: '<' },
  { label: '????', value: '<=' },
  { label: '??', value: 'contains' },
  { label: '??', value: 'regex' },
  { label: '??', value: 'truthy' },
  { label: '??', value: 'falsy' },
]

const swipeDirectionOptions: QuickOption[] = [
  { label: '??', value: 'up' },
  { label: '??', value: 'down' },
  { label: '??', value: 'left' },
  { label: '??', value: 'right' },
]

const variableScopeOptions: QuickOption[] = [
  { label: '??', value: 'local' },
  { label: '??', value: 'global' },
]

const httpMethodOptions: QuickOption[] = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'PATCH', value: 'PATCH' },
  { label: 'DELETE', value: 'DELETE' },
]

const responseTypeOptions: QuickOption[] = [
  { label: '????', value: 'auto' },
  { label: 'JSON', value: 'json' },
  { label: '??', value: 'text' },
  { label: '???', value: 'binary' },
]
</script>


<style scoped>
.config-panel {
  min-height: 560px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.config-empty,
.config-empty-text {
  color: var(--theme-text-secondary);
}

.config-summary,
.config-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.config-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-top: -6px;
}

.config-flow-alert {
  margin-bottom: 4px;
}

.config-helper-alert {
  margin-bottom: 4px;
}

.quick-config-panel {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  background: rgba(var(--theme-accent-rgb), 0.05);
}

.quick-config-title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-text);
}

.quick-config-subtle-alert {
  margin-bottom: 12px;
  background: rgba(var(--theme-surface-rgb), 0.72);
}

.config-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

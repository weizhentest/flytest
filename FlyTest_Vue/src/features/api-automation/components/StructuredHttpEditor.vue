<template>
  <div class="structured-http-editor">
    <div class="structured-http-editor__toolbar">
      <div class="structured-http-editor__hint">
        先点击一个文本输入框，再插入数据工厂引用
        <span v-if="referenceTargetLabel">当前目标：{{ referenceTargetLabel }}</span>
      </div>
      <a-button size="small" :disabled="!projectStore.currentProjectId" @click="openReferencePicker">
        插入数据工厂引用
      </a-button>
    </div>
    <div v-if="showRequestTarget" class="structured-http-editor__top">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item field="method" label="请求方法">
            <a-select v-model="localModel.method">
              <a-option v-for="item in methodOptions" :key="item" :value="item" :label="item" />
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item field="url" label="请求地址">
            <a-input
              v-model="localModel.url"
              placeholder="支持完整 URL 或相对路径"
              @focus="setReferenceTarget('url', '请求地址')"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </div>

    <a-tabs v-model:active-key="activeTab" type="rounded" class="structured-http-editor__tabs">
      <a-tab-pane key="headers" title="Headers">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">请求头</div>
            <div class="editor-tab-description">支持变量占位符，按顺序执行覆盖。</div>
          </div>
          <a-button size="small" @click="addNamedItem(localModel.headers)">新增 Header</a-button>
        </div>
        <div v-if="!localModel.headers.length" class="editor-empty">暂无 Header 配置</div>
        <div v-for="(item, index) in localModel.headers" :key="`header-${index}`" class="kv-row">
          <a-input v-model="item.name" class="kv-row__name" placeholder="名称" />
          <a-input
            v-model="item.value"
            class="kv-row__value"
            placeholder="值"
            @focus="setReferenceTarget(`headers.${index}.value`, `Header 值 #${index + 1}`)"
          />
          <div class="kv-row__toggle">
            <span>启用</span>
            <a-switch v-model="item.enabled" size="small" />
          </div>
          <a-button status="danger" size="mini" @click="removeAt(localModel.headers, index)">删除</a-button>
        </div>
      </a-tab-pane>

      <a-tab-pane key="query" title="Query">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">查询参数</div>
            <div class="editor-tab-description">适用于 URL Query、分页参数和过滤条件。</div>
          </div>
          <a-button size="small" @click="addNamedItem(localModel.query)">新增 Query</a-button>
        </div>
        <div v-if="!localModel.query.length" class="editor-empty">暂无 Query 参数</div>
        <div v-for="(item, index) in localModel.query" :key="`query-${index}`" class="kv-row">
          <a-input v-model="item.name" class="kv-row__name" placeholder="参数名" />
          <a-input
            v-model="item.value"
            class="kv-row__value"
            placeholder="参数值"
            @focus="setReferenceTarget(`query.${index}.value`, `Query 值 #${index + 1}`)"
          />
          <div class="kv-row__toggle">
            <span>启用</span>
            <a-switch v-model="item.enabled" size="small" />
          </div>
          <a-button status="danger" size="mini" @click="removeAt(localModel.query, index)">删除</a-button>
        </div>
      </a-tab-pane>

      <a-tab-pane key="cookies" title="Cookies">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">Cookie</div>
            <div class="editor-tab-description">支持会话态接口和跨步骤 Cookie 透传。</div>
          </div>
          <a-button size="small" @click="addNamedItem(localModel.cookies)">新增 Cookie</a-button>
        </div>
        <div v-if="!localModel.cookies.length" class="editor-empty">暂无 Cookie 配置</div>
        <div v-for="(item, index) in localModel.cookies" :key="`cookie-${index}`" class="kv-row">
          <a-input v-model="item.name" class="kv-row__name" placeholder="Cookie 名" />
          <a-input
            v-model="item.value"
            class="kv-row__value"
            placeholder="Cookie 值"
            @focus="setReferenceTarget(`cookies.${index}.value`, `Cookie 值 #${index + 1}`)"
          />
          <div class="kv-row__toggle">
            <span>启用</span>
            <a-switch v-model="item.enabled" size="small" />
          </div>
          <a-button status="danger" size="mini" @click="removeAt(localModel.cookies, index)">删除</a-button>
        </div>
      </a-tab-pane>

      <a-tab-pane key="auth" title="Auth">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">认证</div>
            <div class="editor-tab-description">基础认证、Bearer、API Key、Cookie、引导登录都在这里配置。</div>
          </div>
        </div>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="认证方式">
              <a-select v-model="localModel.auth.auth_type">
                <a-option
                  v-if="allowEmptyAuth"
                  value=""
                  label="继承接口"
                />
                <a-option value="none" label="无认证" />
                <a-option value="basic" label="Basic" />
                <a-option value="bearer" label="Bearer" />
                <a-option value="api_key" label="API Key" />
                <a-option value="cookie" label="Cookie" />
                <a-option value="bootstrap_request" label="引导登录" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'basic'" :span="8">
            <a-form-item label="用户名">
              <a-input
                v-model="localModel.auth.username"
                placeholder="用户名"
                @focus="setReferenceTarget('auth.username', '认证用户名')"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'basic'" :span="8">
            <a-form-item label="密码">
              <a-input-password
                v-model="localModel.auth.password"
                placeholder="密码"
                @focus="setReferenceTarget('auth.password', '认证密码')"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="['bearer', 'bootstrap_request'].includes(localModel.auth.auth_type)" :span="8">
            <a-form-item label="Header 名">
              <a-input v-model="localModel.auth.header_name" placeholder="Authorization" />
            </a-form-item>
          </a-col>
          <a-col v-if="['bearer', 'bootstrap_request'].includes(localModel.auth.auth_type)" :span="8">
            <a-form-item label="Bearer 前缀">
              <a-input v-model="localModel.auth.bearer_prefix" placeholder="Bearer" />
            </a-form-item>
          </a-col>
          <a-col v-if="['bearer', 'bootstrap_request', 'api_key', 'cookie'].includes(localModel.auth.auth_type)" :span="8">
            <a-form-item label="变量名">
              <a-input v-model="localModel.auth.token_variable" placeholder="token" />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'bearer'" :span="12">
            <a-form-item label="静态 Token">
              <a-input
                v-model="localModel.auth.token_value"
                placeholder="可直接填写，也可交给变量解析"
                @focus="setReferenceTarget('auth.token_value', '静态 Token')"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'api_key'" :span="8">
            <a-form-item label="Key 名">
              <a-input v-model="localModel.auth.api_key_name" placeholder="X-API-Key" />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'api_key'" :span="8">
            <a-form-item label="传递位置">
              <a-select v-model="localModel.auth.api_key_in">
                <a-option value="header" label="Header" />
                <a-option value="query" label="Query" />
                <a-option value="cookie" label="Cookie" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'api_key'" :span="8">
            <a-form-item label="静态 Key 值">
              <a-input
                v-model="localModel.auth.api_key_value"
                placeholder="可留空并用变量解析"
                @focus="setReferenceTarget('auth.api_key_value', '静态 Key 值')"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'cookie'" :span="8">
            <a-form-item label="Cookie 名">
              <a-input v-model="localModel.auth.cookie_name" placeholder="sessionid" />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'bootstrap_request'" :span="12">
            <a-form-item label="引导接口 ID">
              <a-input-number v-model="localModel.auth.bootstrap_request_id" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'bootstrap_request'" :span="12">
            <a-form-item label="引导接口名称">
              <a-input v-model="localModel.auth.bootstrap_request_name" placeholder="例如：登录" />
            </a-form-item>
          </a-col>
          <a-col v-if="localModel.auth.auth_type === 'bootstrap_request'" :span="24">
            <a-form-item label="Token 提取路径">
              <a-input
                v-model="localModel.auth.bootstrap_token_path"
                placeholder="支持多个 JSONPath，用英文逗号分隔"
                @focus="setReferenceTarget('auth.bootstrap_token_path', 'Token 提取路径')"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="body" title="Body">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">请求体</div>
            <div class="editor-tab-description">JSON、表单、Multipart、GraphQL、XML、Raw、Binary 统一编辑。</div>
          </div>
        </div>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="Body 类型">
              <a-select v-model="localModel.body_mode">
                <a-option value="none" label="none" />
                <a-option value="json" label="json" />
                <a-option value="form" label="form-data" />
                <a-option value="urlencoded" label="urlencoded" />
                <a-option value="multipart" label="multipart" />
                <a-option value="raw" label="raw" />
                <a-option value="xml" label="xml" />
                <a-option value="graphql" label="graphql" />
                <a-option value="binary" label="binary/base64" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="超时(ms)">
              <a-input-number v-model="localModel.timeout_ms" :min="1000" :step="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item v-if="localModel.body_mode === 'json'" label="JSON Body">
          <a-textarea
            v-model="localModel.body_json_text"
            :auto-size="{ minRows: 8, maxRows: 18 }"
            placeholder='例如：{"page":1,"size":20}'
            @focus="setReferenceTarget('body_json_text', 'JSON Body')"
          />
        </a-form-item>

        <template v-if="['form', 'urlencoded'].includes(localModel.body_mode)">
          <div class="editor-tab-header editor-tab-header--inline">
            <div class="editor-tab-description">表单字段</div>
            <a-button size="small" @click="addNamedItem(localModel.form_fields)">新增字段</a-button>
          </div>
          <div v-if="!localModel.form_fields.length" class="editor-empty">暂无表单字段</div>
          <div v-for="(item, index) in localModel.form_fields" :key="`form-${index}`" class="kv-row">
            <a-input v-model="item.name" class="kv-row__name" placeholder="字段名" />
            <a-input
              v-model="item.value"
              class="kv-row__value"
              placeholder="字段值"
              @focus="setReferenceTarget(`form_fields.${index}.value`, `表单值 #${index + 1}`)"
            />
            <div class="kv-row__toggle">
              <span>启用</span>
              <a-switch v-model="item.enabled" size="small" />
            </div>
            <a-button status="danger" size="mini" @click="removeAt(localModel.form_fields, index)">删除</a-button>
          </div>
        </template>

        <template v-if="localModel.body_mode === 'multipart'">
          <div class="editor-tab-header editor-tab-header--inline">
            <div class="editor-tab-description">Multipart 文本字段</div>
            <a-button size="small" @click="addNamedItem(localModel.multipart_parts)">新增字段</a-button>
          </div>
          <div v-if="!localModel.multipart_parts.length" class="editor-empty">暂无 multipart 文本字段</div>
          <div v-for="(item, index) in localModel.multipart_parts" :key="`multipart-${index}`" class="kv-row">
            <a-input v-model="item.name" class="kv-row__name" placeholder="字段名" />
            <a-input
              v-model="item.value"
              class="kv-row__value"
              placeholder="字段值"
              @focus="setReferenceTarget(`multipart_parts.${index}.value`, `Multipart 值 #${index + 1}`)"
            />
            <div class="kv-row__toggle">
              <span>启用</span>
              <a-switch v-model="item.enabled" size="small" />
            </div>
            <a-button status="danger" size="mini" @click="removeAt(localModel.multipart_parts, index)">删除</a-button>
          </div>
        </template>

        <a-form-item v-if="localModel.body_mode === 'raw'" label="Raw 文本">
          <a-textarea
            v-model="localModel.raw_text"
            :auto-size="{ minRows: 8, maxRows: 18 }"
            @focus="setReferenceTarget('raw_text', 'Raw 文本')"
          />
        </a-form-item>

        <a-form-item v-if="localModel.body_mode === 'xml'" label="XML 文本">
          <a-textarea
            v-model="localModel.xml_text"
            :auto-size="{ minRows: 8, maxRows: 18 }"
            @focus="setReferenceTarget('xml_text', 'XML 文本')"
          />
        </a-form-item>

        <template v-if="localModel.body_mode === 'graphql'">
          <a-form-item label="GraphQL Query">
            <a-textarea
              v-model="localModel.graphql_query"
              :auto-size="{ minRows: 8, maxRows: 18 }"
              @focus="setReferenceTarget('graphql_query', 'GraphQL Query')"
            />
          </a-form-item>
          <a-form-item label="Operation Name">
            <a-input
              v-model="localModel.graphql_operation_name"
              @focus="setReferenceTarget('graphql_operation_name', 'Operation Name')"
            />
          </a-form-item>
          <a-form-item label="GraphQL Variables">
            <a-textarea
              v-model="localModel.graphql_variables_text"
              :auto-size="{ minRows: 6, maxRows: 12 }"
              @focus="setReferenceTarget('graphql_variables_text', 'GraphQL Variables')"
            />
          </a-form-item>
        </template>

        <a-form-item v-if="localModel.body_mode === 'binary'" label="Base64 内容">
          <a-textarea
            v-model="localModel.binary_base64"
            :auto-size="{ minRows: 6, maxRows: 12 }"
            @focus="setReferenceTarget('binary_base64', 'Base64 内容')"
          />
        </a-form-item>
      </a-tab-pane>

      <a-tab-pane key="files" title="Files">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">文件上传</div>
            <div class="editor-tab-description">适用于 multipart file、二进制占位符和内联 Base64 文件体。</div>
          </div>
          <a-button size="small" @click="addFile">新增文件</a-button>
        </div>
        <div v-if="!localModel.files.length" class="editor-empty">暂无文件配置</div>
        <div v-for="(item, index) in localModel.files" :key="`file-${index}`" class="file-row">
          <a-input v-model="item.field_name" placeholder="表单字段名" />
          <a-select v-model="item.source_type" placeholder="来源">
            <a-option value="path" label="本地路径" />
            <a-option value="base64" label="Base64" />
            <a-option value="placeholder" label="变量占位符" />
          </a-select>
          <a-input
            v-model="item.file_path"
            placeholder="文件路径 / 占位符"
            @focus="setReferenceTarget(`files.${index}.file_path`, `文件路径 #${index + 1}`)"
          />
          <a-input
            v-model="item.file_name"
            placeholder="文件名"
            @focus="setReferenceTarget(`files.${index}.file_name`, `文件名 #${index + 1}`)"
          />
          <a-input v-model="item.content_type" placeholder="Content-Type" />
          <a-textarea
            v-if="item.source_type === 'base64'"
            v-model="item.base64_content"
            :auto-size="{ minRows: 3, maxRows: 6 }"
            placeholder="Base64 内容"
            @focus="setReferenceTarget(`files.${index}.base64_content`, `文件 Base64 #${index + 1}`)"
          />
          <div class="file-row__footer">
            <div class="kv-row__toggle">
              <span>启用</span>
              <a-switch v-model="item.enabled" size="small" />
            </div>
            <a-button status="danger" size="mini" @click="removeAt(localModel.files, index)">删除</a-button>
          </div>
        </div>
      </a-tab-pane>

      <a-tab-pane key="assertions" title="Assertions">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">断言</div>
            <div class="editor-tab-description">支持状态码、Header、Cookie、Regex、JSON Schema、耗时等断言。</div>
          </div>
          <a-button size="small" @click="addAssertion">新增断言</a-button>
        </div>
        <div v-if="!localModel.assertions.length" class="editor-empty">暂无断言配置</div>
        <div v-for="(item, index) in localModel.assertions" :key="`assertion-${index}`" class="assertion-card">
          <div class="assertion-card__top">
            <a-space wrap>
              <a-select v-model="item.assertion_type" style="width: 180px" @change="handleAssertionTypeChange(item)">
                <a-option v-for="option in assertionTypeOptions" :key="option.value" :value="option.value" :label="option.label" />
              </a-select>
              <a-select
                v-if="showOperatorSelector(item.assertion_type)"
                v-model="item.operator"
                style="width: 160px"
              >
                <a-option
                  v-for="option in getAssertionOperatorOptions(item.assertion_type)"
                  :key="option.value"
                  :value="option.value"
                  :label="option.label"
                />
              </a-select>
              <a-input
                v-if="usesSelector(item.assertion_type)"
                v-model="item.selector"
                style="width: 280px"
                :placeholder="getSelectorPlaceholder(item.assertion_type)"
                @focus="setReferenceTarget(`assertions.${index}.selector`, `断言选择器 #${index + 1}`)"
              />
            </a-space>
            <div class="kv-row__toggle">
              <span>启用</span>
              <a-switch v-model="item.enabled" size="small" />
            </div>
            <a-button status="danger" size="mini" @click="removeAt(localModel.assertions, index)">删除</a-button>
          </div>

          <a-row v-if="usesRange(item.assertion_type)" :gutter="12">
            <a-col :span="12">
              <a-form-item label="最小值">
                <a-input-number v-model="item.min_value" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="最大值">
                <a-input-number v-model="item.max_value" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item v-else-if="usesSchema(item.assertion_type)" label="Schema / Contract">
            <a-textarea
              v-model="item.schema_text"
              :auto-size="{ minRows: 6, maxRows: 12 }"
              @focus="setReferenceTarget(`assertions.${index}.schema_text`, `断言 Schema #${index + 1}`)"
            />
          </a-form-item>

          <template v-else-if="usesFlexibleExpectedValue(item.assertion_type)">
            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item label="期望值类型">
                  <a-select v-model="item.expected_value_kind">
                    <a-option value="text" label="文本" />
                    <a-option value="number" label="数值" />
                    <a-option value="json" label="JSON" />
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="16">
                <a-form-item :label="getExpectedLabel(item.assertion_type)">
                  <a-input-number
                    v-if="item.expected_value_kind === 'number'"
                    v-model="item.expected_number"
                    style="width: 100%"
                  />
                  <a-textarea
                    v-else-if="item.expected_value_kind === 'json'"
                    v-model="item.expected_json_text"
                    :auto-size="{ minRows: 4, maxRows: 10 }"
                    placeholder='{"ok": true}'
                    @focus="setReferenceTarget(`assertions.${index}.expected_json_text`, `断言 JSON #${index + 1}`)"
                  />
                  <a-input
                    v-else
                    v-model="item.expected_text"
                    :placeholder="getExpectedPlaceholder(item.assertion_type)"
                    @focus="setReferenceTarget(`assertions.${index}.expected_text`, `断言期望值 #${index + 1}`)"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <a-form-item v-else-if="usesExpectedNumber(item.assertion_type)" label="期望数值">
            <a-input-number v-model="item.expected_number" style="width: 100%" />
          </a-form-item>

          <a-form-item v-else-if="usesExpectedText(item.assertion_type)" label="期望文本">
            <a-input
              v-model="item.expected_text"
              :placeholder="getExpectedPlaceholder(item.assertion_type)"
              @focus="setReferenceTarget(`assertions.${index}.expected_text`, `断言文本 #${index + 1}`)"
            />
          </a-form-item>
        </div>
      </a-tab-pane>

      <a-tab-pane key="extractors" title="Extractors">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">提取器</div>
            <div class="editor-tab-description">支持从响应体、Header、Cookie、Regex 和响应元数据中提取变量。</div>
          </div>
          <a-button size="small" @click="addExtractor">新增提取器</a-button>
        </div>
        <div v-if="!localModel.extractors.length" class="editor-empty">暂无提取器配置</div>
        <div v-for="(item, index) in localModel.extractors" :key="`extractor-${index}`" class="assertion-card">
          <div class="assertion-card__top">
            <a-space wrap>
              <a-select v-model="item.source" style="width: 180px">
                <a-option value="json_path" label="json_path" />
                <a-option value="header" label="header" />
                <a-option value="cookie" label="cookie" />
                <a-option value="regex" label="regex" />
                <a-option value="status_code" label="status_code" />
                <a-option value="response_time" label="response_time" />
              </a-select>
              <a-input
                v-model="item.selector"
                style="width: 260px"
                placeholder="提取路径 / Header / Regex"
                @focus="setReferenceTarget(`extractors.${index}.selector`, `提取器选择器 #${index + 1}`)"
              />
              <a-input v-model="item.variable_name" style="width: 200px" placeholder="变量名" />
            </a-space>
            <div class="kv-row__toggle">
              <span>必填</span>
              <a-switch v-model="item.required" size="small" />
            </div>
            <div class="kv-row__toggle">
              <span>启用</span>
              <a-switch v-model="item.enabled" size="small" />
            </div>
            <a-button status="danger" size="mini" @click="removeAt(localModel.extractors, index)">删除</a-button>
          </div>
          <a-form-item label="默认值">
            <a-input
              v-model="item.default_value"
              placeholder="提取失败时回填默认值"
              @focus="setReferenceTarget(`extractors.${index}.default_value`, `提取器默认值 #${index + 1}`)"
            />
          </a-form-item>
        </div>
      </a-tab-pane>

      <a-tab-pane key="transport" title="Transport">
        <div class="editor-tab-header">
          <div>
            <div class="editor-tab-title">传输层</div>
            <div class="editor-tab-description">SSL 校验、代理、客户端证书、重试和重定向行为都在这里配置。</div>
          </div>
        </div>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="验证 SSL">
              <a-select v-model="localModel.transport.verify_ssl">
                <a-option v-if="allowInheritedTransport" :value="null" label="继承接口" />
                <a-option :value="true" label="开启" />
                <a-option :value="false" label="关闭" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="跟随重定向">
              <a-select v-model="localModel.transport.follow_redirects">
                <a-option v-if="allowInheritedTransport" :value="null" label="继承接口" />
                <a-option :value="true" label="开启" />
                <a-option :value="false" label="关闭" />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="重试次数">
              <a-input-number v-model="localModel.transport.retry_count" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="重试间隔(ms)">
              <a-input-number v-model="localModel.transport.retry_interval_ms" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item label="代理地址">
              <a-input v-model="localModel.transport.proxy_url" placeholder="http://127.0.0.1:7890" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="客户端证书">
              <a-input v-model="localModel.transport.client_cert" placeholder="证书路径" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="客户端私钥">
              <a-input v-model="localModel.transport.client_key" placeholder="私钥路径" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-tab-pane>
    </a-tabs>

    <DataFactoryReferencePicker
      v-model="referencePickerVisible"
      :project-id="projectStore.currentProjectId"
      mode="api"
      @select="handleReferenceSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import DataFactoryReferencePicker from '@/features/data-factory/components/DataFactoryReferencePicker.vue'
import type { ApiAssertionSpec, ApiHttpEditorModel } from '../types'
import {
  createAssertionSpec,
  createExtractorSpec,
  createFileSpec,
  createNamedValueSpec,
  createEmptyHttpEditorModel,
} from '../state/httpEditor'

const props = withDefaults(
  defineProps<{
    modelValue: ApiHttpEditorModel
    showRequestTarget?: boolean
    allowEmptyAuth?: boolean
    allowInheritedTransport?: boolean
  }>(),
  {
    showRequestTarget: true,
    allowEmptyAuth: false,
    allowInheritedTransport: false,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: ApiHttpEditorModel): void
}>()

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const assertionTypeOptions = [
  { value: 'status_code', label: 'Status code' },
  { value: 'status_range', label: 'Status range' },
  { value: 'body_contains', label: 'Body contains' },
  { value: 'body_not_contains', label: 'Body not contains' },
  { value: 'json_path', label: 'JSONPath' },
  { value: 'header', label: 'Header' },
  { value: 'cookie', label: 'Cookie' },
  { value: 'regex', label: 'Regex' },
  { value: 'exists', label: 'Exists' },
  { value: 'not_exists', label: 'Not exists' },
  { value: 'array_length', label: 'Array length' },
  { value: 'response_time', label: 'Response time' },
  { value: 'json_schema', label: 'JSON Schema' },
  { value: 'openapi_contract', label: 'OpenAPI Contract' },
] as const
const activeTab = ref('headers')
const localModel = ref<ApiHttpEditorModel>(createEmptyHttpEditorModel())
const projectStore = useProjectStore()
const referencePickerVisible = ref(false)
const referenceTargetPath = ref('')
const referenceTargetLabel = ref('')
let syncingFromProps = false

const cloneModel = (value: ApiHttpEditorModel) => JSON.parse(JSON.stringify(value)) as ApiHttpEditorModel

const resolveTarget = (path: string) => {
  if (!path) return null
  const segments = path.split('.').map(segment => (/^\d+$/.test(segment) ? Number(segment) : segment))
  let target: any = localModel.value
  for (let index = 0; index < segments.length - 1; index += 1) {
    target = target?.[segments[index] as keyof typeof target]
  }
  if (target === null || target === undefined) return null
  return { target, key: segments[segments.length - 1] as string | number }
}

const getValueAtPath = (path: string) => {
  const resolved = resolveTarget(path)
  if (!resolved) return ''
  return resolved.target?.[resolved.key as keyof typeof resolved.target]
}

const setValueAtPath = (path: string, value: string) => {
  const resolved = resolveTarget(path)
  if (!resolved) return
  const currentValue = getValueAtPath(path)
  if (typeof currentValue === 'string') {
    resolved.target[resolved.key] = `${currentValue}${value}`
    return
  }
  if (currentValue === null || currentValue === undefined) {
    resolved.target[resolved.key] = value
    return
  }
  resolved.target[resolved.key] = value
}

const setReferenceTarget = (path: string, label: string) => {
  referenceTargetPath.value = path
  referenceTargetLabel.value = label
}

const openReferencePicker = () => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目')
    return
  }
  if (!referenceTargetPath.value) {
    Message.warning('请先点击一个文本输入框')
    return
  }
  referencePickerVisible.value = true
}

const handleReferenceSelect = (placeholder: string) => {
  if (!referenceTargetPath.value) return
  setValueAtPath(referenceTargetPath.value, placeholder)
  Message.success('数据工厂引用已插入')
}

watch(
  () => props.modelValue,
  value => {
    syncingFromProps = true
    localModel.value = cloneModel(value)
    Promise.resolve().then(() => {
      syncingFromProps = false
    })
  },
  { deep: true, immediate: true }
)

watch(
  localModel,
  value => {
    if (syncingFromProps) return
    emit('update:modelValue', cloneModel(value))
  },
  { deep: true }
)

const addNamedItem = (items: Array<{ name: string; value: any; enabled?: boolean; order?: number }>) => {
  items.push(
    createNamedValueSpec({
      enabled: true,
      order: items.length,
    })
  )
}

const addFile = () => {
  localModel.value.files.push(
    createFileSpec({
      enabled: true,
      order: localModel.value.files.length,
    })
  )
}

const addAssertion = () => {
  localModel.value.assertions.push(
    createAssertionSpec({
      order: localModel.value.assertions.length,
    })
  )
}

const addExtractor = () => {
  localModel.value.extractors.push(
    createExtractorSpec({
      order: localModel.value.extractors.length,
    })
  )
}

const removeAt = (items: any[], index: number) => {
  items.splice(index, 1)
}

const getAssertionOperatorOptions = (type: ApiAssertionSpec['assertion_type']) => {
  switch (type) {
    case 'status_code':
    case 'array_length':
    case 'response_time':
      return [
        { value: 'equals', label: 'equals' },
        { value: 'not_equals', label: 'not equals' },
        { value: 'gt', label: '>' },
        { value: 'gte', label: '>=' },
        { value: 'lt', label: '<' },
        { value: 'lte', label: '<=' },
      ]
    case 'json_path':
      return [
        { value: 'equals', label: 'equals' },
        { value: 'not_equals', label: 'not equals' },
        { value: 'contains', label: 'contains' },
        { value: 'not_contains', label: 'not contains' },
        { value: 'gt', label: '>' },
        { value: 'gte', label: '>=' },
        { value: 'lt', label: '<' },
        { value: 'lte', label: '<=' },
      ]
    case 'header':
    case 'cookie':
      return [
        { value: 'equals', label: 'equals' },
        { value: 'not_equals', label: 'not equals' },
        { value: 'contains', label: 'contains' },
        { value: 'not_contains', label: 'not contains' },
        { value: 'starts_with', label: 'starts with' },
        { value: 'ends_with', label: 'ends with' },
      ]
    case 'regex':
      return [
        { value: 'exists', label: 'matches' },
        { value: 'equals', label: 'equals' },
        { value: 'contains', label: 'contains' },
        { value: 'not_contains', label: 'not contains' },
      ]
    default:
      return []
  }
}

const usesSelector = (type: ApiAssertionSpec['assertion_type']) => {
  return ['json_path', 'header', 'cookie', 'regex', 'exists', 'not_exists', 'array_length'].includes(type)
}

const showOperatorSelector = (type: ApiAssertionSpec['assertion_type']) => getAssertionOperatorOptions(type).length > 0

const getSelectorPlaceholder = (type: ApiAssertionSpec['assertion_type']) => {
  switch (type) {
    case 'json_path':
    case 'exists':
    case 'not_exists':
    case 'array_length':
      return 'JSONPath, e.g. data.list'
    case 'header':
      return 'Header name, e.g. Content-Type'
    case 'cookie':
      return 'Cookie name, e.g. sessionid'
    case 'regex':
      return 'Regex pattern'
    default:
      return 'Selector'
  }
}

const getExpectedLabel = (type: ApiAssertionSpec['assertion_type']) => {
  if (type === 'response_time') return '阈值 (ms)'
  return '期望值'
}

const getExpectedPlaceholder = (type: ApiAssertionSpec['assertion_type']) => {
  switch (type) {
    case 'body_contains':
      return '输入必须出现的文本'
    case 'body_not_contains':
      return '输入不应出现的文本'
    case 'header':
    case 'cookie':
      return '输入期望值'
    case 'regex':
      return '留空表示只校验正则命中'
    case 'json_path':
      return '输入期望值'
    default:
      return '请输入期望值'
  }
}

const usesExpectedNumber = (type: ApiAssertionSpec['assertion_type']) => {
  return ['status_code', 'array_length', 'response_time'].includes(type)
}

const usesExpectedText = (type: ApiAssertionSpec['assertion_type']) => {
  return ['body_contains', 'body_not_contains', 'header', 'cookie', 'regex'].includes(type)
}

const usesRange = (type: ApiAssertionSpec['assertion_type']) => type === 'status_range'

const usesSchema = (type: ApiAssertionSpec['assertion_type']) => {
  return ['json_schema', 'openapi_contract'].includes(type)
}

const usesFlexibleExpectedValue = (type: ApiAssertionSpec['assertion_type']) => type === 'json_path'

const handleAssertionTypeChange = (item: ApiAssertionSpec) => {
  if (item.assertion_type === 'status_code') {
    item.operator = 'equals'
    item.expected_value_kind = 'number'
    item.expected_number = item.expected_number ?? 200
    item.target = 'body'
  } else if (item.assertion_type === 'status_range') {
    item.operator = 'between'
    item.expected_value_kind = 'number'
    item.target = 'body'
  } else if (item.assertion_type === 'body_contains') {
    item.operator = 'contains'
    item.expected_value_kind = 'text'
    item.target = 'body'
  } else if (item.assertion_type === 'body_not_contains') {
    item.operator = 'not_contains'
    item.expected_value_kind = 'text'
    item.target = 'body'
  } else if (item.assertion_type === 'json_path') {
    item.target = 'json'
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'equals'
    item.expected_value_kind = item.expected_value_kind || 'text'
  } else if (item.assertion_type === 'header') {
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'equals'
    item.expected_value_kind = 'text'
    item.target = 'header'
  } else if (item.assertion_type === 'cookie') {
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'equals'
    item.expected_value_kind = 'text'
    item.target = 'cookie'
  } else if (item.assertion_type === 'regex') {
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'exists'
    item.expected_value_kind = 'text'
    item.target = 'body'
  } else if (item.assertion_type === 'exists') {
    item.operator = 'exists'
    item.target = 'json'
  } else if (item.assertion_type === 'not_exists') {
    item.operator = 'not_exists'
    item.target = 'json'
  } else if (item.assertion_type === 'array_length') {
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'equals'
    item.expected_value_kind = 'number'
    item.expected_number = item.expected_number ?? 0
    item.target = 'json'
  } else if (item.assertion_type === 'response_time') {
    item.operator = getAssertionOperatorOptions(item.assertion_type).some(option => option.value === item.operator)
      ? item.operator
      : 'lte'
    item.expected_value_kind = 'number'
    item.expected_number = item.expected_number ?? 1000
    item.target = 'meta'
  } else if (item.assertion_type === 'json_schema' || item.assertion_type === 'openapi_contract') {
    item.operator = 'validates'
    item.target = 'body'
  } else {
    item.target = item.target || 'body'
    item.operator = item.operator || 'equals'
  }
}
</script>

<style scoped>
.structured-http-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.structured-http-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border: 1px solid var(--color-neutral-3);
  border-radius: 14px;
  background: rgba(var(--primary-6), 0.06);
}

.structured-http-editor__hint {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-3);
}

.structured-http-editor__tabs {
  border: 1px solid var(--color-neutral-3);
  border-radius: 16px;
  padding: 16px;
  background: linear-gradient(180deg, #fbfcfd 0%, #ffffff 100%);
}

.editor-tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.editor-tab-header--inline {
  margin-top: 4px;
}

.editor-tab-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-1);
}

.editor-tab-description {
  font-size: 12px;
  color: var(--color-text-3);
}

.editor-empty {
  padding: 16px;
  border: 1px dashed var(--color-neutral-4);
  border-radius: 12px;
  color: var(--color-text-3);
  background: var(--color-fill-1);
}

.kv-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(220px, 1.5fr) auto auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.kv-row__toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  color: var(--color-text-2);
}

.file-row {
  display: grid;
  gap: 12px;
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--color-neutral-3);
  border-radius: 12px;
  background: var(--color-fill-1);
}

.file-row__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.assertion-card {
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--color-neutral-3);
  border-radius: 12px;
  background: var(--color-bg-2);
}

.assertion-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .structured-http-editor__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .kv-row {
    grid-template-columns: 1fr;
  }

  .assertion-card__top {
    align-items: flex-start;
  }
}
</style>

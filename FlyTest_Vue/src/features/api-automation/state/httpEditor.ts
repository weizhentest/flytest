import type {
  ApiAssertionSpec,
  ApiAssertionExpectedValueKind,
  ApiAuthSpec,
  ApiBodyMode,
  ApiExtractorSpec,
  ApiFileSpec,
  ApiHttpEditorModel,
  ApiNamedValueSpec,
  ApiRequest,
  ApiRequestForm,
  ApiRequestSpecPayload,
  ApiTestCase,
  ApiTestCaseOverrideSpecPayload,
  ApiTestCaseWorkflowEditorStep,
  ApiTestCaseWorkflowStep,
  ApiTransportSpec,
} from '../types'

const cloneJson = <T>(value: T): T => JSON.parse(JSON.stringify(value))

const stringifyJson = (value: any, fallback = '{}') => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const parseJsonText = <T>(text: string, fallback: T): T => {
  if (!text.trim()) return fallback
  return JSON.parse(text) as T
}

const hasOverrideValue = (value: any) => value !== null && value !== undefined && value !== ''

const isDeepEqual = (left: any, right: any) => JSON.stringify(left) === JSON.stringify(right)

const createWorkflowStepKey = () => `workflow-step-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

const hasOwnProperty = (value: object | null | undefined, key: string) =>
  Boolean(value && Object.prototype.hasOwnProperty.call(value, key))

const getReplaceFields = (overrideSpec?: ApiRequestSpecPayload | ApiTestCaseOverrideSpecPayload | null) =>
  new Set((overrideSpec?.replace_fields || []).filter(Boolean))

const inferAssertionExpectedValueKind = (item?: Partial<ApiAssertionSpec> | null): ApiAssertionExpectedValueKind => {
  if (item?.expected_value_kind) return item.expected_value_kind
  if (item?.expected_number !== null && item?.expected_number !== undefined) return 'number'
  if (item?.expected_text !== null && item?.expected_text !== undefined && item.expected_text !== '') return 'text'
  if (item?.assertion_type === 'json_path' && item && hasOwnProperty(item, 'expected_json') && item.expected_json !== undefined) {
    return 'json'
  }
  return 'text'
}

const pickOverrideScalar = <T>(
  overrideSpec: Record<string, any> | undefined | null,
  key: string,
  fallback: T,
  options: {
    allowBlankString?: boolean
  } = {}
): T => {
  if (!hasOwnProperty(overrideSpec, key)) return fallback
  const value = overrideSpec?.[key]
  if (value === null || value === undefined) return fallback
  if (value === '' && !options.allowBlankString) return fallback
  return value as T
}

const pickOverrideJson = <T>(overrideSpec: Record<string, any> | undefined | null, key: string, fallback: T): T => {
  if (!hasOwnProperty(overrideSpec, key)) return fallback
  const value = overrideSpec?.[key]
  return Array.isArray(value) || (value && typeof value === 'object') ? (value as T) : fallback
}

const mergeNamedBucket = (
  baseItems: ApiNamedValueSpec[] = [],
  overrideSpec?: ApiRequestSpecPayload | ApiTestCaseOverrideSpecPayload | null,
  key?: keyof ApiRequestSpecPayload
) => {
  if (!overrideSpec || !key || !hasOwnProperty(overrideSpec, key)) return mergeNamedItems(baseItems, [])
  if (getReplaceFields(overrideSpec).has(String(key))) {
    return normalizeNamedItems((overrideSpec as Record<string, any>)[key] as ApiNamedValueSpec[] | Record<string, any> | null)
  }
  const overrideItems = normalizeNamedItems((overrideSpec as Record<string, any>)[key] as ApiNamedValueSpec[] | Record<string, any> | null)
  return mergeNamedItems(baseItems, overrideItems)
}

const mergeFileBucket = (
  baseItems: ApiFileSpec[] = [],
  overrideSpec?: ApiRequestSpecPayload | ApiTestCaseOverrideSpecPayload | null
) => {
  if (!overrideSpec || !hasOwnProperty(overrideSpec, 'files')) return mergeFileItems(baseItems, [])
  if (getReplaceFields(overrideSpec).has('files')) {
    return normalizeFiles(overrideSpec.files)
  }
  const overrideItems = normalizeFiles(overrideSpec.files)
  return mergeFileItems(baseItems, overrideItems)
}

export const createNamedValueSpec = (overrides: Partial<ApiNamedValueSpec> = {}): ApiNamedValueSpec => ({
  name: '',
  value: '',
  enabled: true,
  order: 0,
  ...overrides,
})

export const createFileSpec = (overrides: Partial<ApiFileSpec> = {}): ApiFileSpec => ({
  field_name: '',
  source_type: 'path',
  file_path: '',
  file_name: '',
  content_type: '',
  base64_content: '',
  enabled: true,
  order: 0,
  ...overrides,
})

export const createRequestAuthSpec = (overrides: Partial<ApiAuthSpec> = {}): ApiAuthSpec => ({
  auth_type: 'none',
  username: '',
  password: '',
  token_value: '',
  token_variable: 'token',
  header_name: 'Authorization',
  bearer_prefix: 'Bearer',
  api_key_name: '',
  api_key_in: 'header',
  api_key_value: '',
  cookie_name: '',
  bootstrap_request_id: null,
  bootstrap_request_name: '',
  bootstrap_token_path: '',
  ...overrides,
})

export const createOverrideAuthSpec = (overrides: Partial<ApiAuthSpec> = {}): ApiAuthSpec => ({
  auth_type: '',
  username: '',
  password: '',
  token_value: '',
  token_variable: '',
  header_name: '',
  bearer_prefix: '',
  api_key_name: '',
  api_key_in: '',
  api_key_value: '',
  cookie_name: '',
  bootstrap_request_id: null,
  bootstrap_request_name: '',
  bootstrap_token_path: '',
  ...overrides,
})

export const createRequestTransportSpec = (overrides: Partial<ApiTransportSpec> = {}): ApiTransportSpec => ({
  verify_ssl: true,
  proxy_url: '',
  client_cert: '',
  client_key: '',
  follow_redirects: true,
  retry_count: 0,
  retry_interval_ms: 500,
  ...overrides,
})

export const createOverrideTransportSpec = (overrides: Partial<ApiTransportSpec> = {}): ApiTransportSpec => ({
  verify_ssl: null,
  proxy_url: '',
  client_cert: '',
  client_key: '',
  follow_redirects: null,
  retry_count: null,
  retry_interval_ms: null,
  ...overrides,
})

export const createAssertionSpec = (overrides: Partial<ApiAssertionSpec> = {}): ApiAssertionSpec => ({
  assertion_type: 'status_code',
  target: 'body',
  selector: '',
  operator: 'equals',
  expected_value_kind: 'number',
  expected_text: '',
  expected_number: 200,
  expected_json: {},
  expected_json_text: '{}',
  min_value: null,
  max_value: null,
  schema_text: '',
  enabled: true,
  order: 0,
  ...overrides,
})

export const createExtractorSpec = (overrides: Partial<ApiExtractorSpec> = {}): ApiExtractorSpec => ({
  source: 'json_path',
  selector: '',
  variable_name: '',
  default_value: '',
  required: false,
  enabled: true,
  order: 0,
  ...overrides,
})

export const createEmptyHttpEditorModel = (overrides: Partial<ApiHttpEditorModel> = {}): ApiHttpEditorModel => ({
  method: 'GET',
  url: '',
  body_mode: 'none',
  timeout_ms: 30000,
  headers: [],
  query: [],
  cookies: [],
  form_fields: [],
  multipart_parts: [],
  files: [],
  auth: createRequestAuthSpec(),
  transport: createRequestTransportSpec(),
  assertions: [createAssertionSpec()],
  extractors: [],
  body_json_text: '{}',
  raw_text: '',
  xml_text: '',
  binary_base64: '',
  graphql_query: '',
  graphql_operation_name: '',
  graphql_variables_text: '{}',
  ...overrides,
})

const normalizeNamedItems = (items?: ApiNamedValueSpec[] | Record<string, any> | null) => {
  if (Array.isArray(items)) {
    return items.map((item, index) =>
      createNamedValueSpec({
        id: item.id,
        name: item.name || '',
        value: item.value ?? '',
        enabled: item.enabled ?? true,
        order: item.order ?? index,
      })
    )
  }
  if (items && typeof items === 'object') {
    return Object.entries(items).map(([name, value], index) =>
      createNamedValueSpec({
        name,
        value,
        enabled: true,
        order: index,
      })
    )
  }
  return []
}

const normalizeFiles = (items?: ApiFileSpec[] | null) => {
  if (!Array.isArray(items)) return []
  return items.map((item, index) =>
    createFileSpec({
      ...item,
      enabled: item.enabled ?? true,
      order: item.order ?? index,
    })
  )
}

const normalizeAssertions = (items?: ApiAssertionSpec[] | Array<Record<string, any>> | null) => {
  if (!Array.isArray(items) || !items.length) {
    return [createAssertionSpec()]
  }
  return items.map((item, index) =>
    createAssertionSpec({
      ...item,
      enabled: item.enabled ?? true,
      order: item.order ?? index,
      expected_value_kind: inferAssertionExpectedValueKind(item),
      expected_json_text: stringifyJson(item.expected_json, '{}'),
    })
  )
}

const normalizeExtractors = (items?: ApiExtractorSpec[] | null) => {
  if (!Array.isArray(items)) return []
  return items.map((item, index) =>
    createExtractorSpec({
      ...item,
      enabled: item.enabled ?? true,
      order: item.order ?? index,
    })
  )
}

const extractContentType = (
  headers?: ApiNamedValueSpec[] | Record<string, any> | null
) => {
  if (Array.isArray(headers)) {
    const header = headers.find(item => String(item?.name || '').toLowerCase() === 'content-type' && item.enabled !== false)
    return String(header?.value || '').trim().toLowerCase()
  }
  if (headers && typeof headers === 'object') {
    const entry = Object.entries(headers).find(([key]) => key.toLowerCase() === 'content-type')
    return String(entry?.[1] || '').trim().toLowerCase()
  }
  return ''
}

const inferBodyModeFromContentType = (
  contentType: string,
  fallback: ApiBodyMode = 'none'
): ApiBodyMode => {
  if (!contentType) return fallback
  if (contentType.includes('graphql')) return 'graphql'
  if (contentType.includes('application/x-www-form-urlencoded')) return 'urlencoded'
  if (contentType.startsWith('multipart/')) return 'multipart'
  if (contentType.includes('application/json') || contentType.endsWith('+json')) return 'json'
  if (
    contentType.includes('application/xml') ||
    contentType.includes('text/xml') ||
    contentType.endsWith('+xml')
  ) return 'xml'
  if (contentType.startsWith('text/')) return 'raw'
  return fallback
}

const requestBodyToEditorState = (
  bodyType: string,
  body: any,
  headers?: ApiNamedValueSpec[] | Record<string, any> | null
) => {
  const fallbackMode = ((bodyType || 'none') as ApiBodyMode)
  const body_mode = inferBodyModeFromContentType(extractContentType(headers), fallbackMode)
  return {
    body_mode,
    body_json_text: body_mode === 'json' ? stringifyJson(body, '{}') : '{}',
    raw_text: body_mode === 'raw' ? String(body ?? '') : '',
    xml_text: body_mode === 'xml' ? String(body ?? '') : '',
  }
}

const overrideFromLegacyScript = (testCase: ApiTestCase): ApiTestCaseOverrideSpecPayload => {
  const script = testCase.script || {}
  const overrides = script?.request_overrides && typeof script.request_overrides === 'object' ? script.request_overrides : {}
  const bodyType = String(overrides.body_type || '')
  const body = overrides.body
  const bodyState = requestBodyToEditorState(bodyType, body, overrides.headers || {})
  return {
    method: String(overrides.method || testCase.request_method || 'GET'),
    url: String(overrides.url || testCase.request_url || ''),
    body_mode: bodyState.body_mode,
    body_json: bodyState.body_mode === 'json' ? parseJsonText(bodyState.body_json_text, {}) : {},
    raw_text: bodyState.raw_text,
    xml_text: bodyState.xml_text,
    binary_base64: '',
    graphql_query: '',
    graphql_operation_name: '',
    graphql_variables: {},
    timeout_ms: Number(overrides.timeout_ms || 30000),
    headers: normalizeNamedItems(overrides.headers || {}),
    query: normalizeNamedItems(overrides.params || {}),
    cookies: [],
    form_fields: bodyState.body_mode === 'form' ? normalizeNamedItems(body || {}) : [],
    multipart_parts: [],
    files: [],
    auth: createOverrideAuthSpec(),
    transport: createOverrideTransportSpec(),
  }
}

const mergeNamedItems = (baseItems: ApiNamedValueSpec[] = [], overrideItems: ApiNamedValueSpec[] = []) => {
  const merged = new Map<string, ApiNamedValueSpec>()
  const orderedNames: string[] = []

  for (const rawItem of [...baseItems, ...overrideItems]) {
    if (!rawItem || typeof rawItem !== 'object') continue
    const item = createNamedValueSpec(rawItem)
    const name = String(item.name || '')
    if (!name) continue
    if (!merged.has(name)) {
      orderedNames.push(name)
      merged.set(name, createNamedValueSpec({ name }))
    }
    merged.set(name, createNamedValueSpec({ ...merged.get(name), ...item }))
  }

  return orderedNames.map((name, index) =>
    createNamedValueSpec({
      ...merged.get(name),
      order: index,
    })
  )
}

const mergeFileItems = (baseItems: ApiFileSpec[] = [], overrideItems: ApiFileSpec[] = []) => {
  const merged = new Map<string, ApiFileSpec>()
  const orderedKeys: string[] = []

  for (const rawItem of [...baseItems, ...overrideItems]) {
    if (!rawItem || typeof rawItem !== 'object') continue
    const item = createFileSpec(rawItem)
    const fieldName = String(item.field_name || '')
    if (!fieldName) continue
    const key = `${fieldName}:${item.file_name || item.file_path || item.order || 0}`
    if (!merged.has(key)) {
      orderedKeys.push(key)
      merged.set(key, createFileSpec({ field_name: fieldName }))
    }
    merged.set(key, createFileSpec({ ...merged.get(key), ...item }))
  }

  return orderedKeys.map((key, index) =>
    createFileSpec({
      ...merged.get(key),
      order: index,
    })
  )
}

const mergeAuthSpec = (baseAuth?: ApiAuthSpec | null, overrideAuth?: Partial<ApiAuthSpec> | null) => {
  const merged = createRequestAuthSpec(baseAuth || {})
  Object.entries(overrideAuth || {}).forEach(([key, value]) => {
    if (value !== null && value !== '') {
      ;(merged as Record<string, any>)[key] = value
    }
  })
  return merged
}

const mergeTransportSpec = (baseTransport?: ApiTransportSpec | null, overrideTransport?: Partial<ApiTransportSpec> | null) => {
  const merged = createRequestTransportSpec(baseTransport || {})
  Object.entries(overrideTransport || {}).forEach(([key, value]) => {
    if (value !== null && value !== '') {
      ;(merged as Record<string, any>)[key] = value
    }
  })
  return merged
}

const mergeRequestEditorModel = (
  baseModel: ApiHttpEditorModel,
  overrideSpec?: ApiRequestSpecPayload | ApiTestCaseOverrideSpecPayload | null
) => {
  if (!overrideSpec) {
    return createEmptyHttpEditorModel(cloneJson(baseModel))
  }

  const baseBodyJson = parseJsonText(baseModel.body_json_text, {})
  const baseGraphqlVariables = parseJsonText(baseModel.graphql_variables_text, {})

  return createEmptyHttpEditorModel({
    ...cloneJson(baseModel),
    method: hasOverrideValue(overrideSpec.method) ? overrideSpec.method : baseModel.method,
    url: hasOverrideValue(overrideSpec.url) ? overrideSpec.url : baseModel.url,
    body_mode: hasOverrideValue(overrideSpec.body_mode) ? overrideSpec.body_mode : baseModel.body_mode,
    timeout_ms: hasOverrideValue(overrideSpec.timeout_ms) ? Number(overrideSpec.timeout_ms) : baseModel.timeout_ms,
    headers: mergeNamedBucket(baseModel.headers, overrideSpec, 'headers'),
    query: mergeNamedBucket(baseModel.query, overrideSpec, 'query'),
    cookies: mergeNamedBucket(baseModel.cookies, overrideSpec, 'cookies'),
    form_fields: mergeNamedBucket(baseModel.form_fields, overrideSpec, 'form_fields'),
    multipart_parts: mergeNamedBucket(baseModel.multipart_parts, overrideSpec, 'multipart_parts'),
    files: mergeFileBucket(baseModel.files, overrideSpec),
    auth: mergeAuthSpec(baseModel.auth, overrideSpec.auth),
    transport: mergeTransportSpec(baseModel.transport, overrideSpec.transport),
    body_json_text: stringifyJson(pickOverrideJson(overrideSpec, 'body_json', baseBodyJson), '{}'),
    raw_text: String(pickOverrideScalar(overrideSpec, 'raw_text', baseModel.raw_text, { allowBlankString: true })),
    xml_text: String(pickOverrideScalar(overrideSpec, 'xml_text', baseModel.xml_text, { allowBlankString: true })),
    binary_base64: String(
      pickOverrideScalar(overrideSpec, 'binary_base64', baseModel.binary_base64, { allowBlankString: true })
    ),
    graphql_query: String(
      pickOverrideScalar(overrideSpec, 'graphql_query', baseModel.graphql_query, { allowBlankString: true })
    ),
    graphql_operation_name: String(
      pickOverrideScalar(overrideSpec, 'graphql_operation_name', baseModel.graphql_operation_name, {
        allowBlankString: true,
      })
    ),
    graphql_variables_text: stringifyJson(pickOverrideJson(overrideSpec, 'graphql_variables', baseGraphqlVariables), '{}'),
  })
}

export const requestToHttpEditorModel = (request?: ApiRequest | null): ApiHttpEditorModel => {
  if (!request) return createEmptyHttpEditorModel()

  const fallbackBodyState = requestBodyToEditorState(request.body_type || 'none', request.body, request.headers)
  const spec = request.request_spec || {
    method: request.method,
    url: request.url,
    body_mode: fallbackBodyState.body_mode,
    body_json: fallbackBodyState.body_mode === 'json' ? request.body || {} : {},
    raw_text: fallbackBodyState.body_mode === 'raw' ? String(request.body ?? '') : '',
    xml_text: fallbackBodyState.xml_text,
    binary_base64: '',
    graphql_query: '',
    graphql_operation_name: '',
    graphql_variables: {},
    timeout_ms: request.timeout_ms || 30000,
    headers: normalizeNamedItems(request.headers),
    query: normalizeNamedItems(request.params),
    cookies: [],
    form_fields: ['form', 'urlencoded'].includes(fallbackBodyState.body_mode) ? normalizeNamedItems(request.body || {}) : [],
    multipart_parts: fallbackBodyState.body_mode === 'multipart' ? normalizeNamedItems(request.body || {}) : [],
    files: [],
    auth: createRequestAuthSpec(),
    transport: createRequestTransportSpec(),
  }

  return createEmptyHttpEditorModel({
    method: spec.method || request.method,
    url: spec.url || request.url,
    body_mode: spec.body_mode || 'none',
    timeout_ms: spec.timeout_ms || request.timeout_ms || 30000,
    headers: normalizeNamedItems(spec.headers),
    query: normalizeNamedItems(spec.query),
    cookies: normalizeNamedItems(spec.cookies),
    form_fields: normalizeNamedItems(spec.form_fields),
    multipart_parts: normalizeNamedItems(spec.multipart_parts),
    files: normalizeFiles(spec.files),
    auth: createRequestAuthSpec(spec.auth || {}),
    transport: createRequestTransportSpec(spec.transport || {}),
    assertions: normalizeAssertions(request.assertion_specs || request.assertions),
    extractors: normalizeExtractors(request.extractor_specs),
    body_json_text: stringifyJson(spec.body_json, '{}'),
    raw_text: spec.raw_text || '',
    xml_text: spec.xml_text || '',
    binary_base64: spec.binary_base64 || '',
    graphql_query: spec.graphql_query || '',
    graphql_operation_name: spec.graphql_operation_name || '',
    graphql_variables_text: stringifyJson(spec.graphql_variables, '{}'),
  })
}

export const requestFormToHttpEditorModel = (form: ApiRequestForm): ApiHttpEditorModel => {
  const bodyState = requestBodyToEditorState(form.body_type, form.body, form.headers || {})
  return createEmptyHttpEditorModel({
    method: form.method,
    url: form.url,
    body_mode: bodyState.body_mode,
    timeout_ms: form.timeout_ms || 30000,
    headers: normalizeNamedItems(form.headers || {}),
    query: normalizeNamedItems(form.params || {}),
    form_fields: ['form', 'urlencoded'].includes(bodyState.body_mode) ? normalizeNamedItems(form.body || {}) : [],
    multipart_parts: bodyState.body_mode === 'multipart' ? normalizeNamedItems(form.body || {}) : [],
    assertions: normalizeAssertions(form.assertions as ApiAssertionSpec[]),
    body_json_text: bodyState.body_mode === 'json' ? stringifyJson(form.body, '{}') : '{}',
    raw_text: bodyState.raw_text,
    xml_text: bodyState.xml_text,
  })
}

export const testCaseToHttpEditorModel = (
  testCase?: ApiTestCase | null,
  baseRequest?: ApiRequest | null
): ApiHttpEditorModel => {
  if (!testCase) {
    return createEmptyHttpEditorModel({
      auth: createOverrideAuthSpec(),
      transport: createOverrideTransportSpec(),
      assertions: [createAssertionSpec()],
    })
  }

  const spec = testCase.request_override_spec || overrideFromLegacyScript(testCase)
  const fallbackRequest: ApiRequest | null =
    baseRequest ||
    (testCase.request_method && testCase.request_url
      ? ({
          id: testCase.request || 0,
          collection: testCase.collection_id || 0,
          collection_name: testCase.collection_name || '',
          name: testCase.request_name || '',
          description: '',
          method: testCase.request_method || 'GET',
          url: testCase.request_url || '',
          headers: {},
          params: {},
          body_type: 'none',
          body: {},
          assertions: [],
          timeout_ms: 30000,
          order: 0,
          created_by: null,
          created_at: testCase.created_at,
          updated_at: testCase.updated_at,
        } as ApiRequest)
      : null)

  const baseModel = fallbackRequest
    ? requestToHttpEditorModel(fallbackRequest)
    : createEmptyHttpEditorModel({
        method: testCase.request_method || 'GET',
        url: testCase.request_url || '',
        auth: createOverrideAuthSpec(),
        transport: createOverrideTransportSpec(),
      })

  const mergedModel = mergeRequestEditorModel(baseModel, spec)
  return createEmptyHttpEditorModel({
    ...cloneJson(mergedModel),
    auth: createOverrideAuthSpec(mergedModel.auth || {}),
    transport: createOverrideTransportSpec(mergedModel.transport || {}),
    assertions: normalizeAssertions(testCase.assertion_specs || testCase.assertions),
    extractors: normalizeExtractors(testCase.extractor_specs),
  })
}

const normalizeNamedItemsForSubmit = (items: ApiNamedValueSpec[]) =>
  items
    .map((item, index) => ({
      id: item.id,
      name: item.name?.trim() || '',
      value: item.value ?? '',
      enabled: item.enabled ?? true,
      order: index,
    }))
    .filter(item => item.name)

const normalizeFilesForSubmit = (items: ApiFileSpec[]) =>
  items
    .map((item, index) => ({
      id: item.id,
      field_name: item.field_name?.trim() || '',
      source_type: item.source_type,
      file_path: item.file_path || '',
      file_name: item.file_name || '',
      content_type: item.content_type || '',
      base64_content: item.base64_content || '',
      enabled: item.enabled ?? true,
      order: index,
    }))
    .filter(item => item.field_name)

const normalizeAssertionsForSubmit = (items: ApiAssertionSpec[]) =>
  items
    .map((item, index) => {
      const assertionType = item.assertion_type
      const expectedValueKind = inferAssertionExpectedValueKind(item)
      const payload = {
        id: item.id,
        enabled: item.enabled ?? true,
        order: index,
        assertion_type: assertionType,
        target: item.target || '',
        selector: item.selector || '',
        operator: item.operator || 'equals',
        expected_text: '',
        expected_number: null as number | null,
        expected_json: {} as Record<string, any> | any[],
        min_value: item.min_value ?? null,
        max_value: item.max_value ?? null,
        schema_text: item.schema_text || '',
      }

      if (['json_schema', 'openapi_contract'].includes(assertionType)) {
        return payload
      }

      if (assertionType === 'status_range') {
        return payload
      }

      if (['exists', 'not_exists'].includes(assertionType)) {
        return payload
      }

      if (['status_code', 'array_length', 'response_time'].includes(assertionType)) {
        payload.expected_number = item.expected_number ?? null
        return payload
      }

      if (assertionType === 'json_path') {
        if (expectedValueKind === 'json') {
          payload.expected_json = parseJsonText(item.expected_json_text || stringifyJson(item.expected_json, '{}'), {})
        } else if (expectedValueKind === 'number') {
          payload.expected_number = item.expected_number ?? null
        } else {
          payload.expected_text = item.expected_text || ''
        }
        return payload
      }

      payload.expected_text = item.expected_text || ''
      return payload
    })
    .filter(item => item.assertion_type)

const normalizeExtractorsForSubmit = (items: ApiExtractorSpec[]) =>
  items
    .map((item, index) => ({
      id: item.id,
      enabled: item.enabled ?? true,
      order: index,
      source: item.source,
      selector: item.selector || '',
      variable_name: item.variable_name?.trim() || '',
      default_value: item.default_value || '',
      required: item.required ?? false,
    }))
    .filter(item => item.variable_name)

export const httpEditorModelToRequestSpec = (model: ApiHttpEditorModel): ApiRequestSpecPayload => ({
  method: model.method,
  url: model.url,
  body_mode: model.body_mode,
  body_json: model.body_mode === 'json' ? parseJsonText(model.body_json_text, {}) : {},
  raw_text: model.body_mode === 'raw' ? model.raw_text : '',
  xml_text: model.body_mode === 'xml' ? model.xml_text : '',
  binary_base64: model.body_mode === 'binary' ? model.binary_base64 : '',
  graphql_query: model.body_mode === 'graphql' ? model.graphql_query : '',
  graphql_operation_name: model.body_mode === 'graphql' ? model.graphql_operation_name : '',
  graphql_variables: model.body_mode === 'graphql' ? parseJsonText(model.graphql_variables_text, {}) : {},
  timeout_ms: Number(model.timeout_ms || 30000),
  headers: normalizeNamedItemsForSubmit(model.headers),
  query: normalizeNamedItemsForSubmit(model.query),
  cookies: normalizeNamedItemsForSubmit(model.cookies),
  form_fields: normalizeNamedItemsForSubmit(model.form_fields),
  multipart_parts: normalizeNamedItemsForSubmit(model.multipart_parts),
  files: normalizeFilesForSubmit(model.files),
  auth: cloneJson(model.auth),
  transport: cloneJson(model.transport),
})

export const httpEditorModelToTestCaseOverrideSpec = (
  model: ApiHttpEditorModel,
  baseRequest?: ApiRequest | null
): ApiTestCaseOverrideSpecPayload => {
  const currentRequestSpec = httpEditorModelToRequestSpec(model)
  if (!baseRequest) {
    return currentRequestSpec
  }

  const baseRequestSpec = httpEditorModelToRequestSpec(requestToHttpEditorModel(baseRequest))
  const replaceFields = [
    'headers',
    'query',
    'cookies',
    'form_fields',
    'multipart_parts',
    'files',
    'body_mode',
    'body_json',
    'raw_text',
    'xml_text',
    'binary_base64',
    'graphql_query',
    'graphql_operation_name',
    'graphql_variables',
    'auth',
    'transport',
  ].filter(field => !isDeepEqual((currentRequestSpec as Record<string, any>)[field], (baseRequestSpec as Record<string, any>)[field]))

  return {
    ...currentRequestSpec,
    ...(replaceFields.length ? { replace_fields: replaceFields } : {}),
  }
}

export const httpEditorModelToAssertionSpecs = (model: ApiHttpEditorModel) => normalizeAssertionsForSubmit(model.assertions)

export const httpEditorModelToExtractorSpecs = (model: ApiHttpEditorModel) => normalizeExtractorsForSubmit(model.extractors)

export const workflowStepToHttpEditorModel = (
  step?: ApiTestCaseWorkflowStep | null,
  request?: ApiRequest | null
): ApiHttpEditorModel => {
  const baseModel = requestToHttpEditorModel(request)
  const mergedModel = mergeRequestEditorModel(baseModel, step?.request_overrides)

  return createEmptyHttpEditorModel({
    ...cloneJson(mergedModel),
    assertions: Array.isArray(step?.assertion_specs)
      ? normalizeAssertions(step?.assertion_specs)
      : cloneJson(baseModel.assertions),
    extractors: Array.isArray(step?.extractor_specs)
      ? normalizeExtractors(step?.extractor_specs)
      : cloneJson(baseModel.extractors),
  })
}

export const createWorkflowStepEditorStep = (
  overrides: Partial<ApiTestCaseWorkflowEditorStep> = {},
  options: {
    request?: ApiRequest | null
    mainRequest?: ApiRequest | null
    index?: number
  } = {}
): ApiTestCaseWorkflowEditorStep => {
  const boundRequest = options.request || options.mainRequest || null
  const referencesMainRequest = Boolean(boundRequest && options.mainRequest && boundRequest.id === options.mainRequest.id)
  const defaultName = boundRequest?.name || `步骤 ${(options.index ?? 0) + 1}`

  return {
    key: overrides.key || createWorkflowStepKey(),
    name: overrides.name || defaultName,
    stage: overrides.stage || 'prepare',
    enabled: overrides.enabled ?? true,
    request_id:
      overrides.request_id !== undefined
        ? overrides.request_id
        : referencesMainRequest
          ? null
          : boundRequest?.id ?? null,
    request_name:
      overrides.request_name !== undefined
        ? overrides.request_name
        : referencesMainRequest
          ? ''
          : boundRequest?.name || '',
    continue_on_failure: overrides.continue_on_failure ?? false,
    editor: overrides.editor
      ? createEmptyHttpEditorModel(cloneJson(overrides.editor))
      : workflowStepToHttpEditorModel(undefined, boundRequest),
  }
}

export const workflowStepToEditorStep = (
  step?: ApiTestCaseWorkflowStep | null,
  options: {
    request?: ApiRequest | null
    mainRequest?: ApiRequest | null
    index?: number
  } = {}
): ApiTestCaseWorkflowEditorStep => {
  const boundRequest = options.request || options.mainRequest || null
  const referencesMainRequest = Boolean(
    boundRequest &&
      options.mainRequest &&
      boundRequest.id === options.mainRequest.id &&
      (step?.request_id === null || step?.request_id === undefined || step?.request_id === boundRequest.id)
  )

  return {
    key: createWorkflowStepKey(),
    name: String(step?.name || boundRequest?.name || `步骤 ${(options.index ?? 0) + 1}`).trim(),
    stage:
      step?.stage === 'prepare' || step?.stage === 'request' || step?.stage === 'teardown'
        ? step.stage
        : 'prepare',
    enabled: step?.enabled ?? true,
    request_id: referencesMainRequest ? null : (options.request?.id ?? step?.request_id ?? null),
    request_name: referencesMainRequest ? '' : (options.request?.name || step?.request_name || ''),
    continue_on_failure: step?.continue_on_failure ?? false,
    editor: workflowStepToHttpEditorModel(step, boundRequest),
  }
}

export const workflowEditorStepToPayload = (
  step: ApiTestCaseWorkflowEditorStep,
  options: {
    request?: ApiRequest | null
    mainRequest?: ApiRequest | null
  } = {}
): ApiTestCaseWorkflowStep => {
  const baseRequest = options.request || options.mainRequest || null
  const baseEditor = workflowStepToHttpEditorModel(undefined, baseRequest)

  const payload: ApiTestCaseWorkflowStep = {
    name: String(step.name || '').trim() || baseRequest?.name || 'workflow_step',
    stage: step.stage,
    enabled: step.enabled,
    continue_on_failure: step.continue_on_failure,
  }

  if (options.request && (!options.mainRequest || options.request.id !== options.mainRequest.id)) {
    payload.request_id = options.request.id
    payload.request_name = options.request.name
  } else if (!options.request && step.request_id) {
    payload.request_id = step.request_id
    payload.request_name = step.request_name
  }

  const currentRequestSpec = httpEditorModelToRequestSpec(step.editor)
  const baseRequestSpec = httpEditorModelToRequestSpec(baseEditor)
  if (!isDeepEqual(currentRequestSpec, baseRequestSpec)) {
    const replaceFields = [
      'headers',
      'query',
      'cookies',
      'form_fields',
      'multipart_parts',
      'files',
      'body_json',
      'raw_text',
      'xml_text',
      'binary_base64',
      'graphql_query',
      'graphql_operation_name',
      'graphql_variables',
    ].filter(field => !isDeepEqual((currentRequestSpec as Record<string, any>)[field], (baseRequestSpec as Record<string, any>)[field]))

    payload.request_overrides = {
      ...currentRequestSpec,
      ...(replaceFields.length ? { replace_fields: replaceFields } : {}),
    }
  }

  const currentAssertions = httpEditorModelToAssertionSpecs(step.editor)
  const baseAssertions = httpEditorModelToAssertionSpecs(baseEditor)
  if (!isDeepEqual(currentAssertions, baseAssertions)) {
    payload.assertion_specs = currentAssertions
  }

  const currentExtractors = httpEditorModelToExtractorSpecs(step.editor)
  const baseExtractors = httpEditorModelToExtractorSpecs(baseEditor)
  if (!isDeepEqual(currentExtractors, baseExtractors)) {
    payload.extractor_specs = currentExtractors
  }

  return payload
}

export const bodyModeToLegacyBodyType = (bodyMode: ApiBodyMode): 'none' | 'json' | 'form' | 'raw' => {
  if (bodyMode === 'json' || bodyMode === 'graphql') return 'json'
  if (bodyMode === 'form' || bodyMode === 'urlencoded' || bodyMode === 'multipart') return 'form'
  if (bodyMode === 'none') return 'none'
  return 'raw'
}

export const requestSpecToLegacyBody = (spec: ApiRequestSpecPayload) => {
  if (spec.body_mode === 'json') {
    return spec.body_json || {}
  }
  if (spec.body_mode === 'form' || spec.body_mode === 'urlencoded') {
    return Object.fromEntries(normalizeNamedItemsForSubmit(spec.form_fields).map(item => [item.name, item.value]))
  }
  if (spec.body_mode === 'multipart') {
    return Object.fromEntries(normalizeNamedItemsForSubmit(spec.multipart_parts).map(item => [item.name, item.value]))
  }
  if (spec.body_mode === 'graphql') {
    return {
      query: spec.graphql_query || '',
      operationName: spec.graphql_operation_name || '',
      variables: spec.graphql_variables || {},
    }
  }
  if (spec.body_mode === 'xml') return spec.xml_text || ''
  if (spec.body_mode === 'binary') return spec.binary_base64 || ''
  if (spec.body_mode === 'raw') return spec.raw_text || ''
  return {}
}

export const requestSpecToLegacyHeaders = (spec: ApiRequestSpecPayload) =>
  Object.fromEntries(normalizeNamedItemsForSubmit(spec.headers).map(item => [item.name, item.value]))

export const requestSpecToLegacyParams = (spec: ApiRequestSpecPayload) =>
  Object.fromEntries(normalizeNamedItemsForSubmit(spec.query).map(item => [item.name, item.value]))

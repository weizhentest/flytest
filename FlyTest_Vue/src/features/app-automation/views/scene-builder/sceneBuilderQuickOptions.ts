export interface QuickOption {
  label: string
  value: string
}

export const selectorTypeOptions: QuickOption[] = [
  { label: '???', value: 'element' },
  { label: '??', value: 'text' },
  { label: '?? ID', value: 'id' },
  { label: '??', value: 'desc' },
  { label: 'XPath', value: 'xpath' },
  { label: '??', value: 'image' },
  { label: '??', value: 'region' },
  { label: '??', value: 'pos' },
]

export const matchModeOptions: QuickOption[] = [
  { label: '??', value: 'contains' },
  { label: '????', value: 'exact' },
  { label: '????', value: 'regex' },
]

export const assertTypeOptions: QuickOption[] = [
  { label: '????', value: 'condition' },
  { label: '????', value: 'exists' },
  { label: '?????', value: 'not_exists' },
  { label: '????', value: 'image' },
  { label: 'OCR ??', value: 'text' },
  { label: 'OCR ??', value: 'number' },
  { label: 'OCR ??', value: 'regex' },
  { label: 'OCR ??', value: 'range' },
]

export const assertOperatorOptions: QuickOption[] = [
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

export const swipeDirectionOptions: QuickOption[] = [
  { label: '??', value: 'up' },
  { label: '??', value: 'down' },
  { label: '??', value: 'left' },
  { label: '??', value: 'right' },
]

export const variableScopeOptions: QuickOption[] = [
  { label: '??', value: 'local' },
  { label: '??', value: 'global' },
]

export const httpMethodOptions: QuickOption[] = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'PATCH', value: 'PATCH' },
  { label: 'DELETE', value: 'DELETE' },
]

export const responseTypeOptions: QuickOption[] = [
  { label: '????', value: 'auto' },
  { label: 'JSON', value: 'json' },
  { label: '??', value: 'text' },
  { label: '???', value: 'binary' },
]


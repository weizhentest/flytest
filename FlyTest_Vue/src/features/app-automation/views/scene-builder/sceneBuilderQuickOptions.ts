export interface QuickOption {
  label: string
  value: string
}

export const selectorTypeOptions: QuickOption[] = [
  { label: '元素', value: 'element' },
  { label: '文本', value: 'text' },
  { label: '资源 ID', value: 'id' },
  { label: '描述', value: 'desc' },
  { label: 'XPath', value: 'xpath' },
  { label: '图像', value: 'image' },
  { label: '区域', value: 'region' },
  { label: '坐标', value: 'pos' },
]

export const matchModeOptions: QuickOption[] = [
  { label: '包含', value: 'contains' },
  { label: '完全匹配', value: 'exact' },
  { label: '正则匹配', value: 'regex' },
]

export const assertTypeOptions: QuickOption[] = [
  { label: '条件判断', value: 'condition' },
  { label: '元素存在', value: 'exists' },
  { label: '元素不存在', value: 'not_exists' },
  { label: '图像断言', value: 'image' },
  { label: 'OCR 文本', value: 'text' },
  { label: 'OCR 数字', value: 'number' },
  { label: 'OCR 正则', value: 'regex' },
  { label: 'OCR 范围', value: 'range' },
]

export const assertOperatorOptions: QuickOption[] = [
  { label: '等于', value: '==' },
  { label: '不等于', value: '!=' },
  { label: '大于', value: '>' },
  { label: '大于等于', value: '>=' },
  { label: '小于', value: '<' },
  { label: '小于等于', value: '<=' },
  { label: '包含', value: 'contains' },
  { label: '匹配', value: 'regex' },
  { label: '为真', value: 'truthy' },
  { label: '为假', value: 'falsy' },
]

export const swipeDirectionOptions: QuickOption[] = [
  { label: '上滑', value: 'up' },
  { label: '下滑', value: 'down' },
  { label: '左滑', value: 'left' },
  { label: '右滑', value: 'right' },
]

export const variableScopeOptions: QuickOption[] = [
  { label: '局部', value: 'local' },
  { label: '全局', value: 'global' },
]

export const httpMethodOptions: QuickOption[] = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'PATCH', value: 'PATCH' },
  { label: 'DELETE', value: 'DELETE' },
]

export const responseTypeOptions: QuickOption[] = [
  { label: '自动识别', value: 'auto' },
  { label: 'JSON', value: 'json' },
  { label: '文本', value: 'text' },
  { label: '二进制', value: 'binary' },
]


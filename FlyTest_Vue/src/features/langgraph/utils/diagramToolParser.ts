export interface DiagramToolPayload {
  action: 'display' | 'edit';
  xml?: string;
  pageName?: string;
}

type JsonRecord = Record<string, unknown>;

const MAX_PARSE_DEPTH = 4;

const safeJsonParse = (value: string): unknown | null => {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const stripCodeFence = (value: string): string => {
  const trimmed = value.trim();
  const match = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : trimmed;
};

const unescapeXml = (xml: string): string => {
  if (!xml.includes('\\')) return xml;
  return xml
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\');
};

const normalizeDiagramPayload = (value: JsonRecord): DiagramToolPayload | null => {
  const actionValue = value.action;
  const action = actionValue === 'display' || actionValue === 'edit' ? actionValue : null;
  if (!action) return null;

  const payload: DiagramToolPayload = { action };

  if (typeof value.xml === 'string' && value.xml.trim()) {
    payload.xml = unescapeXml(value.xml);
  }

  if (typeof value.page_name === 'string' && value.page_name.trim()) {
    payload.pageName = value.page_name.trim();
  }

  return payload;
};

const parseFromString = (value: string, depth: number): DiagramToolPayload | null => {
  if (depth > MAX_PARSE_DEPTH) return null;

  const normalized = stripCodeFence(value);
  if (!normalized) return null;

  const directJson = safeJsonParse(normalized);
  if (directJson !== null) {
    const parsed = parseDiagramToolPayloadFromUnknown(directJson, depth + 1);
    if (parsed) return parsed;
  }

  const toolBlockRegex = /(display_diagram|edit_diagram)\s*:\s*\n?([\s\S]*?)(?=\n{2,}\w+\s*:|$)/g;
  let toolMatch: RegExpExecArray | null = null;
  while ((toolMatch = toolBlockRegex.exec(normalized)) !== null) {
    const body = toolMatch[2]?.trim();
    if (!body) continue;
    const parsed = parseFromString(body, depth + 1);
    if (parsed) return parsed;
  }

  const escapedJson = safeJsonParse(
    normalized.replace(/\\\\"/g, '\\"').replace(/\\\\n/g, '\\n')
  );
  if (escapedJson !== null) {
    const parsed = parseDiagramToolPayloadFromUnknown(escapedJson, depth + 1);
    if (parsed) return parsed;
  }

  const inlineJsonMatch = normalized.match(/\{[\s\S]*"action"\s*:\s*"(display|edit)"[\s\S]*\}/);
  if (inlineJsonMatch && inlineJsonMatch[0]) {
    const inlineJson = safeJsonParse(inlineJsonMatch[0]);
    if (inlineJson !== null) {
      return parseDiagramToolPayloadFromUnknown(inlineJson, depth + 1);
    }
  }

  return null;
};

const parseDiagramToolPayloadFromUnknown = (
  value: unknown,
  depth = 0
): DiagramToolPayload | null => {
  if (depth > MAX_PARSE_DEPTH || value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return parseFromString(value, depth + 1);
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const parsed = parseDiagramToolPayloadFromUnknown(item, depth + 1);
      if (parsed) return parsed;
    }
    return null;
  }

  if (typeof value === 'object') {
    const record = value as JsonRecord;
    const normalized = normalizeDiagramPayload(record);
    if (normalized) return normalized;

    if (typeof record.text === 'string') {
      const parsedFromText = parseFromString(record.text, depth + 1);
      if (parsedFromText) return parsedFromText;
    }
  }

  return null;
};

export const extractDiagramToolPayload = (content: string): DiagramToolPayload | null => {
  if (!content || !content.trim()) return null;
  return parseDiagramToolPayloadFromUnknown(content);
};

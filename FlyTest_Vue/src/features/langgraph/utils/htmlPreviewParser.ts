type JsonLike = Record<string, unknown>;

const DOCTYPE_RE = /<!doctype\s+html[^>]*>/i;
const HTML_BLOCK_RE = /<html[\s\S]*?<\/html>/i;
const CODE_BLOCK_RE = /```(?:html|HTML)?\s*([\s\S]*?)```/g;
const OPEN_CODE_BLOCK_RE = /```(?:html|HTML)?\s*([\s\S]*)$/;
const HTML_SNIPPET_TAG_RE = /<(html|head|body|div|section|article|main|header|footer|form|table|ul|ol|li|style|script|svg|canvas|p|h[1-6]|button|input|textarea|select)\b/i;
const MAX_DEPTH = 4;

const decodeHtmlEntities = (value: string): string => {
  if (!value || !value.includes('&')) return value;
  return value
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'");
};

const extractHtmlDocument = (value: string): string | null => {
  if (!value) return null;
  const content = value.trim();
  if (!content) return null;

  const doctypeMatch = content.match(DOCTYPE_RE);
  if (doctypeMatch && typeof doctypeMatch.index === 'number') {
    const tail = content.slice(doctypeMatch.index);
    const endTagIndex = tail.toLowerCase().lastIndexOf('</html>');
    if (endTagIndex >= 0) {
      return tail.slice(0, endTagIndex + 7).trim();
    }
    return tail.trim();
  }

  const htmlBlock = content.match(HTML_BLOCK_RE);
  if (htmlBlock?.[0]) {
    return htmlBlock[0].trim();
  }

  return null;
};

const safeJsonParse = (value: string): unknown | null => {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const decodeEscapedSequence = (value: string): string => {
  if (!value || value.indexOf('\\') === -1) return value;
  return value
    .replace(/\\u([0-9a-fA-F]{4})/g, (_match, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\');
};

const looksLikeHtmlSnippet = (value: string): boolean => {
  if (!value) return false;
  return HTML_SNIPPET_TAG_RE.test(value);
};

const wrapHtmlSnippet = (snippet: string): string => {
  const trimmed = snippet.trim();
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>HTML Preview</title>
</head>
<body>
${trimmed}
</body>
</html>`;
};

const parseFromUnknown = (value: unknown, depth = 0): string | null => {
  if (depth > MAX_DEPTH || value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    const decoded = decodeHtmlEntities(value);

    const direct = extractHtmlDocument(decoded);
    if (direct) return direct;

    const unescaped = decodeEscapedSequence(decoded);
    if (unescaped !== decoded) {
      const fromUnescaped = extractHtmlDocument(unescaped);
      if (fromUnescaped) return fromUnescaped;
    }

    CODE_BLOCK_RE.lastIndex = 0;
    let codeMatch: RegExpExecArray | null = null;
    while ((codeMatch = CODE_BLOCK_RE.exec(decoded)) !== null) {
      const block = codeMatch[1]?.trim();
      if (!block) continue;
      const parsedBlock = extractHtmlDocument(block);
      if (parsedBlock) return parsedBlock;

      const unescapedBlock = decodeEscapedSequence(block);
      if (unescapedBlock !== block) {
        const parsedUnescapedBlock = extractHtmlDocument(unescapedBlock);
        if (parsedUnescapedBlock) return parsedUnescapedBlock;
      }

      if (looksLikeHtmlSnippet(block)) {
        return wrapHtmlSnippet(block);
      }
      if (looksLikeHtmlSnippet(unescapedBlock)) {
        return wrapHtmlSnippet(unescapedBlock);
      }
    }

    // 兼容流式未闭合代码块
    const openCodeMatch = decoded.match(OPEN_CODE_BLOCK_RE);
    if (openCodeMatch?.[1]) {
      const openBlock = openCodeMatch[1].trim();
      if (openBlock) {
        const parsedOpenBlock = extractHtmlDocument(openBlock);
        if (parsedOpenBlock) return parsedOpenBlock;

        const unescapedOpenBlock = decodeEscapedSequence(openBlock);
        const parsedUnescapedOpenBlock = extractHtmlDocument(unescapedOpenBlock);
        if (parsedUnescapedOpenBlock) return parsedUnescapedOpenBlock;

        if (looksLikeHtmlSnippet(openBlock)) {
          return wrapHtmlSnippet(openBlock);
        }
        if (looksLikeHtmlSnippet(unescapedOpenBlock)) {
          return wrapHtmlSnippet(unescapedOpenBlock);
        }
      }
    }

    const asJson = safeJsonParse(decoded);
    if (asJson !== null) {
      return parseFromUnknown(asJson, depth + 1);
    }

    // 兜底：整段文本不是完整 HTML 文档，但看起来像 HTML 片段
    if (looksLikeHtmlSnippet(decoded)) {
      return wrapHtmlSnippet(decoded);
    }
    const unescapedDecoded = decodeEscapedSequence(decoded);
    if (unescapedDecoded !== decoded && looksLikeHtmlSnippet(unescapedDecoded)) {
      return wrapHtmlSnippet(unescapedDecoded);
    }

    return null;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const parsed = parseFromUnknown(item, depth + 1);
      if (parsed) return parsed;
    }
    return null;
  }

  if (typeof value === 'object') {
    const record = value as JsonLike;
    for (const key of Object.keys(record)) {
      const parsed = parseFromUnknown(record[key], depth + 1);
      if (parsed) return parsed;
    }
  }

  return null;
};

export const extractHtmlPreviewContent = (content: string): string | null => {
  if (!content || !content.trim()) return null;
  return parseFromUnknown(content);
};

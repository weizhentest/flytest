from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any


TOOL_CATEGORIES: list[dict[str, Any]] = [
    {
        "category": "string",
        "name": "字符工具",
        "description": "文本处理、对比、统计和格式化",
        "icon": "icon-font-colors",
    },
    {
        "category": "encoding",
        "name": "编码工具",
        "description": "编码转换、时间戳、二维码与条形码",
        "icon": "icon-code-block",
    },
    {
        "category": "random",
        "name": "随机工具",
        "description": "随机数、随机字符串、UUID 等常用生成器",
        "icon": "icon-shuffle",
    },
    {
        "category": "encryption",
        "name": "加密工具",
        "description": "哈希、AES、HMAC 与加解密辅助",
        "icon": "icon-lock",
    },
    {
        "category": "test_data",
        "name": "测试数据",
        "description": "中文姓名、手机号、邮箱、地址生成",
        "icon": "icon-user-group",
    },
    {
        "category": "json",
        "name": "JSON工具",
        "description": "JSON 校验、对比、转换与查询",
        "icon": "icon-file",
    },
    {
        "category": "crontab",
        "name": "Crontab工具",
        "description": "表达式生成、解析、校验和下次执行时间",
        "icon": "icon-clock-circle",
    },
]

TOOL_SCENARIOS: list[dict[str, str]] = [
    {
        "scenario": "data_generation",
        "name": "数据生成",
        "description": "生成测试数据、随机数据和计划表达式",
    },
    {
        "scenario": "format_conversion",
        "name": "格式转换",
        "description": "编码、大小写、结构化文本和跨格式转换",
    },
    {
        "scenario": "data_validation",
        "name": "数据验证",
        "description": "文本差异、正则、JSON 校验和 Crontab 检查",
    },
    {
        "scenario": "encryption_decryption",
        "name": "加密解密",
        "description": "哈希、AES 和签名相关能力",
    },
]


def _field(
    name: str,
    label: str,
    field_type: str,
    *,
    required: bool = False,
    default: Any = None,
    placeholder: str = "",
    options: list[dict[str, Any]] | None = None,
    rows: int | None = None,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    help_text: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "default": default,
        "placeholder": placeholder,
    }
    if options is not None:
        data["options"] = options
    if rows is not None:
        data["rows"] = rows
    if min_value is not None:
        data["min"] = min_value
    if max_value is not None:
        data["max"] = max_value
    if help_text:
        data["help_text"] = help_text
    return data


TOOLS: list[dict[str, Any]] = [
    {
        "name": "normalize_string",
        "display_name": "字符串处理",
        "description": "裁剪、去空白、压缩空格或清理换行",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-eraser",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=5, placeholder="请输入要处理的文本"),
            _field(
                "mode",
                "处理方式",
                "select",
                required=True,
                default="trim",
                options=[
                    {"label": "首尾裁剪", "value": "trim"},
                    {"label": "移除所有空白", "value": "remove_all_whitespace"},
                    {"label": "压缩连续空格", "value": "collapse_spaces"},
                    {"label": "移除空行", "value": "remove_blank_lines"},
                    {"label": "仅保留单行", "value": "single_line"},
                ],
            ),
        ],
    },
    {
        "name": "text_diff",
        "display_name": "文本对比",
        "description": "对比两段文本的差异并给出相似度",
        "category": "string",
        "scenario": "data_validation",
        "icon": "icon-branch",
        "result_kind": "json",
        "fields": [
            _field("left_text", "文本 A", "textarea", required=True, rows=6, placeholder="请输入第一段文本"),
            _field("right_text", "文本 B", "textarea", required=True, rows=6, placeholder="请输入第二段文本"),
        ],
    },
    {
        "name": "regex_test",
        "display_name": "正则表达式测试",
        "description": "校验正则表达式并返回匹配结果",
        "category": "string",
        "scenario": "data_validation",
        "icon": "icon-search",
        "result_kind": "json",
        "fields": [
            _field("pattern", "正则表达式", "text", required=True, placeholder=r"例如：^[a-zA-Z0-9_]+$"),
            _field("text", "测试文本", "textarea", required=True, rows=5, placeholder="请输入要测试的文本"),
            _field("flags", "修饰符", "multi-select", default=["m"], options=[
                {"label": "忽略大小写 i", "value": "i"},
                {"label": "多行 m", "value": "m"},
                {"label": "点号匹配换行 s", "value": "s"},
            ]),
        ],
    },
    {
        "name": "word_count",
        "display_name": "字数统计",
        "description": "统计字符数、字数、行数和中文字符数",
        "category": "string",
        "scenario": "data_validation",
        "icon": "icon-list",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=6, placeholder="请输入要统计的文本"),
        ],
    },
    {
        "name": "case_convert",
        "display_name": "大小写转换",
        "description": "支持 upper、lower、title、camel、snake 等转换",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-font-size",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4, placeholder="请输入要转换的文本"),
            _field(
                "target_case",
                "目标格式",
                "select",
                required=True,
                default="upper",
                options=[
                    {"label": "UPPER", "value": "upper"},
                    {"label": "lower", "value": "lower"},
                    {"label": "Title Case", "value": "title"},
                    {"label": "Capitalize", "value": "capitalize"},
                    {"label": "swapCase", "value": "swapcase"},
                    {"label": "camelCase", "value": "camel"},
                    {"label": "PascalCase", "value": "pascal"},
                    {"label": "snake_case", "value": "snake"},
                    {"label": "kebab-case", "value": "kebab"},
                ],
            ),
        ],
    },
    {
        "name": "replace_string",
        "display_name": "字符串替换",
        "description": "支持普通替换或正则替换",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-edit",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4, placeholder="请输入原文本"),
            _field("search", "查找内容", "text", required=True, placeholder="请输入要查找的内容"),
            _field("replace", "替换内容", "text", default="", placeholder="请输入替换内容"),
            _field("use_regex", "使用正则", "switch", default=False),
            _field("ignore_case", "忽略大小写", "switch", default=False),
            _field("count", "最大替换次数", "number", default=0, min_value=0, help_text="0 表示全部替换"),
        ],
    },
    {
        "name": "split_text",
        "display_name": "文本分割",
        "description": "按指定分隔符拆分文本为列表",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-menu-unfold",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=5, placeholder="请输入待分割文本"),
            _field("delimiter", "分隔符", "text", required=True, default=",", placeholder="例如：, 或 \\n"),
            _field("trim_items", "去除每项首尾空白", "switch", default=True),
            _field("remove_empty", "移除空项", "switch", default=True),
        ],
    },
    {
        "name": "join_text",
        "display_name": "文本拼接",
        "description": "将列表或多行文本按分隔符重新拼接",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-menu-fold",
        "result_kind": "json",
        "fields": [
            _field("items", "列表数据", "textarea", required=True, rows=5, placeholder='可输入 JSON 数组，或按行输入多个值'),
            _field("delimiter", "连接符", "text", required=True, default=",", placeholder="例如：,、|、\\n"),
            _field("prefix", "前缀", "text", default="", placeholder="可选"),
            _field("suffix", "后缀", "text", default="", placeholder="可选"),
        ],
    },
    {
        "name": "string_format",
        "display_name": "字符串格式化",
        "description": "模板替换、反转、补位等常见格式化操作",
        "category": "string",
        "scenario": "format_conversion",
        "icon": "icon-align-center",
        "result_kind": "json",
        "fields": [
            _field(
                "format_type",
                "格式化方式",
                "select",
                required=True,
                default="template",
                options=[
                    {"label": "模板替换", "value": "template"},
                    {"label": "文本反转", "value": "reverse"},
                    {"label": "左补位", "value": "ljust"},
                    {"label": "右补位", "value": "rjust"},
                    {"label": "居中补位", "value": "center"},
                ],
            ),
            _field("text", "输入文本", "textarea", required=True, rows=4, placeholder="请输入文本或模板"),
            _field("variables", "模板变量", "json", default={}, placeholder='例如：{"name":"FlyTest"}'),
            _field("width", "补位宽度", "number", default=20, min_value=1),
            _field("fillchar", "补位字符", "text", default=" ", placeholder="默认空格"),
        ],
    },
    {
        "name": "base64_encode",
        "display_name": "Base64 编码",
        "description": "将文本编码为 Base64",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4, placeholder="请输入待编码文本"),
            _field("encoding", "字符集", "text", default="utf-8", placeholder="默认 utf-8"),
        ],
    },
    {
        "name": "base64_decode",
        "display_name": "Base64 解码",
        "description": "将 Base64 内容还原为文本",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-unlock",
        "result_kind": "json",
        "fields": [
            _field("text", "Base64 内容", "textarea", required=True, rows=4, placeholder="请输入 Base64 字符串"),
            _field("encoding", "字符集", "text", default="utf-8", placeholder="默认 utf-8"),
        ],
    },
    {
        "name": "timestamp_convert",
        "display_name": "时间戳转换",
        "description": "秒、毫秒与日期时间互转",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-clock-circle",
        "result_kind": "json",
        "fields": [
            _field(
                "mode",
                "转换方向",
                "select",
                required=True,
                default="seconds_to_datetime",
                options=[
                    {"label": "秒 -> 日期时间", "value": "seconds_to_datetime"},
                    {"label": "毫秒 -> 日期时间", "value": "milliseconds_to_datetime"},
                    {"label": "日期时间 -> 秒", "value": "datetime_to_seconds"},
                    {"label": "日期时间 -> 毫秒", "value": "datetime_to_milliseconds"},
                ],
            ),
            _field("value", "输入值", "text", required=True, placeholder="例如：1712381880 或 2026-04-06 12:30:00"),
            _field("timezone", "时区", "text", default="Asia/Shanghai", placeholder="默认 Asia/Shanghai"),
            _field("datetime_format", "时间格式", "text", default="%Y-%m-%d %H:%M:%S"),
        ],
    },
    {
        "name": "unicode_convert",
        "display_name": "Unicode 转换",
        "description": "普通文本与 Unicode 转义互转",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-language",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4),
            _field(
                "mode",
                "转换方式",
                "select",
                required=True,
                default="encode",
                options=[
                    {"label": "文本 -> Unicode", "value": "encode"},
                    {"label": "Unicode -> 文本", "value": "decode"},
                ],
            ),
        ],
    },
    {
        "name": "base_convert",
        "display_name": "进制转换",
        "description": "支持 2 到 36 进制之间转换",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-swap",
        "result_kind": "json",
        "fields": [
            _field("value", "原始数值", "text", required=True, placeholder="例如：1010、255、ff"),
            _field("from_base", "原进制", "number", required=True, default=10, min_value=2, max_value=36),
            _field("to_base", "目标进制", "number", required=True, default=16, min_value=2, max_value=36),
        ],
    },
    {
        "name": "color_convert",
        "display_name": "颜色值转换",
        "description": "HEX、RGB、HSL 之间互转",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-palette",
        "result_kind": "json",
        "fields": [
            _field("value", "颜色值", "text", required=True, placeholder="#1677ff / rgb(22,119,255) / hsl(215,100%,54%)"),
            _field("output_type", "目标格式", "select", required=True, default="hex", options=[
                {"label": "HEX", "value": "hex"},
                {"label": "RGB", "value": "rgb"},
                {"label": "HSL", "value": "hsl"},
            ]),
        ],
    },
    {
        "name": "url_encode",
        "display_name": "URL 编码",
        "description": "对文本做 URL 百分号编码",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-link",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4),
            _field("safe", "保留字符", "text", default="", placeholder="默认全部编码"),
        ],
    },
    {
        "name": "url_decode",
        "display_name": "URL 解码",
        "description": "还原 URL 百分号编码后的文本",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-link",
        "result_kind": "json",
        "fields": [
            _field("text", "URL 编码文本", "textarea", required=True, rows=4),
        ],
    },
    {
        "name": "jwt_decode",
        "display_name": "JWT 解码",
        "description": "解码 JWT Header、Payload 和签名",
        "category": "encoding",
        "scenario": "data_validation",
        "icon": "icon-safe",
        "result_kind": "json",
        "fields": [
            _field("token", "JWT Token", "textarea", required=True, rows=4, placeholder="请输入完整 JWT"),
        ],
    },
    {
        "name": "generate_barcode",
        "display_name": "条形码生成",
        "description": "生成条形码并返回图片预览",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-qrcode",
        "result_kind": "image",
        "fields": [
            _field("text", "条形码内容", "text", required=True, placeholder="请输入条形码内容"),
            _field(
                "barcode_type",
                "条形码类型",
                "select",
                required=True,
                default="code128",
                options=[
                    {"label": "Code128", "value": "code128"},
                    {"label": "EAN13", "value": "ean13"},
                ],
            ),
        ],
    },
    {
        "name": "generate_qrcode",
        "display_name": "二维码生成",
        "description": "根据文本内容生成二维码图片",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-qrcode",
        "result_kind": "image",
        "fields": [
            _field("text", "二维码内容", "textarea", required=True, rows=4, placeholder="请输入二维码内容"),
            _field("box_size", "尺寸倍率", "number", default=8, min_value=2, max_value=20),
            _field("border", "边框", "number", default=2, min_value=0, max_value=10),
        ],
    },
    {
        "name": "image_base64_convert",
        "display_name": "图片 Base64 转换",
        "description": "图片与 Base64 数据互转",
        "category": "encoding",
        "scenario": "format_conversion",
        "icon": "icon-image",
        "result_kind": "json",
        "fields": [
            _field(
                "mode",
                "转换方式",
                "select",
                required=True,
                default="image_to_base64",
                options=[
                    {"label": "图片 -> Base64", "value": "image_to_base64"},
                    {"label": "Base64 -> 图片", "value": "base64_to_image"},
                ],
            ),
            _field("image_data", "图片或 Base64 数据", "upload-base64", required=True, placeholder="可上传图片，也可直接粘贴 Base64/Data URL"),
            _field("include_prefix", "输出带 Data URL 前缀", "switch", default=True),
        ],
    },
    {
        "name": "random_integer",
        "display_name": "随机整数",
        "description": "生成指定范围内的随机整数",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-number",
        "result_kind": "json",
        "fields": [
            _field("min_value", "最小值", "number", required=True, default=1),
            _field("max_value", "最大值", "number", required=True, default=100),
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "random_float",
        "display_name": "随机浮点数",
        "description": "生成指定范围和精度的随机浮点数",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-number",
        "result_kind": "json",
        "fields": [
            _field("min_value", "最小值", "number", required=True, default=0),
            _field("max_value", "最大值", "number", required=True, default=1),
            _field("precision", "小数位数", "number", default=2, min_value=0, max_value=10),
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "random_string",
        "display_name": "随机字符串",
        "description": "按长度和字符集生成随机字符串",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-font-colors",
        "result_kind": "json",
        "fields": [
            _field("length", "字符串长度", "number", required=True, default=12, min_value=1, max_value=256),
            _field(
                "char_type",
                "字符集",
                "select",
                required=True,
                default="alphanumeric",
                options=[
                    {"label": "字母数字", "value": "alphanumeric"},
                    {"label": "纯数字", "value": "digits"},
                    {"label": "小写字母", "value": "lower"},
                    {"label": "大写字母", "value": "upper"},
                    {"label": "字母", "value": "letters"},
                    {"label": "十六进制", "value": "hex"},
                    {"label": "全部（含符号）", "value": "all"},
                ],
            ),
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "random_uuid",
        "display_name": "随机 UUID",
        "description": "生成 UUID v1 或 v4",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-more",
        "result_kind": "json",
        "fields": [
            _field("version", "UUID 版本", "select", default=4, options=[
                {"label": "UUID v1", "value": 1},
                {"label": "UUID v4", "value": 4},
            ]),
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "random_boolean",
        "display_name": "随机布尔值",
        "description": "按概率生成 true/false",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-check-circle",
        "result_kind": "json",
        "fields": [
            _field("true_probability", "true 概率", "number", default=50, min_value=0, max_value=100),
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "random_list_element",
        "display_name": "随机列表元素",
        "description": "从列表中随机抽取一个或多个元素",
        "category": "random",
        "scenario": "data_generation",
        "icon": "icon-list",
        "result_kind": "json",
        "fields": [
            _field("items", "列表数据", "textarea", required=True, rows=5, placeholder='可输入 JSON 数组，或按行输入多个值'),
            _field("count", "抽取数量", "number", default=1, min_value=1, max_value=100),
            _field("unique", "不重复抽取", "switch", default=False),
        ],
    },
    {
        "name": "md5_hash",
        "display_name": "MD5 哈希",
        "description": "生成 MD5 摘要",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [_field("text", "输入文本", "textarea", required=True, rows=4)],
    },
    {
        "name": "sha1_hash",
        "display_name": "SHA1 哈希",
        "description": "生成 SHA1 摘要",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [_field("text", "输入文本", "textarea", required=True, rows=4)],
    },
    {
        "name": "sha256_hash",
        "display_name": "SHA256 哈希",
        "description": "生成 SHA256 摘要",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [_field("text", "输入文本", "textarea", required=True, rows=4)],
    },
    {
        "name": "sha512_hash",
        "display_name": "SHA512 哈希",
        "description": "生成 SHA512 摘要",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [_field("text", "输入文本", "textarea", required=True, rows=4)],
    },
    {
        "name": "aes_encrypt",
        "display_name": "AES 加密",
        "description": "使用 AES 对文本加密并返回 Base64 密文",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-lock",
        "result_kind": "json",
        "fields": [
            _field("text", "输入文本", "textarea", required=True, rows=4),
            _field("password", "密钥口令", "text", required=True, placeholder="请输入 AES 密钥口令"),
            _field("mode", "模式", "select", default="CBC", options=[
                {"label": "CBC", "value": "CBC"},
                {"label": "ECB", "value": "ECB"},
            ]),
        ],
    },
    {
        "name": "aes_decrypt",
        "display_name": "AES 解密",
        "description": "解密 Base64 密文为原始文本",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-unlock",
        "result_kind": "json",
        "fields": [
            _field("cipher_text", "密文", "textarea", required=True, rows=4, placeholder="请输入 Base64 密文"),
            _field("password", "密钥口令", "text", required=True, placeholder="请输入 AES 密钥口令"),
            _field("mode", "模式", "select", default="CBC", options=[
                {"label": "CBC", "value": "CBC"},
                {"label": "ECB", "value": "ECB"},
            ]),
        ],
    },
    {
        "name": "hmac_sign",
        "display_name": "HMAC 签名",
        "description": "按指定算法生成 HMAC 摘要",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-safe",
        "result_kind": "json",
        "fields": [
            _field("text", "原始文本", "textarea", required=True, rows=4),
            _field("secret", "签名密钥", "text", required=True),
            _field("algorithm", "算法", "select", default="sha256", options=[
                {"label": "SHA1", "value": "sha1"},
                {"label": "SHA256", "value": "sha256"},
                {"label": "SHA512", "value": "sha512"},
                {"label": "MD5", "value": "md5"},
            ]),
        ],
    },
    {
        "name": "hash_compare",
        "display_name": "哈希校验",
        "description": "将文本计算哈希后与目标摘要比较",
        "category": "encryption",
        "scenario": "encryption_decryption",
        "icon": "icon-check-circle",
        "result_kind": "json",
        "fields": [
            _field("text", "原始文本", "textarea", required=True, rows=4),
            _field("expected_hash", "目标哈希", "textarea", required=True, rows=3),
            _field("algorithm", "算法", "select", default="sha256", options=[
                {"label": "MD5", "value": "md5"},
                {"label": "SHA1", "value": "sha1"},
                {"label": "SHA256", "value": "sha256"},
                {"label": "SHA512", "value": "sha512"},
            ]),
        ],
    },
    {
        "name": "generate_chinese_name",
        "display_name": "中文姓名生成",
        "description": "生成真实风格的中文姓名",
        "category": "test_data",
        "scenario": "data_generation",
        "icon": "icon-user",
        "result_kind": "json",
        "fields": [
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
            _field("gender", "性别偏好", "select", default="random", options=[
                {"label": "随机", "value": "random"},
                {"label": "男性", "value": "male"},
                {"label": "女性", "value": "female"},
            ]),
        ],
    },
    {
        "name": "generate_chinese_phone",
        "display_name": "手机号生成",
        "description": "生成中国大陆手机号",
        "category": "test_data",
        "scenario": "data_generation",
        "icon": "icon-phone",
        "result_kind": "json",
        "fields": [
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
        ],
    },
    {
        "name": "generate_chinese_email",
        "display_name": "邮箱生成",
        "description": "生成常见风格的测试邮箱",
        "category": "test_data",
        "scenario": "data_generation",
        "icon": "icon-email",
        "result_kind": "json",
        "fields": [
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
            _field("domain", "邮箱域名", "text", default="example.com", placeholder="默认 example.com"),
        ],
    },
    {
        "name": "generate_chinese_address",
        "display_name": "地址生成",
        "description": "生成中文地址或完整住址",
        "category": "test_data",
        "scenario": "data_generation",
        "icon": "icon-location",
        "result_kind": "json",
        "fields": [
            _field("count", "生成数量", "number", default=1, min_value=1, max_value=100),
            _field("full_address", "完整地址", "switch", default=True),
        ],
    },
    {
        "name": "json_format",
        "display_name": "JSON 格式化",
        "description": "格式化 JSON，并支持树形浏览",
        "category": "json",
        "scenario": "format_conversion",
        "icon": "icon-code",
        "result_kind": "json-tree",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8, placeholder="请输入 JSON 文本"),
            _field("indent", "缩进空格数", "number", default=2, min_value=0, max_value=8),
            _field("sort_keys", "按键名排序", "switch", default=False),
        ],
    },
    {
        "name": "json_minify",
        "display_name": "JSON 压缩",
        "description": "压缩 JSON 为单行文本",
        "category": "json",
        "scenario": "format_conversion",
        "icon": "icon-compress",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8),
        ],
    },
    {
        "name": "json_validate",
        "display_name": "JSON 校验",
        "description": "校验 JSON 是否合法并返回错误位置",
        "category": "json",
        "scenario": "data_validation",
        "icon": "icon-check-circle",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8),
        ],
    },
    {
        "name": "jsonpath_query",
        "display_name": "JSONPath 查询",
        "description": "使用 JSONPath 从 JSON 中提取结果",
        "category": "json",
        "scenario": "data_validation",
        "icon": "icon-search",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8),
            _field("path", "JSONPath", "text", required=True, placeholder="例如：$.data.items[*].id"),
        ],
    },
    {
        "name": "json_diff",
        "display_name": "JSON 对比",
        "description": "对比两个 JSON 的差异路径和值",
        "category": "json",
        "scenario": "data_validation",
        "icon": "icon-branch",
        "result_kind": "json",
        "fields": [
            _field("left_text", "JSON A", "textarea", required=True, rows=8),
            _field("right_text", "JSON B", "textarea", required=True, rows=8),
        ],
    },
    {
        "name": "json_to_xml",
        "display_name": "JSON 转 XML",
        "description": "将 JSON 转换为 XML 文本",
        "category": "json",
        "scenario": "format_conversion",
        "icon": "icon-swap",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8),
            _field("root_name", "根节点名称", "text", default="root"),
        ],
    },
    {
        "name": "json_to_yaml",
        "display_name": "JSON 转 YAML",
        "description": "将 JSON 转换为 YAML 文本",
        "category": "json",
        "scenario": "format_conversion",
        "icon": "icon-swap",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8),
        ],
    },
    {
        "name": "json_to_csv",
        "display_name": "JSON 转 CSV",
        "description": "将 JSON 数组对象转换为 CSV 文本",
        "category": "json",
        "scenario": "format_conversion",
        "icon": "icon-swap",
        "result_kind": "json",
        "fields": [
            _field("text", "JSON 内容", "textarea", required=True, rows=8, placeholder="请输入数组或对象 JSON"),
        ],
    },
    {
        "name": "cron_generate",
        "display_name": "Crontab 生成",
        "description": "根据五段式配置生成 Crontab 表达式",
        "category": "crontab",
        "scenario": "data_generation",
        "icon": "icon-clock-circle",
        "result_kind": "json",
        "fields": [
            _field("minute", "分钟", "text", default="0"),
            _field("hour", "小时", "text", default="*"),
            _field("day", "日", "text", default="*"),
            _field("month", "月", "text", default="*"),
            _field("weekday", "周", "text", default="*"),
        ],
    },
    {
        "name": "cron_parse",
        "display_name": "Crontab 解析",
        "description": "解析 Crontab 表达式各字段含义",
        "category": "crontab",
        "scenario": "data_validation",
        "icon": "icon-list",
        "result_kind": "json",
        "fields": [
            _field("expression", "Crontab 表达式", "text", required=True, placeholder="例如：0 */2 * * *"),
        ],
    },
    {
        "name": "cron_next_runs",
        "display_name": "下次执行时间",
        "description": "计算未来 N 次执行时间",
        "category": "crontab",
        "scenario": "data_validation",
        "icon": "icon-forward",
        "result_kind": "json",
        "fields": [
            _field("expression", "Crontab 表达式", "text", required=True),
            _field("count", "返回次数", "number", default=5, min_value=1, max_value=20),
            _field("timezone", "时区", "text", default="Asia/Shanghai"),
        ],
    },
    {
        "name": "cron_validate",
        "display_name": "表达式校验",
        "description": "校验 Crontab 表达式是否合法",
        "category": "crontab",
        "scenario": "data_validation",
        "icon": "icon-check-circle",
        "result_kind": "json",
        "fields": [
            _field("expression", "Crontab 表达式", "text", required=True),
        ],
    },
]


def _extend_tools() -> list[dict[str, Any]]:
    return deepcopy(TOOLS)


def get_tool_definition(tool_name: str) -> dict[str, Any] | None:
    for item in TOOLS:
        if item["name"] == tool_name:
            return deepcopy(item)
    return None


def get_categories() -> list[dict[str, Any]]:
    categories = {item["category"]: deepcopy(item) for item in TOOL_CATEGORIES}
    for category in categories.values():
        category["tools"] = []
    for tool in _extend_tools():
        categories[tool["category"]]["tools"].append(tool)
    return list(categories.values())


def get_scenarios() -> list[dict[str, Any]]:
    counters: dict[str, int] = defaultdict(int)
    for tool in TOOLS:
        counters[tool["scenario"]] += 1
    scenarios: list[dict[str, Any]] = []
    for item in TOOL_SCENARIOS:
        scenario = deepcopy(item)
        scenario["tool_count"] = counters.get(item["scenario"], 0)
        scenarios.append(scenario)
    return scenarios


def get_tool_catalog() -> dict[str, Any]:
    return {
        "categories": get_categories(),
        "scenarios": get_scenarios(),
        "tools": _extend_tools(),
    }

"""
Drawio 图表工具

提供 drawio 图表的创建和编辑功能：
- display_diagram: 创建新的 drawio 图表
- edit_diagram: 编辑现有的 drawio 图表
"""

import json
import logging
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger('orchestrator_integration')


def get_diagram_tools() -> list:
    """获取 Drawio 图表工具列表"""

    @langchain_tool
    def display_diagram(xml: str, page_name: str = "") -> str:
        """
        创建新的 drawio 图表。

        当用户要求创建新图表或从头开始绘制时使用此工具。
        如果用户要求在新页面创建图表，请设置 page_name 参数。

        Args:
            xml: 完整的 drawio XML 内容，必须是有效的 mxGraphModel 格式
            page_name: 可选的页面名称。如果指定，将创建新页面而不是替换现有图表

        Returns:
            JSON 格式的结果，包含 success、action、xml 等字段
        """
        logger.info(f"[display_diagram] page_name={page_name}, xml_length={len(xml) if xml else 0}")

        if not xml or not xml.strip():
            return json.dumps({
                "success": False,
                "error": "XML内容不能为空"
            }, ensure_ascii=False)

        if "<mxGraphModel" not in xml or "<root>" not in xml:
            return json.dumps({
                "success": False,
                "error": "无效的drawio XML格式，必须包含mxGraphModel和root元素"
            }, ensure_ascii=False)

        result = {
            "success": True,
            "action": "display",
            "xml": xml,
            "message": "图表创建成功"
        }

        if page_name and page_name.strip():
            result["page_name"] = page_name.strip()
            result["message"] = f"图表页面 '{page_name}' 创建成功"

        logger.info(f"[display_diagram] 图表创建成功")
        return json.dumps(result, ensure_ascii=False)

    @langchain_tool
    def edit_diagram(operations: str) -> str:
        """
        编辑现有的 drawio 图表。

        支持以下操作类型：
        - replace_page: 替换指定页面的完整内容（推荐，最可靠）
        - add: 在指定页面添加新元素
        - delete: 删除指定 ID 的元素
        - update: 更新元素的属性

        Args:
            operations: JSON 格式的操作列表。每个操作包含：
                - action: 操作类型 ("replace_page" | "add" | "delete" | "update")
                - page_index: 目标页面索引（从 0 开始，默认 0）

                replace_page 操作：
                - page_xml: 完整的页面 mxGraphModel XML
                - page_name: 可选，页面名称

                add 操作：
                - element: 要添加的 mxCell XML

                delete 操作：
                - element_id: 要删除的元素 ID

                update 操作：
                - element_id: 要更新的元素 ID
                - properties: 要更新的属性对象

                示例：
                [{"action": "replace_page", "page_index": 1, "page_name": "小猫", "page_xml": "<mxGraphModel>...</mxGraphModel>"}]

        Returns:
            JSON 格式的结果，包含 success、operations 等字段
        """
        logger.info(f"[edit_diagram] operations_length={len(operations) if operations else 0}")

        try:
            if isinstance(operations, str):
                op_list = json.loads(operations)
            else:
                op_list = operations
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"无法解析操作JSON: {str(e)}"
            }, ensure_ascii=False)

        if not isinstance(op_list, list):
            return json.dumps({
                "success": False,
                "error": "operations必须是一个数组"
            }, ensure_ascii=False)

        valid_actions = ["replace_page", "add", "delete", "update"]
        validated_ops = []

        for i, op in enumerate(op_list):
            if not isinstance(op, dict):
                return json.dumps({
                    "success": False,
                    "error": f"第{i+1}个操作必须是对象"
                }, ensure_ascii=False)

            action = op.get("action")
            if action not in valid_actions:
                return json.dumps({
                    "success": False,
                    "error": f"第{i+1}个操作的action无效，必须是: {', '.join(valid_actions)}"
                }, ensure_ascii=False)

            validated_op = {
                "action": action,
                "pageIndex": op.get("page_index", 0)
            }

            if action == "replace_page":
                if "page_xml" not in op:
                    return json.dumps({
                        "success": False,
                        "error": f"第{i+1}个操作(replace_page)缺少page_xml字段"
                    }, ensure_ascii=False)
                validated_op["pageXml"] = op["page_xml"]
                if "page_name" in op:
                    validated_op["pageName"] = op["page_name"]

            elif action == "add":
                if "element" not in op:
                    return json.dumps({
                        "success": False,
                        "error": f"第{i+1}个操作(add)缺少element字段"
                    }, ensure_ascii=False)
                validated_op["element"] = op["element"]

            elif action == "delete":
                if "element_id" not in op:
                    return json.dumps({
                        "success": False,
                        "error": f"第{i+1}个操作(delete)缺少element_id字段"
                    }, ensure_ascii=False)
                validated_op["elementId"] = op["element_id"]

            elif action == "update":
                if "element_id" not in op or "properties" not in op:
                    return json.dumps({
                        "success": False,
                        "error": f"第{i+1}个操作(update)缺少element_id或properties字段"
                    }, ensure_ascii=False)
                validated_op["elementId"] = op["element_id"]
                validated_op["properties"] = op["properties"]

            validated_ops.append(validated_op)

        if not validated_ops:
            return json.dumps({
                "success": False,
                "error": "至少需要一个操作"
            }, ensure_ascii=False)

        logger.info(f"[edit_diagram] 已准备 {len(validated_ops)} 个编辑操作")
        return json.dumps({
            "success": True,
            "action": "edit",
            "operations": validated_ops,
            "message": f"已准备{len(validated_ops)}个编辑操作"
        }, ensure_ascii=False)

    return [display_diagram, edit_diagram]

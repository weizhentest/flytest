"""PDF export helpers for UI automation AI execution reports."""

from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from django.conf import settings

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError as exc:  # pragma: no cover - depends on optional dependency
    REPORTLAB_AVAILABLE = False
    REPORTLAB_IMPORT_ERROR = exc
else:
    REPORTLAB_IMPORT_ERROR = None


class AIReportPDFGenerator:
    """Generate PDF files for AI execution reports."""

    def __init__(self, report_data: dict[str, Any], report_type: str = "summary") -> None:
        if not REPORTLAB_AVAILABLE:  # pragma: no cover - depends on optional dependency
            raise ImportError(f"reportlab is required for PDF export: {REPORTLAB_IMPORT_ERROR}")

        self.report_data = report_data
        self.report_type = report_type
        self.buffer = BytesIO()
        self.font_name = self._register_font()
        self.styles = self._build_styles()

    def _register_font(self) -> str:
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for font_path in font_paths:
            if not os.path.exists(font_path):
                continue
            try:
                pdfmetrics.registerFont(TTFont("FlyTestPdfFont", font_path))
                return "FlyTestPdfFont"
            except Exception:
                continue
        return "Helvetica"

    def _build_styles(self):
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="FlyTitle",
                parent=styles["Heading1"],
                fontName=self.font_name,
                fontSize=22,
                leading=28,
                textColor=colors.HexColor("#123b79"),
                spaceAfter=16,
            )
        )
        styles.add(
            ParagraphStyle(
                name="FlyHeading",
                parent=styles["Heading2"],
                fontName=self.font_name,
                fontSize=14,
                leading=20,
                textColor=colors.HexColor("#20324d"),
                spaceBefore=10,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="FlyBody",
                parent=styles["BodyText"],
                fontName=self.font_name,
                fontSize=10.5,
                leading=15,
                textColor=colors.HexColor("#1f2937"),
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="FlySmall",
                parent=styles["BodyText"],
                fontName=self.font_name,
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#5b6472"),
                spaceAfter=4,
            )
        )
        return styles

    def generate(self) -> BytesIO:
        document = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
        )

        story: list[Any] = []
        story.extend(self._build_header())
        story.extend(self._build_common_content())

        if self.report_type == "detailed":
            story.extend(self._build_detailed_content())
        elif self.report_type == "performance":
            story.extend(self._build_performance_content())
        else:
            story.extend(self._build_summary_content())

        story.extend(self._build_media_content())

        document.build(story)
        self.buffer.seek(0)
        return self.buffer

    def _p(self, text: Any, style_name: str = "FlyBody") -> Paragraph:
        safe_text = escape(str(text or "-")).replace("\n", "<br/>")
        return Paragraph(safe_text, self.styles[style_name])

    def _section_title(self, title: str) -> list[Any]:
        return [Spacer(1, 0.2 * cm), Paragraph(escape(title), self.styles["FlyHeading"])]

    def _styled_table(self, rows: list[list[Any]], col_widths: list[float]):
        table = Table(rows, colWidths=col_widths, repeatRows=1 if len(rows) > 1 else 0)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), self.font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7e2")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _build_header(self) -> list[Any]:
        report_name = {
            "summary": "AI 执行摘要报告",
            "detailed": "AI 执行详细报告",
            "performance": "AI 执行性能报告",
        }.get(self.report_type, "AI 执行报告")

        info_rows = [
            [self._p("字段", "FlySmall"), self._p("内容", "FlySmall")],
            [self._p("任务名称"), self._p(self.report_data.get("case_name"))],
            [self._p("执行状态"), self._p(self.report_data.get("status_display") or self.report_data.get("status"))],
            [self._p("执行模式"), self._p(self.report_data.get("execution_mode_display") or self.report_data.get("execution_mode"))],
            [self._p("执行后端"), self._p(self.report_data.get("execution_backend_display") or self.report_data.get("execution_backend"))],
            [self._p("模型配置"), self._p(self.report_data.get("model_config_name") or "-")],
            [self._p("导出时间"), self._p(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))],
        ]

        return [
            Paragraph(report_name, self.styles["FlyTitle"]),
            self._styled_table(info_rows, [3.6 * cm, 12.0 * cm]),
        ]

    def _build_common_content(self) -> list[Any]:
        story = self._section_title("任务描述")
        story.append(self._p(self.report_data.get("task_description") or "无"))
        story.append(self._p(f"执行时长：{self._format_duration(self.report_data.get('duration'))}", "FlySmall"))
        story.append(
            self._p(
                "开始时间："
                f"{self.report_data.get('start_time') or '-'}"
                f"　结束时间：{self.report_data.get('end_time') or '-'}",
                "FlySmall",
            )
        )
        if self.report_data.get("error_message"):
            story.extend(self._section_title("错误摘要"))
            story.append(self._p(self.report_data.get("error_message")))
        return story

    def _build_summary_content(self) -> list[Any]:
        story: list[Any] = []
        overview = self.report_data.get("overview") or {}
        statistics = self.report_data.get("statistics") or {}
        timeline = self.report_data.get("timeline") or []
        action_distribution = self.report_data.get("action_distribution") or []

        if overview or statistics:
            story.extend(self._section_title("执行概览"))
            rows = [
                [self._p("指标", "FlySmall"), self._p("数值", "FlySmall")],
                [self._p("完成率"), self._p(f"{overview.get('completion_rate', statistics.get('completion_rate', 0))}%")],
                [self._p("平均步耗时"), self._p(self._format_duration(overview.get("avg_step_time")))],
                [self._p("任务总数"), self._p(statistics.get("total", self.report_data.get("planned_task_count", 0)))],
                [self._p("失败任务"), self._p(statistics.get("failed", self.report_data.get("failed_task_count", 0)))],
            ]
            story.append(self._styled_table(rows, [5.4 * cm, 10.2 * cm]))

        if timeline:
            story.extend(self._section_title("任务时间线"))
            rows = [[self._p("序号", "FlySmall"), self._p("任务", "FlySmall"), self._p("状态", "FlySmall")]]
            for item in timeline:
                rows.append(
                    [
                        self._p(item.get("id")),
                        self._p(item.get("description") or item.get("title")),
                        self._p(item.get("status_display") or item.get("status")),
                    ]
                )
            story.append(self._styled_table(rows, [2.0 * cm, 10.2 * cm, 3.4 * cm]))

        if action_distribution:
            story.extend(self._section_title("动作分布"))
            rows = [[self._p("动作类型", "FlySmall"), self._p("次数", "FlySmall")]]
            for item in action_distribution:
                rows.append([self._p(item.get("action")), self._p(item.get("count"))])
            story.append(self._styled_table(rows, [10.0 * cm, 5.6 * cm]))

        errors = self.report_data.get("errors") or []
        if errors:
            story.extend(self._section_title("错误信息"))
            for item in errors:
                prefix = f"步骤 {item.get('step_number')}：" if item.get("step_number") else ""
                story.append(self._p(f"{prefix}{item.get('message', '未知错误')}"))

        return story

    def _build_detailed_content(self) -> list[Any]:
        story: list[Any] = []
        detailed_steps = self.report_data.get("detailed_steps") or []
        errors = self.report_data.get("errors") or []

        story.extend(self._section_title("步骤明细"))
        if detailed_steps:
            rows = [[self._p("步骤", "FlySmall"), self._p("动作", "FlySmall"), self._p("状态", "FlySmall"), self._p("说明", "FlySmall")]]
            for step in detailed_steps:
                rows.append(
                    [
                        self._p(step.get("step_number")),
                        self._p(step.get("action") or step.get("title")),
                        self._p(step.get("status")),
                        self._p(step.get("description") or step.get("message")),
                    ]
                )
            story.append(self._styled_table(rows, [1.6 * cm, 5.0 * cm, 2.8 * cm, 7.0 * cm]))
        else:
            story.append(self._p("暂无步骤明细。"))

        if errors:
            story.extend(self._section_title("错误信息"))
            for item in errors:
                prefix = f"步骤 {item.get('step_number')}：" if item.get("step_number") else ""
                story.append(self._p(f"{prefix}{item.get('message', '未知错误')}"))

        return story

    def _build_performance_content(self) -> list[Any]:
        story: list[Any] = []
        metrics = self.report_data.get("metrics") or {}
        bottlenecks = self.report_data.get("bottlenecks") or []
        recommendations = self.report_data.get("recommendations") or []

        if metrics:
            story.extend(self._section_title("性能指标"))
            rows = [
                [self._p("指标", "FlySmall"), self._p("数值", "FlySmall")],
                [self._p("总步骤数"), self._p(metrics.get("total_steps", 0))],
                [self._p("步骤通过率"), self._p(f"{metrics.get('pass_rate', 0)}%")],
                [self._p("平均步骤耗时"), self._p(self._format_duration(metrics.get("avg_step_duration")))],
                [self._p("最大步骤耗时"), self._p(self._format_duration(metrics.get("max_step_duration")))],
                [self._p("最小步骤耗时"), self._p(self._format_duration(metrics.get("min_step_duration")))],
            ]
            story.append(self._styled_table(rows, [5.6 * cm, 10.0 * cm]))

        if bottlenecks:
            story.extend(self._section_title("性能瓶颈"))
            rows = [[self._p("步骤", "FlySmall"), self._p("动作", "FlySmall"), self._p("耗时", "FlySmall"), self._p("高于平均", "FlySmall")]]
            for item in bottlenecks:
                rows.append(
                    [
                        self._p(item.get("step_number")),
                        self._p(item.get("action")),
                        self._p(self._format_duration(item.get("duration"))),
                        self._p(f"{item.get('slower_than_avg_by', 0)}%"),
                    ]
                )
            story.append(self._styled_table(rows, [1.8 * cm, 7.8 * cm, 3.0 * cm, 3.0 * cm]))

        if recommendations:
            story.extend(self._section_title("优化建议"))
            for index, item in enumerate(recommendations, start=1):
                story.append(self._p(f"{index}. {item}"))

        return story

    def _build_media_content(self) -> list[Any]:
        story: list[Any] = []
        screenshots = self.report_data.get("screenshots_sequence") or []
        gif_path = self.report_data.get("gif_path")

        if screenshots:
            story.extend(self._section_title("执行截图"))
            max_images = 4
            rendered = 0
            for index, screenshot in enumerate(screenshots[:max_images], start=1):
                local_path = self._resolve_media_path(screenshot)
                if local_path and os.path.exists(local_path):
                    try:
                        image = Image(local_path, width=7.2 * cm, height=4.6 * cm)
                        story.append(self._p(f"截图 {index}", "FlySmall"))
                        story.append(image)
                        story.append(Spacer(1, 0.15 * cm))
                        rendered += 1
                        continue
                    except Exception:
                        pass
                story.append(self._p(f"截图 {index}：{screenshot}", "FlySmall"))

            if len(screenshots) > max_images:
                story.append(self._p(f"其余 {len(screenshots) - max_images} 张截图已省略，可在系统内查看完整记录。", "FlySmall"))
            elif rendered == 0:
                story.append(self._p("当前环境无法在 PDF 中嵌入截图，已保留截图路径。", "FlySmall"))

        if gif_path:
            story.extend(self._section_title("执行回放"))
            story.append(self._p(f"回放文件：{gif_path}", "FlySmall"))

        return story

    def _resolve_media_path(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if os.path.isabs(normalized) and os.path.exists(normalized):
            return normalized

        media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/").strip("/")
        media_root = str(getattr(settings, "MEDIA_ROOT", "") or "")
        if not media_root:
            return None

        cleaned = normalized.lstrip("/")
        if media_url and cleaned.startswith(f"{media_url}/"):
            cleaned = cleaned[len(media_url) + 1 :]
        candidate = os.path.join(media_root, cleaned.replace("/", os.sep))
        return candidate if os.path.exists(candidate) else None

    @staticmethod
    def _format_duration(value: Any) -> str:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return "-"
        if seconds < 60:
            return f"{seconds:.2f}s"
        minutes, remain = divmod(int(seconds), 60)
        if minutes < 60:
            return f"{minutes}m {remain}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {remain}s"

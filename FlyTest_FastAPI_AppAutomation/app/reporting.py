from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .database import BASE_DIR, DATA_DIR, fetch_one, json_loads, utc_now

REPORTS_DIR = DATA_DIR / "reports"

CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain",
}


def get_report_content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def ensure_reports_root(conn) -> Path:
    settings = fetch_one(conn, "SELECT workspace_root FROM settings WHERE id = 1")
    workspace_root = ((settings or {}).get("workspace_root") or "").strip()

    if workspace_root:
        root = Path(workspace_root)
        if not root.is_absolute():
            root = (BASE_DIR / root).resolve()
        reports_root = root / "app-automation-reports"
    else:
        reports_root = REPORTS_DIR

    reports_root.mkdir(parents=True, exist_ok=True)
    return reports_root


def _format_value(value: Any) -> str:
    if value in (None, ""):
        return "-"
    text = str(value)
    return escape(text.replace("T", " ").replace("Z", " UTC"))


def _status_label(execution: dict[str, Any]) -> str:
    result = str(execution.get("result") or "").strip()
    status = str(execution.get("status") or "").strip()
    return result or status or "unknown"


def _render_logs(logs: list[dict[str, Any]]) -> str:
    if not logs:
        return "<tr><td colspan='3' class='empty'>No logs yet.</td></tr>"

    rows: list[str] = []
    for item in logs:
        artifact_html = ""
        artifact = str(item.get("artifact") or "").strip()
        if artifact:
            safe_artifact = escape(artifact, quote=True)
            artifact_html = (
                "<div style='margin-top: 6px;'>"
                f"<a href='{safe_artifact}' target='_blank' rel='noreferrer'>View artifact</a>"
                "</div>"
            )
        rows.append(
            "<tr>"
            f"<td>{_format_value(item.get('timestamp'))}</td>"
            f"<td>{escape(str(item.get('level') or 'info'))}</td>"
            f"<td>{escape(str(item.get('message') or ''))}{artifact_html}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_html(execution: dict[str, Any]) -> str:
    total_steps = int(execution.get("total_steps") or 0)
    passed_steps = int(execution.get("passed_steps") or 0)
    failed_steps = int(execution.get("failed_steps") or 0)
    pass_rate = round(passed_steps / total_steps * 100, 1) if total_steps else 0
    suite_name = execution.get("suite_name") or "-"
    logs = execution.get("logs") or []

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FlyTest APP Execution Report #{execution["id"]}</title>
  <style>
    :root {{
      --brand: #1f72ff;
      --brand-soft: rgba(31, 114, 255, 0.12);
      --text: #11253f;
      --muted: #5d728f;
      --line: #dbe7ff;
      --card: #ffffff;
      --bg: linear-gradient(180deg, #f6faff 0%, #eef5ff 100%);
      --success: #12b76a;
      --warning: #f79009;
      --danger: #f04438;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background: var(--bg);
    }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    .hero {{
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(14px);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 22px 60px rgba(31, 78, 171, 0.14);
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      background: var(--brand-soft);
      color: var(--brand);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 16px 0 8px;
      font-size: 32px;
      line-height: 1.15;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 15px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--card);
      padding: 18px;
    }}
    .label {{
      color: var(--muted);
      font-size: 13px;
    }}
    .value {{
      margin-top: 10px;
      font-size: 28px;
      font-weight: 700;
    }}
    .panels {{
      display: grid;
      grid-template-columns: 1.05fr 1.25fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.96);
      padding: 22px;
      box-shadow: 0 12px 30px rgba(31, 78, 171, 0.08);
    }}
    .panel h2 {{
      margin: 0 0 14px;
      font-size: 18px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .meta-item {{
      border-radius: 16px;
      padding: 14px;
      background: #f8fbff;
      border: 1px solid var(--line);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 16px;
      border: 1px solid var(--line);
    }}
    thead {{
      background: #eff5ff;
    }}
    th, td {{
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      font-size: 14px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      background: var(--brand-soft);
      color: var(--brand);
    }}
    .status.passed {{ color: var(--success); background: rgba(18, 183, 106, 0.14); }}
    .status.failed {{ color: var(--danger); background: rgba(240, 68, 56, 0.14); }}
    .status.stopped {{ color: var(--warning); background: rgba(247, 144, 9, 0.14); }}
    .summary {{
      margin-top: 12px;
      padding: 14px 16px;
      border-radius: 16px;
      background: #f8fbff;
      border: 1px solid var(--line);
      color: var(--muted);
      line-height: 1.7;
    }}
    .empty {{
      text-align: center;
      color: var(--muted);
    }}
    @media (max-width: 920px) {{
      .panels {{
        grid-template-columns: 1fr;
      }}
      .meta-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="eyebrow">FlyTest APP Automation</div>
      <h1>{escape(str(execution.get("case_name") or f"Execution #{execution['id']}"))}</h1>
      <p class="subtitle">Execution #{execution["id"]} · Device {_format_value(execution.get("device_name") or execution.get("device_serial"))}</p>
      <div class="cards">
        <div class="card">
          <div class="label">Status</div>
          <div class="value"><span class="status {escape(_status_label(execution).lower())}">{escape(_status_label(execution))}</span></div>
        </div>
        <div class="card">
          <div class="label">Pass Rate</div>
          <div class="value">{pass_rate}%</div>
        </div>
        <div class="card">
          <div class="label">Steps</div>
          <div class="value">{passed_steps}/{total_steps}</div>
        </div>
        <div class="card">
          <div class="label">Duration</div>
          <div class="value">{_format_value(round(float(execution.get("duration") or 0), 2))}s</div>
        </div>
      </div>
    </section>
    <section class="panels">
      <div class="panel">
        <h2>Execution Overview</h2>
        <div class="meta-grid">
          <div class="meta-item"><div class="label">Suite</div><div>{escape(str(suite_name))}</div></div>
          <div class="meta-item"><div class="label">Triggered By</div><div>{_format_value(execution.get("triggered_by"))}</div></div>
          <div class="meta-item"><div class="label">Started At</div><div>{_format_value(execution.get("started_at"))}</div></div>
          <div class="meta-item"><div class="label">Finished At</div><div>{_format_value(execution.get("finished_at"))}</div></div>
          <div class="meta-item"><div class="label">Passed Steps</div><div>{passed_steps}</div></div>
          <div class="meta-item"><div class="label">Failed Steps</div><div>{failed_steps}</div></div>
        </div>
        <div class="summary">{escape(str(execution.get("report_summary") or execution.get("error_message") or "No summary generated yet."))}</div>
      </div>
      <div class="panel">
        <h2>Execution Logs</h2>
        <table>
          <thead>
            <tr>
              <th style="width: 180px;">Timestamp</th>
              <th style="width: 100px;">Level</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>{_render_logs(logs if isinstance(logs, list) else [])}</tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>
"""


def write_execution_report(conn, execution_id: int) -> str:
    execution = fetch_one(
        conn,
        """
        SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial, ts.name AS suite_name
        FROM executions e
        LEFT JOIN test_cases tc ON tc.id = e.test_case_id
        LEFT JOIN devices d ON d.id = e.device_id
        LEFT JOIN test_suites ts ON ts.id = e.test_suite_id
        WHERE e.id = ?
        """,
        (execution_id,),
    )
    if execution is None:
        raise FileNotFoundError("执行记录不存在")

    execution["logs"] = json_loads(execution.get("logs"), [])

    report_dir = ensure_reports_root(conn) / f"execution-{execution_id}"
    report_dir.mkdir(parents=True, exist_ok=True)

    index_path = report_dir / "index.html"
    index_path.write_text(_render_html(execution), encoding="utf-8")

    report_path = str(report_dir)
    if execution.get("report_path") != report_path:
        conn.execute(
            "UPDATE executions SET report_path = ?, updated_at = ? WHERE id = ?",
            (report_path, utc_now(), execution_id),
        )
    return report_path


def resolve_report_file(conn, execution_id: int, file_path: str = "index.html") -> Path:
    execution = fetch_one(conn, "SELECT report_path FROM executions WHERE id = ?", (execution_id,))
    if execution is None:
        raise FileNotFoundError("执行记录不存在")

    report_path = (execution.get("report_path") or "").strip()
    if not report_path:
        report_path = write_execution_report(conn, execution_id)

    report_dir = Path(report_path).resolve()
    candidate = (report_dir / (file_path or "index.html")).resolve()

    try:
        candidate.relative_to(report_dir)
    except ValueError as exc:
        raise FileNotFoundError("无效的报告文件路径") from exc

    if not candidate.exists():
        if candidate.name == "index.html":
            write_execution_report(conn, execution_id)
        if not candidate.exists():
            raise FileNotFoundError("报告文件不存在")

    if not candidate.is_file():
        raise FileNotFoundError("报告文件不存在")

    return candidate

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class HtmlReportAdapter:
    def __init__(self, template_root: Path) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(template_root),
            autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        )

    def build_html_report(self, case_dir: Path, context: dict) -> Path:
        template = self.environment.get_template("report.html.j2")
        report_path = case_dir / "outputs" / "reports" / "report.html"
        report_path.write_text(template.render(**context), encoding="utf-8")
        return report_path

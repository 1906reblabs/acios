#!/usr/bin/env python3
"""
Robust ACIOS build system.

Features:
- Fail-fast validation with clear diagnostics
- Deterministic report ordering
- HTML generation verification
- Safer template rendering
- GitHub Actions friendly logging
- Automatic output directory creation
- Build summary at end of run

Usage:
  python build.py report reports/vol09.md
  python build.py index reports/
  python build.py all reports/
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any

import jinja2
from markupsafe import Markup

from afi_parser import parse_report, md, md_inline

ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "reports"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "output"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_TEMPLATES = ["issue.j2", "index.j2"]
REQUIRED_META_FIELDS = [
    "vol",
    "date",
    "filename",
    "title",
]


def log(msg: str) -> None:
    print(f"[ACIOS] {msg}")


def fail(msg: str, code: int = 1) -> None:
    print(f"[ACIOS:ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


# -----------------------------------------------------------------------------
# Validate environment
# -----------------------------------------------------------------------------

def validate_environment() -> None:
    if not TEMPLATE_DIR.exists():
        fail(f"Missing templates directory: {TEMPLATE_DIR}")

    for tmpl in REQUIRED_TEMPLATES:
        path = TEMPLATE_DIR / tmpl
        if not path.exists():
            fail(f"Missing template: {tmpl}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Jinja
# -----------------------------------------------------------------------------

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=jinja2.StrictUndefined,
)

env.filters["md"] = lambda t: Markup(md(t or ""))
env.filters["md_inline"] = lambda t: Markup(md_inline(t or ""))
env.filters["safe"] = Markup


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def title_html(title: str) -> str:
    if not title:
        return ""

    if "<em>" not in title:
        title = re.sub(r"\*(.+?)\*", r"<em>\1</em>", title)

    return title


env.filters["title_html"] = lambda t: Markup(title_html(t or ""))


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def validate_report_data(data: dict[str, Any], source: Path) -> None:
    meta = data.get("meta", {})

    missing = [f for f in REQUIRED_META_FIELDS if not meta.get(f)]

    if missing:
        raise ValueError(
            f"{source.name} missing frontmatter fields: {', '.join(missing)}"
        )

    filename = meta.get("filename", "")

    if not filename.endswith(".html"):
        raise ValueError(
            f"{source.name} filename must end with .html"
        )

# -----------------------------------------------------------------------------
# Metadata normalization
# -----------------------------------------------------------------------------

def normalize_meta(meta: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "title": "",
        "title_plain": "",
        "standfirst": "",
        "subtitle": "",
        "summary": "",
        "author": "",
        "badges": [],
    }

    for key, value in defaults.items():
        meta.setdefault(key, value)

    return meta
# -----------------------------------------------------------------------------
# Rendering
# -----------------------------------------------------------------------------

def render(template_name: str, context: dict[str, Any], output_name: str) -> Path:
    try:
        template = env.get_template(template_name)
    except Exception as exc:
        fail(f"Unable to load template {template_name}: {exc}")

    try:
        html = template.render(**context)
    except Exception:
        traceback.print_exc()
        fail(f"Template rendering failed for {output_name}")

    output_path = OUTPUT_DIR / output_name

    output_path.write_text(html, encoding="utf-8")

    if not output_path.exists():
        fail(f"HTML file was not written: {output_path}")

    size = output_path.stat().st_size

    if size < 100:
        fail(f"Generated HTML suspiciously small: {output_name} ({size} bytes)")

    log(f"Generated {output_name} ({size} bytes)")

    return output_path


# -----------------------------------------------------------------------------
# Report discovery
# -----------------------------------------------------------------------------

def discover_reports(directory: Path) -> list[Path]:
    if not directory.exists():
        fail(f"Reports directory not found: {directory}")

    reports = sorted(directory.glob("*.md"))

    if not reports:
        fail(f"No markdown reports found in {directory}")

    log(f"Discovered {len(reports)} report(s)")

    return reports


# -----------------------------------------------------------------------------
# Build one report
# -----------------------------------------------------------------------------

def build_report(report_path: Path) -> dict[str, Any]:
    log(f"Parsing {report_path.name}")

    try:
        data = parse_report(report_path)
    except Exception:
        traceback.print_exc()
        fail(f"Failed parsing report: {report_path.name}")

    validate_report_data(data, report_path)

    meta = data.get("meta", {})
    components = data.get("components", {})

    output_name = meta.get("filename")

    render(
        "issue.j2",
        {
            "meta": meta,
            "c": components,
        },
        output_name,
    )

    return data


# -----------------------------------------------------------------------------
# Build index
# -----------------------------------------------------------------------------

def build_index(issues: list[dict[str, Any]]) -> None:
    latest = issues[-1] if issues else {}

    render(
        "index.j2",
        {
            "issues": list(reversed(issues)),
            "latest": latest,
        },
        "index.html",
    )


# -----------------------------------------------------------------------------
# Build all
# -----------------------------------------------------------------------------

def build_all(reports_dir: Path) -> None:
    reports = discover_reports(reports_dir)

    built: list[dict[str, Any]] = []

    for report in reports:
        try:
            built.append(build_report(report))
        except Exception:
            traceback.print_exc()
            fail(f"Build aborted on {report.name}")

    build_index(built)

    generated = sorted(OUTPUT_DIR.glob("*.html"))

    if not generated:
        fail("Build completed but no HTML files were generated")

    log("Build successful")
    log(f"Generated {len(generated)} HTML file(s)")

    for html in generated:
        log(f" - {html.name}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    validate_environment()

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1].strip().lower()
    target = Path(sys.argv[2])

    if mode == "report":
        if not target.exists():
            fail(f"Report file not found: {target}")

        build_report(target)
        return

    if mode == "index":
        reports = discover_reports(target)
        issues = [parse_report(r) for r in reports]
        build_index(issues)
        return

    if mode == "all":
        build_all(target)
        return

    fail(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()

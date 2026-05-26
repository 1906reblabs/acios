#!/usr/bin/env python3
"""
build.py — ACIOS build system
Converts structured Markdown reports to HTML using Jinja2 templates.

Usage:
  python build.py report <report.md>           # build one issue HTML
  python build.py index  <reports_dir>         # build index from all .md files
  python build.py all    <reports_dir>         # build every issue + index

Output lands in ./output/ by default.  Set OUTPUT_DIR env var to override.

GitHub Actions example:
  - run: python build.py all reports/
  - run: cp -r output/* docs/          # or deploy step
"""

import os
import sys
import re
from pathlib import Path

import jinja2
import markdown2

from afi_parser import parse_report, md, md_inline

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT     = Path(__file__).parent
TMPL_DIR = ROOT / "templates"
OUT_DIR  = Path(os.getenv("OUTPUT_DIR", ROOT / "output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Jinja2 env ────────────────────────────────────────────────────────────────

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TMPL_DIR)),
    autoescape=jinja2.select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=jinja2.Undefined,          # silently ignore missing vars
)

# Register markdown filters so templates can use {{ text | md }} and {{ text | md_inline }}
env.filters["md"]        = lambda t: jinja2.Markup(md(t or ""))
env.filters["md_inline"] = lambda t: jinja2.Markup(md_inline(t or ""))

# Pass raw HTML through without double-escaping
env.filters["safe"] = jinja2.Markup


def _title_html(title: str) -> str:
    """
    Convert plain-text title with *italic* markers to HTML <em> tags.
    Leaves existing <em>/<br> tags untouched.
    """
    if not title:
        return ""
    # Convert *text* → <em>text</em> only if not already HTML
    if "<em>" not in title:
        title = re.sub(r"\*(.+?)\*", r"<em>\1</em>", title)
    return title


env.filters["title_html"] = lambda t: jinja2.Markup(_title_html(t or ""))


# ── Render helper ─────────────────────────────────────────────────────────────

def render(template_name: str, ctx: dict, out_name: str) -> Path:
    tmpl = env.get_template(template_name)
    html = tmpl.render(**ctx)
    out  = OUT_DIR / out_name
    out.write_text(html, encoding="utf-8")
    print(f"✓  {out}")
    return out


# ── Build modes ───────────────────────────────────────────────────────────────

def build_report(md_path: Path) -> dict:
    """Parse one .md report and render it to HTML. Returns parsed data."""
    data       = parse_report(md_path)
    meta       = data.get("meta", {})
    components = data.get("components", {})
    filename   = meta.get("filename", md_path.stem + ".html")

    render("issue.j2", dict(meta=meta, c=components), filename)
    return data


def _collect_reports(reports_dir: Path) -> list[dict]:
    """
    Load all .md files from reports_dir, sorted newest-first by vol number
    (falls back to filename sort).
    """
    md_files = sorted(reports_dir.glob("*.md"), reverse=True)
    issues = []
    for f in md_files:
        try:
            data = parse_report(f)
            issues.append(data)
        except Exception as exc:
            print(f"[build] Warning: skipping {f.name}: {exc}", file=sys.stderr)
    return issues


def build_index(reports_dir: Path) -> None:
    """Render index.html from all .md files in reports_dir."""
    issues = _collect_reports(reports_dir)
    latest = issues[0] if issues else {}
    render("index.j2", dict(issues=issues, latest=latest), "index.html")


def build_all(reports_dir: Path) -> None:
    """Build every issue HTML + the index."""
    md_files = sorted(reports_dir.glob("*.md"), reverse=True)
    issues   = []
    for f in md_files:
        try:
            data = build_report(f)
            issues.append(data)
        except Exception as exc:
            print(f"[build] Warning: {f.name}: {exc}", file=sys.stderr)
    latest = issues[0] if issues else {}
    render("index.j2", dict(issues=issues, latest=latest), "index.html")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode   = sys.argv[1].lower()
    target = Path(sys.argv[2])

    if mode == "report":
        if not target.is_file():
            sys.exit(f"File not found: {target}")
        build_report(target)

    elif mode == "index":
        if not target.is_dir():
            sys.exit(f"Directory not found: {target}")
        build_index(target)

    elif mode == "all":
        if not target.is_dir():
            sys.exit(f"Directory not found: {target}")
        build_all(target)

    else:
        sys.exit(f"Unknown mode '{mode}'. Use: report | index | all")

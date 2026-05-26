#!/usr/bin/env python3
"""
afi_parser.py — Antifragile Africa Crypto report parser
Converts structured ACIOS Markdown reports into a Python dict
that the Jinja2 build templates consume.

MD Report Format
----------------
  ---
  # YAML frontmatter
  vol: "07"
  vol_roman: "VII"
  date: "19 May 2026"
  filename: "antifragile_africa_weekly_19may2026.html"
  title: "The CBN Held. The Ratchet Held. The Thesis Is Running *Its Verdict.*"
  title_plain: "..."
  standfirst: "..."
  audit: "4.93"
  agents: "28"
  layers: "7"
  new_signal: "BCEAO Consultation Paper"
  next_vol: "08"
  badges:
    - text: "Latest"
      cls: "badge-vol"
  ---

  ## SPREADS
  - Nigeria · NGN | ~16.8% | alert | ↓ FLOOR HOLDING | t-down | Note text.

  ## EXECUTIVE BRIEF
  HEADLINE: THE CBN HELD...

  Paragraph one text...

  ---

  Paragraph two text...

  RISK: Key risk text here.
  SUMMARY: One-line summary here.

  ## INSIGHTS
  ### INSIGHT
  CONF: HIGH
  HEADLINE: The 7:1 Compression Ratio...
  Body text...
  SOURCE: Macro Analyst · Contrarian Analyst

  ## HEATMAP
  CAPTION: **Cycle 07's defining geographic story...**
  ### ALERTS
  - ⚡ Kenya +6 → 87 | **VASP Regulations...** elevates Kenya...
  ### CELLS
  - Kenya | 87 | c-gr | l-green | ↑ +6 VASP GAZETTE | t-up | Highest EAC score ever.

  ## FULLSTACK
  ### LAYER Monetary Competition
  Body paragraphs (use --- to separate)...
  [1st order]: ...
  [2nd order]: ...
  [3rd order]: ...
  ### LAYER Blockchain Infrastructure
  ...
  ### CROSS-LAYER
  #### Cross-insight title here
  Body text...

  ## FRAGILITY
  SCORE: 3.8
  SCORE_CLS: low
  STATUS: MEDIUM — DECLINING TREND
  CHANGE: ↓ -0.4 from Vol. 06
  DESC: Description text...
  ### BARS
  - Label text | 50% | fb-med | 5.0
  ### RISKS
  #### RISK 01: Title Here
  LEVEL: MEDIUM
  LEVEL_CLS: risk-med
  Risk description...

  ## OPPORTUNITIES
  ### OPP
  TIER: Tier 1 · Regulatory Window
  TITLE: Kenya VASP First 10...
  SCORE: 9.2
  Thesis paragraphs (--- separated)...
  FOR WHOM: Exchange operators...
  TIMEFRAME: Immediate
  TRIGGER: CBK/CMA portal opens
  INVALIDATION: Framework delays...

  ## POWERMAP
  ### CARD Nigeria — State vs. Crypto
  STATUS: CONTESTED → Crypto Gaining
  - Fiat On-Ramp | CBN/banks (weakening grip) | p-contested
  ### SHIFT
  BORDER_CLS:
  LABEL: ★ HISTORIC: Kenya Reaches 87 CMS
  LABEL_CLS:
  TITLE: Kenya VASP Gazette Locks In...
  Shift body text...

  ## BLACKSWAN
  ### SCENARIO
  CARD_CLS: s-low
  PROB: LOW
  TREND: ↓ Declining
  TREND_CLS: t-down
  NEW: false
  TITLE: BCEAO Framework Goes Restrictive
  Paragraph 1...
  ---
  Paragraph 2...
  TRIGGER: BCEAO publishes framework with...

  ## SIGNAL_NOISE
  ### TABLE
  - Development name | sn-ss | STRONG SIGNAL | Rationale text here.
  ### UNRESOLVED
  #### Unresolved item title
  CONDITION: Becomes SIGNAL if...
  REVIEW: Vol. 09 · August 2026

  ## RECOMMENDATIONS
  ### REC R01
  ACTION: Submit VASP license application...
  FOR WHOM: Exchange Operator
  TIMEFRAME: Immediate
  TRIGGER: CBK/CMA portal opens
  RISK: Capital requirement may change.

  ## MEMORY
  ### TRENDS
  - **Nigeria Dollarization Ratchet — STABLE:** 7:1 ratio confirmed...
  ### COUNTRIES
  - **Nigeria:** State-vs-crypto contest updated...
  ### RESOLVED
  - **P-06-03 — CORRECT:** Predicted CBN communiqué silent...
  ### PREDICTIONS
  - P-07-01 | BCEAO framework published as permissive... | HIGH
  ### WATCHLIST
  - **June 1:** Kenya VASP application portal opens...

Usage:
    from afi_parser import parse_report
    data = parse_report("reports/vol07.md")
    # data["meta"]           -> frontmatter dict
    # data["components"]     -> section dict keyed by normalized name
"""

import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

try:
    import markdown2
except ImportError:
    sys.exit("pip install markdown2")

# ── Markdown helpers ──────────────────────────────────────────────────────────

_MD_EXTRAS = ["fenced-code-blocks", "tables", "smarty-pants", "strike"]


def md(text: str) -> str:
    """Render Markdown block to HTML."""
    if not text:
        return ""
    return markdown2.markdown(text.strip(), extras=_MD_EXTRAS)


def md_inline(text: str) -> str:
    """Render Markdown inline, strip outer <p> tags."""
    if not text:
        return ""
    html = markdown2.markdown(text.strip(), extras=_MD_EXTRAS).strip()
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return html


def md_paras(text: str) -> list[str]:
    """Split text on --- dividers and render each block."""
    parts = re.split(r"\n---+\n", text.strip())
    return [md(p.strip()) for p in parts if p.strip()]


# ── Frontmatter ───────────────────────────────────────────────────────────────

def parse_frontmatter(src: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", src, re.DOTALL)
    if not m:
        return {}, src
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"YAML frontmatter error: {e}") from e
    return meta, src[m.end():]


# ── Section & subsection splitting ───────────────────────────────────────────

def split_sections(body: str) -> dict[str, str]:
    """Split on ## SECTION headers → {NORMALISED_KEY: content}."""
    parts = re.split(r"^##\s+(.+)$", body, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    it = iter(parts[1:])
    for name in it:
        content = next(it, "")
        key = _norm(name)
        sections[key] = content.strip()
    return sections


def split_subsections(content: str) -> dict[str, str]:
    """Split on ### SUBSECTION headers within a section."""
    parts = re.split(r"^###\s+(.+)$", content, flags=re.MULTILINE)
    subs: dict[str, str] = {}
    it = iter(parts[1:])
    for name in it:
        body = next(it, "")
        key = _norm(name)
        subs[key] = body.strip()
    return subs


def _norm(s: str) -> str:
    """Normalise a header name to a safe Python key."""
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


# ── Field extractor ───────────────────────────────────────────────────────────

def extract_field(text: str, key: str, default: str = "") -> tuple[str, str]:
    """
    Pull KEY: value from text (case-insensitive).
    Returns (value, text_with_line_removed).
    """
    pattern = rf"(?m)^{re.escape(key)}:\s*(.+)$"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return default, text
    value = m.group(1).strip()
    remaining = text[: m.start()] + text[m.end():]
    return value, remaining


# ── Section parsers ───────────────────────────────────────────────────────────

def parse_spreads(content: str) -> list[dict]:
    """
    Line format: Country | Val | val_cls | Trend | trend_cls | Note
    """
    out = []
    for line in content.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 6:
            out.append(dict(
                country=p[0], val=p[1], val_cls=p[2],
                trend=p[3], trend_cls=p[4], note=p[5],
            ))
    return out


def parse_executive_brief(content: str) -> dict:
    headline, content = extract_field(content, "HEADLINE")
    risk, content     = extract_field(content, "RISK")
    summary, content  = extract_field(content, "SUMMARY")
    return dict(
        headline=headline,
        paragraphs=md_paras(content),
        risk=md_inline(risk),
        summary=md_inline(summary),
    )


def parse_insights(content: str) -> list[dict]:
    blocks = re.split(r"###\s+INSIGHT\b", content, flags=re.IGNORECASE)
    out = []
    for i, block in enumerate(blocks[1:], 1):
        conf, block     = extract_field(block, "CONF", "MEDIUM")
        headline, block = extract_field(block, "HEADLINE", f"Insight {i}")
        source, block   = extract_field(block, "SOURCE", "")
        conf_cls = {"HIGH": "conf-h", "MEDIUM": "conf-m", "LOW": "conf-l"}.get(conf.upper(), "conf-m")
        out.append(dict(
            num=f"{i:02d}",
            conf=conf,
            conf_cls=conf_cls,
            headline=md_inline(headline),
            body=md(block.strip()),
            source=source,
        ))
    return out


def parse_heatmap(content: str) -> dict:
    cap_m = re.search(r"(?m)^CAPTION:\s*(.+)$", content, re.IGNORECASE)
    caption = ""
    if cap_m:
        caption = cap_m.group(1).strip()
        content = content[: cap_m.start()] + content[cap_m.end():]

    sub = split_subsections(content)

    alerts = []
    for line in sub.get("alerts", "").splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|", 1)]
        alerts.append(dict(label=p[0], body=md_inline(p[1]) if len(p) > 1 else ""))

    cells = []
    for line in sub.get("cells", "").splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 7:
            cells.append(dict(
                country=p[0], score=p[1], score_cls=p[2], border_cls=p[3],
                trend=p[4], trend_cls=p[5], note=p[6],
            ))

    return dict(caption=md_inline(caption), alerts=alerts, cells=cells)


def parse_fullstack(content: str) -> dict:
    pattern = r"^###\s+(.+)$"
    parts   = re.split(pattern, content, flags=re.MULTILINE)

    layers: list[dict]        = []
    cross_insights: list[dict] = []
    layer_num = 1

    it = iter(parts[1:])
    for name in it:
        body = next(it, "").strip()
        name = name.strip()

        if re.match(r"CROSS", name, re.IGNORECASE):
            ci_parts = re.split(r"^####\s+(.+)$", body, flags=re.MULTILINE)
            ci_it = iter(ci_parts[1:])
            for ci_title in ci_it:
                ci_body = next(ci_it, "")
                cross_insights.append(dict(
                    title=md_inline(ci_title.strip()),
                    body=md(ci_body.strip()),
                ))
        elif re.match(r"LAYER\s+", name, re.IGNORECASE):
            layer_name = re.sub(r"(?i)^LAYER\s+", "", name).strip()
            anchor = f"sl{layer_num}"

            # Detect [Nth order] markers
            order_re = r"\[(?:1st|2nd|3rd|first|second|third)\s+order\]"
            markers  = re.findall(order_re, body, re.IGNORECASE)
            if markers:
                seg = re.split(order_re, body, flags=re.IGNORECASE)
                orders = [
                    dict(label=m.strip("[]"), text=md(t.strip()))
                    for m, t in zip(markers, seg[1:])
                ]
                layers.append(dict(
                    num=f"{layer_num:02d}", name=layer_name,
                    anchor=anchor, paras=[], orders=orders,
                ))
            else:
                layers.append(dict(
                    num=f"{layer_num:02d}", name=layer_name,
                    anchor=anchor, paras=md_paras(body), orders=[],
                ))
            layer_num += 1

    return dict(layers=layers, cross_insights=cross_insights)


def parse_fragility(content: str) -> dict:
    score,     content = extract_field(content, "SCORE", "5.0")
    score_cls, content = extract_field(content, "SCORE_CLS", "med")
    status,    content = extract_field(content, "STATUS", "MEDIUM")
    change,    content = extract_field(content, "CHANGE", "")
    desc,      content = extract_field(content, "DESC", "")

    sub = split_subsections(content)

    bars = []
    for line in sub.get("bars", "").splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 4:
            bars.append(dict(label=p[0], width=p[1], cls=p[2], val=p[3]))

    risks = []
    risks_raw = sub.get("risks", "")
    risk_blocks = re.split(r"^####\s+RISK\s+(\d+):\s*(.+)$", risks_raw, flags=re.MULTILINE)
    ri = iter(risk_blocks[1:])
    for rank in ri:
        title = next(ri, "")
        body  = next(ri, "").strip()
        level_cls, body = extract_field(body, "LEVEL_CLS", "risk-med")
        level,     body = extract_field(body, "LEVEL", "MEDIUM")
        risks.append(dict(
            rank=f"{int(rank):02d}", name=title.strip(),
            desc=md(body.strip()), level_cls=level_cls, level=level,
        ))

    return dict(
        score=score, score_cls=score_cls, status=status,
        change=change, desc=md_inline(desc), bars=bars, risks=risks,
    )


def parse_opportunities(content: str) -> list[dict]:
    blocks = re.split(r"###\s+OPP\b", content, flags=re.IGNORECASE)
    out = []
    for block in blocks[1:]:
        tier,         block = extract_field(block, "TIER", "Tier 2")
        title,        block = extract_field(block, "TITLE", "Opportunity")
        score,        block = extract_field(block, "SCORE", "7.0")
        for_whom,     block = extract_field(block, "FOR WHOM", "")
        timeframe,    block = extract_field(block, "TIMEFRAME", "")
        trigger,      block = extract_field(block, "TRIGGER", "")
        invalidation, block = extract_field(block, "INVALIDATION", "")
        out.append(dict(
            tier=tier,
            title=md_inline(title),
            score=score,
            thesis_paragraphs=md_paras(block.strip()),
            meta=[
                dict(label="For Whom",  val=for_whom),
                dict(label="Timeframe", val=timeframe),
                dict(label="Trigger",   val=trigger),
            ],
            invalidation=md_inline(invalidation),
        ))
    return out


def parse_powermap(content: str) -> dict:
    pattern = r"^###\s+(CARD|SHIFT)\b\s*(.*)$"
    parts   = re.split(pattern, content, flags=re.MULTILINE | re.IGNORECASE)

    cards, shifts = [], []
    it = iter(parts[1:])
    for kind in it:
        name = next(it, "").strip()
        body = next(it, "").strip()
        kind = kind.strip().upper()

        if kind == "CARD":
            status, body = extract_field(body, "STATUS", "CONTESTED")
            rows = []
            for line in body.splitlines():
                line = line.strip().lstrip("-").strip()
                if not line or line.startswith("#"):
                    continue
                p = [x.strip() for x in line.split("|")]
                if len(p) >= 3:
                    rows.append(dict(label=p[0], val=p[1], val_cls=p[2]))
            cards.append(dict(country=name, status=status, rows=rows))

        elif kind == "SHIFT":
            border_cls, body = extract_field(body, "BORDER_CLS", "")
            label,      body = extract_field(body, "LABEL", "")
            label_cls,  body = extract_field(body, "LABEL_CLS", "")
            title,      body = extract_field(body, "TITLE", "")
            shifts.append(dict(
                border_cls=border_cls, label=label,
                label_cls=label_cls,  title=title,
                body=md(body.strip()),
            ))

    return dict(cards=cards, shifts=shifts)


def parse_blackswan(content: str) -> list[dict]:
    blocks = re.split(r"###\s+SCENARIO\b", content, flags=re.IGNORECASE)
    out = []
    for block in blocks[1:]:
        card_cls,  block = extract_field(block, "CARD_CLS", "s-low")
        prob,      block = extract_field(block, "PROB", "LOW")
        trend,     block = extract_field(block, "TREND", "→ Stable")
        trend_cls, block = extract_field(block, "TREND_CLS", "t-neutral")
        new_s,     block = extract_field(block, "NEW", "false")
        title,     block = extract_field(block, "TITLE", "Scenario")
        trigger,   block = extract_field(block, "TRIGGER", "")
        paras = [md(p.strip()) for p in re.split(r"\n---+\n", block.strip()) if p.strip()]
        out.append(dict(
            card_cls=card_cls,
            prob_val=prob,
            trend=trend,
            trend_cls=trend_cls,
            new_tag=new_s.lower() in ("true", "yes", "1"),
            title=md_inline(title),
            paragraphs=paras,
            trigger=md_inline(trigger),
        ))
    return out


def parse_signal_noise(content: str) -> dict:
    sub = split_subsections(content)

    rows = []
    for line in sub.get("table", "").splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 4:
            rows.append(dict(dev=p[0], cls=p[1], badge=p[2], rationale=p[3]))

    unresolved = []
    ur_raw  = sub.get("unresolved", "")
    ur_parts = re.split(r"^####\s+(.+)$", ur_raw, flags=re.MULTILINE)
    ur_it = iter(ur_parts[1:])
    for ur_title in ur_it:
        ur_body = next(ur_it, "").strip()
        condition, ur_body = extract_field(ur_body, "CONDITION", "")
        review,    ur_body = extract_field(ur_body, "REVIEW", "")
        unresolved.append(dict(
            title=ur_title.strip(),
            condition=md_inline(condition),
            review=review,
        ))

    return dict(rows=rows, unresolved=unresolved)


def parse_recommendations(content: str) -> list[dict]:
    ids    = re.findall(r"###\s+REC\s+(\w+)", content, re.IGNORECASE)
    blocks = re.split(r"###\s+REC\s+\w+", content, flags=re.IGNORECASE)
    out = []
    for rec_id, block in zip(ids, blocks[1:]):
        action,    block = extract_field(block, "ACTION", "")
        for_whom,  block = extract_field(block, "FOR WHOM", "")
        timeframe, block = extract_field(block, "TIMEFRAME", "")
        trigger,   block = extract_field(block, "TRIGGER", "")
        risk,      block = extract_field(block, "RISK", "")
        out.append(dict(
            num=rec_id.upper(),
            action=md_inline(action),
            for_whom=for_whom,
            timeframe=timeframe,
            trigger=trigger,
            risk=md_inline(risk),
        ))
    return out


def parse_memory(content: str) -> dict:
    sub = split_subsections(content)

    def bullet_list(text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            line = line.strip().lstrip("-*").strip()
            if line:
                items.append(md_inline(line))
        return items

    pred_log = []
    for line in sub.get("predictions", "").splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) >= 3:
            conf = p[2].upper()
            conf_cls = {"HIGH": "pc-h", "MEDIUM": "pc-m", "LOW": "pc-l"}.get(conf, "pc-m")
            pred_log.append(dict(id=p[0], text=md_inline(p[1]), conf_cls=conf_cls, conf=conf))

    return dict(
        trends=bullet_list(sub.get("trends", "")),
        countries=bullet_list(sub.get("countries", "")),
        resolved=bullet_list(sub.get("resolved", "")),
        predictions=pred_log,
        watchlist=bullet_list(sub.get("watchlist", "")),
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

_PARSERS: dict[str, Any] = {
    "spreads":            parse_spreads,
    "executive_brief":    parse_executive_brief,
    "insights":           parse_insights,
    "heatmap":            parse_heatmap,
    "fullstack":          parse_fullstack,
    "fragility":          parse_fragility,
    "opportunities":      parse_opportunities,
    "powermap":           parse_powermap,
    "blackswan":          parse_blackswan,
    "black_swan":         parse_blackswan,
    "signal_noise":       parse_signal_noise,
    "signal_vs_noise":    parse_signal_noise,
    "recommendations":    parse_recommendations,
    "memory":             parse_memory,
}


# ── Public API ────────────────────────────────────────────────────────────────

def parse_report(path: "str | Path") -> dict:
    """
    Parse an ACIOS .md report and return a structured dict:
      {
        "meta":       { ...frontmatter... },
        "components": { "spreads": [...], "executive_brief": {...}, ... }
      }
    """
    src = Path(path).read_text(encoding="utf-8")
    meta, body = parse_frontmatter(src)
    sections   = split_sections(body)

    components: dict[str, Any] = {}
    for key, raw in sections.items():
        parser = _PARSERS.get(key)
        if parser:
            try:
                components[key] = parser(raw)
            except Exception as exc:
                print(f"[afi_parser] Warning: {key!r}: {exc}", file=sys.stderr)
                components[key] = {"_raw": raw, "_error": str(exc)}
        else:
            components[key] = {"_raw": raw}

    return dict(meta=meta, components=components)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python afi_parser.py <report.md>")
        sys.exit(1)

    result = parse_report(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))

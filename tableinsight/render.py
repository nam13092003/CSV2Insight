"""Render analysis results to Markdown and a self-contained HTML report (inline SVG charts)."""
import html
import math
import re

L = {
    "vi": {"title": "Báo cáo insight dữ liệu", "overview": "Tổng quan dữ liệu", "rows": "dòng", "cols": "cột",
           "summary": "Tóm tắt điều hành", "top": "Insight nổi bật", "recs": "Khuyến nghị", "caveats": "Lưu ý",
           "time": "Xu hướng theo thời gian", "segment": "Phân khúc & yếu tố ảnh hưởng",
           "relation": "Quan hệ giữa các biến", "distribution": "Phân phối & ngoại lai",
           "quality": "Chất lượng & cấu trúc dữ liệu", "columns": "Vai trò các cột", "method": "Phương pháp",
           "evidence": "Bằng chứng", "all": "Tất cả insight", "sampled": "(phân tích trên mẫu ngẫu nhiên",
           "column": "Cột", "role": "Vai trò", "missing": "Thiếu", "unique": "Số giá trị khác nhau",
           "llm_note": "Tóm tắt viết bởi {m}; mọi con số đã được đối chiếu tự động với kết quả thống kê.",
           "tmpl_note": "Tóm tắt tự động (không dùng LLM).", "target": "Biến mục tiêu",
           "method_text": "Insight được tìm bằng kiểm định thống kê (ANOVA/Kruskal theo hạng, Spearman, Cramér's V, "
                          "Mann-Kendall, mô hình điểm gãy có hiệu chỉnh sup-F, tách mùa vụ), lọc theo mức ý nghĩa "
                          "p < 0.001 và ngưỡng độ lớn hiệu ứng, loại bỏ quan hệ hiển nhiên (cột trùng, cột suy ra, "
                          "phân cấp), rồi xếp hạng theo: trọng số loại × độ lớn hiệu ứng × phạm vi ảnh hưởng, có đa dạng hoá."},
    "en": {"title": "Data insight report", "overview": "Dataset overview", "rows": "rows", "cols": "columns",
           "summary": "Executive summary", "top": "Top insights", "recs": "Recommendations", "caveats": "Caveats",
           "time": "Trends over time", "segment": "Segments & drivers", "relation": "Relationships",
           "distribution": "Distributions & outliers", "quality": "Data quality & structure",
           "columns": "Column roles", "method": "Method", "evidence": "Evidence", "all": "All insights",
           "sampled": "(analyzed on a random sample of", "column": "Column", "role": "Role", "missing": "Missing",
           "unique": "Distinct values",
           "llm_note": "Summary written by {m}; every number was automatically checked against the statistics.",
           "tmpl_note": "Automatic summary (no LLM).", "target": "Target",
           "method_text": "Insights are found with statistical tests (rank ANOVA/Kruskal, Spearman, Cramér's V, "
                          "Mann-Kendall, sup-F-corrected change-point model, seasonal decomposition), filtered at "
                          "p < 0.001 plus effect-size thresholds, with trivial relations removed (duplicate, derived, "
                          "hierarchical columns), then ranked by type weight x effect size x impact with diversification."},
}
THEMES = ["time", "segment", "relation", "distribution"]


def template_summary(result, lang):
    by = {i["id"]: i for i in result["insights"]}
    top = [by[i] for i in result["top_insights"]]
    qual = [i for i in result["insights"] if i["theme"] == "quality"]
    return {
        "headline": top[0]["text"][lang] if top else "",
        "key_takeaways": [{"text": i["text"][lang], "evidence": [i["id"]]} for i in top[1:6]],
        "recommendations": [],
        "caveats": [{"text": i["text"][lang], "evidence": [i["id"]]} for i in qual[:3]],
    }


def _md_inline(t):
    return t


def _p(p):
    if p is None:
        return ""
    return "p < 1e-6" if p < 1e-6 else f"p = {p:.1g}"


def to_markdown(result, summary, lang="vi", llm_report=None):
    t = L[lang]; ds = result["dataset"]
    by = {i["id"]: i for i in result["insights"]}
    out = [f"# {t['title']}: `{ds['source'].split('/')[-1]}`", ""]
    s = f"**{ds['rows']:,} {t['rows']} × {ds['columns']} {t['cols']}**"
    if ds.get("sampled"):
        s += f" {t['sampled']} {ds['analyzed_rows']:,} {t['rows']})"
    if ds.get("target"):
        s += f" · {t['target']}: `{ds['target']}`"
    out += [s, ""]
    out += [f"## {t['summary']}", ""]
    if summary.get("headline"):
        out += [f"**{summary['headline']}**", ""]
    for it in summary.get("key_takeaways", []):
        ev = f" _({', '.join(it['evidence'])})_" if it.get("evidence") else ""
        out.append(f"- {it['text']}{ev}")
    if summary.get("recommendations"):
        out += ["", f"**{t['recs']}**", ""]
        for it in summary["recommendations"]:
            ev = f" _({', '.join(it['evidence'])})_" if it.get("evidence") else ""
            out.append(f"- {it['text']}{ev}")
    if summary.get("caveats"):
        out += ["", f"**{t['caveats']}**", ""]
        for it in summary["caveats"]:
            out.append(f"- {it['text'] if isinstance(it, dict) else it}")
    note = t["llm_note"].format(m=llm_report["model"]) if llm_report and llm_report.get("ok") else t["tmpl_note"]
    out += ["", f"<sub>{note}</sub>", ""]
    out += [f"## {t['top']}", ""]
    for k, iid in enumerate(result["top_insights"], 1):
        i = by[iid]
        out.append(f"{k}. **[{i['id']}]** {i['text'][lang]}  \n   <sub>{i['type']} · score {i['score']:.2f}"
                   + (f" · {_p(i['p'])}" if i.get("p") is not None else "") + "</sub>")
    out.append("")
    for th in THEMES + ["quality"]:
        items = [i for i in result["insights"] if i["theme"] == th]
        if not items:
            continue
        out += [f"## {t[th]}", ""]
        for i in items:
            out.append(f"- **[{i['id']}]** {i['text'][lang]}")
        out.append("")
    out += [f"## {t['columns']}", "", f"| {t['column']} | {t['role']} | {t['missing']} | {t['unique']} |", "|---|---|---|---|"]
    for c in result["columns"]:
        role = c["role"] + (f" ({c['agg']})" if c.get("agg") else "")
        out.append(f"| `{c['column']}` | {role} | {100 * c.get('missing_pct', 0):.1f}% | {c.get('n_unique', '')} |")
    out += ["", f"## {t['method']}", "", t["method_text"], ""]
    return "\n".join(out)


# ---------------- HTML ----------------
def _esc(s):
    s = html.escape(str(s))
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)


def _fmt_tick(v):
    a = abs(v)
    if a >= 1e9: return f"{v / 1e9:.1f}B"
    if a >= 1e6: return f"{v / 1e6:.1f}M"
    if a >= 1e3: return f"{v / 1e3:.1f}K"
    if a >= 10 or v == int(v): return f"{v:.0f}"
    return f"{v:.2f}"


def svg_chart(ch, w=560, h=220):
    if not ch or ch.get("kind") not in ("bar", "line"):
        return ""
    labels, vals = ch.get("labels", []), ch.get("values", [])
    if not vals:
        return ""
    unit = ch.get("unit", "")
    pl, pr, pt, pb = 52, 12, 14, 46
    iw, ih = w - pl - pr, h - pt - pb
    vmin = min(0.0, min(vals)); vmax = max(vals)
    if vmax == vmin:
        vmax = vmin + 1
    def Y(v): return pt + ih - (v - vmin) / (vmax - vmin) * ih
    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img">']
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4; y = Y(v)
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{pl - 6}" y="{y + 4:.1f}" class="tick" text-anchor="end">{_fmt_tick(v)}{unit}</text>')
    n = len(vals)
    hl = set(map(str, ch.get("highlight", []) or []))
    step = max(1, math.ceil(n / max(1, int(iw / (62 if ch['kind'] == 'line' else 44)))))
    if ch["kind"] == "bar":
        bw = iw / n
        for k, (lab, v) in enumerate(zip(labels, vals)):
            x = pl + k * bw + bw * 0.15; y = Y(max(v, 0)); y0 = Y(0)
            cls = "bar hl" if str(lab) in hl else "bar"
            parts.append(f'<rect x="{x:.1f}" y="{min(y, y0):.1f}" width="{bw * 0.7:.1f}" height="{abs(y0 - y):.1f}" class="{cls}" rx="2"><title>{html.escape(str(lab))}: {v:,.4g}</title></rect>')
            if k % step == 0:
                parts.append(f'<text x="{x + bw * 0.35:.1f}" y="{h - pb + 14}" class="tick" text-anchor="middle">{html.escape(str(lab)[:9])}</text>')
    else:
        xs = [pl + (k + 0.5) * iw / n for k in range(n)]
        pts = " ".join(f"{x:.1f},{Y(v):.1f}" for x, v in zip(xs, vals))
        parts.append(f'<polyline points="{pts}" class="line"/>')
        mk = ch.get("marker")
        for k, (x, lab) in enumerate(zip(xs, labels)):
            if mk is not None and str(lab) == str(mk):
                parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{pt + ih}" class="marker"/>')
                parts.append(f'<circle cx="{x:.1f}" cy="{Y(vals[k]):.1f}" r="4" class="dot"/>')
            if k % step == 0:
                parts.append(f'<text x="{x:.1f}" y="{h - pb + 14}" class="tick" text-anchor="middle">{html.escape(str(lab)[:10])}</text>')
    parts.append("</svg>")
    return "".join(parts)


CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#656d76;--card:#ffffff;--line:#e4e1da;--accent:#2f6fde;--hl:#e8590c;--grid:#ece9e2}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e6e6;--muted:#9aa3ad;--card:#1d2024;--line:#2c3036;--accent:#6ea0ff;--hl:#ff8c4a;--grid:#2a2e33}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e6e6;--muted:#9aa3ad;--card:#1d2024;--line:#2c3036;--accent:#6ea0ff;--hl:#ff8c4a;--grid:#2a2e33}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.meta{color:var(--muted)}code{font:13px ui-monospace,Menlo,Consolas,monospace;background:color-mix(in srgb,var(--accent) 10%,transparent);padding:1px 5px;border-radius:4px}
.headline{font-size:18px;font-weight:600;margin:8px 0 12px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.card .h{display:flex;gap:10px;align-items:baseline}.badge{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 8px;white-space:nowrap}
.id{font-weight:700;color:var(--accent)}.small{font-size:12px;color:var(--muted)}ul{padding-left:20px}li{margin:4px 0}
.chart{width:100%;max-width:640px;height:auto;margin-top:8px;display:block}.grid{stroke:var(--grid)}.tick{fill:var(--muted);font-size:10px}.bar{fill:var(--accent);opacity:.75}.bar.hl{fill:var(--hl);opacity:1}
.line{fill:none;stroke:var(--accent);stroke-width:2}.marker{stroke:var(--hl);stroke-dasharray:4 3}.dot{fill:var(--hl)}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
.ev{font-size:12px;color:var(--muted)}
"""


def to_html(result, summary, lang="vi", llm_report=None):
    t = L[lang]; ds = result["dataset"]
    by = {i["id"]: i for i in result["insights"]}
    name = ds["source"].replace("\\", "/").split("/")[-1]
    h = [f"<!doctype html><html lang='{lang}'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>{html.escape(t['title'])}</title><style>{CSS}</style></head><body><main>"]
    meta = f"{ds['rows']:,} {t['rows']} × {ds['columns']} {t['cols']}"
    if ds.get("sampled"):
        meta += f" {t['sampled']} {ds['analyzed_rows']:,} {t['rows']})"
    if ds.get("target"):
        meta += f" · {t['target']}: <code>{html.escape(ds['target'])}</code>"
    h.append(f"<h1>{html.escape(t['title'])}</h1><div class='meta'><code>{html.escape(name)}</code> · {meta}</div>")
    h.append(f"<h2>{t['summary']}</h2>")
    if summary.get("headline"):
        h.append(f"<div class='headline'>{_esc(summary['headline'])}</div>")
    def ul(items):
        s = "<ul>"
        for it in items:
            txt = it["text"] if isinstance(it, dict) else it
            ev = it.get("evidence") if isinstance(it, dict) else None
            s += f"<li>{_esc(txt)}" + (f" <span class='ev'>({', '.join(ev)})</span>" if ev else "") + "</li>"
        return s + "</ul>"
    h.append(ul(summary.get("key_takeaways", [])))
    if summary.get("recommendations"):
        h.append(f"<h3>{t['recs']}</h3>" + ul(summary["recommendations"]))
    if summary.get("caveats"):
        h.append(f"<h3>{t['caveats']}</h3>" + ul(summary["caveats"]))
    note = t["llm_note"].format(m=llm_report["model"]) if llm_report and llm_report.get("ok") else t["tmpl_note"]
    h.append(f"<div class='small'>{html.escape(note)}</div>")
    h.append(f"<h2>{t['top']}</h2>")
    for iid in result["top_insights"]:
        i = by[iid]
        pv = f" · {_p(i['p'])}" if i.get("p") is not None else ""
        h.append(f"<div class='card'><div class='h'><span class='id'>{i['id']}</span><span>{_esc(i['text'][lang])}</span></div>"
                 f"{svg_chart(i.get('chart'))}<div class='small'>{i['type']} · score {i['score']:.2f}{pv}</div></div>")
    for th in THEMES + ["quality"]:
        items = [i for i in result["insights"] if i["theme"] == th]
        if not items:
            continue
        h.append(f"<h2>{t[th]}</h2><ul>")
        for i in items:
            h.append(f"<li><span class='id'>{i['id']}</span> {_esc(i['text'][lang])} <span class='badge'>{i['type']}</span></li>")
        h.append("</ul>")
    h.append(f"<h2>{t['columns']}</h2><table><tr><th>{t['column']}</th><th>{t['role']}</th><th>{t['missing']}</th><th>{t['unique']}</th></tr>")
    for c in result["columns"]:
        role = c["role"] + (f" ({c['agg']})" if c.get("agg") else "")
        h.append(f"<tr><td><code>{html.escape(c['column'])}</code></td><td>{role}</td><td>{100 * c.get('missing_pct', 0):.1f}%</td><td>{c.get('n_unique', '')}</td></tr>")
    h.append(f"</table><h2>{t['method']}</h2><p class='small'>{html.escape(t['method_text'])}</p></main></body></html>")
    return "".join(h)

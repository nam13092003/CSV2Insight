#!/usr/bin/env python3
"""CSV -> data insights.

Usage:
  python insight.py data.csv                     # statistics + LLM summary (if key available)
  python insight.py data.csv --no-llm            # statistics only (fully offline)
  python insight.py data.csv --target churn --lang en --out reports/
  python insight.py data.csv --context "Dữ liệu bán hàng chuỗi cửa hàng 2023-2024"

Outputs <out>/<name>_insights.json, <name>_report.md, <name>_report.html
Requires: pandas, numpy (no scipy/sklearn). LLM via OpenRouter, models <= 8B params only.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tableinsight.pipeline import analyze, to_jsonable  # noqa: E402
from tableinsight.profile import read_csv_robust, infer_roles  # noqa: E402
from tableinsight import llm as L  # noqa: E402
from tableinsight.render import to_markdown, to_html, template_summary  # noqa: E402


def main(argv=None):
    for st in (sys.stdout, sys.stderr):  # Windows consoles with legacy code pages
        try:
            st.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Tìm insight tự động từ bảng CSV")
    ap.add_argument("csv")
    ap.add_argument("--target", help="cột mục tiêu (vd. churn) để phân tích yếu tố ảnh hưởng")
    ap.add_argument("--lang", default="vi", choices=["vi", "en"])
    ap.add_argument("--top", type=int, default=10, help="số insight nổi bật")
    ap.add_argument("--out", default="insight_output")
    ap.add_argument("--no-llm", action="store_true", help="không gọi LLM")
    ap.add_argument("--llm-roles", action="store_true", help="dùng LLM để gợi ý ngữ nghĩa cột (sum/mean, cột ID)")
    ap.add_argument("--model", action="append", help="model OpenRouter (≤8B); có thể lặp để làm dự phòng")
    ap.add_argument("--key-file", default=None, help="file chứa OpenRouter key (mặc định openrouter_key.txt)")
    ap.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    ap.add_argument("--context", default="", help="mô tả ngắn bối cảnh dữ liệu cho phần tóm tắt")
    ap.add_argument("--max-rows", type=int, default=1_000_000, help="lấy mẫu nếu file lớn hơn")
    a = ap.parse_args(argv)

    log = lambda *x: print(*x, file=sys.stderr)  # noqa: E731
    llm = None
    if not a.no_llm:
        key = L.load_key(a.key_file)
        if key:
            try:
                llm = L.LLM(key, a.model, base_url=a.base_url, log=log)
            except ValueError as e:
                log(f"[llm] {e}"); return 2
        else:
            log("[llm] không tìm thấy key -> chỉ dùng thống kê")

    overrides = None
    if llm and a.llm_roles:
        try:
            raw = read_csv_robust(a.csv)
            df, roles = infer_roles(raw.head(5000))
            overrides = L.suggest_roles(llm, df, roles, a.lang)
            log(f"[llm] gợi ý vai trò cột: {overrides}")
        except Exception as e:  # noqa
            log(f"[llm] bỏ qua gợi ý vai trò cột: {e}")

    result = analyze(a.csv, target=a.target, top_k=a.top, role_overrides=overrides, max_rows=a.max_rows)
    log(f"[stats] {len(result['insights'])} insight trong {result['elapsed_sec']}s")

    summary, report = template_summary(result, a.lang), None
    if llm:
        try:
            summary, report = L.narrate(llm, result, a.lang, a.context)
            if not summary.get("key_takeaways"):
                summary, report = template_summary(result, a.lang), None
            else:
                log(f"[llm] tóm tắt viết bởi {report['model']}")
            if report and report["removed_sentences"]:
                log(f"[llm] đã loại {len(report['removed_sentences'])} câu chứa số không kiểm chứng được")
        except Exception as e:  # noqa
            log(f"[llm] lỗi, dùng tóm tắt tự động: {e}")
            report = None
    result["summary"] = summary
    result["llm"] = report

    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, os.path.splitext(os.path.basename(a.csv))[0])
    with open(base + "_insights.json", "w", encoding="utf-8") as f:
        json.dump(to_jsonable(result), f, ensure_ascii=False, indent=1)
    with open(base + "_report.md", "w", encoding="utf-8") as f:
        f.write(to_markdown(result, summary, a.lang, report))
    with open(base + "_report.html", "w", encoding="utf-8") as f:
        f.write(to_html(result, summary, a.lang, report))
    print(f"OK -> {base}_report.html | _report.md | _insights.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

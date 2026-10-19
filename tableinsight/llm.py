"""Optional LLM layer (OpenRouter, models <= 8B params).

The LLM never computes statistics. It only (a) writes an executive narrative from verified facts and
(b) optionally suggests column semantics. Every number it writes is checked against the facts;
sentences with unverifiable numbers are retried, then removed.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

DEFAULT_MODELS = [
    "qwen/qwen3-vl-8b-instruct",          # Qwen3 8B (text+vision), strong multilingual/Vietnamese
    "meta-llama/llama-3.1-8b-instruct",   # verified working on OpenRouter (Oct 2026)
    "mistralai/ministral-8b-2512",
    "ibm-granite/granite-4.2-8b",
    "qwen/qwen-2.5-7b-instruct",
    "google/gemma-3-4b-it",
]   # note: qwen/qwen3-8b was deprecated on OpenRouter (Oct 9, 2026)
# known small models whose size is not obvious from the id
KNOWN_SIZE_B = {"mistralai/ministral-8b": 8, "mistralai/ministral-3b": 3, "microsoft/phi-4-mini-instruct": 3.8}
MAX_PARAMS_B = 8.0


def model_size_b(model_id):
    if model_id in KNOWN_SIZE_B:
        return KNOWN_SIZE_B[model_id]
    m = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)b(?![a-z])", model_id.lower().split("/")[-1])
    if not m:
        return None
    # "e4b" style (gemma-3n) -> effective params; mixture "8x7b" -> treat as big
    if re.search(r"\d+x\d+(\.\d+)?b", model_id.lower()):
        return 999.0
    return max(float(v) for v in m)


def check_model_allowed(model_id):
    size = model_size_b(model_id)
    if size is None:
        raise ValueError(f"Không xác định được số tham số của model '{model_id}'. Chỉ cho phép model ≤ {MAX_PARAMS_B:g}B "
                         f"(id phải chứa kích thước, ví dụ '...-8b').")
    if size > MAX_PARAMS_B:
        raise ValueError(f"Model '{model_id}' có ~{size:g}B tham số, vượt giới hạn {MAX_PARAMS_B:g}B.")
    return size


def load_key(key_file=None):
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"].strip()
    cands = [key_file] if key_file else []
    here = os.path.dirname(os.path.abspath(__file__))
    cands += ["openrouter_key.txt", os.path.join(here, "..", "openrouter_key.txt")]
    for c in cands:
        if c and os.path.exists(c):
            txt = open(c, encoding="utf-8").read().strip()
            m = re.search(r"sk-or-[A-Za-z0-9_\-]+", txt)
            return m.group(0) if m else txt.splitlines()[0].strip()
    return None


class LLM:
    def __init__(self, key, models=None, base_url="https://openrouter.ai/api/v1", timeout=90, log=print):
        self.key = key
        self.models = models or DEFAULT_MODELS
        for m in self.models:
            check_model_allowed(m)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.log = log
        self.used_model = None
        self.dead = set()

    def chat(self, messages, temperature=0.2, max_tokens=1400):
        last_err = None
        for model in [m for m in self.models if m not in self.dead]:
            for attempt in range(3):
                try:
                    body = {"model": model, "messages": messages, "temperature": temperature,
                            "max_tokens": max_tokens, "reasoning": {"enabled": False}}
                    req = urllib.request.Request(
                        self.base_url + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                        headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                                 "HTTP-Referer": "https://github.com/tableinsight", "X-Title": "tableinsight"})
                    with urllib.request.urlopen(req, timeout=self.timeout) as r:
                        data = json.loads(r.read().decode("utf-8"))
                    if "error" in data:
                        raise RuntimeError(str(data["error"])[:300])
                    txt = data["choices"][0]["message"].get("content") or ""
                    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
                    if not txt:
                        raise RuntimeError("empty response")
                    self.used_model = model
                    return txt
                except urllib.error.HTTPError as e:
                    last_err = f"{model}: HTTP {e.code} {e.read()[:200]!r}"
                    if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                        time.sleep(2 * (attempt + 1)); continue
                    if e.code in (400, 404):
                        self.dead.add(model)
                    break  # 4xx (bad model id, auth...) -> next model
                except urllib.error.URLError as e:  # network/proxy problem: other models won't help
                    last_err = f"{model}: {e}"
                    if attempt < 1:
                        time.sleep(1.5); continue
                    raise RuntimeError(f"Không kết nối được OpenRouter ({e.reason}). Kiểm tra mạng/proxy.")
                except Exception as e:  # noqa
                    last_err = f"{model}: {e}"
                    if attempt < 1:
                        time.sleep(1.5); continue
                    break
            self.log(f"[llm] model {model} failed: {last_err}")
        raise RuntimeError(f"All LLM models failed. Last error: {last_err}")


# ---------------- number verification ----------------
NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?\s*[%MBK]?(?![\w])")


def _to_float(tok):
    t = tok.strip().replace(",", "").replace(" ", "")
    mult = 1.0
    if t.endswith("%"):
        t = t[:-1]
    elif t[-1:] in "MBK":
        mult = {"M": 1e6, "B": 1e9, "K": 1e3}[t[-1]]; t = t[:-1]
    try:
        return float(t) * mult
    except ValueError:
        return None


def allowed_numbers(texts):
    vals = set()
    for t in texts:
        for tok in NUM_RE.findall(t):
            v = _to_float(tok)
            if v is not None:
                vals.add(round(v, 6)); vals.add(round(abs(v), 6))
    return vals


def unverified_numbers(text, allowed, small_int_ok=10):
    bad = []
    for tok in NUM_RE.findall(text):
        v = _to_float(tok)
        if v is None:
            continue
        if float(v).is_integer() and 0 <= v <= small_int_ok:
            continue
        ok = any(abs(v - a) <= max(0.006 * abs(a), 0.0051) for a in allowed)
        if not ok:
            bad.append(tok.strip())
    return bad


def _extract_json(txt):
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no JSON object in response")
    return json.loads(txt[a:b + 1])


# ---------------- tasks ----------------
SYS_VI = ("Bạn là chuyên gia phân tích dữ liệu. Bạn CHỈ được dùng các phát hiện và con số được cung cấp; "
          "không tự tính toán, không suy đoán số mới, không bịa nguyên nhân chắc chắn. Viết tiếng Việt ngắn gọn, "
          "rõ ràng cho người làm kinh doanh. Giữ nguyên tên cột trong dấu `backtick`. Trả về DUY NHẤT một JSON hợp lệ.")
SYS_EN = ("You are a senior data analyst. Use ONLY the findings and numbers provided; never compute or invent new "
          "numbers or assert causes as certain. Write concise, plain English for business readers. Keep column "
          "names in `backticks`. Return ONLY one valid JSON object.")


def _facts_payload(result, lang, max_items=12):
    by = {i["id"]: i for i in result["insights"]}
    top = [by[i] for i in result["top_insights"]][:max_items]
    qual = [i for i in result["insights"] if i["theme"] == "quality"][:6]
    def item(i):
        return {"id": i["id"], "type": i["type"], "finding": i["text"][lang]}
    ds = result["dataset"]
    return {
        "dataset": {"rows": ds["rows"], "columns": ds["columns"], "target": ds.get("target")},
        "key_findings": [item(i) for i in top],
        "data_quality": [item(i) for i in qual],
    }


def narrate(llm, result, lang="vi", context=""):
    payload = _facts_payload(result, lang)
    texts = [json.dumps(payload, ensure_ascii=False)]
    allowed = allowed_numbers(texts)
    ids = {f["id"] for f in payload["key_findings"] + payload["data_quality"]}
    if lang == "vi":
        instr = ("Dựa trên các phát hiện dưới đây, hãy viết JSON với khóa:\n"
                 '- "headline": 1 câu tóm tắt quan trọng nhất (≤ 30 từ)\n'
                 '- "key_takeaways": 3–5 ý, mỗi ý là object {"text": ..., "evidence": ["I01", ...]} — gộp các phát hiện liên quan, nói rõ ý nghĩa kinh doanh\n'
                 '- "recommendations": 2–4 hành động cụ thể nên làm/kiểm tra tiếp, mỗi ý {"text": ..., "evidence": [...]}\n'
                 '- "caveats": 1–3 lưu ý về chất lượng dữ liệu hoặc giới hạn (tương quan ≠ nhân quả)\n'
                 "Mọi con số phải lấy nguyên văn từ phát hiện. Không thêm số mới.")
    else:
        instr = ("From the findings below write JSON with keys:\n"
                 '- "headline": one most important sentence (<= 30 words)\n'
                 '- "key_takeaways": 3-5 items {"text": ..., "evidence": ["I01", ...]} — merge related findings and state the business meaning\n'
                 '- "recommendations": 2-4 concrete next actions/checks, each {"text": ..., "evidence": [...]}\n'
                 '- "caveats": 1-3 notes on data quality or limits (correlation != causation)\n'
                 "Every number must be copied verbatim from the findings. Do not add new numbers.")
    if context:
        instr += ("\nBối cảnh do người dùng cung cấp: " if lang == "vi" else "\nUser-provided context: ") + context
    msgs = [{"role": "system", "content": SYS_VI if lang == "vi" else SYS_EN},
            {"role": "user", "content": instr + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=1) + "\n/no_think"}]
    report = {"model": None, "attempts": 0, "removed_sentences": [], "ok": False}
    out = None
    for attempt in range(2):
        report["attempts"] += 1
        raw = llm.chat(msgs)
        try:
            out = _extract_json(raw)
        except Exception as e:  # noqa
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "JSON không hợp lệ. Chỉ trả về một JSON object hợp lệ." if lang == "vi"
                      else "Invalid JSON. Return only one valid JSON object."}]
            out = None
            continue
        bad = _collect_bad(out, allowed)
        if not bad:
            break
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": (f"Các số sau không có trong phát hiện: {sorted(set(bad))}. Viết lại, chỉ dùng số có sẵn."
                                              if lang == "vi" else
                                              f"These numbers are not in the findings: {sorted(set(bad))}. Rewrite using only given numbers.")}]
    if out is None:
        raise RuntimeError("LLM did not return valid JSON")
    out, removed = _sanitize(out, allowed, ids)
    report.update(model=llm.used_model, removed_sentences=removed, ok=True)
    return out, report


def _iter_texts(out):
    if isinstance(out.get("headline"), str):
        yield out["headline"]
    for k in ("key_takeaways", "recommendations", "caveats"):
        for it in out.get(k, []) or []:
            yield it["text"] if isinstance(it, dict) else str(it)


def _collect_bad(out, allowed):
    bad = []
    for t in _iter_texts(out):
        bad += unverified_numbers(t, allowed)
    return bad


def _split_sentences(t):
    return [s for s in re.split(r"(?<=[.!?;])\s+", t.strip()) if s]


def _clean_text(t, allowed, removed):
    keep = []
    for s in _split_sentences(t):
        if unverified_numbers(s, allowed):
            removed.append(s)
        else:
            keep.append(s)
    return " ".join(keep).strip()


def _sanitize(out, allowed, ids):
    removed = []
    res = {"headline": _clean_text(str(out.get("headline", "")), allowed, removed)}
    for k in ("key_takeaways", "recommendations", "caveats"):
        items = []
        for it in out.get(k, []) or []:
            if isinstance(it, dict):
                txt = _clean_text(str(it.get("text", "")), allowed, removed)
                ev = [e for e in it.get("evidence", []) or [] if isinstance(e, str) and e in ids]
            else:
                txt, ev = _clean_text(str(it), allowed, removed), []
            if txt:
                items.append({"text": txt, "evidence": ev})
        res[k] = items[:6]
    return res, removed


def suggest_roles(llm, df, roles, lang="vi"):
    """Ask the LLM for column semantics; only 'agg' (sum/mean) for measures and 'ignore' for id-like are applied."""
    cols = []
    for c, r in roles.items():
        if c.startswith("_"):
            continue
        sample = [str(v)[:30] for v in df[c].dropna().astype(str).unique()[:5]]
        cols.append({"column": c, "detected_role": r["role"], "agg": r.get("agg"), "samples": sample})
    instr = ("For each column decide: is it an identifier (ignore), and for numeric measures should totals be "
             "summed across rows ('sum', e.g. revenue, quantity, count) or averaged ('mean', e.g. price, rate, age, score)? "
             'Return JSON {"columns": {"<name>": {"agg": "sum"|"mean"|null, "is_identifier": true|false, "description": "<5-10 words>"}}}.')
    msgs = [{"role": "system", "content": "You are a data engineer. Return only valid JSON."},
            {"role": "user", "content": instr + "\n" + json.dumps(cols, ensure_ascii=False) + "\n/no_think"}]
    out = _extract_json(llm.chat(msgs, temperature=0.0, max_tokens=1500))
    over = {}
    for c, v in (out.get("columns") or {}).items():
        if c not in roles or not isinstance(v, dict):
            continue
        o = {}
        if roles[c]["role"] == "measure" and not roles[c].get("also_dimension") and v.get("agg") in ("sum", "mean"):
            if v["agg"] == "sum" and (df[c].dropna() < 0).any():
                pass
            else:
                o["agg"] = v["agg"]
        if v.get("is_identifier") is True and roles[c]["role"] in ("dimension", "text") and roles[c]["n_unique"] > 0.5 * len(df):
            o["role"] = "id"
        if isinstance(v.get("description"), str):
            o["desc"] = v["description"][:80]
        if o:
            over[c] = o
    return over

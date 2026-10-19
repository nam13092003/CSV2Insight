"""Fake OpenRouter endpoint for offline testing of the LLM layer.
1st call: answer contains a hallucinated number (must be caught and retried).
2nd call: answer still contains one bad sentence (must be removed by sanitizer).
Model ids starting with 'bad/' return HTTP 404 (tests fallback)."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

CALLS = {"n": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["model"].startswith("bad/"):
            self.send_response(404); self.end_headers(); self.wfile.write(b'{"error":"no model"}'); return
        user = body["messages"][1]["content"]
        ids = re.findall(r'"id": "(I\d+)"', user)
        finds = re.findall(r'"finding": "([^"]+)"', user)
        CALLS["n"] += 1
        f0 = finds[0] if finds else "x"
        if CALLS["n"] == 1:
            txt = {"headline": "Doanh thu tăng 37.5% và đạt 9,999,999 đơn vị.",
                   "key_takeaways": [{"text": f0, "evidence": ids[:1]}], "recommendations": [], "caveats": []}
        else:
            txt = {"headline": f0,
                   "key_takeaways": [{"text": finds[1] if len(finds) > 1 else f0, "evidence": ids[1:2] + ["I99"]},
                                     {"text": "Nhóm này đóng góp 12345 đơn vị. Cần theo dõi thêm.", "evidence": []}],
                   "recommendations": [{"text": "Kiểm tra nguyên nhân sụt giảm của nhóm nổi bật.", "evidence": ids[:1]}],
                   "caveats": ["Tương quan không đồng nghĩa nhân quả."]}
        out = {"choices": [{"message": {"content": "<think>hmm</think>```json\n" + json.dumps(txt, ensure_ascii=False) + "\n```"}}]}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8765), H).serve_forever()

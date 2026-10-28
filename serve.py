#!/usr/bin/env python3
"""本地服务：静态文件 + 手动刷新 API

- GET  /                 静态页面
- POST /api/refresh      触发 update.sh（后台跑，不阻塞）
- GET  /api/status       查询刷新进度与日志

线上（GitHub Pages）没有这个后端，前端会自动降级为"只重新拉取数据文件"。
"""
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
UPDATE = os.path.join(BASE, "update.sh")
PORT = int(os.environ.get("PORT", 8899))

STATE = {
    "running": False,
    "log": [],
    "started": None,
    "finished": None,
    "ok": None,
    "date": None,
}
LOCK = threading.Lock()


def _latest_date():
    try:
        d = json.load(open(os.path.join(BASE, "data", "dashboard.json")))
        return d["rows"][-1]["date"]
    except Exception:
        return None


def run_update():
    with LOCK:
        STATE.update(running=True, log=[], started=time.time(),
                     finished=None, ok=None)
    try:
        p = subprocess.Popen(
            ["/bin/bash", UPDATE],
            cwd=BASE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in p.stdout:
            line = line.rstrip()
            if not line:
                continue
            with LOCK:
                STATE["log"].append(line)
                if len(STATE["log"]) > 300:
                    STATE["log"] = STATE["log"][-300:]
        p.wait()
        ok = (p.returncode == 0)
    except Exception as e:
        with LOCK:
            STATE["log"].append(f"执行异常: {e}")
        ok = False

    with LOCK:
        STATE.update(running=False, finished=time.time(), ok=ok, date=_latest_date())


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def log_message(self, fmt, *args):
        pass  # 静音访问日志

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] == "/api/refresh":
            with LOCK:
                if STATE["running"]:
                    self._json(409, {"error": "busy"})
                    return
            threading.Thread(target=run_update, daemon=True).start()
            self._json(200, {"ok": True, "msg": "started"})
            return
        self.send_error(404)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/status":
            with LOCK:
                snap = dict(STATE)
                snap["log"] = STATE["log"][-12:]
            self._json(200, snap)
            return
        # 静态文件不缓存，保证刷新后拿到新的 data.js
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(BASE)
    with Server(("0.0.0.0", PORT), Handler) as httpd:
        print(f"serving on http://127.0.0.1:{PORT}  (Ctrl+C 停止)")
        httpd.serve_forever()

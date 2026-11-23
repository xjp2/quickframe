"""QuickFrame T1 job service — stdlib HTTP server, single-process worker.

API:
  POST /jobs            {topic, template, lengthSec, aspect, voice, tone,
                         captions, music, duck, silentVoice?} -> 202 {job}
                         409 + blocker payload if no TTS vendor and
                         silentVoice not set (no simulated render)
  GET  /jobs/<id>       job state + 7-key stage log + download (signed URL)
  GET  /jobs            recent ids
  GET  /files/<key>?exp=&sig=   signed download (HMAC, expiring)
  GET  /healthz/service real readiness (ffmpeg, fonts, TTS vendor, store)

Job state persists to jobs/<id>.json (T5 seed). Deployable as-is on any
host with python + ffmpeg; hosting decision is the owner's (see README).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import brand, env, images, runner, store, voice

_jobs: dict[str, dict] = {}
_queue: list[str] = []
_lock = threading.Lock()
_re = re.compile(r"^/(jobs(?:/[a-z0-9-]+)?|files/[^?]+|healthz/service)$")


# ---------------------------------------------------------------- CORS
# The website (Hashmeta site origin) calls this service cross-origin, so the
# JSON endpoints need CORS. Allowed origins are a single configurable value:
#   QF_CORS_ORIGIN = "*" | comma-separated allowlist
# Default allowlist covers the production site + local dev origins. This does
# NOT touch the job contract or the seven stage keys — it only adds response
# headers and an OPTIONS preflight handler.
_DEFAULT_CORS_ORIGINS = (
    "https://quickframe.geo.hashmeta.tech,"
    "http://127.0.0.1:8777,http://localhost:8777,"
    "http://127.0.0.1:3000,http://localhost:3000"
)


def _cors_allowlist():
    raw = (os.environ.get("QF_CORS_ORIGIN") or "").strip()
    if raw == "*":
        return "*"
    return [o.strip() for o in (raw or _DEFAULT_CORS_ORIGINS).split(",") if o.strip()]


def _cors_origin(req_origin: str | None):
    """Return the value to echo in Access-Control-Allow-Origin, or None to omit
    CORS headers (unknown origin -> browser blocks; same-origin needs none)."""
    allow = _cors_allowlist()
    if allow == "*":
        return req_origin or "*"
    if req_origin and req_origin in allow:
        return req_origin
    return None


def _persist(job: dict):
    with open(os.path.join(env.jobs_dir(), f"{job['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)


def _fail_stage(job: dict, status: str):
    """Mark the stage currently in flight as failed/blocked for the UI chips."""
    ss = job.get("stageState", {})
    for k in reversed(brand.PIPELINE):
        if ss.get(k) == "running":
            ss[k] = status
            return


def _load_existing():
    for p in os.listdir(env.jobs_dir()):
        if p.endswith(".json"):
            with open(os.path.join(env.jobs_dir(), p), encoding="utf-8") as f:
                j = json.load(f)
            _jobs[j["id"]] = j
            if j["state"] == "queued":
                _queue.append(j["id"])


def _worker_loop():
    while True:
        jid = None
        with _lock:
            if _queue:
                jid = _queue.pop(0)
        if not jid:
            time.sleep(0.2)
            continue
        job = _jobs[jid]
        job["state"] = "running"
        _persist(job)
        try:
            runner.run(job)
            job["state"] = "done"
        except runner.Blocker as b:
            job["state"] = "blocked"
            job["blocker"] = {"code": b.code, "message": b.message}
            _fail_stage(job, "blocked")
        except Exception as e:
            job["state"] = "failed"
            job["error"] = {"type": type(e).__name__, "message": str(e)}
            job["trace"] = traceback.format_exc(limit=6)
            _fail_stage(job, "failed")
        _persist(job)


class Handler(BaseHTTPRequestHandler):
    server_version = "QuickFrameT1/0.1"

    def _cors_actual(self):
        """Emit CORS headers on an actual (non-preflight) response if the caller's
        Origin is allowed. Call before end_headers()."""
        o = _cors_origin(self.headers.get("Origin"))
        if o:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # noqa: N802  (CORS preflight)
        o = _cors_origin(self.headers.get("Origin"))
        self.send_response(204 if o else 400)
        if o:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_actual()
        self.end_headers()
        self.wfile.write(body)

    def _public_base(self) -> str:
        """Absolute base used to mint signed download URLs.

        Priority: explicit QF_PUBLIC_BASE, else the public URL the reverse proxy
        forwarded (HF Spaces sets Host + X-Forwarded-Proto to the Space domain),
        else loopback. This makes GET /jobs/<id> return a URL that actually works
        on the deployed Space without any per-deploy config.
        """
        env_base = os.environ.get("QF_PUBLIC_BASE")
        if env_base:
            return env_base.rstrip("/")
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        if host:
            return f"{proto}://{host}"
        return "http://127.0.0.1:8777"

    def do_POST(self):  # noqa: N802
        if self.path != "/jobs":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            cfg = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "invalid JSON body"})
        if not str(cfg.get("topic") or "").strip():
            return self._send(400, {"error": "topic is required"})
        if not cfg.get("silentVoice") and not voice.available():
            return self._send(409, {"error": {
                "code": "tts_vendor_missing",
                "message": str(voice.TTSNotConfigured()),
                "hint": "set QF_TTS_CMD, or send silentVoice=true for a validation render"}})
        jid = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        job = {"id": jid, "cfg": cfg, "state": "queued", "log": [],
               "stages": brand.PIPELINE, "createdAt": round(time.time(), 3),
               "public_base": self._public_base(),
               "stageState": {k: "pending" for k in brand.PIPELINE}}
        with _lock:
            _jobs[jid] = job
            _queue.append(jid)
        _persist(job)
        self._send(202, {"id": jid, "state": "queued", "stages": brand.PIPELINE})

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            try:
                with open(p, "rb") as f:
                    html = f.read()
            except FileNotFoundError:
                return self._send(404, {"error": "index.html missing"})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self._cors_actual()
            self.end_headers()
            self.wfile.write(html)
            return
        if u.path == "/healthz/service":
            fonts = {}
            for k in ("display", "hand", "mono", "body"):
                p, sub = env.find_font(k)
                fonts[k] = {"resolved": os.path.basename(p), "substituted": sub}
            return self._send(200, {
                "ok": True, "ffmpeg": env.ffmpeg_bin(), "cpu": env.cpu_count(),
                "voiceVendor": voice.available(), "fonts": fonts,
                "images": {"mode": images.mode(), "model": images.MODEL},
                "storeFreeNote": "local filesystem backend",
                "stages": brand.PIPELINE})
        if u.path == "/jobs":
            with _lock:
                ids = sorted(_jobs.keys())[-50:]
            return self._send(200, {"jobs": [{"id": i, "state": _jobs[i]["state"]} for i in ids]})
        m = re.match(r"^/jobs/([a-z0-9-]+)$", u.path)
        if m:
            job = _jobs.get(m.group(1))
            if not job:
                return self._send(404, {"error": "no such job"})
            out = {k: job.get(k) for k in ("id", "state", "stages", "stageState",
                                           "log", "result", "download", "blocker",
                                           "error", "createdAt")}
            return self._send(200, out)
        m = re.match(r"^/files/(.+)$", u.path)
        if m:
            key = m.group(1)
            ok, why = store.verify(key, q.get("exp", [""])[0], q.get("sig", [""])[0])
            if not ok:
                return self._send(403, {"error": why})
            try:
                p = store.path(key)
            except FileNotFoundError:
                return self._send(404, {"error": "no such object"})
            ctype = "video/mp4" if p.endswith(".mp4") else "application/json"
            with open(p, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(key)}"')
            self._cors_actual()
            self.end_headers()
            self.wfile.write(data)
            return
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # quiet
        pass


def main(port: int = 8777):
    os.environ.setdefault("QF_ROOT", env.ROOT)
    _load_existing()
    threading.Thread(target=_worker_loop, daemon=True).start()
    # Bind host is configurable for container/host deploy (0.0.0.0); defaults to
    # loopback for local dev so the service is never accidentally world-open.
    host = os.environ.get("QF_HOST", "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"QuickFrame T1 job service on http://{host}:{port} "
          f"(voice vendor {'configured' if voice.available() else 'NOT configured'})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    main(int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8777)))

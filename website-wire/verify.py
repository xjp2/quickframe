"""QuickFrame website-wire — end-to-end verification against the LOCAL T1 service.

Proves the exact call flow the storefront uses, on an UNSEEN topic, and that the
CORS the website needs is in place. No simulated render: a real MP4 must come out
and is probed. Exits non-zero on any failed claim.

Run the service first:
    (from D:\\qf-t1-build)  QF_RENDER_WORKERS=1 python -m qf.server 8777
then:
    python verify.py
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request, urllib.error
from urllib.parse import urlparse
import numpy as np

BASE = os.environ.get("QF_ACCEPT_BASE", "http://127.0.0.1:8777")
SITE_ORIGIN = "https://quickframe.geo.hashmeta.tech"
STAGES = ["script", "boards", "art", "voice", "captions", "encode", "publish"]
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# An unseen topic (not used by any prior acceptance run) + the cfg the storefront
# sends for it (mapped from the studio-demo controls, per generator-wire.js).
TOPIC = "how do noise-cancelling headphones cancel sound"
CFG = {"topic": TOPIC, "template": "why", "lengthSec": 12,
       "aspect": "16:9", "voice": "calm-01", "captions": "karaoke", "music": "drive"}


def jreq(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), (json.loads(raw) if raw[:1] in (b"{", b"[") else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, dict(e.headers), json.loads(raw)
        except Exception:
            return e.code, dict(e.headers), raw


def urlpath(url):
    p = urlparse(url)
    return p.path + (f"?{p.query}" if p.query else "")


def check_cors():
    print("== CORS (what the website needs) ==")
    st, hd, _ = jreq("OPTIONS", "/jobs", headers={
        "Origin": SITE_ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    acao = hd.get("Access-Control-Allow-Origin")
    assert st == 204 and acao == SITE_ORIGIN, f"preflight for site origin -> {st}, ACAO={acao}"
    assert "POST" in (hd.get("Access-Control-Allow-Methods") or ""), "POST not allowed"
    print(f"  site origin preflight -> 204, ACAO={acao}, methods={hd.get('Access-Control-Allow-Methods')}")

    st2, _, _ = jreq("OPTIONS", "/jobs", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert st2 == 400, f"disallowed origin should be rejected, got {st2}"
    print("  unknown origin preflight -> 400 (not in allowlist)")

    st3, hd3, _ = jreq("GET", "/healthz/service", headers={"Origin": SITE_ORIGIN})
    assert hd3.get("Access-Control-Allow-Origin") == SITE_ORIGIN, "actual GET missing CORS header"
    print("  GET /healthz with site Origin -> ACAO echoed")


def main():
    check_cors()

    st, _, h = jreq("GET", "/healthz/service")
    assert st == 200 and h["voiceVendor"], f"service not ready: {h}"
    print("\n== job contract (unseen topic) ==")
    print("health: ffmpeg present, voice vendor configured")

    st, _, j = jreq("POST", "/jobs", CFG)
    assert st == 202, f"POST -> {st} {j}"
    jid = j["id"]
    assert j["stages"] == STAGES, "stage keys drifted at create"
    print(f"job {jid} queued · topic={TOPIC!r}")

    job, deadline = None, time.time() + 300
    while time.time() < deadline:
        _, _, job = jreq("GET", f"/jobs/{jid}")
        if job["state"] in ("done", "failed", "blocked"):
            break
        time.sleep(1.5)
    print("stage log:")
    for e in job["log"]:
        print(f"  [{e['stage']}] {e['line']}")
    assert job["state"] == "done", f"ended {job['state']}: {job.get('error') or job.get('blocker')}"
    assert job["stages"] == STAGES, "stage keys drifted"
    assert all(job["stageState"].get(k) == "done" for k in STAGES), f"stageState not all done: {job['stageState']}"

    r = job["result"]
    assert r["voice"]["tts"] == "edge-tts", f"voice engine: {r['voice']['tts']}"
    assert sum(len(s["cues"]) for s in r["scenes"]) > 0, "no captions"
    print(f"contract: {len(r['scenes'])} scenes · {r['totalSec']}s · {r['credits']} credits · "
          f"voice={r['voice']['tts']} · cues={sum(len(s['cues']) for s in r['scenes'])}")

    url = job["download"]["url"]
    print("\n== signed download ==")
    st, _, mp4 = jreq("GET", urlpath(url))
    assert st == 200 and len(mp4) > 50_000, f"signed download -> {st}, {len(mp4)} bytes"
    out = os.path.join(OUT_DIR, f"e2e-{jid}.mp4")
    open(out, "wb").write(mp4)

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", out],
        capture_output=True, text=True).stdout)
    v = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert v["codec_name"] == "h264" and a, "not a real h264+aac encode"
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-map", "0:a", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    arr = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
    rms = float(np.sqrt((arr ** 2).mean())) if arr.size else 0.0
    dur = float(probe["format"]["duration"])
    print(f"mp4: {v['codec_name']} {v['width']}x{v['height']} {dur:.2f}s "
          f"{len(mp4)} bytes audio={[x['codec_name'] for x in a]} RMS={rms:.4f}")
    assert rms > 0.01, "audio effectively silent — voice did not render speech"

    bad = url.replace(url.split("sig=")[1][:8], "0" * 8)
    st, _, _ = jreq("GET", urlpath(bad))
    assert st == 403, f"tampered signed URL accepted ({st})"
    print("tampered signed URL -> 403 (signature enforced)")

    print("\nEVIDENCE")
    print("  job id :", jid)
    print("  signed url:", url)
    print("  mp4 file  :", out)
    print("VERIFY: PASS")


if __name__ == "__main__":
    main()

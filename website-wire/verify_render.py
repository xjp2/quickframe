"""End-to-end proof that the wired studio-demo form can drive the LIVE Render
backend. Submits the EXACT cfg the storefront's buildCfg() produces (template
'why', lengthSec 30, aspect 16:9, voice calm-01, captions karaoke, music drive),
polls like startRun(), then does what finishRun() does with download.url.
Uses an unseen topic and a real 30s render. No simulation."""
from __future__ import annotations
import json, os, subprocess, time, urllib.request, urllib.error
from urllib.parse import urlparse
import numpy as np

BASE = "https://quickframe-t1.onrender.com"
SITE_ORIGIN = "https://quickframe.geo.hashmeta.tech"
STAGES = ["script", "boards", "art", "voice", "captions", "encode", "publish"]
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TOPIC = "why do airplanes leave white trails in the sky"
CFG = {"topic": TOPIC, "template": "why", "lengthSec": 30,
       "aspect": "16:9", "voice": "calm-01", "captions": "karaoke", "music": "drive"}


def req(method, url, body=None, headers=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        js = json.loads(raw) if raw[:1] in (b"{", b"[") else raw
        # Render's proxy lowercases header names; keep a case-insensitive view.
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}, js


def main():
    print("BASE =", BASE)
    # 1) health (voice vendor must be configured or POST returns 409)
    st, _, h = req("GET", BASE + "/healthz/service")
    print("health:", st, "voiceVendor=", h.get("voiceVendor"), "stages=", h.get("stages"))
    assert st == 200 and h.get("voiceVendor") is True, f"service not ready: {h}"
    assert h.get("stages") == STAGES, "stage keys drifted on the deployed service"

    # 2) CORS preflight exactly as the browser sends it from the site origin
    st, hd, _ = req("OPTIONS", BASE + "/jobs", headers={
        "Origin": SITE_ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    print("preflight:", st, "ACAO=", hd.get("access-control-allow-origin"))
    assert st == 204 and hd.get("access-control-allow-origin") == SITE_ORIGIN, "CORS preflight failed"

    # 3) POST /jobs  (startRun)
    t0 = time.time()
    st, _, j = req("POST", BASE + "/jobs", CFG)
    print("POST /jobs ->", st, j)
    assert st == 202, f"POST -> {st} {j}"
    jid = j["id"]
    assert j["stages"] == STAGES

    # 4) poll like the wired startRun()/poll() (which tolerates transient errors)
    job, deadline = None, time.time() + 360
    seen = -1
    while time.time() < deadline:
        try:
            _, _, job = req("GET", BASE + f"/jobs/{jid}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  poll transient error ({e}); retrying next tick (mirrors wired catch)")
            time.sleep(2)
            continue
        ss = job.get("stageState", {})
        line = " ".join(f"{k}:{ss.get(k,'-')}" for k in STAGES)
        ndone = sum(1 for k in STAGES if ss.get(k) == "done")
        if ndone != seen:
            seen = ndone
            print(f"  [{time.time()-t0:5.1f}s] state={job['state']:8s} {line}")
        if job["state"] in ("done", "failed", "blocked"):
            break
        time.sleep(2)
    assert job["state"] == "done", f"ended {job['state']}: {job.get('error') or job.get('blocker')}"
    print(f"stage log ({len(job['log'])} entries):")
    for e in job["log"]:
        print(f"  [{e['stage']}] {e['line']}")

    # 5) finishRun() reads download.url + result
    d = job["download"]; r = job["result"]
    print(f"\nresult: scenes={len(r['scenes'])} totalSec={r['totalSec']} credits={r.get('credits')} "
          f"voice={r['voice']['tts']} cues={sum(len(s['cues']) for s in r['scenes'])}")
    assert r["voice"]["tts"] == "edge-tts", r["voice"]
    assert sum(len(s["cues"]) for s in r["scenes"]) > 0, "no captions"
    url = d["url"]
    print("download.url =", url)
    print("expiresIn=", d.get("expiresIn"), "sizeBytes=", d.get("sizeBytes"), "durationSec=", d.get("durationSec"))

    # 6) fetch the signed MP4 (this is what the player <video src> + download link use)
    p = urlparse(url)
    dlpath = BASE + p.path + (f"?{p.query}" if p.query else "")
    mp4 = None
    for attempt in range(6):
        try:
            st, _, mp4 = req("GET", dlpath, timeout=180)
            if st == 200 and len(mp4) > 50_000:
                break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  download transient error ({e}); retry {attempt+1}")
            mp4 = None
        time.sleep(3)
    assert mp4 is not None and st == 200 and len(mp4) > 50_000, f"signed download failed: {st}"
    out = os.path.join(OUT_DIR, f"render-e2e-{jid}.mp4")
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
    print(f"mp4: {v['codec_name']} {v['width']}x{v['height']} {dur:.2f}s {len(mp4)} bytes "
          f"audio={[x['codec_name'] for x in a]} RMS={rms:.4f}")
    assert rms > 0.01, "audio effectively silent"

    print("\nEVIDENCE")
    print("  job id :", jid)
    print("  topic  :", TOPIC)
    print("  signed :", url)
    print("  mp4    :", out)
    print("RENDER E2E: PASS")


if __name__ == "__main__":
    main()

"""QuickFrame T1 — real-voice acceptance (the actual product claim).

Unseen topic -> POST /jobs (real edge-tts voice, NOT silent) -> poll the 7-stage
log -> download via the signed URL -> ffprobe + a non-silent-audio check.
Proves: a topic never seen before returns a downloadable MP4 with real speech
and captions anchored to real word timings. Exits non-zero on any failed claim.

Run the server first (python -m qf.server 8777), then:
    python acceptance.py "why does the moon look bigger near the horizon"
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request, urllib.error
from urllib.parse import urlparse
import numpy as np

BASE = os.environ.get("QF_ACCEPT_BASE", "http://127.0.0.1:8777")
STAGES = ["script", "boards", "art", "voice", "captions", "encode", "publish"]


def jreq(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw[:1] in b"{[" else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def urlpath(url: str) -> str:
    """Absolute signed URL -> path?query, so the request goes to BASE regardless
    of the QF_PUBLIC_BASE the server minted it with."""
    p = urlparse(url)
    return p.path + (f"?{p.query}" if p.query else "")


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "why does the moon look bigger near the horizon"
    ok = True

    st, h = jreq("GET", "/healthz/service")
    assert st == 200 and h["voiceVendor"], f"service not ready: {h}"
    print("health: ffmpeg present, voice vendor configured")

    REQ_LEN = 12
    st, j = jreq("POST", "/jobs", {"topic": topic, "template": "why", "lengthSec": REQ_LEN,
                                    "aspect": "16:9", "voice": "calm-01",
                                    "captions": "blocks", "music": "drive"})
    assert st == 202, f"POST -> {st} {j}"
    jid = j["id"]
    print(f"job {jid} queued · topic={topic!r}")

    job, deadline = None, time.time() + 300
    while time.time() < deadline:
        _, job = jreq("GET", f"/jobs/{jid}")
        if job["state"] in ("done", "failed", "blocked"):
            break
        time.sleep(1.5)
    print("stage log:")
    for e in job["log"]:
        print(f"  [{e['stage']}] {e['line']}")
    assert job["state"] == "done", f"ended {job['state']}: {job.get('error') or job.get('blocker')}"
    assert job["stages"] == STAGES, "stage keys drifted"

    r = job["result"]
    assert r["voice"]["tts"] == "edge-tts", f"voice engine: {r['voice']['tts']}"
    arts = [s["art"] for s in r["scenes"]]
    assert len(set(arts)) == len(arts), "art repeats within a job"
    assert sum(len(s["cues"]) for s in r["scenes"]) > 0, "no captions"
    print(f"contract: {len(r['scenes'])} scenes · {r['totalSec']}s · {r['credits']} credits · "
          f"voice={r['voice']['tts']} · cues={sum(len(s['cues']) for s in r['scenes'])}")

    url = job["download"]["url"]
    st, mp4 = jreq("GET", urlpath(url))
    assert st == 200 and len(mp4) > 50_000, f"signed download -> {st}, {len(mp4)} bytes"
    out = os.path.join(os.environ.get("QF_ROOT", "."), f"accept-{jid}.mp4")
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
    # lengthSec must be honored: rendered duration within ~15% of the request.
    dev = abs(dur - REQ_LEN) / REQ_LEN
    print(f"duration: requested {REQ_LEN}s -> actual {dur:.2f}s ({dev*100:.0f}% off)")
    assert dev <= 0.15, f"lengthSec not honored: requested {REQ_LEN}s, rendered {dur:.2f}s"

    bad = url.replace(url.split("sig=")[1][:8], "0" * 8)
    st, _ = jreq("GET", urlpath(bad))
    assert st == 403, f"tampered signed URL accepted ({st})"
    print("tampered signed URL -> 403 (signature enforced)")

    print("ACCEPTANCE:", "PASS" if ok else "FAIL")
    print("download:", url)
    print("file:", out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

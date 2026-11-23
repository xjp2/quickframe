"""T1 acceptance smoke: unseen topic -> POST /jobs -> poll -> signed URL ->
download real MP4 -> ffprobe verify. Run from the project root:

    python -m qf.smoke            # validation render (silent voice, flagged)

Exits non-zero on any failed claim. Prints measured evidence.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8777"
TOPIC = "why elevator music exists"  # never in any spine example


def req(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    ok = True
    st, h = req("GET", "/healthz/service")
    assert st == 200, "service not up"
    print("health:", json.dumps(h, indent=2))

    st, j = req("POST", "/jobs", {"topic": TOPIC, "template": "why", "lengthSec": 14,
                                  "aspect": "16:9", "voice": "calm-01", "captions": "blocks",
                                  "music": "drive", "silentVoice": True})
    assert st == 202, f"POST /jobs -> {st} {j}"
    jid = j["id"]
    print(f"job {jid} queued")

    deadline = time.time() + 300
    state = "queued"
    while time.time() < deadline:
        st, job = req("GET", f"/jobs/{jid}")
        state = job["state"]
        if state in ("done", "failed", "blocked"):
            break
        time.sleep(1.0)
    print("stage log:")
    for e in job["log"]:
        print(f"  [{e['stage']}] {e['line']}")
    assert state == "done", f"job ended {state}: {job.get('error') or job.get('blocker')}"

    r = job["result"]
    # contract checks
    for k in ("id", "topic", "subject", "template", "templateName", "scenes",
              "totalSec", "credits", "warnings"):
        assert k in r, f"job JSON missing {k}"
    assert [s for s in job["stages"]] == ["script", "boards", "art", "voice",
                                          "captions", "encode", "publish"]
    sc = r["scenes"][0]
    for k in ("i", "beat", "vo", "caption", "onText", "motion", "art", "whyArt",
              "clip", "sec", "words", "chars", "start", "end", "cues"):
        assert k in sc, f"scene missing {k}"
    assert all(c["at"] >= s["start"] - 1e-6 and c["at"] <= s["end"] + 1e-6
               for s in r["scenes"] for c in s["cues"]), "cues outside scene windows"
    arts = [s["art"] for s in r["scenes"]]
    assert len(set(arts)) == len(arts), "art repeats"
    print("contract: OK · scenes:", [(s["art"], s["onText"]) for s in r["scenes"]])
    print("warnings:", r["warnings"])

    # download via signed URL
    url = job["download"]["url"]
    assert url.startswith(BASE), f"signed url base {url}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        mp4 = resp.read()
    out = rf"D:\qf-t1-build\.render_work\accept-{jid}.mp4"
    with open(out, "wb") as f:
        f.write(mp4)
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
         "-show_streams", out], capture_output=True, text=True).stdout)
    v = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    dur = float(probe["format"]["duration"])
    print(f"mp4: {v['codec_name']} {v['width']}x{v['height']} {dur:.2f}s "
          f"{len(mp4)} bytes, audio streams: {len(a)} ({a[0]['codec_name'] if a else 'none'})")
    assert v["codec_name"] == "h264" and a and len(mp4) > 50_000, "not a real encode"

    # tamper check on the signature
    bad = url.replace("sig=" + url.split("sig=")[1][:8], "sig=" + "0" * 8)
    try:
        urllib.request.urlopen(bad, timeout=10)
        print("SIGNATURE CHECK FAILED: tampered URL accepted")
        ok = False
    except urllib.error.HTTPError as e:
        print(f"tampered signed URL -> {e.code} (expected 403)")

    print("SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

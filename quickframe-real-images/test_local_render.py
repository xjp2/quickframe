"""End-to-end local render test against http://127.0.0.1:8790.
POST /jobs -> poll GET /jobs/<id> -> download signed MP4 -> ffprobe -> frames.
Writes its own report (no PowerShell redirection).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8790"
HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC = "why do rivers bend and curve across flat plains"

body = json.dumps({"topic": TOPIC, "template": "why", "lengthSec": 15,
                   "aspect": "16:9", "voice": "calm-01", "captions": "blocks",
                   "music": "drive"}).encode()
req = urllib.request.Request(BASE + "/jobs", data=body,
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    created = json.load(r)
jid = created["id"]
print("job:", jid, flush=True)

job = None
t0 = time.time()
while time.time() - t0 < 900:
    time.sleep(5)
    with urllib.request.urlopen(BASE + f"/jobs/{jid}", timeout=30) as r:
        job = json.load(r)
    ss = job.get("stageState", {})
    print(f"  {round(time.time()-t0)}s state={job['state']} stages={ss}", flush=True)
    if job["state"] in ("done", "blocked", "failed"):
        break

report = {"job": jid, "state": job["state"], "elapsed": round(time.time() - t0, 1),
          "log": job.get("log"), "blocker": job.get("blocker"), "error": job.get("error")}
if job["state"] == "done":
    url = job["download"]["url"]
    mp4 = os.path.join(HERE, f"local-render-{jid}.mp4")
    with urllib.request.urlopen(url, timeout=120) as r, open(mp4, "wb") as f:
        f.write(r.read())
    probe = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                            "-show_format", "-show_streams", mp4],
                           capture_output=True, text=True, check=True).stdout
    pj = json.loads(probe)
    v = next(s for s in pj["streams"] if s["codec_type"] == "video")
    a = next(s for s in pj["streams"] if s["codec_type"] == "audio")
    report["mp4"] = {"path": mp4, "bytes": os.path.getsize(mp4),
                     "duration": pj["format"]["duration"],
                     "video": f"{v['codec_name']} {v['width']}x{v['height']}",
                     "audio": f"{a['codec_name']} {a.get('sample_rate')}Hz"}
    # decoded audio RMS (non-silent proof)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-map", "0:a",
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                         capture_output=True, check=True).stdout
    import array
    samples = array.array("h"); samples.frombytes(raw)
    rms = (sum(s * s for s in samples) / max(1, len(samples))) ** 0.5 / 32768
    report["audio_rms"] = round(rms, 4)
    # one frame per scene at mid-scene (visual proof of AI images + captions)
    for sc in job["result"]["scenes"]:
        mid = (sc["start"] + sc["end"]) / 2
        fp = os.path.join(HERE, f"local-frame-{jid}-s{sc['i']}.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(mid), "-i", mp4,
                        "-frames:v", "1", "-q:v", "3", fp], check=True)
    # tampered signed URL must 403
    bad = url[:-8] + ("aaaaaaaa" if not url.endswith("aaaaaaaa") else "bbbbbbbb")
    try:
        urllib.request.urlopen(bad, timeout=30)
        report["tampered_url"] = "UNEXPECTED 200"
    except urllib.error.HTTPError as e:
        report["tampered_url"] = e.code
with open(os.path.join(HERE, "local-render-report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps({k: v for k, v in report.items() if k != "log"}, indent=2))
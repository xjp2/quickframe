"""Render backend verification: wait for the new build (healthz gains the
`images` field), then run a real job on an unseen topic and download the MP4.
Writes its own report JSON.
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

BASE = "https://quickframe-t1.onrender.com"
HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC = "why do autumn leaves change color before falling"
report = {"topic": TOPIC}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "quickframe-verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# 1) wait for redeploy: new build exposes healthz.images
t0 = time.time()
health = None
while time.time() - t0 < 1500:
    try:
        health = get(BASE + "/healthz/service")
        if "images" in health:
            print(f"new build live after {round(time.time()-t0)}s: images={health['images']}", flush=True)
            break
        print(f"  old build still serving ({round(time.time()-t0)}s)", flush=True)
    except Exception as e:
        print(f"  healthz: {type(e).__name__} ({round(time.time()-t0)}s)", flush=True)
    time.sleep(20)
if not health or "images" not in health:
    report["blocker"] = "new build not live within 25 min"
    with open(os.path.join(HERE, "render-report.json"), "w") as f:
        json.dump(report, f, indent=2)
    raise SystemExit(report["blocker"])
report["health"] = health

# 2) real job, unseen topic
body = json.dumps({"topic": TOPIC, "template": "why", "lengthSec": 15,
                   "aspect": "16:9", "voice": "calm-01", "captions": "blocks",
                   "music": "drive"}).encode()
req = urllib.request.Request(BASE + "/jobs", data=body,
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=90) as r:
    created = json.load(r)
jid = created["id"]
report["job"] = jid
print("job:", jid, flush=True)

job = None
t1 = time.time()
while time.time() - t1 < 1500:
    time.sleep(10)
    try:
        job = get(BASE + f"/jobs/{jid}")
    except Exception as e:
        print(f"  poll: {type(e).__name__}", flush=True)
        continue
    print(f"  {round(time.time()-t1)}s state={job['state']} stages={job.get('stageState')}", flush=True)
    if job["state"] in ("done", "blocked", "failed"):
        break
report["state"] = job["state"]
report["elapsed"] = round(time.time() - t1, 1)
report["log"] = job.get("log")
report["blocker"] = job.get("blocker")
report["error"] = job.get("error")

if job["state"] == "done":
    url = job["download"]["url"]
    mp4 = os.path.join(HERE, f"render-{jid}.mp4")
    with urllib.request.urlopen(url, timeout=180) as r, open(mp4, "wb") as f:
        f.write(r.read())
    pj = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                                    "-show_format", "-show_streams", mp4],
                                   capture_output=True, text=True, check=True).stdout)
    v = next(s for s in pj["streams"] if s["codec_type"] == "video")
    a = next(s for s in pj["streams"] if s["codec_type"] == "audio")
    report["mp4"] = {"path": mp4, "bytes": os.path.getsize(mp4),
                     "duration": pj["format"]["duration"],
                     "video": f"{v['codec_name']} {v['width']}x{v['height']}",
                     "audio": f"{a['codec_name']} {a.get('sample_rate')}Hz"}
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-map", "0:a",
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                         capture_output=True, check=True).stdout
    import array
    samples = array.array("h"); samples.frombytes(raw)
    report["audio_rms"] = round((sum(s*s for s in samples)/max(1, len(samples)))**0.5/32768, 4)
    for sc in job["result"]["scenes"]:
        mid = (sc["start"] + sc["end"]) / 2
        fp = os.path.join(HERE, f"render-frame-{jid}-s{sc['i']}.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(mid), "-i", mp4,
                        "-frames:v", "1", "-q:v", "3", fp], check=True)
    bad = url[:-8] + ("aaaaaaaa" if not url.endswith("aaaaaaaa") else "bbbbbbbb")
    try:
        urllib.request.urlopen(bad, timeout=60)
        report["tampered_url"] = "UNEXPECTED 200"
    except urllib.error.HTTPError as e:
        report["tampered_url"] = e.code

with open(os.path.join(HERE, "render-report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps({k: v for k, v in report.items() if k not in ("log", "health")}, indent=2))
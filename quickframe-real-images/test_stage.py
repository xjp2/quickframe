"""Stage-only test: engine.build -> images.fetch_all for an unseen topic.
Run from D:\quickframe-t1 so `qf` resolves. Writes its own report JSON.
"""
import json
import os
import sys
import time

sys.path.insert(0, r"D:\quickframe-t1")
os.environ.setdefault("QF_ROOT", r"D:\quickframe-t1")

from qf import engine, images  # noqa: E402

TOPIC = "why do rivers bend and curve across flat plains"
cfg = {"topic": TOPIC, "template": "why", "lengthSec": 15, "aspect": "16:9",
       "voice": "calm-01", "captions": "blocks", "music": "drive",
       "id": "imgstage-test-001"}
job = engine.build(cfg)
print(f"scenes={len(job['scenes'])} totalSec={job['totalSec']}")
for sc in job["scenes"]:
    print(f"  s{sc['i']} beat={sc['beat']} art={sc['art']}")
    print(f"    prompt: {images.scene_prompt(job, sc)[:160]}...")

t0 = time.time()
manifest = images.fetch_all(job)
report = {"topic": TOPIC, "scenes": len(job["scenes"]),
          "fetch_total_sec": round(time.time() - t0, 2), "manifest": manifest}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stage-report.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))

# cache-hit re-run must be instant and not re-fetch
t1 = time.time()
m2 = images.fetch_all(job)
assert all(m["cached"] for m in m2), "second run should be all cache hits"
print(f"cache re-run: {round(time.time() - t1, 3)}s, all cached=True")
import json, time, urllib.request, urllib.parse, os, sys
sys.path.insert(0, r"D:\quickframe-t1")
os.environ.setdefault("QF_ROOT", r"D:\quickframe-t1")
from qf import engine, images

cfg = {"topic": "why do rivers bend and curve across flat plains", "template": "why",
       "lengthSec": 15, "aspect": "16:9", "id": "imgstage-test-001"}
job = engine.build(cfg)
rep = []
for sc in job["scenes"]:
    prompt = images.scene_prompt(job, sc)
    seed = images.seed_for(job["topic"], "why", sc["beat"], sc["i"])
    url = (images.ENDPOINT + urllib.parse.quote(prompt)
           + f"?width=1024&height=576&seed={seed}&nologo=true&model=flux")
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quickframe-t1/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        rep.append({"i": sc["i"], "ok": True, "bytes": len(data), "sec": round(time.time()-t0,1)})
    except Exception as e:
        rep.append({"i": sc["i"], "ok": False, "error": str(e), "sec": round(time.time()-t0,1)})
    time.sleep(6)
print(json.dumps(rep, indent=2))
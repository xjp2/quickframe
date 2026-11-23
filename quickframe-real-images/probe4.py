import json, time, urllib.request, urllib.parse, os, sys
sys.path.insert(0, r"D:\quickframe-t1")
os.environ.setdefault("QF_ROOT", r"D:\quickframe-t1")
from qf import engine, images

cfg = {"topic": "why do rivers bend and curve across flat plains", "template": "why",
       "lengthSec": 15, "aspect": "16:9", "id": "imgstage-test-001"}
job = engine.build(cfg)
sc = job["scenes"][1]
prompt = images.scene_prompt(job, sc)
seed = images.seed_for(job["topic"], "why", sc["beat"], sc["i"])
url = (images.ENDPOINT + urllib.parse.quote(prompt)
       + f"?width=1024&height=576&seed={seed}&nologo=true&model=flux")

def attempt(tag):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quickframe-t1/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
            return {"tag": tag, "ok": True, "bytes": len(data), "sec": round(time.time()-t0,1),
                    "headers": dict(r.headers)}
    except urllib.error.HTTPError as e:
        body = e.read()[:500].decode("utf-8", "replace")
        return {"tag": tag, "ok": False, "status": e.code, "body": body,
                "headers": dict(e.headers), "sec": round(time.time()-t0,1)}
    except Exception as e:
        return {"tag": tag, "ok": False, "error": str(e)}

rep = [attempt("immediate")]
for wait in (30, 60, 90):
    time.sleep(wait)
    r = attempt(f"after_{wait}s")
    rep.append(r)
    if r.get("ok"):
        break
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe4-report.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(rep, f, indent=2)
print(json.dumps(rep, indent=2))
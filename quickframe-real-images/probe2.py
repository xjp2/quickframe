import json, time, urllib.request, urllib.parse, os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe2-report.json")
rep = {}

def get(url, timeout=120):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quickframe-t1/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return {"ok": True, "status": r.status, "ctype": r.headers.get("Content-Type"),
                    "bytes": len(data), "sec": round(time.time()-t0,1)}
    except Exception as e:
        return {"ok": False, "error": str(e), "sec": round(time.time()-t0,1)}

rep["models_list"] = get("https://image.pollinations.ai/models", 30)
prompt = "a winding river across flat green plains, cool blue teal palette, cinematic clean editorial illustration, no text"
enc = urllib.parse.quote(prompt)
for m in ["flux", "turbo", "flux-realism", "flux-anime", "flux-3d", "default"]:
    u = f"https://image.pollinations.ai/prompt/{enc}?width=768&height=432&seed=7&nologo=true&model={m}"
    rep[f"model_{m}"] = get(u)
# no model param at all
rep["no_model_param"] = get(f"https://image.pollinations.ai/prompt/{enc}?width=768&height=432&seed=7&nologo=true")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(rep, f, indent=2)
print(json.dumps(rep, indent=2))
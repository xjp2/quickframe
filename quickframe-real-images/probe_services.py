"""Probe free image services from this machine (render path = Python urllib).
Pollinations: no key. HF inference: needs token (none on file) -> only check
whether the endpoint is reachable at all, expect 401 without token.
Writes its own report (PowerShell redirection corrupts files on this box).
"""
import json
import os
import ssl
import time
import urllib.request
import urllib.parse

os.environ.setdefault("PYTHONHTTPSVERIFY", "1")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe-report.json")
report = {}


def fetch(url, timeout=180):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "quickframe-t1/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return {"ok": True, "status": r.status,
                    "ctype": r.headers.get("Content-Type"),
                    "bytes": len(data), "sec": round(time.time() - t0, 1),
                    "head": data[:16].hex()}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "sec": round(time.time() - t0, 1)}


prompt = ("cinematic clean editorial illustration, a lighthouse on a rocky coast at dusk, "
          "cool blue and teal palette, soft light, minimal flat shapes, no text, no words, no letters")
enc = urllib.parse.quote(prompt)

# 1) Pollinations flux, small size (lightweight for 512MB render host)
u1 = f"https://image.pollinations.ai/prompt/{enc}?width=768&height=432&seed=42&nologo=true&model=flux"
report["pollinations_flux_768"] = fetch(u1)

# 2) Pollinations turbo (faster model fallback)
u2 = f"https://image.pollinations.ai/prompt/{enc}?width=768&height=432&seed=42&nologo=true&model=turbo"
report["pollinations_turbo_768"] = fetch(u2)

# 3) HF inference without token — expect 401/402/403, proves reachability only
u3 = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
report["hf_no_token"] = fetch(u3, timeout=30)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
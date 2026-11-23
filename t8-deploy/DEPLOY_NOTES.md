# DEPLOY_NOTES — QuickFrame T1 job service

**Status: built and verified locally; deploy-ready for HF Spaces; NOT pushed.**
The service in `qf/` renders real MP4s with real edge-tts voice and passes the
acceptance test on this machine. The owner has chosen **Hugging Face Spaces,
free CPU tier** as the target, and this folder is a valid Docker-SDK Space repo
root. The only thing standing between this and a live public URL is the HF
account step in §1 (a username + Write token I do not have). This folder
deliberately creates no paid cloud service.

---

## 1. What is proven (measured here)

- `POST /jobs` with an **unseen topic** runs all 7 stages and returns a
  downloadable MP4 whose boards are drawn fresh from the topic (not a fixed pool).
- Render is **real FFmpeg** (`qf/driver.py` → libx264 + AAC, 1920×1080,
  `+faststart`), gated by the safe-area `audit()` (0 violations).
- Voice is **real speech**: edge-tts streams audio + `WordBoundary` events;
  scenes are re-timed to actual spoken length and captions are rebuilt from the
  measured word timings. Verified non-silent (decoded PCM RMS ≈ 0.13).
- Downloads are **genuinely signed**: HMAC-SHA256 with expiry; a tampered
  signature returns 403.

Reproduce: `python -m qf.server 8777` then `python acceptance.py "<new topic>"`.

---

## 2. Hosting — Hugging Face Spaces (Docker SDK, free CPU tier)

The owner's decision. This folder is the **Space repo root**: `README.md`
front-matter declares `sdk: docker` + `app_port: 7860`, and the `Dockerfile`
builds a Python 3.12 image with FFmpeg baked in. Upload the contents and the
Space builds and serves it.

**Why Docker SDK and not a default image:** FFmpeg is required for the render and
the default Gradio/Streamlit Spaces images do not reliably include it. `python:3.12-slim`
also has no FFmpeg, so the Dockerfile installs it via `apt-get install ffmpeg`.
This is exactly the "use the Docker SDK if you need FFmpeg in the image" case.

### The exact account step (the only blocker to a live URL)

I have **no Hugging Face account or token on file** and cannot create one. To
push, the owner must provide:

1. An HF **username** (account created at huggingface.co — separate from the
   QwenWork login).
2. An **access token with `write` scope**: HF → Settings → Access Tokens → New
   token → Role **Write** → copy the `hf_…` string.
3. Approval to create the Space (it is a published artifact).

Then, from this folder:

```bash
huggingface-cli repo create quickframe --type space --space_sdk docker --repo-type space
git init -q && git add . && git commit -qm "QuickFrame T1 (edge-tts voice + FFmpeg render)"
git push "https://oauth:${HF_TOKEN}@huggingface.co/spaces/${HF_USERNAME}/quickframe" main
```

After the build goes green, the service is live at
`https://${HF_USERNAME}-quickframe.hf.space` (POST `/jobs`, GET `/jobs/<id>`,
signed `/files/...` downloads). `QF_PUBLIC_BASE` does **not** need to be set —
signed URLs are derived from the forwarded `Host`/`X-Forwarded-Proto` headers.

### Free-tier behavior to expect (documented, not worked around)

- **Idle sleep:** unpinned free Spaces stop after inactivity and cold-start on the
  next request (the first job after sleep pays container-start latency).
- **Ephemeral disk:** `store.py` writes to the container FS, which is wiped on
  restart/sleep-to-zero. MP4s and job state survive only while the instance is
  up. Durable storage needs an external bucket (B1).
- **Resource limits:** `cpu-basic` is ~2 vCPU / 16 GB. Set `QF_RENDER_WORKERS=2`
  for throughput there; the `malloc failed` I hit was on a laptop with ~0.5 GB
  free, not the Space. Default is `1` (safe everywhere).

Environment knobs: `PORT` (7860), `QF_HOST` (0.0.0.0 in the image), `QF_ROOT`,
`QF_PUBLIC_BASE` (override the auto-derived base only if behind another domain),
`QF_RENDER_WORKERS`, `QF_TTS_CMD` (optional vendor adapter that overrides edge-tts),
`QF_IMAGE_MODE` (`pollinations` default, `off` = vector boards), `QF_IMAGE_MODEL`
(default `flux`), `QF_IMAGE_TIMEOUT` (per-request seconds, default 180).


---

## 3. Blockers / gaps (reported, not worked around)

| # | Gap | Impact | Needed |
|---|---|---|---|
| B1 | **No durable object store** | `store.py` is a local-filesystem backend with real signed URLs, but on the free Space the disk is **ephemeral** — MP4s vanish on restart/idle-to-zero. The T1 contract "object store → signed URL" is implemented in shape, not durability. | An S3/R2/GCS-compatible bucket (paid) **or** a host with a persistent volume. Swap `store.put/path` only; keep `signed_url/verify`. |
| B2 | **edge-tts needs outbound network** | Voice stage calls Microsoft's TTS endpoint per scene. If egress is blocked at the deploy host, `synth_voice` raises `TTSNotWired` (a hard blocker) — it never fakes audio. | Allow egress, or set `QF_TTS_CMD` to another vendor. |
| B3 | **Vendored fonts not on this machine** | Fraunces/Caveat are absent, so `env.find_font` substitutes system faces (DejaVu/Georgia/Segoe). Text still typesets and stays in the safe area, but the brand typeface is not the shipped one. | Drop the two `.ttf`s into `assets/fonts/` (the encoder typesets all on-screen text). |
| B4 | **T2 LLM script not wired** | `engine.build` uses the deterministic spine. `lengthSec` is now honored by selecting the number of beats that fits the target (~2.4 words/sec) plus a clamped natural TTS rate correction — a 12 s job renders ~12 s (measured ±5%). A target longer than the full spine's word count stays content-limited (renders shorter, with a warning). | Replace `line_for()` body with one model call that writes to a target word budget for richer, length-exact scripts. |
| B5 | **T3 per-scene image model — WIRED (2026-11-21)** | `qf/images.py` fetches one real AI illustration per scene from Pollinations (keyless free tier; `model=flux` URL, anonymously served by `sana` per `x-model-used`). Cached per job under `.render_work/images-<id>/` with prompt-hash sidecars; distinctness enforced by byte-hash; free-tier logo band cropped; all readable text still typeset by the encoder. Failure after 5 retries = honest 503 BLOCKED (`image_service_unavailable`), never a silent stickman fallback; `QF_IMAGE_MODE=off` restores vector boards. Anonymous bursts return 402 — patient backoff (10/20/30/45 s) + 6 s scene pacing measured to recover. | Remaining: style consistency is prompt-level (shared cool-palette suffix), not a character sheet; a keyed tier would remove the 402 queueing. |
| B6 | **T7 uploaders not wired** | `publish` produces a manifest + signed URL only. YouTube/TikTok posting is out of scope for T1. | App registration + Data API / Content Posting API (review lead time). |
| B7 | **T9 guardrails pending** | No moderation on prompt/output, no rate/credit abuse control, no AIGC disclosure enforcement, no retention window. | Needed before a paid user. |
| B8 | **CPU-bound, single instance** | One worker process renders serially; concurrency needs a queue + multiple workers on a bigger host. | Size the fleet from the measured ~25 s encode per ~34 s job. |

---

## 4. What is deploy-ready now

- ✅ `qf/` service (stdlib HTTP) + encoder + edge-tts voice + signed-URL store.
- ✅ `README.md` front-matter: `sdk: docker`, `app_port: 7860`, `pinned: false`
  (free tier) — the Space SDK config HF reads.
- ✅ `Dockerfile`: FFmpeg + DejaVu + ca-certificates baked in, non-root UID 1000,
  health check, binds `0.0.0.0:7860`, runs `python -m qf.server`.
- ✅ `requirements.txt`: pillow, numpy, edge-tts.
- ✅ `acceptance.py`: the real-voice end-to-end test (passes locally).
- ✅ Signed URLs auto-derive the Space's public `https://…hf.space` base.

**Push = §1 account step only.** Until then, build/run locally to verify the
image: `docker build -t quickframe-t1 . && docker run -p 7860:7860
-e QF_HOST=0.0.0.0 quickframe-t1`, then `python acceptance.py "<new topic>"`
against `http://127.0.0.1:7860`.


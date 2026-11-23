---
title: QuickFrame
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Prompt to MP4 job service (edge-tts voice + FFmpeg render)
---

# QuickFrame — T1 job service

Prompt → MP4. `POST /jobs {topic, template, lengthSec, aspect, voice, captions,
music}` runs the seven-stage pipeline and returns a **downloadable, real**
`master.mp4` with **real speech** (Microsoft Edge neural TTS) and captions
anchored to real word timings.

```
script -> boards -> art -> voice -> captions -> encode -> publish
```

This is the working service, not scaffolding. It was built from the AGENTS.md
spec on a machine that has none of the original QuickFrame source, and it is
verified end-to-end (see `acceptance.py`).

## Run locally

```bash
pip install -r requirements.txt          # pillow, numpy, edge-tts (ffmpeg via system)
python -m qf.server 8777                  # stdlib HTTP server, loopback by default
python acceptance.py "why does the moon look bigger near the horizon"
```

`acceptance.py` POSTs an unseen topic with real voice, polls the 7-stage log,
downloads through the signed URL, and asserts h264+AAC with a non-silent audio
track. Measured on this box: 5 scenes, ~34 s, 1920×1080, ~1.1 MB, RMS ≈ 0.13.

## Deploy to Hugging Face Spaces (free CPU tier)

Target chosen by the owner. This folder **is** the Space repo root — upload its
contents (`README.md`, `Dockerfile`, `requirements.txt`, `qf/`, `acceptance.py`)
to a Docker-SDK Space and it builds and serves on the public URL.

**Why `sdk: docker` (not the default Gradio/Streamlit images):** the render needs
**FFmpeg**, and the default Spaces images do not reliably ship it. The Dockerfile
starts from `python:3.12-slim` (no ffmpeg) and installs it explicitly via
`apt-get install ffmpeg`, plus `ca-certificates` so edge-tts can reach Microsoft's
TTS endpoint. That is the whole reason for the Docker SDK.

**How it serves:** `python -m qf.server` binds `0.0.0.0:7860` (set in the
Dockerfile via `QF_HOST`/`PORT`), matching `app_port: 7860`. Signed download URLs
are auto-derived from the forwarded `Host`/`X-Forwarded-Proto` headers, so on the
Space they come back as `https://<user>-<space>.hf.space/files/...` with no extra
config. Override with `QF_PUBLIC_BASE` only if you put it behind another domain.

**Account step required to push (I do not have these — see `DEPLOY_NOTES.md` §1):**
an HF username and a **Write** token. Nothing is deployed until you provide them.

```bash
# one-time, from this folder, once you have the username + hf_... Write token:
huggingface-cli repo create quickframe --type space --space_sdk docker --repo-type space
git init -q && git add . && git commit -qm "QuickFrame T1 (edge-tts voice + FFmpeg render)"
git push "https://oauth:${HF_TOKEN}@huggingface.co/spaces/${HF_USERNAME}/quickframe" main
```

Free tier caveats (documented, not worked around): the Space **sleeps when idle**
(cold start on the next hit) and its disk is **ephemeral** — rendered MP4s are lost
on restart, so the signed URL is valid only while the instance is up. A durable
object store is `store.py`'s swap point (needs your approval to provision).

## API

| Route | Purpose |
|---|---|
| `GET /` | in-browser demo page (submit a topic → watch the 7 stages → download). What the Space webview shows. |
| `POST /jobs` | create + run a job → `202 {id, state, stages}` |
| `GET /jobs/<id>` | state + the 7-key stage log + `stageState` map + result + signed `download.url` |
| `GET /jobs` | recent job ids |
| `GET /files/<key>?exp=&sig=` | signed, expiring MP4/manifest download (HMAC-SHA256) |
| `GET /healthz/service` | ffmpeg, fonts, voice vendor, store, stage keys |

## Files

| Path | Role |
|---|---|
| `qf/server.py` | HTTP surface + job queue (stdlib `http.server`). Binds `QF_HOST`:`PORT`. Serves `GET /`. |
| `qf/index.html` | the in-browser demo page served at `/` (form → poll the 7 stages → download). |
| `qf/runner.py` | the 7-stage pipeline; re-times scenes to real VO length. |
| `qf/engine.py` | deterministic script pass + art-direction layer (the T2 seam). |
| `qf/art.py` | stickman/whiteboard board renderer (the T3 art layer). |
| `qf/voice.py` | **edge-tts** provider (real speech + word boundaries) + synth beds. |
| `qf/driver.py` | the rebuilt FFmpeg encoder: `frame_at` / `render` / `audit` safe-area gate. |
| `qf/store.py` | content-addressed object store + HMAC signed URLs (local FS backend). |
| `qf/env.py` | ffmpeg/font/path resolution — nothing points at `/tmp`. |
| `qf/brand.py` | pipeline stage keys, aspects, beds, caption styles, voices (the registry). |
| `Dockerfile` | python:3.12-slim + ffmpeg + DejaVu + `edge-tts`; runs `python -m qf.server`. |

## Honest status (read `DEPLOY_NOTES.md`)

- **Real render, real voice — verified.** No simulated pipeline.
- **Voice = edge-tts**: free, no API key, no quota, but needs outbound network
  to Microsoft's TTS endpoint at render time.
- **Object store is a local-filesystem backend** with genuinely signed, expiring
  URLs. It is **not durable** across a container restart and is **not** a cloud
  bucket yet — `store.py` is the swap point.
- **Hosting: Hugging Face Spaces, free CPU tier** (owner's decision). This folder
  is deploy-ready but **not yet pushed** — it needs an HF username + Write token
  (see `DEPLOY_NOTES.md` §1). No paid service is created here.
- **T2/T3/T7/T9 are not done**: the script is the deterministic spine (so
  `lengthSec` is honored by sizing the number of beats to the target and applying
  a natural TTS rate correction — a 12 s job renders ~12 s, measured within ~5%;
  very long targets beyond the spine's word count are content-limited and come
  out shorter with a warning), boards are locally vector-rendered (not a
  per-scene image model), and YouTube/TikTok uploaders are not wired.

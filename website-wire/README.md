# QuickFrame website → T1 job service (wiring)

Goal: make `https://quickframe.geo.hashmeta.tech` a real storefront — a visitor
types a topic, the site calls the T1 job service, and the service returns a real,
downloadable MP4.

**Scope honoured:** all new deliverables live in this folder (`D:\opc\website-wire\`).
The only change outside it is the **CORS patch to the T1 service** (`server.py`),
which the task explicitly authorised. Nothing was deployed and no paid service was
created. The live site was **not** edited (see §6 — it would break until the backend
has a public URL, and publishing needs your approval).

---

## 1. What the service API is (read from `D:\qf-t1-build\qf\server.py`)

| Route | Purpose |
|---|---|
| `POST /jobs` | body `{topic, template, lengthSec, aspect, voice, tone, captions, music, silentVoice?}` → `202 {id, state:"queued", stages}`. `409` if no TTS vendor and `silentVoice` not set. |
| `GET /jobs/<id>` | `{id, state, stages, stageState{7 keys}, log[], result, download, blocker, error}`. `state` ∈ queued/running/done/failed/blocked. |
| `GET /files/<key>?exp=&sig=` | HMAC-SHA256 signed, expiring MP4/manifest download. `download.url` points here. |
| `GET /healthz/service` | ffmpeg / fonts / voice vendor / stage keys. |

Seven stage keys (unchanged, the promise):
`script → boards → art → voice → captions → encode → publish`.

`download.url` is **already absolute** (the service derives its base from the
forwarded `Host`/`X-Forwarded-Proto`), so the browser just uses it as-is.

## 2. The call flow implemented (`generator-wire.js`)

```
form submit -> POST {API_BASE}/jobs -> poll GET {API_BASE}/jobs/<id> (1.5s)
  -> render progress from job.stageState + job.log onto the 7 rail chips
  -> on done, set <video> src + download link to job.download.url (real MP4)
```

It replaces the studio-demo block's simulated `startRun()`/`finishRun()`
(setTimeout "seq" + Canvas + MediaRecorder → `blob:` URL) with the real service
call. Everything else in the block stays.

### Single configurable value
`QF_API_BASE` at the top of `generator-wire.js` is the **only** host reference.
- Now (local): `http://127.0.0.1:8777`
- After HF Spaces deploy: `https://<hf-username>-quickframe.hf.space`

### Control → contract mapping (and the honest gaps)
The storefront UI does not map 1:1 to the job contract. Mapping used:

| UI control | T1 `cfg` field | Note |
|---|---|---|
| topic | `topic` | direct |
| aspect (16:9 / 9:16) | `aspect` | direct |
| captions label | `captions` | Bold pop/Karaoke→`karaoke`, Clean lower-third→`clean`, None→`none` |
| voice label | `voice` | Friendly→`calm-01`, Fast→`bright-01`, Calm teacher/Deadpan→`doc-01` |
| "No voiceover (music only)" | `silentVoice:true` | real silent VO + music bed (service-supported) |
| *not in UI* | `template` | default `why` (configurable const) |
| *not in UI* | `music` | default `drive` (configurable const) |
| *not in UI* | `lengthSec` | default `12` (configurable const) |

**Gaps (reported, not faked):**
- **Style cards (stickman/whiteboard/AIGC):** the T1 service has no visual-style
  input — boards are always the local vector renderer (`art.py`). The control is
  cosmetic for now; it is not sent. (T3 per-scene image model not wired.)
- **Output language 中文:** the script engine is English-only. The wiring sends
  English and does **not** claim a Chinese render. zh needs the T2 LLM engine.
- **Publishing to YouTube/TikTok:** not wired (T7). The site's publish sheet stays
  a "connect your channel" stub — the real output is the signed MP4 download.

## 3. CORS (added to the service)

`server.py` had **no** CORS (no `do_OPTIONS`, no `Access-Control-*` headers) — the
website (different origin) could not call it. Patched:
- `do_OPTIONS` preflight → `204` (+ `Allow-Methods: GET, POST, OPTIONS`,
  `Allow-Headers: Content-Type`, `Max-Age: 600`) for allowed origins, `400` otherwise.
- `Access-Control-Allow-Origin` + `Vary: Origin` on all JSON, HTML and file responses.
- Allowed origins are a **single configurable value** `QF_CORS_ORIGIN`
  (`"*"` or comma list). Default allowlist includes
  `https://quickframe.geo.hashmeta.tech` + local dev origins.
- The job contract and the seven stage keys are untouched.

The identical patch is mirrored to the deploy bundle `D:\opc\t8-deploy\qf\server.py`
so build and deploy stay in sync.

## 4. Verification (real, measured — no simulated render)

`verify.py` runs the storefront's exact flow against the **local** service
(`python -m qf.server 8777`, `QF_RENDER_WORKERS=1`) on an **unseen** topic.

Last run — **PASS**:
- topic: `how do noise-cancelling headphones cancel sound`
- **job id: `20261119-153459-39ef0e`**
- all 7 stages → `done`; real edge-tts voice (12.2s), karaoke captions (11 cues),
  encode `audit 0 violations`
- MP4 probe: **h264 1920×1080, 12.17s, 470,818 bytes, audio aac, RMS 0.1312** (non-silent)
- signed download `200`; **tampered signature → 403**
- CORS: site-origin preflight `204` + ACAO echoed; unknown origin `400`
- artifact: `D:\opc\website-wire\e2e-20261119-153459-39ef0e.mp4`

Reproduce: with the service running, `python verify.py`.

## 5. Evidence ledger

| Claim | Proof | Where |
|---|---|---|
| Real MP4 from unseen topic | ffprobe h264 1920×1080 12.17s + audio RMS 0.1312 | `e2e-20261119-153459-39ef0e.mp4`, `verify.py` output |
| Real speech (not fake) | voice=edge-tts, cues rebuilt from word timings | job log `[voice]`/`[captions]` |
| Signed URL enforced | valid→200, tampered→403 | `verify.py` |
| CORS works for the site | preflight 204 + ACAO; evil origin 400 | `verify.py` / live probe |
| Contract unchanged | 7 stage keys asserted at create + done | `verify.py` |

## 6. Making the live site call the real service (the exact remaining step)

The wiring is done and proven against the local service. To go live it needs the
backend on a **public URL the browser can reach** — which is blocked on the
Hugging Face account (the service is not deployed; no HF username/token on file).

**To deploy (owner action — nothing here is published without your approval):**
1. Create an HF account at huggingface.co (separate from QwenWork login).
2. Settings → Access Tokens → New token → Role **Write** → copy the `hf_…` string.
3. From `D:\opc\t8-deploy\` (a valid Docker-SDK Space repo root, FFmpeg baked in):
   ```bash
   huggingface-cli repo create quickframe --type space --space_sdk docker --repo-type space
   git init -q && git add . && git commit -qm "QuickFrame T1 (edge-tts voice + FFmpeg render + CORS)"
   git push "https://oauth:${HF_TOKEN}@huggingface.co/spaces/${HF_USERNAME}/quickframe" main
   ```
   Live at `https://${HF_USERNAME}-quickframe.hf.space`.

**Then, two one-line edits:**
- In `generator-wire.js`: set `QF_API_BASE = "https://${HF_USERNAME}-quickframe.hf.space"`.
- On the service (Space env): `QF_CORS_ORIGIN` already allows the site origin by
  default, so no change needed unless you put it behind another domain.

**Applying the front-end to the Hashmeta site** (page id 6, block `generator`,
`blockType: rawHtml`) — this IS possible from here via the Hashmeta MCP
`update_page` (`edits` find/replace on the block HTML), but I have **not** run it,
because pointing the live form at a not-yet-deployed backend would break the
storefront, and publishing needs your approval. When you approve, the edit is:
1. Insert the `QF_API_BASE` + mapping + new `startRun()`/`finishRun()` from
   `generator-wire.js` into the block's IIFE, and delete `recordVideo()`/`makeFrames()`.
2. Keep `_status: "draft"` first to preview, then publish.

Free-tier caveats (from `t8-deploy/DEPLOY_NOTES.md`): the Space sleeps when idle
(first render cold-starts) and its disk is ephemeral — download promptly; durable
storage needs a bucket (your approval).

---

## 7. UPDATE 2026-11-20 — live on Render, front-end applied as a draft

The HF plan is dead. The T1 service is now **live on Render** at
`https://quickframe-t1.onrender.com`, `generator-wire.js` points `QF_API_BASE` there,
and `QF_DEFAULT_LENGTH_S = 30`.

### What was applied to the site (NOT published)
- `update_page` (Hashmeta MCP) applied the wiring to **page id 6, block `generator`**
  (`blockType: rawHtml`) via 4 surgical find/replace edits, keeping `_status: "draft"`.
- Inserted `QF_API_BASE` + label→contract maps + `buildCfg()`; replaced the old
  simulation `finishRun()`/`startRun()` with the real POST→poll→signed-download flow;
  deleted `recordVideo()`/`makeFrames()` (and the `makeFrames` call in the captions
  toggle). The 7 stage keys and the job contract are unchanged.
- **Verified**: the saved draft block is byte-identical to a locally-built target that
  passes `node --check`; `makeFrames`/`recordVideo` are gone; `QF_API_BASE` = the Render
  URL; `lengthSec` default 30. Publish center shows the Studio Demo as **1 dirty page,
  manual mode, not published** — waiting for your preview + approval.

### Backend verified reachable from the site origin (CORS)
- `/healthz/service` → 200, `voiceVendor: true`, stages = the 7 keys.
- Preflight `OPTIONS /jobs` with `Origin: https://quickframe.geo.hashmeta.tech` →
  **204 + `Access-Control-Allow-Origin` = the site** (Render's proxy lowercases header
  names; the browser is case-insensitive, so this is fine).
- Full real render succeeded end-to-end on an 8s job:
  `20261120-160200-3b6fba` → edge-tts voice, 11 karaoke cues, `audit 0 violations`,
  h264 1280×720 10.20s, aac, RMS 0.1309, signed URL, real MP4
  (`render-e2e-20261120-160200-3b6fba.mp4`). Reproduce: `python verify_render.py`.

### BLOCKER — the storefront default (30s) does not complete on Render free tier
- Reproducible: **every `lengthSec: 30` job dies during `encode`** (two distinct topics).
  The poll returns `502 Bad Gateway` (instance down / restarting) for ~30s, then
  `404 no such job` forever. `GET /jobs` afterwards shows `{"jobs": []}` — the restart
  wipes the in-memory job table **and** the job files.
- Root cause: encode is CPU-heavy and scales with length — a 10s video took **54s** to
  encode, so a 30s video encodes ~2.5 min; the free Render instance is killed (OOM /
  request timeout) mid-encode. The service stores jobs in memory + ephemeral disk
  (`storeFreeNote: "local filesystem backend"`), so a restart loses everything.
- The **front-end wiring is correct and resilient** (it retries transient poll errors),
  but it cannot recover a job the instance dropped. This is a backend/infra fix, not a
  wiring fix.

### What is needed to make 30s renders reliable (owner decision)
1. A **persistent Render instance** (paid tier, no sleep / higher RAM) so a 2.5-min
   encode survives; **and/or** move the render off the request path (background worker
   with a longer budget).
2. **Durable job store + object storage** (e.g. S3/R2 for the MP4, Postgres/Redis for
   job state) so a restart does not lose in-flight jobs or signed URLs.
3. Interim mitigation without infra spend: lower `QF_DEFAULT_LENGTH_S` (e.g. 12–15s,
   which completes on the free tier) — but that changes the storefront default and
   should be your call.

Until (1)+(2) are in place, do **not** publish the draft to the live storefront for the
30s default — visitors would hit a job that dies at encode. The draft is ready to
preview; publishing is gated on your approval and on the backend fix.

---

## 8. UPDATE 2026-11-20 (later) — interim mitigation applied: default is now 15s

Per the interim option above, the storefront default was lowered so renders complete on
the Render free tier.

- `generator-wire.js`: `QF_DEFAULT_LENGTH_S = 15`.
- Re-applied to the live site (page 6, block `generator`) via `update_page` with a single
  targeted edit `QF_DEFAULT_LENGTH_S = 30` → `= 15`, kept `_status: "draft"` (**not
  published**). New draft `contentHash = 5d276a4c409649ee9df5fec39b23ca90838589b3`.
- Verified the saved draft: exactly one `QF_DEFAULT_LENGTH_S = 15`, still a draft, wiring
  intact (`makeFrames`/`recordVideo` gone, Render `QF_API_BASE`, `buildCfg`/`finishRun(j,jid)`
  present), and the block passes `node --check`.

### Real 15s end-to-end render against Render — PASS
- Job `20261120-161244-7122d4`, topic "how do vaccines train your immune system".
- All 7 stages reached `done`; `[encode] done 73.3s · 14.00s mp4 · 0.42 MB`; `audit 0 violations`.
- voice=edge-tts, 9 karaoke cues, signed URL issued.
- MP4: **h264 1280×720, 14.00s, 418,174 bytes, audio aac, RMS 0.1314** (non-silent).
- Artifact: `render-e2e-20261120-161244-7122d4.mp4`.

Note: 15s still encodes ~73s on the free instance (≈5× real-time) and completed, but it
is close to the free tier's stability margin. The durable fixes in §7 (persistent instance
+ durable job store + object storage) remain the real remedy; 15s is a safe interim default.

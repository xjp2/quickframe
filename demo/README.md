# QuickFrame demo video — plan (hackathon submission)

**Event:** QwenWork x Hashmeta AI One-Person Company Hackathon
**Due:** Sun 23 Nov 2026, 23:59 SGT · submit via https://luma.link/KohjTskYPo
**Length:** 3:00. Files here: `narration-script.md` (voice track), `shot-list.md` (what to record, in order), this README (the honest evidence ledger + recording checklist).

**Core story (supersedes the old `demo-script.md` five-slot framing entirely):**
One prompt → one finished MP4, produced by the real job service. 7 stages, logged by their real keys:
`script → boards → art → voice → captions → encode → publish`.

**One rule for the whole video:** every claim on screen must be backed by a file or a recording listed below. Where something is not built, the narration says so — honesty is a feature of this demo, not a weakness.

---

## 1. Evidence ledger — what is real today (verified from files, 19 Nov 2026)

| Claim we can make | Proof | Where |
|---|---|---|
| Job service exists: `POST /jobs` → queued job → 7-key stage log → signed expiring download URL | Real stdlib HTTP server + single-process worker; honest 409 when TTS missing | `D:\qf-t1-build\qf\server.py` |
| Runner executes all 7 stages for real; raises blockers instead of faking | `runner.run()` — script/boards/art/voice/captions/encode/publish, blocker codes | `D:\qf-t1-build\qf\runner.py` |
| Encode is real FFmpeg (rawvideo → libx264 + AAC, 30 fps) with a safe-area gate that fails the job on any violation | `audit()` → `render()`; module-level e2e traces exist (`.render_work\e2e-22980\e2e.mp4`) | `D:\qf-t1-build\qf\driver.py` |
| Boards are drawn fresh per job from a topic seed — not a fixed pool | `art.draw_board()` + `board_seed(job_id, topic)` | `D:\qf-t1-build\qf\art.py` |
| Script pass: deterministic spines (6 templates × 5 beats, trimmed to fit `lengthSec`) with real timing math; LLM seam documented | `engine.line_for()` is the T2 seam; spine-trim warning observed live in job `20261119-132659-832953` | `D:\qf-t1-build\qf\engine.py` |
| **Voice-over is real**: edge-tts neural TTS is the wired default backend; cues rebuilt from actual per-word timings; every scene re-timed to actual spoken duration so video/audio/captions share one clock | `voice.py` (`EDGE_VOICES`, `boundary="WordBoundary"`), `runner.py` voice stage; job JSON `result.voice.tts == "edge-tts"` | `D:\opc\demo\capture\job-20261119-132659-832953.json` |
| **HTTP path runs end-to-end**: `POST /jobs` → 7-stage log → signed URL → download → ffprobe (h264 1920×1080, aac) → tampered URL rejected 403 | SMOKE PASS 19 Nov 2026, job `20261119-132659-832953` · console transcript, job JSON and the 14.88 s MP4 are in `capture\` | `D:\opc\demo\capture\smoke-console.log` |
| Music beds are real synthesized audio mixed into the file | `voice.bed()` deterministic synth; `voice.mix()` | `D:\qf-t1-build\qf\voice.py` |
| Object store + HMAC signed expiring URLs, tamper-checked | `store.signed_url()/verify()`; smoke tests a tampered URL expecting 403 | `D:\qf-t1-build\qf\store.py`, `smoke.py` |
| Board re-roll: same topic, different boards — samples on disk | contact sheet + rerollA/rerollB scene PNGs | `D:\opc\t3-images\samples\how-contactless-payment-works*` |
| LLM script pass exists as a separate module with captured model responses | `engine.js` + providers + `out\sample-response.json`, `out\verify-agent-response.json` | `D:\opc\t2-script\` |
| Deploy bundle is prepared (HF Spaces, FFmpeg in image, honest adapter that never fakes a render) | `app.py`, `Dockerfile`, `DEPLOY_NOTES.md` — **prepared, NOT deployed** | `D:\opc\t8-deploy\` |
| Storefront is live | Hashmeta QuickFrame site, trial until 17 Dec 2026 | https://quickframe.geo.hashmeta.tech |
| The product was built by QwenWork agents from one spec file | T1/T2/T3/T8 work packages + specs in this folder | `D:\opc\` (this project) |

## 2. What is NOT true yet — do not claim it (mark to-record-later)

| Gap | Status | Effect on demo |
|---|---|---|
| The smoke run exists as a captured console transcript + artifacts, not as filmed screen footage | PASS transcript in `capture\smoke-console.log`; re-run is reproducible at any time | Shots 5–8 still need the camera on a live re-run — but it is now guaranteed to work, and shot 8's playback can be filmed from `capture\accept-20261119-132659-832953.mp4` today |
| Voice uses the free edge-tts neural engine (no key, unofficial MS endpoint); no premium vendor chosen | `QF_TTS_CMD` adapter seam exists and takes precedence, unset | Narration may say "real neural voice" (true) — not "premium voice vendor" (not chosen). Silent renders only when explicitly requested with no backend at all |
| T2 LLM pass and T3 reroll are separate modules, not integrated into the Python service | `engine.py` still deterministic; T2 is JS; T3 is a standalone step | Show them as real artifacts on disk; do not claim the service rerolls boards or calls an LLM yet |
| No deployed public endpoint | HF deploy blocked on Phair's account/token + explicit approval (`DEPLOY_NOTES.md` §1) | Demo runs the service locally on `127.0.0.1:8777` |
| YouTube/TikTok uploaders not written | publish stage = store + signed URL + manifest only | Say "publish writes the manifest; uploaders are next" |
| Original front-end (index/studio) not on this machine | per `qwenwork-task-t1.md` | Do not show Studio UI; show the real API + the MP4 instead |
| Billing/credits/watermark enforcement server-side | UI-only in the old build (T6) | No pricing claims in the demo |
| Typography on this machine is system-substituted (`/healthz/service` reports `substituted: true` for all four kinds — georgiab/segoesc/consola/arial, not the spec's Fraunces/Caveat) | Vendored fonts absent from this box | Renders are real but the visual identity differs from the spec; don't claim Fraunces/Caveat on screen, and don't promise the final look — promise the pipeline |

## 3. Recording checklist (before anything else is edited)

1. **Hero: full smoke run, filmed** (≈ 2 min of footage). Already proven once (transcript: `capture\smoke-console.log`, 19 Nov, SMOKE PASS). To film it:
   - **Check the port first.** A supervised `python -m qf.server` (T1 agent's) may already be listening on 8777 — record against that one; do not fight it for the port. If you must start your own: from `D:\qf-t1-build`, `python -m qf.server 8777`. The startup line now reads "voice vendor configured" (edge-tts).
   - terminal 2: `python -m qf.smoke` — POSTs the unseen topic *"why elevator music exists"*, prints the 7-stage log (real edge-tts voice lines included), downloads the MP4 via the signed URL, ffprobes it (h264 + aac), and shows the tampered-URL → 403 check.
   - **If the job ends `failed: MemoryError` at encode** (seen once on this box under memory pressure): restart the server with `QF_RENDER_WORKERS=1` set in its environment before filming. Do not simulate the run.
   - Note for narration sync: scene count follows `lengthSec` — the live engine trims the spine to fit (14 s → 2 scenes). Don't film-say "five scenes" unless the log says five.
2. **Playback of the produced MP4** — copy already in `capture\accept-20261119-132659-832953.mp4` (14.88 s, 1920×1080, h264+aac, real edge-tts voice + drive bed). Full screen, with the file properties visible once.
3. **Re-roll comparison** — build a side-by-side from the existing T3 PNGs (`samples\...` vs `...-rerollA` vs `...-rerollB`); no model needed, files exist now.
4. **Hashmeta site scroll-through** — https://quickframe.geo.hashmeta.tech, real browser, no mockups.
5. **QwenWork build B-roll (optional but strong)** — the task chats where the T1 spec was dispatched; one screen of `qwenwork-task-t1.md`.
6. Narration record: Phair's own voice or the channel's TTS (the demo's own VO is separate from the product's T4 gap — do not mix them up on screen).
7. Assemble in the geography-channel pipeline (ffmpeg), 1920×1080, 3:00.

## 4. Honest topic choice for the on-screen prompt

Use **"why elevator music exists"** — it is the exact topic in `smoke.py`, so the recording is the acceptance test itself, not a staged demo.

# QuickFrame demo — shot list (3:00, 1920×1080)

Statuses: **RECORD-NOW** = source exists on this machine today · **TO-RECORD** = capture after the named step (README §3) · **BUILD** = generate from existing files · No shot may use a mockup or a staged UI.

| # | Time | Shot | Visual / source | Status |
|---|---|---|---|---|
| 1 | 0:00–0:06 | Cold open | Black → QuickFrame board (any still from `t3-images\samples\how-contactless-payment-works\`, e.g. `scene00_clock.png`) with title card "QUICKFRAME — one prompt in, one video out" | BUILD (from PNGs on disk) |
| 2 | 0:06–0:15 | The prompt | Terminal, real typing: the `POST /jobs` JSON with `"topic": "why elevator music exists"` being entered (part of the smoke run) | TO-RECORD (checklist 3.1) |
| 3 | 0:15–0:27 | Seven stages, named | Lower-third strip animating the real keys in order: script · boards · art · voice · captions · encode · publish (type them as mono text; they are `brand.PIPELINE`, not design copy) | BUILD |
| 4 | 0:27–0:40 | The code | Quick cuts, 3–4 s each, real files opened: `qf/server.py` (routes), `qf/runner.py` (stage comments), `qf/driver.py` (`render()` ffmpeg cmd line) | TO-RECORD (screen scroll of `D:\qf-t1-build\qf\`) |
| 5 | 0:40–1:00 | Job submitted, log starts | The smoke run: `job … queued`, then stage lines appearing — `script … scenes`, `boards … stills`, `art …` | TO-RECORD (3.1) — run proven 19 Nov, transcript `capture\smoke-console.log`; re-run for the camera |
| 6 | 1:00–1:15 | Boards drawn | Cut to the boards directory from the run (`boards-<id>\scene-*.png`), flipping through the fresh stills (count follows `lengthSec`) | TO-RECORD (3.1) |
| 7 | 1:15–1:30 | Voice + encode + gate | Log lines: `edge-tts render …s · cues + scene times rebuilt from real word timings`, `audit 0 violations at 1920x1080 · rendering`, then `done … mp4 · … MB`; then the tamper check line `tampered signed URL -> 403` | TO-RECORD (3.1) |
| 8 | 1:30–1:50 | **Hero: the MP4 plays** | Full-screen playback of `accept-20261119-132659-832953.mp4` (in `capture\`) — first ~10 s with voice + captions + music audible, then a seek to a mid-video board. Keep file properties (size/duration) visible for one beat | RECORD-NOW (3.2 — file exists today) |
| 9 | 1:50–2:05 | Re-roll | Three-column contact sheet: original vs rerollA vs rerollB scene PNGs, same topic — poses/accents differ, glyphs stay | BUILD (3.3, from `t3-images\samples\`) |
| 10 | 2:05–2:15 | LLM pass, honestly | `t2-script\out\sample-response.json` on screen (the airplane-mode script) with caption "built + verified as a module — integration next" | TO-RECORD (open file; exists now) |
| 11 | 2:15–2:27 | The storefront | Browser scroll of https://quickframe.geo.hashmeta.tech — hero, pricing, signup | RECORD-NOW (3.4) |
| 12 | 2:27–2:35 | Gaps stated plainly | Simple text card, mono, read as it appears: "voice: free neural engine today, premium vendor next · deploy: awaiting one approval · uploaders: next" — no apology, no spin | BUILD |
| 13 | 2:35–2:55 | The OPC frame | One diagram, three boxes: QwenWork agents (build) → this pipeline (product) → Hashmeta site (storefront); built as motion text or the `qwenwork-task-t1.md` spec page + task chat B-roll | BUILD / TO-RECORD (3.5, optional B-roll) |
| 14 | 2:55–3:00 | Close | QuickFrame board still + tagline "Give it a topic." + site URL | BUILD |

## Assembly notes

- Shots 5–8 are one continuous smoke recording — capture it in a single session, cut later. If the smoke fails or the MP4 looks wrong, stop and fix before editing; do not paper over with B-roll.
- Audio: narration track ducks the terminal/typing sounds; the MP4 playback (shot 8) plays at full volume — it's the product's own audio and the best proof.
- Text cards use the same fonts the encoder uses (serif display / mono labels) so the demo looks like the product, not like a pitch deck.
- Order of production: do 3.1 (smoke) first — the whole video stands on it. Shots 1, 3, 9, 12, 14 can be built today while the rest waits.

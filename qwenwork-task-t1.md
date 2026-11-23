# QwenWork task — QuickFrame T1: prompt → MP4 job service

## Context (read first)
- Project: QuickFrame — stickman/whiteboard explainer-video generator, monthly subscription.
  Site: https://quickframe.geo.hashmeta.tech (Hashmeta, subscription active through 2026-12-17).
- Full work state is in `AGENTS.md` in this folder. Front-end + FFmpeg encode pipeline are PROVEN.
  There is NO backend, no server, no model call. Script engine is a deterministic stub.
  No TTS exists. Jobs live only in browser localStorage.
- Hashmeta CANNOT host this backend (its feasibility task failed: "the plan changes nothing").
  Hashmeta is a website builder/CMS only. Do not ask Hashmeta to build the backend.

## The job (T1 — do this first, it is the only risky one)
Wrap the existing CLI encode pipeline into a real job service:
  POST /jobs {topic, template, lengthSec, aspect, voice, captions, music}
  → script (T2: replace stub with one LLM call, keep engine.build() return shape)
  → per-scene image call (T3: replace fixed pool, keep artFor as art-direction layer)
  → voice (T4: wire a TTS vendor, return per-word timings into the cue array)
  → FFmpeg render (tools_build/driver.py render() — already proven)
  → object store → signed URL for a downloadable MP4.

## Anchors (real files — the source is NOT on this laptop yet; find it first)
- tools_build/driver.py:11 job load, :42 frame_at(m), :153 render(), :195 audit() safe-area gate.
- engine.js build(cfg) is the script seam; keep its return shape (job JSON §3 in AGENTS.md).
- Stage keys to preserve: script → boards → art → voice → captions → encode → publish.
- Contracts: job JSON fields, cue timings in seconds, caption styles, beds — all in AGENTS.md §3.

## Acceptance test
A topic never seen before returns a downloadable MP4 whose boards differ from the pool on disk.
No simulated render, no fake pipeline. If a capability (hosting, TTS, storage) is missing,
report it as a blocker — do not substitute a simulation.

## Where it runs — UNDECIDED, needs Phair
Hashmeta cannot host it. QwenWork agents are not a hosted backend.
Options to present to Phair: his own Linux server, or a cloud host. Do not create paid
cloud services without his approval. Build the service as deployable code first.

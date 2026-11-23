# QuickFrame demo — narration script (3:00)

Total ≈ 400 words. Read at a conversational pace; sections 3 and 6 run over live footage — let the screen lead, don't rush. Every factual claim maps to the evidence ledger in `README.md`; nothing here promises an unbuilt feature.

---

### S1 · Hook — 0:00–0:15 (≈ 35 words)

> QuickFrame. One prompt in — one finished explainer video out. And the company behind it is one person, because AI agents did the building. No mockups in this video. Everything you see is the real thing, running.

### S2 · The promise, in code — 0:15–0:40 (≈ 60 words)

> Give it any topic and it runs a seven-stage pipeline: script, boards, art, voice, captions, encode, publish. Those words aren't marketing. They're the actual keys in the job log, in the code. Each stage either produces a real artifact — or stops the job with an honest error. That rule is why the output can be trusted.

### S3 · Live run — 0:40–1:50 (≈ 130 words, paced to the terminal)

> Here's the job service, running on my machine. I post one topic — "why elevator music exists" — a topic the system has never seen. It queues. Watch the log: script — a beat sheet, trimmed to the length I asked for. Boards — whiteboard scenes drawn fresh for this topic, not picked from a pool. Voice — real neural speech, and its word timings re-time the whole edit. Captions — burned in by the encoder, cued to those exact words. Music — a synthesized bed, mixed under. Encode — real FFmpeg, and a safe-area audit that fails the job if a single word leaves the broadcast line. Publish — stored, with a signed, expiring download link. Tamper with the link? Rejected. And here's the file.

> *(beat — let the MP4 play, 6–10 s, no narration)*

### S4 · Variation — 1:50–2:05 (≈ 35 words)

> Same topic, re-roll the boards: different poses, different accents, same story. Every job carries its own seed, so nothing repeats. And the script pass itself? A language-model version is already built and verified as its own module — wiring it into the service is next.

### S5 · The one-person company — 2:05–2:35 (≈ 60 words)

> Behind the product: the storefront is live on Hashmeta. The backend, the art step, the deploy bundle — all built by QwenWork agents working from a single spec file. What isn't done, I'll say plainly: the voice you just heard is a free neural engine — a premium vendor is next — and the public deploy waits on one approval from me.

### S6 · Close — 2:35–3:00 (≈ 40 words)

> One person. One prompt. One finished video — and a company that tells you exactly what's real. QuickFrame. Give it a topic.

---

## Delivery notes

- **S3 is the spine.** Record it against the actual smoke run (README checklist §3.1) and fit the words to the real log lines; if a stage line differs, change the narration to match the screen — never the reverse.
- **The 6–10 s playback beat:** choose the moment when the stickman board is fully drawn with a caption on screen.
- **S5 honesty beat:** slow down slightly on "What isn't done, I'll say plainly" — this is the line that differentiates the submission.
- Voice: Phair's own voice preferred (OPC = one person, one voice); fallback is the geography-channel TTS. Product VO (T4) is a different thing — don't use it for the demo track to avoid blurring the claim.

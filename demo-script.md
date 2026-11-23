# QuickFrame Demo Video — 3-Minute Script

**Hackathon:** QwenWork x Hashmeta AI One-Person Company Hackathon
**Due:** Sun 23 Nov 2026, 23:59 SGT — submission link from the QwenWork confirmation email (https://luma.link/KohjTskYPo)
**Length:** 3:00 (180 seconds). Narration ≈ 390 words.
**Rule for the whole video:** show the real working product. Screen-record the real QwenWork agent chat and the real Hashmeta site. No slides of fake UI, no mockups, no claims the product can't do.

---

## Shot list and narration

| Time | Shot / visual | Narration (read exactly as written) | On-screen text |
|---|---|---|---|
| 0:00–0:12 | Hook. Screen recording of a blank QwenWork chat. A topic is typed: "how contactless payment works". | "One person. One company. One question: can an AI agent run it? This is QuickFrame — give it a topic, and it writes your explainer script." | "QUICKFRAME — one person, one company" |
| 0:12–0:35 | Problem. Quick cuts: a creator staring at a blank doc; a messy notes app; a clock. | "Explainer videos live or die on the script. But most creators stare at a blank page, or paste a topic into a chatbot and get a flat wall of text. QuickFrame fixes that with a method, not just a model." | "Blank page → flat script" |
| 0:35–0:55 | The method. Simple five-box graphic (built as a text card, not a fake screenshot): Topic, Audience, One Idea, Confusion to Resolve, Next Step. | "Five slots. Topic, audience, one idea, the confusion to clear up, and what the viewer should do next. Fill all five, and the script writes itself. Skip one, and the video falls flat." | "THE FIVE SLOTS" |
| 0:55–1:40 | Live demo, part 1 — the agent. Screen recording, real time, no cuts inside the exchange: the agent asks the four missing-slot questions; the user answers; the agent confirms the brief; the script appears with its word count. | "Watch it work. I give it a topic — nothing else. It asks me four questions. I answer in plain words. And then — a full script, checked, with its word count. I didn't write a word of it." | "Topic in → finished script out" |
| 1:40–2:20 | Live demo, part 2 — the site. Screen recording of the real QuickFrame site on Hashmeta: the public demo, the trial signup. | "That's the agent. Here's the shop. The QuickFrame site runs the public demo, and anyone can start a trial. The agent sends people here, and the site sends them back to the agent." | "app.hashmeta.ai — QuickFrame" |
| 2:20–2:50 | The company. Simple architecture diagram on screen (three boxes, from `opc-architecture.md`): QwenWork agent → Hashmeta site → n8n / phone / VM. | "And behind it, a whole company. The agent talks to customers. The site sells. And my own machines run the schedule — the daily digest, the articles, the trial watch. One person, approving things for five minutes a day." | "Agent · Storefront · Schedule" |
| 2:50–3:00 | Close. QuickFrame logo / site on screen. | "QuickFrame. Give it a topic — it gives you a script. Try it." | "QUICKFRAME — try it" |

---

## Narration lines (full text, in order)

1. "One person. One company. One question: can an AI agent run it? This is QuickFrame — give it a topic, and it writes your explainer script."
2. "Explainer videos live or die on the script. But most creators stare at a blank page, or paste a topic into a chatbot and get a flat wall of text. QuickFrame fixes that with a method, not just a model."
3. "Five slots. Topic, audience, one idea, the confusion to clear up, and what the viewer should do next. Fill all five, and the script writes itself. Skip one, and the video falls flat."
4. "Watch it work. I give it a topic — nothing else. It asks me four questions. I answer in plain words. And then — a full script, checked, with its word count. I didn't write a word of it."
5. "That's the agent. Here's the shop. The QuickFrame site runs the public demo, and anyone can start a trial. The agent sends people here, and the site sends them back to the agent."
6. "And behind it, a whole company. The agent talks to customers. The site sells. And my own machines run the schedule — the daily digest, the articles, the trial watch. One person, approving things for five minutes a day."
7. "QuickFrame. Give it a topic — it gives you a script. Try it."

**Word count:** ≈ 390 words total, ≈ 56 words per section on average. Sections 4 and 6 run over live screen recordings, so pace the narration to the action on screen rather than rushing.

---

## Production notes

- **Voice:** Phair's own voice, or Kore TTS (same voice as the geography channel). Keep it conversational, not announcer-style.
- **Captions:** Burned-in captions throughout, same style as the channel (big text cards for punchlines are optional here — this is a product demo, keep captions small and lower-third).
- **Screen recordings:** Record the real agent conversation in QwenWork and the real site at app.hashmeta.ai. If the agent is not built yet, record nothing — build it first (see `quickframe-agent-spec.md` §9), then record.
- **Do not show:** a fake dashboard, a mockup of the agent clicking through the site (it can't — no browser use), any usage or signup numbers (none are verified), any speaking-rate figures, or any claim about the 300-character cap in the signed-in app.
- **Music:** Light, neutral bed under narration; cut it under the live demo section so the typing and the agent's replies are the focus.
- **Render:** ffmpeg on the Seeker phone or this VM, `-movflags +faststart`, 1080p plus a 720p version — same pipeline as the geography channel.

## Pre-demo checklist

- [ ] FILI invite accepted (expires ~24 Nov 2026) — confirm team / seat access before recording.
- [ ] Script Coach agent created in QwenWork from `quickframe-agent-spec.md` and both test flows pass.
- [ ] Every [NEEDS PHAIR] in the agent spec either confirmed or removed from the demo — nothing unconfirmed appears on screen or in narration.
- [ ] Hashmeta site trial live; public demo works on camera.
- [ ] Agent share link on the site (if the site allows it).
- [ ] Demo recorded, captioned, rendered (1080p + 720p, faststart), watched through once.
- [ ] Submitted via https://luma.link/KohjTskYPo before Sun 23 Nov 2026, 23:59 SGT.

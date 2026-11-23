# QuickFrame One-Person Company — Architecture

**Product:** QuickFrame — a script-writing tool for explainer videos
**Hackathon:** QwenWork x Hashmeta AI One-Person Company Hackathon
**Demo due:** Sun 23 Nov 2026, 23:59 SGT — 3-minute demo video, submission link from the QwenWork confirmation email (https://luma.link/KohjTskYPo)
**Date:** 18 Nov 2026

## 0. The shape in one paragraph

QuickFrame is a one-person company with three parts. The **front door** is a QwenWork chat agent, the QuickFrame Script Coach: a visitor talks to it, it runs the five-slot script method, and hands back a finished explainer script. The **storefront** is the QuickFrame site on Hashmeta (trial active until 17 Dec 2026), which hosts the public demo, the trial signup, and AI-written marketing articles. Everything that has to run on a schedule — daily digests, article drafting, trial-expiry watch — runs on **Phair's own machines** (n8n at n8n.xjp2automation.online, the Seeker phone, this VM), exactly how the faceless geography YouTube channel already runs today. That split exists because QwenWork has no cloud agents and no browser-use agents: nothing in QwenWork runs unattended, so anything scheduled lives outside it. Phair is the human in the loop for exactly one job: confirming product facts and approving anything published.

```
Visitor ──► QwenWork agent (Script Coach, chat-triggered)
              │  topic in → five slots → finished script out
              │  links out to the public demo + trial signup
              ▼
         Hashmeta site (QuickFrame storefront, trial until 17 Dec 2026)
              │  public demo · trial signup · AI articles
              ▼
         n8n / phone / VM (scheduled jobs, Phair's own infra)
              │  daily digest · article pipeline · trial-expiry watch
              ▼
         Phair (confirms facts, approves publishes, answers what the agent can't)
```

---

## 1. Function map

| # | Business function | Runs on | Trigger | Handoff | Status |
|---|---|---|---|---|---|
| 1 | Script generation (the product) | QwenWork chat agent — QuickFrame Script Coach | User message in QwenWork | Agent delivers the script in chat; links to the public demo / trial on the Hashmeta site | **To wire** — spec written (`quickframe-agent-spec.md`); agent not yet created in QwenWork |
| 2 | Public demo | Hashmeta site (QuickFrame) | Visitor opens the site | Visitor tries the demo → trial signup | **Live** — site trial active until 17 Dec 2026 |
| 3 | Trial signup / sales | Hashmeta site | Visitor signs up on the site | Signup → Phair sees it in the daily digest (Job 1) | **Live** (site) / **to wire** (digest) |
| 4 | Marketing articles | Hashmeta AI articles, drafted from the knowledge base | n8n Job 2 (weekly, manual trigger) → Phair approves → publish | Draft → Phair review → Hashmeta publish | **Blocked** — knowledge base is missing 30 facts; drafts may only use verified facts |
| 5 | Support (answering questions) | QwenWork agent + Phair | User asks the agent; agent escalates what it doesn't know | Agent answers from the knowledge base; unknowns go into the daily digest for Phair | **To wire** — needs the agent live + Job 1 |
| 6 | Ops — daily digest | n8n Job 1 (daily 08:00 SGT) | Cron in n8n | n8n → Muse → Phair in this chat | **To wire** — n8n instance exists; job not built |
| 7 | Ops — trial-expiry watch | n8n Job 3 (daily) | Cron in n8n | Alert Phair 7 days and 1 day before 17 Dec 2026 | **To wire** |
| 8 | Ops — analytics | Manual weekly check + n8n digest | Phair, Mondays | Numbers recorded in the goal file | **To wire** — QwenWork agent usage stats unknown; see §5 |
| 9 | Demo video production | Phone / VM (ffmpeg, TTS) | Phair triggers | Render → review → submit via the Luma link | **To wire** — script in `demo-script.md` |
| 10 | Finance (trial → paid) | **[NEEDS PHAIR]** — pricing, paid plans, and post-trial terms are unknown | — | — | **Unknown** |

---

## 2. Piece by piece

### 2a. QwenWork chat agent — the front door

- **What:** One agent, the QuickFrame Script Coach, built from `quickframe-agent-spec.md`.
- **Runs when:** Only when a user talks to it. There is no always-on mode — QwenWork has no cloud agents.
- **Can do:** Chat, follow the system prompt, ask the five-slot questions, draft and revise scripts, run the quality checks, link out to the demo and the site.
- **Cannot do:** Browse the web or the Hashmeta site itself (no browser-use agents), run on a schedule, send messages unprompted, or report its own usage stats.
- **Wire-up steps:**
  1. In QwenWork (xiujee02@gmail.com), create the agent from the spec.
  2. Run the two test flows and the guardrail tests in the spec, Section 9.
  3. Correct every [NEEDS PHAIR] in the spec before publishing the agent.
  4. Get the agent's share link and put it on the Hashmeta site as "Try the Script Coach". [NEEDS PHAIR — confirm the Hashmeta site allows adding a link/button.]

### 2b. Hashmeta site — the storefront

- **What:** The QuickFrame site at app.hashmeta.ai. Trial (30 days) active until 17 Dec 2026.
- **Runs:** The public demo, trial signup, and AI-written marketing articles.
- **Live now:** Site + trial. The knowledge base exists but is missing 30 facts (10 named in the 17 Nov email, all about the script tool; 20 unnamed).
- **Wire-up steps:**
  1. Add the agent share link to the site (see 2a step 4).
  2. Do not publish any article that states an unverified fact. Every article draft goes through Phair review (Job 2) until the 30 facts are confirmed.
  3. Decide before 17 Dec 2026: paid plan, or export/close. Job 3 will remind Phair. [NEEDS PHAIR — pricing and post-trial terms.]

### 2c. n8n — the scheduled backbone (Phair's own infra)

n8n at n8n.xjp2automation.online. Nothing here runs inside QwenWork; that is the point — scheduled work lives on Phair's own machines, the same way the geography channel's pipeline runs on a schedule today.

**Job 1 — Daily digest (daily 08:00 SGT, cron trigger)**
- What it does: checks for anything new overnight — Hashmeta trial signups/activity, questions the agent couldn't answer, article drafts waiting — and sends Phair one short digest in this chat via Muse.
- Handoff: n8n → Muse → Phair. Phair answers the escalated questions; the answers go back into the knowledge base and the agent spec.
- Status: to build. (n8n instance exists; the geography v2.1 workflow is built but not yet applied — do not touch it. Build Job 1 as a new, separate workflow.)

**Job 2 — Article pipeline (weekly, manual trigger)**
- What it does: takes one knowledge-base topic, drafts an article using verified facts only, and holds it for Phair's review. Nothing publishes without Phair's approval.
- Blocked until: Phair confirms the 30 missing facts (or confirms which ones to leave out). Drafting from unverified facts is how the knowledge base got into its current state.
- Handoff: n8n draft → Phair review → publish on Hashmeta.

**Job 3 — Trial-expiry watch (daily, cron trigger)**
- What it does: from 10 Dec 2026, alerts Phair at 7 days and 1 day before the trial ends (17 Dec 2026) to decide on a paid plan or export.
- Status: to build. [NEEDS PHAIR — paid-plan price and terms.]

### 2d. Phone / VM — compute and production

- **Seeker phone (Termux ffmpeg) and this VM:** render the demo video, generate TTS narration, and hold working files — the same setup the geography channel uses. No new infrastructure needed.
- **Phair (human in the loop):** exactly three jobs — (1) confirm product facts the agent and articles need, (2) approve anything before it publishes, (3) answer the questions the agent escalates. Everything else is handled by the three pieces above.

---

## 3. What's live vs what Phair must wire up

| Live today (18 Nov 2026) | To wire up (before the 23 Nov demo) |
|---|---|
| QwenWork account signed in (xiujee02@gmail.com, 17 Nov 8:24pm) | Create the Script Coach agent in QwenWork from the spec |
| FILI team invite received (17 Nov, from 张妩雪) — acceptance unconfirmed, link expires ~24 Nov | Accept the FILI invite if that is the team / seat activation |
| Hashmeta QuickFrame site + trial (until 17 Dec 2026) | Add the agent link to the site |
| Knowledge base (with 30 missing facts) | Confirm the 30 facts (or mark which to leave out) |
| n8n instance, phone, VM (proven by the geography channel) | Build n8n Jobs 1–3 as new workflows (do not touch the geography v2.1 workflow) |
| Demo video script (`demo-script.md`) | Record, edit, and submit the demo video by Sun 23 Nov 23:59 SGT |

---

## 4. Handoffs (the seams where things break)

1. **Visitor → agent:** visitor talks to the agent in QwenWork. If the visitor wants the demo, the agent links to the Hashmeta site — it cannot take them there itself (no browser use).
2. **Agent → Phair:** anything the agent doesn't know goes into the daily digest (Job 1). The agent never invents an answer to close the gap.
3. **Phair → knowledge base:** Phair's answers to escalated questions are written into the knowledge base and the agent spec, so the agent gets smarter instead of escalating the same question twice.
4. **n8n → Phair:** one digest a day, 08:00 SGT. No other notifications — Phair already gets enough pings.
5. **Site → Phair:** trial signups surface in the digest, not as instant alerts.

---

## 5. Operating rhythm (after the demo)

- **Daily, 08:00 SGT:** Job 1 digest. Phair answers escalations (5 min), approves or rejects any pending article draft.
- **Weekly, Monday:** Phair checks agent usage and site numbers by hand and records them in the goal file. [NEEDS PHAIR — confirm whether QwenWork shows agent usage stats; if it doesn't, usage is measured by asking users, not by dashboard.]
- **Weekly:** Job 2 drafts one article from verified facts only.
- **10 Dec 2026 onward:** Job 3 trial-expiry alerts; decide paid plan vs export before 17 Dec 2026.

---

## 6. Constraints and risks (do not design around these)

1. **No cloud agents in QwenWork.** Nothing runs unattended inside QwenWork. Any "the company runs itself" claim must rest on n8n/phone/VM, not on QwenWork.
2. **No browser-use agents.** The agent cannot operate the demo, the site, or any web page. Demos must show the agent in chat and the site on screen as separate, real things — never pretend the agent clicked through the site.
3. **Knowledge base gaps.** 30 facts missing. Until Phair confirms them, the agent and the articles must say "I don't know" on those points. An agent that guesses is worse than one that asks.
4. **Trial ends 17 Dec 2026.** The storefront has a 4-week runway from the hackathon. Pricing and post-trial terms are unknown.
5. **FILI invite expires ~24 Nov 2026.** If the invite is the seat activation, accept it before the demo is due — losing team access after submitting would be worse than a weak demo.
6. **One person.** Phair is the only human. The OPC works only if his daily job stays at ~5 minutes of approvals and answers. Anything that needs him hourly is not a one-person company.

---

## 7. Open questions for Phair ([NEEDS PHAIR] list)

1. Is the FILI invite the seat activation? Have you accepted it?
2. Exact names and definitions of the five slots (see agent spec §10).
3. Does the 300-character cap apply in the signed-in app?
4. In the studio demo, can a visitor edit/regenerate the script or only read it?
5. Is the laptop-throttling example's full script text publicly viewable?
6. QuickFrame pricing, paid plans, and post-trial terms.
7. Can the Hashmeta site link out to the QwenWork agent?
8. Does QwenWork show agent usage stats?
9. What are the 20 unnamed missing knowledge-base facts?
10. Is there a real signup / usage number to quote anywhere? (Do not quote any number until confirmed.)

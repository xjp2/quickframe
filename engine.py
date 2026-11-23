"""Script engine (deterministic) + art-direction layer — rebuilt from the
AGENTS.md §3 job contract. Return shape is the job JSON the app consumes:

  id, topic, subject, template, templateName, audience, tone, voice{...}, aspect,
  music, captions, title, hook, totalSec, words, description, tags[],
  thumbnail{text, art}, credits, warnings[],
  scenes[] { i, beat, vo, caption, onText, motion, art, whyArt, clip, sec, words,
             chars, start, end, cues[{text, at}] }

cfg in: {topic, template, lengthSec, aspect, voice, tone, captions, music, duck}

Deterministic: same topic + cfg => same script (spec §1 "Script engine (stub)
deterministic"). T2 (LLM) replaces `line_for()`'s body only; this build ships
the deterministic version because no LLM key exists on this machine — it is
the real production path of the original stub, not a mock.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

from . import brand


class ScriptEngineError(RuntimeError):
    """Raised when the LLM script stage (T2) cannot produce text. Carries a
    stable `code` so the runner surfaces it as a clean BLOCKED state instead of
    silently falling back to the deterministic stub (owner rule: never fake it)."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

# 6 spines x 5 beats. {T} = topic phrase interpolated.
TEMPLATES: dict[str, list[dict]] = {
    "why": [
        {"beat": "hook", "motion": "walk",
         "line": "You have seen {T} a hundred times. Almost nobody can explain it.",
         "onText": "why {T}?"},
        {"beat": "question", "motion": "point",
         "line": "So here is the honest question: why does {T} work the way it does?",
         "onText": "the real question"},
        {"beat": "build", "motion": "draw",
         "line": "Start with one small piece. It follows a simple rule, and the rule is doing all the work.",
         "onText": "one rule"},
        {"beat": "turn", "motion": "count",
         "line": "Stack those pieces and something surprising happens. That is where {T} comes from.",
         "onText": "it stacks"},
        {"beat": "land", "motion": "nod",
         "line": "Next time you meet {T}, you already know how it works. Follow for the next one.",
         "onText": "now you know"},
    ],
    "compounding": [
        {"beat": "hook", "motion": "point",
         "line": "Saving more feels virtuous. It is also the slowest lever you own.",
         "onText": "the slow lever"},
        {"beat": "mechanism", "motion": "draw",
         "line": "Compounding pays interest on interest. The first dollar earns, then the earnings earn.",
         "onText": "earnings earn"},
        {"beat": "math", "motion": "count",
         "line": "Run {T} for ten years and the curve bends. Time in the market beats timing added.",
         "onText": "the bend"},
        {"beat": "obstacle", "motion": "shake",
         "line": "The trap is impatience. Two flat years and most people quit right before the bend.",
         "onText": "quit before the bend"},
        {"beat": "action", "motion": "walk",
         "line": "Automate it, leave it alone, and let {T} do the boring work. Follow for part two.",
         "onText": "set it, forget it"},
    ],
    "myth": [
        {"beat": "myth", "motion": "shake",
         "line": "Everyone says {T} works like this. It is wrong, and the wrong version is everywhere.",
         "onText": "the common myth"},
        {"beat": "origin", "motion": "point",
         "line": "The myth survived because it is comfortable. Nobody profits from checking it.",
         "onText": "why it stuck"},
        {"beat": "evidence", "motion": "draw",
         "line": "Look at one concrete case. The facts point somewhere else entirely.",
         "onText": "the actual case"},
        {"beat": "reality", "motion": "count",
         "line": "Here is what is really happening in {T}. It is less tidy and far more interesting.",
         "onText": "the real mechanism"},
        {"beat": "takeaway", "motion": "nod",
         "line": "Next time someone repeats the myth, you can explain the truth. Follow for the next myth.",
         "onText": "now you can explain it"},
    ],
    "howto": [
        {"beat": "promise", "motion": "walk",
         "line": "You can get good at {T} with one habit, repeated where you already are.",
         "onText": "one habit"},
        {"beat": "step1", "motion": "point",
         "line": "Step one: pick the smallest version that fits in five minutes.",
         "onText": "step 1: go small"},
        {"beat": "step2", "motion": "draw",
         "line": "Step two: attach it to something you already do every day.",
         "onText": "step 2: attach it"},
        {"beat": "step3", "motion": "count",
         "line": "Step three: count only streaks, not results, for two weeks. {T} follows the streak.",
         "onText": "step 3: count streaks"},
        {"beat": "trap", "motion": "shake",
         "line": "The trap is upgrading too early. Boring and repeated beats exciting and rare. Follow for the template.",
         "onText": "do not upgrade yet"},
    ],
    "story": [
        {"beat": "origin", "motion": "walk",
         "line": "It started as a footnote. {T} was never supposed to be the story.",
         "onText": "a footnote"},
        {"beat": "problem", "motion": "shake",
         "line": "Then everything broke. The plan everyone trusted fell apart in a week.",
         "onText": "it broke"},
        {"beat": "turn", "motion": "point",
         "line": "The fix came from the smallest team in the room, with the dumbest idea on the board.",
         "onText": "the unlikely fix"},
        {"beat": "climb", "motion": "count",
         "line": "It worked, then it scaled, then it became {T} that nobody can switch off.",
         "onText": "then it scaled"},
        {"beat": "outcome", "motion": "nod",
         "line": "History remembers the outcome, not the accident. Follow for the next story.",
         "onText": "remember the accident"},
    ],
    "inside": [
        {"beat": "door", "motion": "walk",
         "line": "Step past the sign. Here is how {T} actually runs on a normal Tuesday.",
         "onText": "past the sign"},
        {"beat": "surface", "motion": "point",
         "line": "What customers see is one desk and one queue. That is the entire stage.",
         "onText": "one desk, one queue"},
        {"beat": "hidden", "motion": "draw",
         "line": "What they never see is the chain of quiet checks behind every single move.",
         "onText": "the hidden chain"},
        {"beat": "engine", "motion": "count",
         "line": "The engine is boring: a clock, a threshold, and a rule nobody argues with.",
         "onText": "clock, threshold, rule"},
        {"beat": "signal", "motion": "nod",
         "line": "Next time {T} feels instant, remember the queue that made it look easy.",
         "onText": "the queue behind it"},
    ],
}

TEMPLATE_NAMES = {
    "why": "Why it works", "compounding": "The compounding spine",
    "myth": "Myth bust", "howto": "How-to", "story": "Origin story",
    "inside": "Inside the process",
}

# Art-direction layer (keeps the role of artFor from engine.js:20): motion
# hint -> candidate glyph keys; keyword match on the vo line wins, then a
# deterministic pick that never repeats within a job.
MOTION_GLYPHS = {
    "walk": ["path", "people", "arrow"],
    "point": ["target", "speech", "magnifier"],
    "draw": ["gear", "bulb", "flow"],
    "count": ["coins", "bars", "clock"],
    "shake": ["cross", "alert", "cloud"],
    "nod": ["check", "people", "target"],
}
KEYWORD_GLYPHS = [
    (r"interest|money|dollar|earn|save|price|cost", "coins"),
    (r"year|week|day|time|clock|hours|minutes|seconds", "clock"),
    (r"step|habit|repeat|streak|again", "path"),
    (r"rule|mechan|engine|works|system|chain", "gear"),
    (r"idea|know|understand|explain|light", "bulb"),
    (r"myth|wrong|false|never|quit|trap|broke", "cross"),
    (r"right|truth|fix|answer|land|remember", "check"),
    (r"people|team|nobody|everyone|customer", "people"),
    (r"question|ask|look|see|watch|find", "magnifier"),
    (r"grow|bend|curve|scale|stack|count", "bars"),
    (r"say|says|voice|call|repeat", "speech"),
    (r"target|goal|aim|pick|choose", "target"),
    (r"flow|queue|line|pipeline", "flow"),
    (r"alert|warning|danger|risk|flat", "alert"),
    (r"cloud|cloudy|murky|hidden|fog", "cloud"),
    (r"arrow|direction|next|forward", "arrow"),
]

_STOP = {"a", "an", "the", "why", "how", "what", "when", "does", "do", "is",
         "of", "in", "on", "to", "for", "and", "it", "this", "that", "be"}


def _norm(topic: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", topic.lower())
    return re.sub(r"\s+", " ", t).strip()


def _subject(topic: str) -> str:
    words = [w for w in _norm(topic).split() if w]
    if not words:
        return topic.strip()
    if words[0] in _STOP and len(words) > 1:
        words = words[1:]
    return " ".join(words[:6])


def line_for(beat: dict, topic: str) -> str:
    """The T2 seam. Keep this signature; swap the body for one model call
    and preserve the return (a spoken line). Deterministic spine now."""
    return beat["line"].replace("{T}", _subject(topic))


# --------------------------------------------------------------------------
# T2 LLM script bridge (D:\opc\t2-script). When QF_SCRIPT_ENGINE=t2, the script
# stage pulls its creative TEXT from the T2 engine (one Node call, QwenWork model
# in-the-loop via the `agent` provider) instead of the deterministic spine above.
#
# Division of labour is unchanged from the spec: the model is creative (vo /
# caption / onText / title / hook / description / tags / thumbnail), the ENGINE
# is the clock — timing, glyph art-direction (_pick_art, bound to art.py's
# vocabulary), voice registry and credits stay in this Python build so the
# drawing/voice/encode stages keep consuming the exact §3 job shape.
# --------------------------------------------------------------------------

def _t2_enabled() -> bool:
    return os.environ.get("QF_SCRIPT_ENGINE", "").strip().lower() in ("t2", "llm", "quickframe-t2")


def _t2_dir() -> str:
    return os.environ.get("QF_T2_DIR") or r"D:\opc\t2-script"


def _t2_response_path(topic: str, template: str) -> str:
    """Where the QwenWork model's authored JSON response lives. Explicit via
    QF_T2_RESPONSE, else deterministic per (topic, template) so a re-run of the
    same job finds the same authored script."""
    env_p = os.environ.get("QF_T2_RESPONSE")
    if env_p:
        return env_p
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60] or "job"
    return os.path.join(_t2_dir(), "llm-responses", f"response-{template}-{slug}.json")


def _llm_text(cfg: dict, template: str, n_beats: int) -> dict:
    """Call the T2 engine once and return its creative text fields, keyed for
    mapping into this build. Raises ScriptEngineError (never a silent stub) if
    the model response is not available."""
    node = shutil.which("node") or "node"
    cli = os.path.join(_t2_dir(), "bin", "cli.js")
    if not os.path.isfile(cli):
        raise ScriptEngineError("t2_missing", f"T2 script engine not found at {cli}")

    topic = cfg["topic"]
    length = float(cfg.get("lengthSec") or 20)
    aspect = cfg.get("aspect") or "16:9"
    tone = cfg.get("tone") or "plain, spoken, confident"
    resp = _t2_response_path(topic, template)
    existed = os.path.isfile(resp)

    out_fd, out_path = tempfile.mkstemp(prefix="qf-t2-job-", suffix=".json")
    os.close(out_fd)
    try:
        cmd = [node, cli, "--provider", "agent", "--topic", topic,
               "--spine", template, "--seconds", str(int(round(length))),
               "--aspect", aspect, "--tone", tone,
               "--response", resp, "--out", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 2:  # T2 agent provider: response file absent
            prompt_path = (re.search(r"prompt\s+->\s+(\S+)", proc.stderr) or [None, "?"])[1]
            raise ScriptEngineError(
                "llm_script_pending",
                "LLM script stage is waiting for the QwenWork model to author the "
                f"response.\n  prompt   -> {prompt_path}\n  response <- {resp}\n"
                "Author the schema-shaped JSON there (the model, not the stub), then "
                "re-run the job. Not falling back to the deterministic spine.")
        if proc.returncode != 0:
            raise ScriptEngineError("t2_error",
                                    f"T2 engine exited {proc.returncode}: {proc.stderr.strip()[:400]}")
        with open(out_path, encoding="utf-8") as f:
            job = json.load(f)
    except subprocess.TimeoutExpired:
        raise ScriptEngineError("t2_timeout", "T2 engine call timed out (120s)")
    finally:
        if os.path.isfile(out_path):
            os.remove(out_path)

    scenes = job.get("scenes") or []
    if len(scenes) != n_beats:
        raise ScriptEngineError("t2_scene_count",
                                f"T2 returned {len(scenes)} scenes; spine {template!r} needs {n_beats}")
    return {
        "vo": [s.get("vo", "") for s in scenes],
        "caption": [s.get("caption", "") for s in scenes],
        "onText": [s.get("onText", "") for s in scenes],
        "title": job.get("title"),
        "hook": job.get("hook"),
        "description": job.get("description"),
        "tags": job.get("tags"),
        "thumbnail": (job.get("thumbnail") or {}).get("text"),
        "_authored": resp,
        "_wasPendingBefore": not existed,
    }


def _word_chunk(text: str, size: int = 4) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] if words else []


def build(cfg: dict) -> dict:
    """Deterministic script pass. cfg keys per contract; returns job JSON §3."""
    warnings: list[str] = []
    topic = (cfg.get("topic") or "").strip()
    if not topic:
        raise ValueError("cfg.topic is required")
    if len(topic) > 300:
        warnings.append("topic exceeds 300 chars (public-demo cap); shortened for the board")
        topic = topic[:300]

    template = cfg.get("template") or "why"
    if template not in TEMPLATES:
        warnings.append(f"unknown template {template!r}; used 'why'")
        template = "why"
    beats = TEMPLATES[template]

    aspect = cfg.get("aspect") or "16:9"
    if aspect not in brand.ASPECTS:
        warnings.append(f"aspect {aspect!r} unsupported by encoder; used 16:9")
        aspect = "16:9"

    voice_name = cfg.get("voice") or "calm-01"
    if voice_name not in brand.VOICES:
        warnings.append(f"voice {voice_name!r} not in registry; used calm-01")
        voice_name = "calm-01"
    rate = brand.VOICES[voice_name]["rate"]

    captions = cfg.get("captions") or "blocks"
    if captions not in brand.CAPTION_STYLES:
        warnings.append(f"caption style {captions!r} unknown; used 'blocks'")
        captions = "blocks"

    music = cfg.get("music") or "drive"
    if music not in brand.BEDS:
        warnings.append(f"bed {music!r} unknown; used 'drive'")
        music = "drive"
    if music == "ai":
        warnings.append("bed-ai.mp3 asset not present on this machine; mixed 'drive' instead")
        music_sub = "drive"
    else:
        music_sub = music

    length = float(cfg.get("lengthSec") or 20)
    length = max(8.0, min(120.0, length))

    # --- spoken lines -> duration budget.
    # Real edge-tts pace is ~2.4 words/sec (calibrated), and the render is
    # content-bound: a fixed 5-beat spine is ~34 s of speech. The old code scaled
    # FAKE scene durations to lengthSec, but the voice stage re-timed every scene
    # to the real audio and threw that budget away (a "12 s" job rendered ~36 s).
    # Fix honestly: size the NUMBER of beats to the target, then apply a small,
    # natural TTS rate correction so the chosen speech lands on budget. The runner
    # still re-times to real audio — which now matches, because the content does.
    # LLM script pass (T2): when QF_SCRIPT_ENGINE=t2, the creative TEXT comes from
    # the T2 engine (QwenWork model in-the-loop via the agent provider). The clock
    # (timing, glyph art-direction, trimming, credits) below is unchanged.
    llm = _llm_text(cfg, template, len(beats)) if _t2_enabled() else None
    if llm:
        warnings.append("script text authored by the T2 LLM engine "
                        "(QwenWork model, agent provider) — not the deterministic spine")

    def _beat_text(bi, b):
        if llm:
            vo = (llm["vo"][bi] or "").strip() or line_for(b, topic)
            cap = (llm["caption"][bi] or "").strip() or vo
            on = (llm["onText"][bi] or "").strip() or b["onText"].replace("{T}", _subject(topic))
        else:
            vo = line_for(b, topic)
            cap = vo
            on = b["onText"].replace("{T}", _subject(topic))
        return vo, cap, on

    est = []
    for bi, b in enumerate(beats):
        vo, cap, on = _beat_text(bi, b)
        n_words = len(vo.split())
        est.append({"beat": b, "vo": vo, "caption": cap, "onText": on,
                    "words": n_words,
                    "sec": n_words / brand.SPEECH_WPS_TTS / rate})
    total_all = sum(e["sec"] for e in est)

    # beats that fit the target (>= 2 so there is always a hook and a takeaway)
    avg = total_all / max(1, len(est))
    k = max(2, min(len(est), int(round(length / avg))))
    if k >= len(est):
        keep = list(range(len(est)))
    else:
        keep = sorted({round(i * (len(est) - 1) / (k - 1)) for i in range(k)})
    chosen = [est[i] for i in keep]
    sel_est = sum(e["sec"] for e in chosen)

    # gentle rate correction so the chosen speech hits the budget (clamped natural)
    rate_factor = min(brand.RATE_MAX, max(brand.RATE_MIN, sel_est / length))
    tts_rate = round(rate * rate_factor, 3)

    if len(chosen) < len(est):
        warnings.append(f"target {length:.0f}s fits ~{len(chosen)} of {len(est)} beats; "
                        f"trimmed the spine to match lengthSec")

    used_art: set[str] = set()
    scenes = []
    t = 0.0
    for i, e in enumerate(chosen):
        vo, n_words, b = e["vo"], e["words"], e["beat"]
        sec = round(e["sec"] / rate_factor, 2)
        art, why = _pick_art(vo, b["motion"], topic, i, used_art)
        chunks = _word_chunk(vo)
        chunk_n = max(1, len(chunks))
        cues = [{"text": c, "at": round(t + (sec * j / chunk_n), 3)}
                for j, c in enumerate(chunks)]
        scenes.append({
            "i": i, "beat": b["beat"], "vo": vo, "caption": e["caption"],
            "onText": e["onText"],
            "motion": b["motion"], "art": art, "whyArt": why,
            "clip": "",  # AIGC clips are out of scope for the rebuilt encoder (spec §5.6)
            "sec": sec, "words": n_words, "chars": len(vo),
            "start": round(t, 3), "end": round(t + sec, 3), "cues": cues,
        })
        t += sec
        if n_words > 22:
            warnings.append(f"scene {i}: {n_words} words may rush the pace")

    total = round(t, 2)
    words = sum(s["words"] for s in scenes)
    subject = _subject(topic)
    seed = hashlib.sha256(f"{subject}|{template}".encode()).hexdigest()

    # packaging: deterministic defaults, overridden by the LLM's authored text when present
    title = f"{subject.capitalize()} — explained in {int(round(total))} seconds"
    hook = scenes[0]["vo"]
    description = (f"A {total:.0f}s {TEMPLATE_NAMES[template].lower()} explainer about {subject}. "
                   f"Made with QuickFrame: script, boards, captions, music, render — one prompt.")
    tags = [w for w in _norm(subject).split() if w not in _STOP][:8] + ["quickframe", "explainer"]
    thumb_text = scenes[0]["onText"]
    if llm:
        title = (llm["title"] or "").strip() or title
        hook = (llm["hook"] or "").strip() or hook
        description = (llm["description"] or "").strip() or description
        if isinstance(llm["tags"], list) and llm["tags"]:
            tags = [str(x).strip() for x in llm["tags"] if str(x).strip()][:8]
        thumb_text = (llm["thumbnail"] or "").strip() or thumb_text

    return {
        "id": cfg.get("id") or f"job-{seed[:10]}",
        "topic": topic, "subject": subject,
        "template": template, "templateName": TEMPLATE_NAMES[template],
        "audience": cfg.get("audience") or "curious general audience",
        "tone": cfg.get("tone") or "plain, spoken, confident",
        "voice": {"name": voice_name, "rate": tts_rate, "tts": cfg.get("tts") or "silent"},
        "aspect": aspect, "music": music, "captions": captions,
        "duck": cfg.get("duck", 0.0),
        "title": title,
        "hook": hook,
        "totalSec": total, "words": words,
        "description": description,
        "tags": tags,
        "thumbnail": {"text": thumb_text, "art": scenes[0]["art"]},
        "credits": max(1, -(-total // brand.SECONDS_PER_CREDIT)),  # ceil
        "warnings": warnings,
        "scenes": scenes,
        "_musicResolved": music_sub,  # engine-internal, stripped before API output
    }


def _pick_art(vo: str, motion: str, topic: str, i: int, used: set[str]):
    """artFor equivalent: keyword match first, then motion set, then global
    rotation — never repeats within a job (spec §2 T3)."""
    for pat, glyph in KEYWORD_GLYPHS:
        if re.search(pat, vo, re.I) and glyph not in used:
            used.add(glyph)
            return glyph, f"keyword match in vo -> {glyph}"
    for glyph in MOTION_GLYPHS.get(motion, []):
        if glyph not in used:
            used.add(glyph)
            return glyph, f"motion '{motion}' -> {glyph}"
    from .art import GLYPH_KEYS
    for glyph in GLYPH_KEYS:
        if glyph not in used:
            used.add(glyph)
            return glyph, "fallback rotation (no repeat)"
    used.add(f"repeat{i}")
    return GLYPH_KEYS[i % len(GLYPH_KEYS)], "all glyphs used; cycled"

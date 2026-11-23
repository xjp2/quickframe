"""Job runner: executes the seven-stage pipeline over a job and records the
stage log keyed exactly on brand.PIPELINE (script -> boards -> art -> voice
-> captions -> encode -> publish). Log format is the promise (spec T8):
one line per stage event, plus per-stage durations.

Stages:
  script   engine.build(cfg)                       (deterministic; T2 seam)
  boards   per-scene AI illustrations (T3 real)   (Pollinations, cached per job)
  art      art-direction summary + still manifest  (what artFor became)
  voice    TTS vendor or explicit silent track     (503 blocker if no vendor)
  captions cue timeline validation + style mirror
  encode   audit() gate -> driver.render() -> mp4  (real FFmpeg)
  publish  object store put -> signed URL + manifest (external uploaders: not wired)
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

from . import art, brand, driver, engine, env, images, store, voice


class Blocker(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _log(job: dict, stage: str, msg: str):
    job["log"].append({"ts": round(time.time(), 3), "stage": stage, "line": msg})


def _stage(job: dict, key: str, status: str):
    """Per-stage status map the web UI polls (pending/running/done/failed/blocked)."""
    job.setdefault("stageState", {})[key] = status


def _timed(fn):
    def wrap(*a, **k):
        t0 = time.time()
        r = fn(*a, **k)
        return r, round(time.time() - t0, 3)
    return wrap


def run(job: dict) -> dict:
    """job: {id, cfg, log, state, ...}. Mutates and returns it. Raises Blocker
    for missing capabilities instead of simulating them."""
    cfg = dict(job["cfg"])
    cfg["id"] = job["id"]
    silent = bool(cfg.pop("silentVoice", False))
    for k in brand.PIPELINE:
        _stage(job, k, "pending")

    # ---- script
    _stage(job, "script", "running")
    engine_mode = "T2 LLM" if engine._t2_enabled() else "deterministic stub"
    _log(job, "script", f"building beat sheet: engine={engine_mode} template={cfg.get('template', 'why')} topic={cfg.get('topic')!r}")
    try:
        built, dt = _timed(engine.build)(cfg)
    except engine.ScriptEngineError as e:
        # The LLM script stage could not produce text. Surface it as BLOCKED with
        # the exact reason — never a silent fallback to the stub (owner rule).
        _log(job, "script", f"blocked: {e.code}")
        raise Blocker(e.code, str(e), 503)
    job["result"] = {k: v for k, v in built.items() if not k.startswith("_")}
    _log(job, "script", f"done {dt}s · engine={engine_mode} · {len(built['scenes'])} scenes · {built['totalSec']}s · {built['credits']} credits")
    _stage(job, "script", "done")

    # ---- boards (REAL per-scene AI illustrations, cached per job; then stills)
    _stage(job, "boards", "running")
    W, H = brand.ASPECTS[built["aspect"]]
    img_manifest = []
    if images.enabled():
        _log(job, "boards", f"image stage: pollinations/{images.MODEL} · "
                            f"{len(built['scenes'])} scenes · cache=images-{job['id']}")
        try:
            img_manifest = images.fetch_all(built)
        except images.ImageStageError as e:
            # Honest blocker: never silently fall back to stickman boards.
            _log(job, "boards", f"blocked: {e.code}")
            raise Blocker(e.code, str(e), 503)
        for m in img_manifest:
            how = "cache hit" if m["cached"] else f"generated in {m['sec']}s"
            _log(job, "boards", f"scene {m['i']}: {how} · seed={m['seed']} · "
                                f"{m['bytes'] / 1024:.0f} KB")
    else:
        _log(job, "boards", "image stage OFF (QF_IMAGE_MODE) · vector boards")
    stills_dir = os.path.join(env.work_dir(), f"boards-{job['id']}")
    os.makedirs(stills_dir, exist_ok=True)
    stills = []
    t0 = time.time()
    for sc in built["scenes"]:
        img, _ = art.draw_board(built, sc, W, H, t=1.0)
        p = os.path.join(stills_dir, f"scene-{sc['i']}.png")
        img.save(p)
        stills.append(p)
    _log(job, "boards", f"done {round(time.time() - t0, 3)}s · {len(stills)} stills -> {os.path.basename(stills_dir)}"
                        + (f" · {len(img_manifest)} AI illustrations composited" if img_manifest else ""))
    _stage(job, "boards", "done")

    # ---- art (direction layer summary: glyph per scene, no repeats)
    _stage(job, "art", "running")
    glyphs = [sc["art"] for sc in built["scenes"]]
    assert len(set(glyphs)) == len(glyphs), "art repeats within a job"
    _log(job, "art", "done · " + " · ".join(f"s{i}:{sc['art']}({sc['whyArt'].split(' -> ')[0].split(' ')[0]})"
                                            for i, sc in enumerate(built["scenes"])))
    if img_manifest:
        served = img_manifest[0].get("model", images.MODEL)
        _log(job, "art", f"illustrations: {len(img_manifest)} distinct AI images "
                         f"(pollinations, model served: {served}) · shared cool-palette style · "
                         f"all readable text typeset by the encoder, never the image model")
    _stage(job, "art", "done")

    # ---- voice
    _stage(job, "voice", "running")
    total = built["totalSec"]
    bed_name = built["_musicResolved"]
    t0 = time.time()
    if voice.available():
        # Real TTS per scene. Re-time every scene to its ACTUAL spoken duration so
        # the video segment, the concatenated audio, and the cue timeline all
        # share one clock (the arithmetic timing from engine.build is only the
        # pre-voice estimate). Cues are rebuilt from real word-boundary timings.
        parts = []
        cursor = 0.0
        try:
            for sc in built["scenes"]:
                samples, words = voice.synth_voice(sc["vo"], built["voice"]["name"],
                                                   built["voice"]["rate"])
                dur = len(samples) / voice.SR
                sc["start"] = round(cursor, 3)
                sc["sec"] = round(dur, 2)
                sc["end"] = round(cursor + dur, 3)
                sc["cues"] = voice.rebuild_cues(built["scenes"], words, sc["i"],
                                                sc["start"], dur)
                parts.append(samples)
                cursor += dur
        except voice.TTSNotWired as e:
            # edge-tts importable but the render failed (e.g. network) — a real,
            # surfaced blocker, never a fake track.
            raise Blocker(e.code, str(e), 503)
        samples = np.concatenate(parts) if parts else voice.silent_voice(total)
        total = round(cursor, 2)
        built["totalSec"] = total
        built["credits"] = max(1, -(-total // brand.SECONDS_PER_CREDIT))
        built["voice"]["tts"] = ("vendor(QF_TTS_CMD)" if os.environ.get("QF_TTS_CMD")
                                 else "edge-tts")
        built["description"] = (
            f"A {total:.0f}s {built['templateName'].lower()} explainer about "
            f"{built['subject']}. Made with QuickFrame: script, boards, captions, "
            f"music, voice, render — one prompt.")
        _log(job, "voice", f"{built['voice']['tts']} render {total:.1f}s · "
                          f"{len(built['scenes'])} scenes · cues + scene times "
                          f"rebuilt from real word timings")
    elif silent:
        samples = voice.silent_voice(total)
        built["warnings"].append("voice track is SILENT (validation render, no TTS vendor) — not a shippable VO")
        _log(job, "voice", f"done {round(time.time() - t0, 3)}s · silent track requested (QF_TTS_CMD unset)")
    else:
        raise Blocker("tts_vendor_missing", str(voice.TTSNotConfigured()))
    bed, _bed_dt = _timed(voice.bed)(bed_name, total)
    pcm = voice.mix(samples, bed, brand.BED_MIX.get(bed_name, 0.87), total)
    wav = os.path.join(env.work_dir(), f"audio-{job['id']}.wav")
    driver.write_wav(wav, pcm)
    _log(job, "voice", f"bed={bed_name} mixed {brand.BED_MIX.get(bed_name, 0):.2f} · {total:.2f}s audio")
    _stage(job, "voice", "done")

    # ---- captions: validate cue monotonicity inside scenes (contract check)
    _stage(job, "captions", "running")
    for sc in built["scenes"]:
        ats = [c["at"] for c in sc["cues"]]
        if ats != sorted(ats) or (ats and (ats[0] < sc["start"] - 1e-6 or ats[-1] > sc["end"] + 1e-6)):
            raise Blocker("cue_invalid", f"scene {sc['i']}: cues outside scene window", 500)
    _log(job, "captions", f"done · style={built['captions']} · cues={sum(len(s['cues']) for s in built['scenes'])}")
    _stage(job, "captions", "done")

    # ---- encode: safe-area gate first (audit == the promise of zero violations)
    _stage(job, "encode", "running")
    segs = [dict(sc, _job={k: v for k, v in built.items() if k != "scenes"})
            for sc in built["scenes"]]
    t0 = time.time()
    violations = driver.audit(segs, (W, H), label=job["id"])
    if violations:
        raise Blocker("safe_area", f"audit blocked {len(violations)} text bbox violations", 500)
    _log(job, "encode", f"audit 0 violations at {W}x{H} · rendering")
    mp4, _enc_dt = _timed(driver.render)(f"qf-{job['id']}", segs, wav, gain=1.0, fade_out=0.0,
                                         workers=int(os.environ.get("QF_RENDER_WORKERS", "0"))
                                                 or min(2, env.cpu_count()))
    probe = env.ffprobe_json(mp4)
    dur = float(probe["format"]["duration"])
    size = os.path.getsize(mp4)
    _log(job, "encode", f"done {round(time.time() - t0, 3)}s · {dur:.2f}s mp4 · {size / 1e6:.2f} MB")
    _stage(job, "encode", "done")

    # ---- publish: object store + signed URL + manifest (T7 uploaders NOT wired)
    _stage(job, "publish", "running")
    key = _timed(store.put)(mp4)[0]
    base = (job.get("public_base")
            or os.environ.get("QF_PUBLIC_BASE", "http://127.0.0.1:8777")).rstrip("/")
    url = store.signed_url(key, base)
    manifest = {
        "title": built["title"], "description": built["description"],
        "tags": built["tags"], "aspect": built["aspect"],
        "formats": ["mp4-169" if built["aspect"] == "16:9" else "mp4-916"],
        "disclose": "AI-generated content (AIGC) label pending T9 policy hook",
        "destinations": "YouTube/TikTok uploaders not wired (out of scope for T1)",
    }
    mp = os.path.join(env.work_dir(), f"manifest-{job['id']}.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    mkey = store.put(mp)
    _log(job, "publish", f"done · stored {key} · signed URL ttl={store.DEFAULT_TTL_S}s · uploaders: none wired")
    _stage(job, "publish", "done")

    job["result"] = {k: v for k, v in built.items() if not k.startswith("_")}
    job["download"] = {"key": key, "url": url, "expiresIn": store.DEFAULT_TTL_S,
                       "sizeBytes": size, "durationSec": dur,
                       "manifestUrl": store.signed_url(mkey, base)}
    return job

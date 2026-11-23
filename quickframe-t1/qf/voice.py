"""Voice stage: TTS vendor interface + deterministic music beds.

Honesty rules (spec + owner directive):
- Voice is produced by a REAL TTS engine, never faked. Two backends:
  1. edge-tts (Microsoft Edge neural TTS) — free, no API key, no quota. This is
     the wired default: it streams speech + real per-word WordBoundary timings.
     If edge-tts is not importable or the network is unreachable, synth_voice()
     raises TTSNotWired (a hard blocker) — it does NOT emit fake speech.
  2. QF_TTS_CMD (optional vendor adapter, T4): a command template with
     {text} {out} {json} {voice} {rate}; must write a mono SR Hz WAV to {out}
     and a word-timing JSON [{"word","start","end"}] (seconds) to {json}.
     When set, it takes precedence over edge-tts.
- The only non-fake, non-vendor audio option is an explicitly requested SILENT
  voice track (real zero PCM, flagged in job.warnings) for pipeline validation.
- Music beds are a real deterministic numpy reimplementation (synth.py lineage),
  not a model call; mixed at brand.BED_MIX with fade.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile

import numpy as np

from . import brand, env

SR = 48000

# edge-tts neural voices: a clear English voice per brand voice name.
# rate is taken from brand.VOICES[name]["rate"] (a multiplier), mapped to the
# edge-tts percentage string. These are the free, no-key Microsoft neural voices.
EDGE_VOICES = {
    "calm-01":   "en-US-AriaNeural",   # clear, neutral-female
    "bright-01": "en-US-AriaNeural",
    "doc-01":    "en-US-GuyNeural",    # clear male, slower doc read
}
EDGE_DEFAULT = "en-US-AriaNeural"


class TTSNotConfigured(RuntimeError):
    def __init__(self):
        super().__init__(
            "No TTS vendor wired (T4). Set QF_TTS_CMD to a command that renders "
            "speech + per-word timings, or post the job with silentVoice=true for "
            "a pipeline-validation render (flagged in warnings, not shipped as VO).")
        self.code = "tts_vendor_missing"


class TTSNotWired(RuntimeError):
    """edge-tts is the wired default; raised only when it is unavailable AND no
    QF_TTS_CMD is configured. A hard blocker — never fake speech."""
    def __init__(self, detail: str):
        super().__init__(
            "Voice stage could not produce real speech: " + detail +
            " Install edge-tts (pip install edge-tts) and ensure network access "
            "to Microsoft's TTS endpoint, or set QF_TTS_CMD to a vendor adapter. "
            "Refusing to synthesize fake audio.")
        self.code = "tts_unreachable"


def _edge_importable() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def available() -> bool:
    """True when a real (non-fake) voice backend can be reached."""
    return bool(os.environ.get("QF_TTS_CMD")) or _edge_importable()


def _edge_rate(rate_mult: float) -> str:
    pct = int(round((float(rate_mult) - 1.0) * 100))
    return f"{pct:+d}%"


async def _edge_stream(text: str, voice_name: str, rate_mult: float):
    """Stream one utterance: return (mp3_bytes, [{word,start,end}]).
    WordBoundary offset/duration are 100-nanosecond ticks -> /1e7 = seconds."""
    import edge_tts
    name = EDGE_VOICES.get(voice_name, EDGE_DEFAULT)
    com = edge_tts.Communicate(text, name, rate=_edge_rate(rate_mult),
                               boundary="WordBoundary")
    audio = bytearray()
    words: list[dict] = []
    async for ch in com.stream():
        t = ch.get("type")
        if t == "audio":
            audio += ch["data"]
        elif t == "WordBoundary":
            off = ch.get("offset", 0) / 1e7
            dur = ch.get("duration", 0) / 1e7
            words.append({"word": ch.get("text", ""),
                          "start": round(off, 3), "end": round(off + dur, 3)})
    return bytes(audio), words


def _mp3_to_mono_wav(mp3: str, wav: str) -> None:
    subprocess.run(
        [env.ffmpeg_bin(), "-y", "-v", "error", "-i", mp3,
         "-ac", "1", "-ar", str(SR), wav], check=True)


def _edge_synth(text: str, voice: str, rate: float):
    """Real edge-tts render for one line -> (mono float samples, word timings)."""
    wd = os.path.join(env.work_dir(), f"tts-{os.getpid()}-{next(_edge_counter)}")
    os.makedirs(wd, exist_ok=True)
    mp3 = os.path.join(wd, "a.mp3")
    wav = os.path.join(wd, "a.wav")
    try:
        try:
            audio, words = asyncio.run(_edge_stream(text, voice, rate))
        except Exception as e:
            raise TTSNotWired(f"edge-tts stream failed ({type(e).__name__}: {e}).")
        if not audio:
            raise TTSNotWired("edge-tts returned zero audio bytes.")
        with open(mp3, "wb") as f:
            f.write(audio)
        _mp3_to_mono_wav(mp3, wav)
        return _read_wav(wav), words
    finally:
        shutil.rmtree(wd, ignore_errors=True)


import itertools
_edge_counter = itertools.count(1)


def _read_wav(path: str) -> np.ndarray:
    import wave
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getframerate() == SR, \
            f"voice backend must output mono {SR} Hz WAV, got {w.getnchannels()}ch {w.getframerate()}Hz"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    return data


def synth_voice(text: str, voice: str, rate: float):
    """Full voice pass used by the runner. Priority: QF_TTS_CMD vendor adapter,
    then native edge-tts. Raises a hard blocker if neither can produce real
    speech — never a fake track."""
    cmd_tpl = os.environ.get("QF_TTS_CMD")
    if cmd_tpl:
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        timings_p = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        cmd = (cmd_tpl.replace("{text}", json.dumps(text)).replace("{out}", out)
               .replace("{json}", timings_p).replace("{voice}", voice).replace("{rate}", str(rate)))
        subprocess.run(cmd, shell=True, check=True)
        samples = _read_wav(out)
        with open(timings_p, encoding="utf-8") as f:
            words = json.load(f)
        return samples, words
    if _edge_importable():
        return _edge_synth(text, voice, rate)
    raise TTSNotWired("edge-tts not importable and QF_TTS_CMD unset.")


def silent_voice(total_sec: float) -> np.ndarray:
    """Explicit validation path: real zero PCM. Callers must append a warning."""
    return np.zeros(int(total_sec * SR))


def rebuild_cues(scenes: list[dict], words: list[dict], scene_index: int,
                 scene_start: float, scene_sec: float) -> list[dict]:
    """Feed vendor per-word timings into the cue array instead of cueSplit
    (T4 contract). Groups words into the same 4-word chunks, `at` from audio."""
    chunks, cur, cur_t = [], [], None
    for wd in words:
        cur.append(wd["word"])
        if cur_t is None:
            cur_t = wd["start"]
        if len(cur) == 4:
            chunks.append((cur_t, " ".join(cur)))
            cur, cur_t = [], None
    if cur:
        chunks.append((cur_t if cur_t is not None else scene_sec, " ".join(cur)))
    return [{"text": t, "at": round(scene_start + max(0.0, s), 3)} for s, t in chunks]


# ---------------------------------------------------------------- beds
# Deterministic synth, same contract as studio.js BEDS: chalk/drive/lofi,
# 30 s loops, mixed at 0.85-0.9 with fade (brand.BED_MIX).
def bed(name: str, seconds: float) -> np.ndarray:
    """Stereo float bed, exactly `seconds` long, deterministic (seed fixed)."""
    if name == "none":
        return np.zeros((int(seconds * SR), 2))
    rng = np.random.default_rng({"chalk": 11, "drive": 22, "lofi": 33}.get(name, 22))
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)

    def tone(freq, at, dur, amp, kind="sine"):
        i0, i1 = int(at * SR), min(n, int((at + dur) * SR))
        if i0 >= n or i1 <= i0:
            return
        seg = t[i0:i1] - at
        env = np.minimum(1, seg / 0.01) * np.exp(-3.2 * seg)
        x = np.sin(2 * np.pi * freq * seg)
        if kind == "tri":
            x = 2 * np.abs(2 * (freq * seg % 1) - 1) - 1
        if kind == "kick":
            x = np.sin(2 * np.pi * (120 * np.exp(-8 * seg) + 40) * seg) * np.exp(-6 * seg)
        out[i0:i1] += amp * env * x

    if name == "chalk":
        scale = [261.63, 293.66, 329.63, 392.0, 440.0]
        for beat in range(int(seconds * 2)):
            if rng.random() < 0.55:
                f = scale[int(rng.integers(len(scale)))]
                tone(f, beat * 0.5, 0.9, 0.16)
        tone(130.8, 0, 1.8, 0.10, "tri")
    elif name == "drive":
        chords = [[196.0, 246.94, 293.66], [174.61, 220.0, 261.63],
                  [196.0, 246.94, 293.66], [146.83, 196.0, 246.94]]
        bar = 2.0
        for b in range(int(np.ceil(seconds / bar))):
            ch = chords[b % 4]
            for f in ch:
                tone(f, b * bar, bar * 0.95, 0.06, "tri")
            tone(58.0, b * bar, 0.4, 0.14)
            tone(58.0, b * bar + 1.0, 0.4, 0.12)
            for k in range(8):
                tone(ch[k % 3] * 2, b * bar + k * 0.25, 0.1, 0.035)
    else:  # lofi
        for b in range(int(np.ceil(seconds / 2.4))):
            for f, at in [(110.0, 0.0), (164.81, 0.6), (196.0, 1.2)]:
                tone(f, b * 2.4 + at, 1.4, 0.075, "tri")
                tone(f * 1.005, b * 2.4 + at, 1.4, 0.05, "tri")  # detune wash
            tone(220.0, b * 2.4 + 0.3, 0.2, 0.05)
            tone(246.94, b * 2.4 + 1.5, 0.2, 0.05)
    noise = rng.standard_normal(n) * 0.004
    left = out + noise
    right = out + rng.standard_normal(n) * 0.004
    stereo = np.stack([left, right], axis=1)
    fade = min(brand.BED_FADE_OUT_S, seconds / 3)
    k = int(fade * SR)
    if k > 0:
        stereo[-k:] *= np.linspace(1, 0, k)[:, None]
    peak = np.max(np.abs(stereo)) or 1.0
    return stereo / peak * 0.9


def mix(voice_mono: np.ndarray, bed_stereo: np.ndarray, mix_gain: float,
        total_sec: float) -> np.ndarray:
    """Voice at full, bed at brand.BED_MIX, hard-clipped to total length.
    Returns int16 stereo."""
    n = int(total_sec * SR)
    v = np.zeros(n)
    v[:min(n, len(voice_mono))] = voice_mono[:n]
    b = np.zeros((n, 2))
    b[:min(n, len(bed_stereo))] = bed_stereo[:n]
    out = np.stack([v, v], axis=1) * 0.85 + b * mix_gain
    out = np.clip(out, -1, 1)
    return (out * 32767).astype(np.int16)

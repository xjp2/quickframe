"""Encode pipeline — the rebuilt tools_build/driver.py.

Signatures preserved from the original anchors (AGENTS.md §2 T1):
  frame_at(m)                      -> one output frame (:42)
  render(name, segs, audio, gain, fade_out, workers) -> frames -> mp4 (:153)
  audit(segs, canvas, label)       -> the safe-area gate (:195)

Real render only: rawvideo RGB24 piped into libx264 + AAC. No mock, no stub
output. Frame scratch is per-run under .render_work/ and dirs are created by
audit()/render() themselves (spec trap §5.7: never delete a live frame dir;
makedirs exist_ok).
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import subprocess

import numpy as np
from PIL import Image

from . import art, brand, env

FPS = 30
DRAW_RAMP_S = 0.7  # fraction of scene spent "drawing", then hold


# ------------------------------------------------------------------ frame_at
def _caption_state(scene: dict, local_t: float):
    """Which caption chunk is on screen at local_t, and the karaoke word index
    within it. Cues are {text, at} in seconds over the GLOBAL timeline."""
    cues = scene["cues"]
    idx = -1
    for j, c in enumerate(cues):
        if local_t + scene["start"] >= c["at"] - 1e-6:
            idx = j
    if idx < 0:
        return "", [], -1
    chunk = cues[idx]["text"]
    words = chunk.split()
    # highlight window: words spoken so far within this chunk
    nxt = cues[idx + 1]["at"] if idx + 1 < len(cues) else scene["end"]
    span = max(0.01, nxt - cues[idx]["at"])
    done = (local_t + scene["start"] - cues[idx]["at"]) / span
    hi = min(len(words) - 1, int(done * len(words)))
    return chunk, words, hi


def frame_at(m: dict) -> bytes:
    """m: {job, scene, local_t, W, H, opts}. Returns RGB24 bytes for one frame."""
    job, scene, local_t = m["job"], m["scene"], m["local_t"]
    W, H, opts = m["W"], m["H"], m["opts"]
    dur = scene["end"] - scene["start"]
    # quantized draw-progress: at most 12 distinct boards per scene are cached
    nsteps = min(12, max(1, int(round(dur / DRAW_RAMP_S)))) if DRAW_RAMP_S else 1
    step = dur / nsteps
    k = min(nsteps, int(local_t / step + 1e-9))
    t = min(1.0, k * step / DRAW_RAMP_S) if DRAW_RAMP_S else 1.0
    cache = m.setdefault("_cache", {})
    key = (scene["i"], round(t, 4))
    if key not in cache:
        img, _boxes = art.draw_board(job, scene, W, H, t=t, caption_mode="none")
        cache[key] = img
    img = cache[key]
    chunk, words, hi = _caption_state(scene, local_t)
    if chunk and job["captions"] != "none":
        # composite caption directly into the raw frame (fast, deterministic)
        from PIL import ImageDraw
        buf = img.copy()
        d = ImageDraw.Draw(buf)
        lay = art.layout(W, H)
        cx0, cy0, cx1, cy1 = art._rect(lay, "caption")
        style = job["captions"]
        if style == "clean":
            art.fit_text(d, chunk, (cx0, cy0, cx1, cy0 + int((cy1 - cy0) * 0.42)),
                         "mono", int(lay["unit"] * 0.036), art.INK)
        else:
            px = int(lay["unit"] * 0.062)
            lines = art.wrap(d, chunk, "display", px, cx1 - cx0)
            while len(lines) > 3 and px > 20:
                px = int(px * 0.9)
                lines = art.wrap(d, chunk, "display", px, cx1 - cx0)
            f = art._font("display", px)
            lh = int(px * 1.25)
            oy = cy0 + ((cy1 - cy0) - lh * len(lines)) // 2
            for ln in lines:
                if style == "karaoke":
                    art._karaoke(d, ln, cx0, oy, f, words, hi)
                else:
                    d.text((cx0, oy), ln, font=f, fill=art.INK)
                oy += lh
            if style == "blocks":
                accent = art.ACCENTS[(art.board_seed(job["id"], job["topic"])
                                      + scene["i"]) % len(art.ACCENTS)]
                d.rectangle([cx0, cy1 - 6, cx1, cy1], fill=accent)
        return buf.tobytes()
    return img.tobytes()


# ------------------------------------------------------------------ workers
def _worker(payload: dict) -> str:
    """Render a frame range for one scene; writes RGB24 bytes to a scratch
    chunk file and returns its path (keeps pool IPC memory bounded)."""
    job = payload["job"]
    scene = payload["scene"]
    W, H, fps = payload["W"], payload["H"], payload["fps"]
    opts = payload["opts"]
    n0, n1 = payload["range"]
    cache = {}
    path = os.path.join(payload["run"], f"chunk-{scene['i']}-{n0}.rgb")
    with open(path, "wb") as f:
        for k in range(n0, n1):
            local_t = k / fps
            m = {"job": job, "scene": scene, "local_t": local_t,
                 "W": W, "H": H, "opts": opts, "_cache": cache}
            f.write(frame_at(m))
    return path


def _scene_ranges(segs: list[dict], fps: int) -> list[tuple[dict, int, int]]:
    ranges = []
    for sc in segs:
        n = max(1, int(round((sc["end"] - sc["start"]) * fps)))
        ranges.append((sc, 0, n))
    return ranges


# ------------------------------------------------------------------ audit
def audit(segs: list[dict], canvas: tuple[int, int], label: str = "") -> list[dict]:
    """Safe-area gate (driver.py:195 in the original). Checks every text bbox
    the encoder can place — title, beat label, onText, and every caption chunk
    at full draw — against the broadcast safe area. Returns violations."""
    W, H = canvas
    lay = art.layout(W, H)
    fx, fy = brand.SAFE_AREA, brand.SAFE_AREA
    lim = (W * (1 - fx) / 2, H * (1 - fy) / 2,
           W - W * (1 - fx) / 2, H - H * (1 - fy) / 2)
    violations = []
    for sc in segs:
        job_stub = sc["_job"]
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (W, H), art.PAPER)
        d = ImageDraw.Draw(img)
        boxes = []
        for key in ("title", "beat", "onText"):
            txt = {"title": job_stub["title"].upper(),
                   "beat": f"{sc['beat'].upper()}  ·  SCENE {sc['i'] + 1}",
                   "onText": sc["onText"]}[key]
            kind = {"title": "display", "beat": "mono", "onText": "hand"}[key]
            px = {"title": 0.055, "beat": 0.030, "onText": 0.052}[key]
            b, _ = art.fit_text(d, txt, art._rect(lay, key), kind,
                                int(lay["unit"] * px), art.INK)
            boxes.append((key, b))
        if job_stub["captions"] != "none":
            for c in sc["cues"]:
                cx0, cy0, cx1, cy1 = art._rect(lay, "caption")
                b, _ = art.fit_text(d, c["text"], (cx0, cy0, cx1, cy1),
                                    "display", int(lay["unit"] * 0.045), art.INK)
                boxes.append(("caption", b))
        for what, b in boxes:
            if b[0] < lim[0] - 1 or b[1] < lim[1] - 1 or b[2] > lim[2] + 1 or b[3] > lim[3] + 1:
                violations.append({"scene": sc["i"], "kind": what, "bbox": list(b),
                                   "limit": list(lim), "label": label})
    return violations


# ------------------------------------------------------------------ render
def render(name: str, segs: list[dict], audio: str, gain: float = 1.0,
           fade_out: float = 0.0, workers: int | None = None,
           opts: dict | None = None) -> str:
    """frames -> mp4 (driver.py:153). Writes <name>.mp4 under .render_work/<run>/.
    segs: list of scene dicts, each carrying `_job` (the full job JSON).
    audio: wav path (int16 stereo). Returns the mp4 path."""
    opts = opts or {}
    job0 = segs[0]["_job"]
    W, H = brand.ASPECTS[job0["aspect"]]
    total = segs[-1]["end"]
    run = os.path.join(env.work_dir(), f"{name}-{os.getpid()}")
    os.makedirs(run, exist_ok=True)  # trap §5.7: create, never assume
    out = os.path.join(run, f"{name}.mp4")
    workers = workers or min(2, env.cpu_count())

    # audio filter (gain + fade), real PCM through ffmpeg
    afilter = f"volume={gain}"
    if fade_out > 0:
        afilter += f",afade=t=out:st={max(0.0, total - fade_out):.3f}:d={fade_out}"
    cmd = [env.ffmpeg_bin(), "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-i", audio, "-map", "0:v", "-map", "1:a",
           "-af", afilter, "-acodec", "aac", "-b:a", "160k",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        with mp.Pool(processes=max(1, workers)) as pool:
            tasks = []
            for sc, n0, n1 in _scene_ranges(segs, FPS):
                if workers <= 1:
                    step = max(1, (n1 - n0))
                else:
                    step = max(30, (n1 - n0) // (workers * 3))
                for a in range(n0, n1, step):
                    tasks.append({"job": job0, "scene": sc, "W": W, "H": H,
                                  "fps": FPS, "opts": opts, "run": run,
                                  "range": (a, min(n1, a + step))})
            for path in pool.imap(_worker, tasks):
                with open(path, "rb") as cf:
                    shutil.copyfileobj(cf, proc.stdin, length=1 << 20)
                os.remove(path)  # chunk consumed; scratch stays bounded
        proc.stdin.close()
        proc.wait()
    except Exception:
        proc.kill()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {proc.returncode} rendering {name}")
    return out


def write_wav(path: str, pcm: np.ndarray):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(pcm.tobytes())

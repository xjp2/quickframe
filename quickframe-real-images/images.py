"""T3 REAL image stage — one AI-generated illustration per scene.

Service: Pollinations.ai (https://image.pollinations.ai/prompt/...), model=flux.
Chosen because it is the only keyless free endpoint reachable from this render
path (probed 2026-11-21: flux 200/image-jpeg in ~6s; turbo 402; HF
api-inference DNS does not resolve and the free tier needs a token anyway).
Honesty note: the anonymous flux endpoint is actually served by the "sana"
model (x-model-used response header) — free, keyless, real text-to-image.
No API key, no paid service, stdlib urllib only — no new dependency.

Contract kept:
  - The 7 stage keys are untouched. Images are fetched in the `boards` stage
    (per-scene stills) and composited by art.draw_board in place of the
    stickman+glyph stage drawing. All readable text is STILL typeset by the
    encoder (spec trap §5: text never comes from the image model — every
    prompt ends with explicit no-text negatives).
  - One DISTINCT image per scene: per-scene seed + per-scene motif/composition.
    Consistency comes from one shared style suffix (cool indigo/blue/cyan/teal
    palette on off-white paper, matching the live T3 palette in art.ACCENTS).
  - Cache per job: .render_work/images-<jobid>/scene-<i>.jpg. A re-run of the
    same job never re-fetches. Files are validated with PIL before reuse.
  - Honest failure: after retries, raise ImageStageError -> runner surfaces a
    503 BLOCKED job. NEVER a silent fallback to stickman (owner rule). Set
    QF_IMAGE_MODE=off to explicitly render the vector boards instead.

Memory (Render free tier, 512MB): fetch <=1024px, store JPEG, load lazily per
process with an lru_cache (3-5 scenes x ~1.8MB RGB = bounded).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import urllib.parse
import urllib.request
from functools import lru_cache

from PIL import Image

from . import env

ENDPOINT = "https://image.pollinations.ai/prompt/"
MODEL = os.environ.get("QF_IMAGE_MODEL", "flux")
FETCH_TIMEOUT_S = int(os.environ.get("QF_IMAGE_TIMEOUT", "180"))
# Anonymous tier: bursts return 402 (queue/rate limit) while cached results
# serve instantly. Measured 2026-11-21: a fresh generation succeeds after
# ~30-60s of spacing. Retry patiently; pace scenes apart.
RETRIES = 5
BACKOFF_S = (10, 20, 30, 45)
SCENE_PACING_S = 6
MAX_EDGE = 1024  # downscale ceiling before caching (memory + encode speed)

# Shared style suffix — identical for every scene of every job: this is what
# keeps the series on-style (cool/neutral, cinematic, clean, text-free).
# "not photorealistic" is load-bearing: the free sana model drifts to photo
# landscapes without an explicit illustration lock (measured 2026-11-21).
STYLE = (
    "stylized digital illustration, clean editorial picture-book style, smooth "
    "matte painted shapes, soft diffuse lighting, cool palette of indigo, blue, "
    "cyan and teal on an off-white paper background, subtle depth, high quality, "
    "uncluttered composition, not photorealistic, no photograph, "
    "no text, no words, no letters, no numbers, no watermark, no logo"
)
# The anonymous tier ignores nologo=true and stamps a small "pollinations.ai"
# badge in the bottom-right corner. Crop the bottom band before caching so no
# third-party mark ever reaches a frame (the encoder typesets all real text).
LOGO_CROP_FRAC = 0.10

# glyph key -> concrete visual motif (art.py vocabulary stays the source of
# art-direction; the image stage renders the same idea as an illustration)
MOTIFS = {
    "coins": "a small stack of shining coins",
    "clock": "a round clock with clear hands",
    "path": "a winding path leading toward the horizon",
    "gear": "two interlocking gears",
    "bulb": "a glowing light bulb",
    "cross": "a bold crossed-out mark over a faded shape",
    "check": "a bold confident check mark",
    "people": "two simple friendly human figures",
    "magnifier": "a magnifying glass hovering over small details",
    "bars": "a rising bar chart with three bars",
    "speech": "a single empty speech bubble",
    "target": "an archery target with an arrow in the center",
    "flow": "three flowing arrows moving through a pipeline",
    "alert": "a warning triangle beside a small cliff edge",
    "cloud": "a soft low cloud over a quiet landscape",
    "arrow": "a single forward-pointing arrow on a path",
}

# beat -> composition hint so consecutive scenes frame differently
COMPOSITIONS = {
    "hook": "wide establishing shot, one striking focal point",
    "question": "curious close-up framing, shallow depth",
    "build": "one single object centered, lots of negative space",
    "turn": "dynamic diagonal composition showing accumulation",
    "land": "calm resolved wide shot, balanced symmetry",
    "myth": "split composition, one side faded and one side crisp",
    "origin": "quiet documentary framing, muted background",
    "evidence": "macro detail shot, one concrete object",
    "reality": "layered cutaway view revealing inner structure",
    "takeaway": "warm-free calm closing shot, open sky",
    "promise": "inviting forward-leaning composition",
    "step1": "minimal single-step vignette",
    "step2": "two objects joined, connection in focus",
    "step3": "rhythmic repetition of small marks",
    "trap": "tense composition, one small figure near an edge",
    "problem": "broken pieces scattered, dramatic light",
    "climb": "upward sweeping composition, growing scale",
    "outcome": "monumental wide shot, settled and still",
    "door": "view through an open doorway",
    "surface": "clean front-desk scene, one queue",
    "hidden": "behind-the-scenes cutaway, quiet machinery",
    "engine": "precise mechanical close-up, clockwork feel",
    "signal": "wide calm shot with one small signal light",
    "mechanism": "interlocking parts in motion, diagram-like clarity",
    "math": "an elegant bending curve rising over time",
    "obstacle": "a flat plateau before a steep rise",
    "action": "a hand setting a simple switch, decisive",
}


class ImageStageError(RuntimeError):
    """The free image service could not deliver a scene illustration. Carries
    a stable code so the runner surfaces BLOCKED instead of faking visuals."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def mode() -> str:
    return (os.environ.get("QF_IMAGE_MODE") or "pollinations").strip().lower()


def enabled() -> bool:
    return mode() not in ("off", "none", "vector", "stickman")


def job_dir(job_id: str) -> str:
    p = os.path.join(env.work_dir(), f"images-{job_id}")
    os.makedirs(p, exist_ok=True)
    return p


def scene_path(job_id: str, i: int) -> str:
    return os.path.join(job_dir(job_id), f"scene-{i}.jpg")


def seed_for(topic: str, template: str, beat: str, i: int) -> int:
    h = hashlib.sha256(f"{topic}|{template}|{beat}|{i}".encode()).hexdigest()
    return int(h[:12], 16) % 1_000_000_000


def scene_prompt(job: dict, scene: dict) -> str:
    subject = job.get("subject") or job.get("topic") or "the idea"
    motif = MOTIFS.get(scene.get("art"), "one simple symbolic object")
    comp = COMPOSITIONS.get(scene.get("beat"), "clean centered composition")
    return (f"{subject}, {comp}, with a subtle symbolic hint of {motif}. {STYLE}")


def _fetch_size(aspect: str) -> tuple[int, int]:
    if aspect == "9:16":
        return 576, 1024
    if aspect == "1:1":
        return 768, 768
    return 1024, 576


def _valid_image(path: str) -> bool:
    try:
        with Image.open(path) as im:
            im.verify()
        return os.path.getsize(path) > 4096  # reject error-page crumbs
    except Exception:
        return False


def _fetch_one(prompt: str, seed: int, w: int, h: int, dest: str) -> float:
    url = (ENDPOINT + urllib.parse.quote(prompt)
           + f"?width={w}&height={h}&seed={seed}&nologo=true&model={MODEL}")
    t0 = time.time()
    last = ""
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quickframe-t1/1.0"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as r:
                ctype = r.headers.get("Content-Type", "")
                used = r.headers.get("x-model-used") or MODEL
                data = r.read()
            if not ctype.startswith("image/"):
                raise ImageStageError("image_bad_response",
                                      f"content-type {ctype!r} (not an image)")
            im = Image.open(io.BytesIO(data))
            im.load()
            im = im.convert("RGB")
            # strip the free-tier logo band (bottom-right badge)
            im = im.crop((0, 0, im.width, int(im.height * (1 - LOGO_CROP_FRAC))))
            if max(im.size) > MAX_EDGE:
                sc = MAX_EDGE / max(im.size)
                im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))),
                               Image.LANCZOS)
            im.save(dest, "JPEG", quality=88)
            if not _valid_image(dest):
                raise ImageStageError("image_corrupt", "cached file failed PIL verify")
            return round(time.time() - t0, 2), used
        except ImageStageError:
            raise
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_S[attempt])
    raise ImageStageError("image_service_unavailable",
                          f"Pollinations {MODEL} failed after {RETRIES} attempts: {last}")


def _meta_path(job_id: str, i: int) -> str:
    return os.path.join(job_dir(job_id), f"scene-{i}.meta.json")


def _cache_fresh(job_id: str, i: int, prompt: str, seed: int) -> bool:
    """Cache hit only when the file is a valid image AND was generated from
    the exact current prompt+seed (style/prompt edits must not serve stale art)."""
    p, mp = scene_path(job_id, i), _meta_path(job_id, i)
    if not (os.path.isfile(p) and _valid_image(p) and os.path.isfile(mp)):
        return False
    try:
        with open(mp, encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("prompt") == prompt and meta.get("seed") == seed
    except Exception:
        return False


def fetch_all(job: dict) -> list[dict]:
    """Fetch (or reuse cached) illustrations for every scene. Returns a
    manifest: [{i, path, seed, cached, sec, bytes}]. Raises ImageStageError."""
    w, h = _fetch_size(job.get("aspect", "16:9"))
    out = []
    for sc in job["scenes"]:
        p = scene_path(job["id"], sc["i"])
        seed = seed_for(job["topic"], job.get("template", "why"), sc["beat"], sc["i"])
        prompt = scene_prompt(job, sc)
        if _cache_fresh(job["id"], sc["i"], prompt, seed):
            with open(_meta_path(job["id"], sc["i"]), encoding="utf-8") as f:
                used = json.load(f).get("model", MODEL)
            out.append({"i": sc["i"], "path": p, "seed": seed, "cached": True,
                        "sec": 0.0, "bytes": os.path.getsize(p), "model": used})
            continue
        dt, used = _fetch_one(prompt, seed, w, h, p)
        with open(_meta_path(job["id"], sc["i"]), "w", encoding="utf-8") as f:
            json.dump({"prompt": prompt, "seed": seed, "model": used}, f)
        out.append({"i": sc["i"], "path": p, "seed": seed, "cached": False,
                    "sec": dt, "bytes": os.path.getsize(p), "model": used})
        time.sleep(SCENE_PACING_S)  # stay under the anonymous burst limit
    # distinctness guarantee: no two scenes may share identical image bytes
    hashes = []
    for m in out:
        with open(m["path"], "rb") as f:
            hashes.append(hashlib.sha256(f.read()).hexdigest())
    if len(set(hashes)) != len(hashes):
        raise ImageStageError("image_repeat", "two scenes received identical images")
    return out


@lru_cache(maxsize=8)
def _load(path: str, _mtime: float) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGB")


def load_photo(job_id: str, i: int) -> Image.Image | None:
    """The compositing seam for art.draw_board. None when the stage is off or
    the file is absent (boards stage guarantees presence before encode)."""
    if not enabled():
        return None
    p = scene_path(job_id, i)
    if not os.path.isfile(p):
        return None
    return _load(p, os.path.getmtime(p))


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Aspect-fill crop to exactly w x h (no distortion, no letterbox)."""
    src_ratio, dst_ratio = img.width / img.height, w / h
    if src_ratio > dst_ratio:
        nw = int(img.height * dst_ratio)
        x0 = (img.width - nw) // 2
        img = img.crop((x0, 0, x0 + nw, img.height))
    else:
        nh = int(img.width / dst_ratio)
        y0 = (img.height - nh) // 2
        img = img.crop((0, y0, img.width, y0 + nh))
    return img.resize((w, h), Image.LANCZOS)
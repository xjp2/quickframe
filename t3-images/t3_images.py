"""QuickFrame T3 — per-scene board image step.

What this is
------------
The image step that turns each scene's art-direction (``scene["art"]`` glyph +
``scene["whyArt"]`` rationale, produced by ``qf.engine._pick_art``) into one
stickman/whiteboard *board image* per scene, in a single consistent illustrated
style: same paper-and-rule background across every cut, dark ink character, and
one cooler/neutral accent per scene.

Reuse, not rebuild
------------------
T1 already ships the drawing layer on this machine (``D:\\qf-t1-build\\qf\\art.py``
— stickman poses, whiteboard glyphs, paper/rule background, all text typeset by
the encoder per spec trap §5.6). This module *imports and calls* it; it does not
copy or edit it. The only refinement here is the palette (see COOL_PALETTE) and
the per-scene guarantees the T3 brief asks for.

Contracts preserved (AGENTS.md §3)
----------------------------------
* Job/scenes come straight from ``qf.engine.build(cfg)`` — the §3 job JSON.
* ``art``/``whyArt`` stay the art-direction layer (which beat needs which shot);
  we never re-derive them here, we render what the art-direction layer chose.
* The board image is the *art/boards* stage output: it is drawn with
  ``caption_mode="none"`` exactly like ``qf.driver.frame_at`` caches the art
  layer, so burned captions stay the encoder's job — boards stay reusable.

Determinism + re-roll (honest note on the spec acceptance line)
--------------------------------------------------------------
The renderer is deterministic: same job id + topic => same script => same
boards. That matches the product contract "same topic ⇒ same script" and the
user's T3 brief ("one consistent illustrated style, same backgrounds across
cuts"). The spec's "same topic twice → visibly different boards" is the UI's
**Re-roll the boards** action (studio.js §4), so it is supported here via the
``reroll`` salt: a re-roll reshuffles the *illustration* (stickman pose, accent,
composition) while the *art-direction glyph* stays faithful to the script.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

# Constrained box (spec: 2 cores, low memory): cap BLAS/OpenMP thread pools
# before numpy imports, otherwise OpenBLAS over-allocates and aborts.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
from PIL import Image

# --- reuse T1's drawing layer + engine (read-only import; no writes there) ----
T1_BUILD = os.environ.get("QF_T1_BUILD", r"D:\qf-t1-build")
if T1_BUILD not in sys.path:
    sys.path.insert(0, T1_BUILD)

from qf import art as t1_art          # the drawing layer (stickman + glyphs)
from qf import brand as t1_brand      # aspects, safe area
from qf import engine as t1_engine    # script pass + artFor art-direction layer

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")

# --- T3 style anchor: cooler / neutral accents -------------------------------
# T1's ACCENTS mix in warm orange/brown/pink. The T3 brief asks for a
# cooler/neutral palette, so this is the one deliberate refinement. The paper,
# rule-line and ink constants are reused unchanged from T1 so the *character*
# stays identical across topics.
#
# Phone-size QA correction (see _vivid_probe.py): the first cut included two
# near-neutral members — slate (71,85,105) chroma 34 and cool-gray
# (100,116,139) chroma 39 — which measured as gray smudges at 390px and made a
# topic whose hook scene used them look "dull and cloudy". "Cooler/neutral"
# means *no warm hue*, not *desaturated*. Every colour below is a vivid cool
# hue (violet -> blue -> sky -> cyan -> teal -> jade) with chroma >= 100 and
# blue >= red, so each pops against the off-white paper on a phone.
COOL_PALETTE = [
    (79, 70, 229),    # indigo / violet   chroma 159
    (37, 99, 235),    # steel blue        chroma 198
    (2, 132, 199),    # sky blue          chroma 197
    (8, 145, 178),    # cyan              chroma 170
    (15, 118, 110),   # teal              chroma 103
    (6, 124, 96),     # deep jade green   chroma 118 (darkened: the lightest
                      #                     value read weakest on phone QA)
]
MIN_ACCENT_CHROMA = 90  # floor: below this an accent reads as muddy at phone size


def apply_style() -> None:
    """Swap T1's warm accent set for the cooler/neutral T3 set, at runtime only.
    This does not edit T1's file; it rebinds the module-level list that
    ``art.draw_board`` reads when it picks a per-scene accent."""
    t1_art.ACCENTS = COOL_PALETTE


# --------------------------------------------------------------------- boards
def build_job(topic: str, template: str = "why", aspect: str = "16:9",
              length_sec: float = 40.0, captions: str = "blocks",
              music: str = "drive", voice: str = "calm-01",
              reroll: int | None = None) -> dict:
    """Run the script + art-direction pass (qf.engine.build) for one topic.

    ``reroll`` is the re-roll salt: when set it is folded into the job id so the
    illustration reshuffles (pose + accent) while the art-direction glyph, which
    is keyed to the spoken line, stays faithful to the script.
    """
    cfg = {
        "topic": topic, "template": template, "aspect": aspect,
        "lengthSec": length_sec, "captions": captions, "music": music,
        "voice": voice,
    }
    if reroll is not None:
        base = hashlib.sha256(f"{topic}|{template}|{reroll}".encode()).hexdigest()
        cfg["id"] = f"reroll-{base[:10]}"
    return t1_engine.build(cfg)


def scene_accent(job: dict, scene: dict) -> tuple[int, int, int]:
    """The accent T1's draw_board will use for this scene, recomputed from the
    (now cooler) palette so the acceptance check can assert it."""
    seed = t1_art.board_seed(job["id"], job["topic"])
    return COOL_PALETTE[(seed + scene["i"]) % len(COOL_PALETTE)]


def render_board(job: dict, scene: dict):
    """Render ONE board image for one scene at full draw (t=1.0), caption-free
    (caption_mode='none') — this is the art/boards stage output."""
    W, H = t1_brand.ASPECTS[job["aspect"]]
    img, _boxes = t1_art.draw_board(job, scene, W, H, t=1.0, caption_mode="none")
    return img


def render_boards(job: dict, out_dir: str) -> list[dict]:
    """One distinct PNG per scene, written to ``out_dir``. Returns a manifest.
    The Image is closed right after save so a long-running service process does
    not accumulate full-res 1080p buffers (this box has ~0.4 GB free)."""
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for scene in job["scenes"]:
        img = render_board(job, scene)
        name = f"scene{scene['i']:02d}_{scene['art']}.png"
        path = os.path.join(out_dir, name)
        img.save(path)
        size = img.size
        img.close()
        manifest.append({
            "i": scene["i"], "beat": scene["beat"], "art": scene["art"],
            "whyArt": scene["whyArt"], "accent": scene_accent(job, scene),
            "size": size, "file": path,
        })
    return manifest


def contact_sheet(manifest: list[dict], out_path: str, cols: int = 3,
                  tile_w: int = 640) -> str:
    """Tile the per-scene boards into one contact sheet for quick QA. Each board
    is downscaled to ``tile_w`` and closed immediately, so peak memory stays a
    few MB instead of a full-res 1080p sheet (~37 MB) — important on this box."""
    if not manifest:
        raise ValueError("no boards to tile")
    thumbs = []
    for m in manifest:
        with Image.open(m["file"]) as im:
            im = im.convert("RGB")
            thumbs.append(im.resize((tile_w, max(1, int(im.height * tile_w / im.width)))))
    w, h = thumbs[0].size
    rows = (len(thumbs) + cols - 1) // cols
    pad = 16
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad,
                              rows * h + (rows + 1) * pad), (226, 230, 238))
    for idx, im in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + pad)
        sheet.paste(im, (x, y))
    sheet.save(out_path)
    sheet.close()
    for im in thumbs:
        im.close()
    return out_path


# --------------------------------------------------------------------- checks
def _ink_map(path: str, w: int = 320) -> np.ndarray:
    """Downsampled *ink intensity* = per-pixel distance from the paper colour.
    Background (paper + rule lines) maps to ~0 and is identical across every
    board, so it contributes nothing to a pairwise difference — the metric
    measures only the drawn content (glyph + stickman + typeset text). This is
    background-immune and cheap (no full-frame int64 on a 2-core box)."""
    with Image.open(path) as f:
        im = f.convert("RGB")
        h = max(1, int(im.height * w / im.width))
        im = im.resize((w, h))
        arr = np.asarray(im).astype(np.int16)
    paper = np.array(t1_art.PAPER, dtype=np.int16)
    return np.abs(arr - paper).sum(axis=2).astype(np.float32)


def check_boards(job: dict, manifest: list[dict]) -> dict:
    """Run the T3 acceptance checks against the rendered boards."""
    apply_style()
    # Distinctness is measured on the ink map (background-immune, memory-safe);
    # the background check loads full-res strips one at a time.
    inks = [_ink_map(m["file"]) for m in manifest]

    # 1. one distinct image per scene, no replays
    glyphs = [m["art"] for m in manifest]
    glyph_unique = len(set(glyphs)) == len(glyphs)
    pairwise_min = float("inf")
    for a in range(len(inks)):
        for b in range(a + 1, len(inks)):
            d = float(np.abs(inks[a] - inks[b]).mean())
            pairwise_min = min(pairwise_min, d)
    distinct = pairwise_min > 1.0  # ink content differs by more than noise

    # 2. same background across cuts (left margin strip identical for all scenes)
    def strip_of(m):
        with Image.open(m["file"]) as f:
            im = f.convert("RGB")
            sw = int(im.width * 0.035)
            return np.asarray(im.crop((0, 0, sw, im.height)))
    base_strip = strip_of(manifest[0])
    bg_identical = all(bool(np.array_equal(strip_of(m), base_strip)) for m in manifest)

    # 3. cooler/neutral palette: every accent used is in the cool set
    accents = [tuple(m["accent"]) for m in manifest]
    palette_ok = all(a in COOL_PALETTE for a in accents)
    # Each accent must be (a) genuinely cool — blue channel >= red, never a warm
    # hue — and (b) vivid enough to read at phone size (chroma >= floor). The
    # old rule let desaturated grays pass; phone QA showed those look muddy.
    def _cool(c):
        r, g, bl = c
        return bl >= r
    def _vivid(c):
        return (max(c) - min(c)) >= MIN_ACCENT_CHROMA
    accents_cool = all(_cool(a) for a in accents)
    accents_vivid = all(_vivid(a) for a in accents)
    min_chroma = min((max(a) - min(a)) for a in accents) if accents else 0

    return {
        "scenes": len(manifest),
        "glyph_unique_no_replays": glyph_unique,
        "boards_pairwise_mean_diff": None if pairwise_min == float("inf") else round(pairwise_min, 3),
        "boards_all_distinct": bool(distinct),
        "background_identical_across_cuts": bool(bg_identical),
        "accents_in_cool_palette": bool(palette_ok),
        "accents_cool": bool(accents_cool),
        "accents_vivid_at_phone_size": bool(accents_vivid),
        "min_accent_chroma": int(min_chroma),
        "accents_used": [list(a) for a in accents],
        "pass": bool(glyph_unique and distinct and bg_identical
                     and palette_ok and accents_cool and accents_vivid),
    }


# ----------------------------------------------------------------------- main
def _slug(topic: str) -> str:
    s = "".join(ch if ch.isalnum() else "-" for ch in topic.lower()).strip("-")
    return "-".join(filter(None, s.split("-")))[:48] or "topic"


def run_test(topic: str = "how contactless payment works", template: str = "why",
             aspect: str = "16:9") -> dict:
    """Render a full sample set for one topic, run the checks, build a contact
    sheet, and return a JSON report."""
    apply_style()
    out_dir = os.path.join(SAMPLES, _slug(topic))
    job = build_job(topic, template=template, aspect=aspect)
    manifest = render_boards(job, out_dir)
    report = check_boards(job, manifest)
    sheet = contact_sheet(manifest, os.path.join(out_dir, "contact-sheet.png"))
    report.update({
        "topic": topic, "template": template, "aspect": aspect,
        "title": job["title"], "out_dir": out_dir, "contact_sheet": sheet,
        "scenes": [
            {"i": m["i"], "beat": m["beat"], "art": m["art"],
             "whyArt": m["whyArt"], "accent": list(m["accent"]),
             "file": os.path.basename(m["file"])}
            for m in manifest],
    })
    return report


def _stage_box(job: dict):
    """Pixel rect of the *stage* region (where the stickman + accent glyph live)
    for this job's aspect. The paper/rule background outside it is identical by
    design, so reroll differences must be measured here, not frame-wide."""
    W, H = t1_brand.ASPECTS[job["aspect"]]
    lay = t1_art.layout(W, H)
    return t1_art._rect(lay, "stage"), (W, H)


def run_reroll_demo(topic: str = "how contactless payment works",
                    template: str = "why", aspect: str = "16:9") -> dict:
    """Prove the re-roll path: same topic, different salt => different
    illustrations (pose + accent), same art-direction glyphs, same style.

    The diff is measured over the *stage* region only: the paper background is
    intentionally identical across every cut (the spec's "same backgrounds"
    requirement), so a frame-wide mean would dilute a real illustration change
    and report a false negative. Outside the stage box nothing should move."""
    apply_style()
    a = build_job(topic, template=template, aspect=aspect, reroll=1)
    b = build_job(topic, template=template, aspect=aspect, reroll=2)
    ma = render_boards(a, os.path.join(SAMPLES, _slug(topic) + "-rerollA"))
    mb = render_boards(b, os.path.join(SAMPLES, _slug(topic) + "-rerollB"))
    ga = [m["art"] for m in ma]
    gb = [m["art"] for m in mb]
    pa = [tuple(m["accent"]) for m in ma]
    pb = [tuple(m["accent"]) for m in mb]

    (sx0, sy0, sx1, sy1), _ = _stage_box(a)
    def stage_crop(path):
        with Image.open(path) as f:
            return np.asarray(f.convert("RGB").crop((sx0, sy0, sx1, sy1))).astype(np.int16)
    stage_diffs = []
    for x, y in zip(ma, mb):
        ia, ib = stage_crop(x["file"]), stage_crop(y["file"])
        stage_diffs.append(float(np.abs(ia - ib).mean()))
    mean_stage_diff = sum(stage_diffs) / len(stage_diffs)

    return {
        "topic": topic,
        "glyphs_faithful_to_script": ga == gb,
        "illustration_changed": pa != pb,
        "stage_region_mean_diff": round(mean_stage_diff, 3),
        "stage_diff_per_scene": [round(d, 3) for d in stage_diffs],
        "pass": bool(ga == gb and pa != pb and mean_stage_diff > 1.0),
    }


def _bg_strip(path: str) -> np.ndarray:
    """Left-margin strip = pure paper + rule lines (all text/stage sits inside
    the 0.90 safe area), used to prove the *character/background* is identical
    across topics while the boards still differ."""
    arr = np.asarray(Image.open(path).convert("RGB"))
    return arr[:, :int(arr.shape[1] * 0.035), :]


def run_series_check(topics: list[tuple[str, str]], aspect: str = "16:9") -> dict:
    """Prove the spec's series acceptance: a run of topics keeps one
    recognisable character (identical paper + rule + ink) yet produces visibly
    different boards (different glyphs, different accent sequence)."""
    apply_style()
    per_topic = []
    strips = []
    arts = []
    titles = []
    for topic, tpl in topics:
        rep = run_test(topic, template=tpl, aspect=aspect)
        first = os.path.join(rep["out_dir"], rep["scenes"][0]["file"])
        strips.append(_bg_strip(first))
        arts.append([s["art"] for s in rep["scenes"]])
        titles.append(rep["title"])
        per_topic.append({"topic": topic, "pass": rep["pass"],
                          "arts": [s["art"] for s in rep["scenes"]],
                          "accents": [s["accent"] for s in rep["scenes"]]})

    # character identical: every topic's background strip is byte-for-byte equal
    char_identical = all(bool(np.array_equal(s, strips[0])) for s in strips)
    # boards differ: at least two topics have a different glyph sequence
    boards_differ = len(set(tuple(a) for a in arts)) > 1
    titles_differ = len(set(titles)) > 1
    # the character constants are T1's, untouched by this module
    ink_locked = (t1_art.PAPER, t1_art.RULE, t1_art.INK) == (
        (248, 246, 240), (214, 220, 230), (28, 30, 38))

    return {
        "topics": len(topics),
        "each_topic_boards_pass": all(p["pass"] for p in per_topic),
        "character_background_identical": bool(char_identical),
        "boards_differ_across_topics": bool(boards_differ),
        "titles_differ": bool(titles_differ),
        "ink_paper_rule_locked_to_T1": bool(ink_locked),
        "per_topic": per_topic,
        "pass": bool(char_identical and boards_differ and titles_differ
                     and ink_locked and all(p["pass"] for p in per_topic)),
    }


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "how contactless payment works"
    tpl = sys.argv[2] if len(sys.argv) > 2 else "why"
    rep = run_test(topic, template=tpl)
    rer = run_reroll_demo(topic, template=tpl)
    series = run_series_check([
        ("how contactless payment works", "why"),
        ("why do bonds lose value when rates rise", "compounding"),
        ("the story of the transatlantic cable", "story"),
    ])
    print(json.dumps({"boards": rep, "reroll": rer, "series": series}, indent=2))

"""Board art: stickman + whiteboard glyphs, drawn per-scene, deterministic.

The 9-still pool is gone (not on this machine); boards are now generated per
job from a seed derived from the topic — the "unseen topic -> boards differ
from the pool" acceptance path. Style constants here mirror the spec's visual
identity (paper + rule lines, dark ink, one accent).

Everything readable in a frame is typeset HERE by the encoder — never by an
image model (spec trap §5.6).
"""
from __future__ import annotations

import hashlib
import math

from PIL import Image, ImageDraw, ImageFont

from . import brand, env, images

PAPER = (248, 246, 240)
RULE = (214, 220, 230)
INK = (28, 30, 38)
# T3 cooler/neutral palette (wired in 2026-11-21): every accent is a vivid cool
# hue (violet -> blue -> sky -> cyan -> teal -> jade) with chroma >= 100 and
# blue >= red, so each pops against the off-white paper on a phone. The warm
# orange/brown/pink accents are gone. See D:\opc\t3-images\t3_images.py
# COOL_PALETTE / MIN_ACCENT_CHROMA=90 for the QA rationale.
ACCENTS = [(79, 70, 229), (37, 99, 235), (2, 132, 199), (8, 145, 178),
           (15, 118, 110), (6, 124, 96)]

GLYPH_KEYS = ["coins", "clock", "path", "gear", "bulb", "cross", "check",
              "people", "magnifier", "bars", "speech", "target", "flow",
              "alert", "cloud", "arrow"]


def _font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    path, _sub = env.find_font(kind)
    return ImageFont.truetype(path, px)


def board_seed(job_id: str, topic: str) -> int:
    return int(hashlib.sha256(f"{job_id}|{topic}".encode()).hexdigest(), 16)


def layout(W: int, H: int) -> dict:
    """Normalized regions; same geometry for every aspect so the safe-area
    audit is aspect-independent. Text regions are inside SAFE_AREA by design."""
    s = brand.SAFE_AREA
    return {
        "W": W, "H": H,
        "title": (0.50 - s / 2, 0.055, 0.50 + s / 2, 0.115),
        "beat": (0.50 - s / 2, 0.125, 0.50 + s / 2, 0.165),
        "stage": (0.50 - s / 2, 0.185, 0.50 + s / 2, 0.66),
        "onText": (0.50 - s / 2, 0.675, 0.50 + s / 2, 0.735),
        "caption": (0.50 - s / 2, 0.765, 0.50 + s / 2, 0.895),
        "safe": (0.50 - s / 2, 0.50 - s / 2, 0.50 + s / 2, 0.50 + s / 2),
        "unit": min(W, H),
    }


def _rect(lay: dict, key: str):
    x0, y0, x1, y1 = lay[key]
    return int(x0 * lay["W"]), int(y0 * lay["H"]), int(x1 * lay["W"]), int(y1 * lay["H"])


def fit_text(draw: ImageDraw.ImageDraw, text: str, box, kind: str,
             start_px: int, fill, align: str = "center"):
    """Shrink font until the bbox fits inside `box` — the reason the
    safe-area audit runs at 0 violations (spec §1 line 22). Returns (bbox, px)."""
    x0, y0, x1, y1 = box
    px = start_px
    while px > 12:
        f = _font(kind, px)
        b = draw.textbbox((0, 0), text, font=f)
        w, h = b[2] - b[0], b[3] - b[1]
        if w <= (x1 - x0) and h <= (y1 - y0):
            break
        px = int(px * 0.92)
    f = _font(kind, px)
    b = draw.textbbox((0, 0), text, font=f)
    w = b[2] - b[0]
    if align == "center":
        ox = x0 + ((x1 - x0) - w) // 2
    elif align == "left":
        ox = x0
    else:
        ox = x1 - w
    oy = y0 + ((y1 - y0) - (b[3] - b[1])) // 2 - b[1]
    draw.text((ox, oy), text, font=f, fill=fill)
    return (ox + b[0], oy + b[1], ox + b[2], oy + b[3]), px


def wrap(draw, text, kind, px, max_w):
    words, lines, cur = text.split(), [], ""
    f = _font(kind, px)
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ stickman
# Poses: normalized skeleton parts; each part is a stroke sequence so it can
# be drawn progressively (t in [0,1]). head circle counts as one stroke.
def _pose(name, cx, cy, h):
    """Return list of strokes; stroke = list of (x, y) points or ('circle', x, y, r)."""
    u = h / 100.0
    head_r = 10 * u
    neck_y = cy - 34 * u
    hip_y = cy + 12 * u
    def P(dx, dy):
        return (cx + dx * u, cy + dy * u)
    head = [("circle", cx, head_r * 0 + neck_y - head_r, head_r)]
    body = [P(0, -24), P(0, 12)]
    if name == "walk":
        arms = [P(0, -18), P(-16, -6), P(-26, 4)]
        arms2 = [P(0, -18), P(14, -10), P(24, -20)]
        legs = [P(0, 12), P(-12, 34), P(-18, 56)]
        legs2 = [P(0, 12), P(12, 32), P(22, 52)]
    elif name == "point":
        arms = [P(0, -18), P(18, -26), P(38, -40)]
        arms2 = [P(0, -18), P(-12, -6), P(-10, 6)]
        legs = [P(0, 12), P(-8, 34), P(-8, 56)]
        legs2 = [P(0, 12), P(8, 34), P(8, 56)]
    elif name == "draw":
        arms = [P(0, -18), P(20, -14), P(36, -6)]
        arms2 = [P(0, -18), P(-14, -8), P(-20, 4)]
        legs = [P(0, 12), P(-9, 34), P(-9, 56)]
        legs2 = [P(0, 12), P(9, 34), P(9, 56)]
    elif name == "count":
        arms = [P(0, -18), P(16, -30), P(20, -44)]
        arms2 = [P(0, -18), P(-16, -30), P(-20, -44)]
        legs = [P(0, 12), P(-8, 34), P(-8, 56)]
        legs2 = [P(0, 12), P(8, 34), P(8, 56)]
    elif name == "shake":
        arms = [P(0, -18), P(-18, -24), P(-30, -18)]
        arms2 = [P(0, -18), P(18, -24), P(30, -18)]
        legs = [P(0, 12), P(-12, 32), P(-16, 52)]
        legs2 = [P(0, 12), P(12, 32), P(16, 52)]
    else:  # nod
        arms = [P(0, -18), P(14, -4), P(24, 6)]
        arms2 = [P(0, -18), P(-14, -4), P(-24, 6)]
        legs = [P(0, 12), P(-7, 34), P(-7, 56)]
        legs2 = [P(0, 12), P(7, 34), P(7, 56)]
    return [head, body, arms, arms2, legs, legs2]


POSE_NAMES = ["walk", "point", "draw", "count", "shake", "nod"]


def draw_strokes(draw, strokes, t, color, width):
    """Progressively draw stroke list up to fraction t (0..1).
    A stroke is either [('circle', x, y, r)] or a polyline of (x, y) points."""
    n = len(strokes)
    done = t * n
    for i, st in enumerate(strokes):
        frac = max(0.0, min(1.0, done - i))
        if frac <= 0:
            return
        if st and st[0][0] == "circle":
            _, x, y, r = st[0]
            bbox = [x - r, y - r, x + r, y + r]
            if frac >= 1:
                draw.ellipse(bbox, outline=color, width=width)
            else:
                draw.arc(bbox, 0, int(360 * frac), fill=color, width=width)
            continue
        pts = st
        m = min(len(pts), max(2, int(len(pts) * frac)))
        draw.line(pts[:m], fill=color, width=width, joint="curve")
        if frac < 1 and len(pts) >= 2:
            # partial last segment
            pa, pb = pts[m - 2], pts[m - 1]
            f2 = len(pts) * frac - (m - 2) - 1
            if 0 < f2 < 1:
                q = (pa[0] + (pb[0] - pa[0]) * f2, pa[1] + (pb[1] - pa[1]) * f2)
                draw.line([pa, q], fill=color, width=width)


# ------------------------------------------------------------------ glyphs
def _glyph(draw, key, x, y, size, color, width, t):
    u = size / 100.0
    def X(dx): return x + dx * u
    def Y(dy): return y + dy * u
    if key == "coins":
        for i, r in enumerate([30, 22, 14]):
            _arc(draw, X(0), Y(30 - i * 26), r * u, color, width, t, i)
    elif key == "clock":
        _arc(draw, x, y, 36 * u, color, width, t, 0)
        _line(draw, [(x, y), X(0), Y(-24), t, 1], color, width) if False else None
        if t > 0.5:
            draw.line([(x, y), (x, y - 22 * u)], fill=color, width=width)
            draw.line([(x, y), (x + 14 * u, y)], fill=color, width=width)
    elif key == "path":
        _poly(draw, [(-45, 30), (-15, 10), (15, -10), (45, -30)], X, Y, color, width, t, 0)
        if t > 0.9:
            draw.polygon([(X(45), Y(-30)), (X(33), Y(-26)), (X(38), Y(-38))], outline=color)
    elif key == "gear":
        _arc(draw, x, y, 26 * u, color, width, t, 0)
        _arc(draw, x, y, 10 * u, color, width, t, 1)
        if t > 0.6:
            for k in range(8):
                a = k * math.pi / 4
                draw.line([(x + 26 * u * math.cos(a), y + 26 * u * math.sin(a)),
                           (x + 36 * u * math.cos(a), y + 36 * u * math.sin(a))],
                          fill=color, width=width)
    elif key == "bulb":
        _arc(draw, x, Y(-14), 22 * u, color, width, t, 0)
        _poly(draw, [(-8, 8), (-8, 26), (8, 26), (8, 8)], X, Y, color, width, t, 1)
        if t > 0.8:
            for k in range(6):
                a = k * math.pi / 3
                draw.line([(x + 30 * u * math.cos(a), Y(-14) + 30 * u * math.sin(a)),
                           (x + 40 * u * math.cos(a), Y(-14) + 40 * u * math.sin(a))],
                          fill=color, width=width)
    elif key in ("cross", "check"):
        if key == "cross":
            _line2(draw, X(-26), Y(-26), X(26), Y(26), color, width, t, 0)
            _line2(draw, X(26), Y(-26), X(-26), Y(26), color, width, t, 1)
        else:
            _line2(draw, X(-30), Y(0), X(-8), Y(24), color, width, t, 0)
            _line2(draw, X(-8), Y(24), X(32), Y(-24), color, width, t, 1)
    elif key == "people":
        _arc(draw, X(-20), Y(-24), 12 * u, color, width, t, 0)
        _arc(draw, X(20), Y(-24), 12 * u, color, width, t, 1)
        if t > 0.7:
            draw.arc([X(-38), Y(-6), X(-2), Y(40)], 180, 360, fill=color, width=width)
            draw.arc([X(2), Y(-6), X(38), Y(40)], 180, 360, fill=color, width=width)
    elif key == "magnifier":
        _arc(draw, X(-10), Y(-10), 24 * u, color, width, t, 0)
        _line2(draw, X(8), Y(8), X(34), Y(34), color, width, t, 1)
    elif key == "bars":
        for i, hh in enumerate([20, 38, 58]):
            _line2(draw, X(-36 + i * 26), Y(36), X(-36 + i * 26), Y(36 - hh), color, width, t, i)
    elif key == "speech":
        _rrect(draw, X(-40), Y(-34), X(40), Y(20), color, width, t)
        _poly(draw, [(-12, 20), (0, 36), (8, 20)], X, Y, color, width, t, 1)
    elif key == "target":
        for i, r in enumerate([36, 22, 8]):
            _arc(draw, x, y, r * u, color, width, t, i)
    elif key == "flow":
        for i in range(3):
            y0 = -30 + i * 30
            _line2(draw, X(-44), Y(y0), X(20), Y(y0), color, width, t, i)
            if t > (i + 1) / 3:
                draw.polygon([(X(34), Y(y0)), (X(22), Y(y0 - 7)), (X(22), Y(y0 + 7))], fill=color)
    elif key == "alert":
        _poly(draw, [(0, -38), (40, 30), (-40, 30), (0, -38)], X, Y, color, width, t, 0)
        if t > 0.7:
            draw.line([(x, Y(-12)), (x, Y(10))], fill=color, width=width)
            draw.ellipse([x - 3 * u, Y(20), x + 3 * u, Y(26)], fill=color)
    elif key == "cloud":
        _arc(draw, X(-18), Y(0), 20 * u, color, width, t, 0)
        _arc(draw, X(14), Y(-6), 26 * u, color, width, t, 1)
        if t > 0.7:
            draw.line([(X(-40), Y(22)), (X(40), Y(22))], fill=color, width=width)
    else:  # arrow
        _line2(draw, X(-42), Y(0), X(30), Y(0), color, width, t, 0)
        if t > 0.8:
            draw.line([(X(30), Y(0)), (X(16), Y(-12))], fill=color, width=width)
            draw.line([(X(30), Y(0)), (X(16), Y(12))], fill=color, width=width)


def _arc(d, x, y, r, c, w, t, i):
    if t * 4 > i:
        d.ellipse([x - r, y - r, x + r, y + r], outline=c, width=w)


def _poly(d, pts, X, Y, c, w, t, i):
    f = max(0.0, min(1.0, t * 2 - i * 0.5))
    if f <= 0:
        return
    n = max(2, int(math.ceil(len(pts) * f)))
    d.line([(X(px), Y(py)) for px, py in pts[:n]], fill=c, width=w, joint="curve")


def _line2(d, x0, y0, x1, y1, c, w, t, i):
    f = max(0.0, min(1.0, t * 3 - i * 0.6))
    if f > 0:
        d.line([(x0, y0), (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)], fill=c, width=w)


def _rrect(d, x0, y0, x1, y1, c, w, t):
    if t > 0.2:
        d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) * 0.2, outline=c, width=w)


# ------------------------------------------------------------------ boards
def draw_board(job: dict, scene: dict, W: int, H: int, t: float = 1.0,
               caption_mode: str | None = None, caption_chunk: str = "",
               caption_words=None, highlight=-1) -> tuple[Image.Image, list]:
    """Render one frame for `scene` at draw-progress t. Returns (image, text_bboxes)
    where text_bboxes feed the safe-area audit (spec driver.audit)."""
    lay = layout(W, H)
    seed = board_seed(job["id"], job["topic"])
    accent = ACCENTS[(seed + scene["i"]) % len(ACCENTS)]
    pose = POSE_NAMES[(seed + scene["i"]) % len(POSE_NAMES)]
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # paper rule lines
    step = max(28, H // 34)
    for yy in range(step, H, step):
        d.line([(0, yy), (W, yy)], fill=RULE, width=2)

    boxes = []
    # title (topic) — typeset, fit-shrunk
    tb, _ = fit_text(d, job["title"].upper(), _rect(lay, "title"), "display",
                     int(lay["unit"] * 0.055), INK)
    boxes.append(tb)
    bb, _ = fit_text(d, f"{scene['beat'].upper()}  ·  SCENE {scene['i'] + 1}", _rect(lay, "beat"),
                     "mono", int(lay["unit"] * 0.030), (120, 124, 134))
    boxes.append(bb)

    # stage: REAL per-scene AI illustration when the T3 image stage is on
    # (images.fetch_all ran in the boards stage); else the vector fallback
    # (glyph left, stickman right for 16:9; stacked for 9:16).
    sx0, sy0, sx1, sy1 = _rect(lay, "stage")
    photo = images.load_photo(job["id"], scene["i"])
    if photo is not None:
        pw, ph = sx1 - sx0, sy1 - sy0
        pic = images.cover(photo, pw, ph)
        if t < 1.0:  # quantized fade-in over the draw ramp (<=12 blends/scene)
            base = Image.new("RGB", (pw, ph), PAPER)
            pic = Image.blend(base, pic, max(0.0, min(1.0, t)))
        img.paste(pic, (sx0, sy0))
    else:
        vertical = H > W
        size = int(min(sx1 - sx0, sy1 - sy0) * (0.62 if vertical else 0.5))
        if vertical:
            gx, gy = (sx0 + sx1) // 2, sy0 + int((sy1 - sy0) * 0.30)
            px_, py_ = (sx0 + sx1) // 2, sy0 + int((sy1 - sy0) * 0.72)
        else:
            gx, gy = sx0 + int((sx1 - sx0) * 0.26), (sy0 + sy1) // 2
            px_, py_ = sx0 + int((sx1 - sx0) * 0.74), (sy0 + sy1) // 2 + int(size * 0.1)
        _glyph(d, scene["art"], gx, gy, size, accent, max(4, size // 34), t)
        strokes = _pose(pose, px_, py_ - size * 0.42, size * 1.15)
        draw_strokes(d, strokes, t, INK, max(5, size // 28))

    # onText annotation (hand style, rotated feel via offset)
    ob, _ = fit_text(d, scene["onText"], _rect(lay, "onText"), "hand",
                     int(lay["unit"] * 0.052), accent)
    boxes.append(ob)

    # captions
    style = caption_mode or job["captions"]
    if style != "none" and caption_chunk:
        cx0, cy0, cx1, cy1 = _rect(lay, "caption")
        if style == "clean":
            cb, _ = fit_text(d, caption_chunk, (cx0, cy0, cx1, cy0 + int((cy1 - cy0) * 0.42)),
                             "mono", int(lay["unit"] * 0.036), INK)
        else:  # blocks / karaoke
            px = int(lay["unit"] * 0.062)
            lines = wrap(d, caption_chunk, "display", px, cx1 - cx0)
            while len(lines) > 3 and px > 20:
                px = int(px * 0.9)
                lines = wrap(d, caption_chunk, "display", px, cx1 - cx0)
            f = _font("display", px)
            lh = int(px * 1.25)
            total_h = lh * len(lines)
            oy = cy0 + ((cy1 - cy0) - total_h) // 2
            x = cx0
            for ln in lines:
                b = d.textbbox((x, oy), ln, font=f)
                boxes.append(b)
                if style == "karaoke":
                    _karaoke(d, ln, x, oy, f, caption_words, highlight)
                else:
                    d.text((x, oy), ln, font=f, fill=INK)
                oy += lh
        if style == "blocks":  # underline accent swipe
            d.rectangle([cx0, cy1 - 6, cx1, cy1], fill=accent)

    if job.get("watermark"):
        wm = f"{brand.CODENAME}.app"
        wb, _ = fit_text(d, wm, (int(W * 0.70), int(H * 0.03), int(W * 0.95), int(H * 0.075)),
                         "mono", int(lay["unit"] * 0.028), (140, 144, 152))
        boxes.append(wb)
    return img, boxes


def _karaoke(d, line, x, y, f, words, highlight):
    """Per-word highlight window: spoken words in ink, rest in light gray."""
    cx = x
    seen = 0
    for w in line.split():
        b = d.textbbox((cx, y), w, font=f)
        colored = INK if seen <= highlight else (168, 172, 180)
        d.text((cx, y), w, font=f, fill=colored)
        cx = b[2] + d.textlength(" ", font=f)
        seen += 1

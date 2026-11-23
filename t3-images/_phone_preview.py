"""Phone-size preview + vividness stats for the T3 sample boards.

Renders each board at a real phone width (390 px, like an iPhone logical
viewport) so the 'dull / cloudy' judgment is made at the size a viewer sees,
and prints numeric colour stats (accent saturation, frame contrast) to back it.
Working script — outputs go to _phone_preview/, not the samples deliverable.
"""
from __future__ import annotations
import os, sys
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
OUT = os.path.join(HERE, "_phone_preview")
PHONE_W = 390  # typical phone logical width

TOPICS = {
    "contactless (base)": "how-contactless-payment-works",
    "contactless (rerollA)": "how-contactless-payment-works-rerollA",
    "contactless (rerollB)": "how-contactless-payment-works-rerollB",
    "bonds/rates": "why-do-bonds-lose-value-when-rates-rise",
    "transatlantic cable": "the-story-of-the-transatlantic-cable",
}


def scenes(d):
    return sorted(os.path.join(SAMPLES, d, f)
                  for f in os.listdir(os.path.join(SAMPLES, d))
                  if f.startswith("scene") and f.endswith(".png"))


def phone_strip(label, d, cols=1):
    """Stack this topic's boards at phone width into one vertical scroll image."""
    ims = [Image.open(p).convert("RGB") for p in scenes(d)]
    th = [im.resize((PHONE_W, int(im.height * PHONE_W / im.width))) for im in ims]
    gap = 10
    H = sum(t.height for t in th) + gap * (len(th) + 1)
    sheet = Image.new("RGB", (PHONE_W, H), (20, 22, 28))  # dark phone bezel-ish bg
    y = gap
    for t in th:
        sheet.paste(t, (0, y)); y += t.height + gap
    path = os.path.join(OUT, "phone-" + "".join(c if c.isalnum() else "_" for c in label) + ".png")
    sheet.save(path)
    return path


def stats(d):
    """Accent saturation + full-frame luminance contrast, averaged over scenes."""
    sats, cons = [], []
    for p in scenes(d):
        a = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
        mx = a.max(2); mn = a.min(2)
        # accent pixels = saturated (not paper, not gray ink): chroma high
        chroma = (mx - mn)
        acc = a[chroma > 40]                      # the coloured glyph/text pixels
        if len(acc):
            sats.append(float((acc.max(1) - acc.min(1)).mean()))
        lum = (0.299*a[:,:,0] + 0.587*a[:,:,1] + 0.114*a[:,:,2])
        cons.append(float(lum.std()))
    return (round(sum(sats)/len(sats), 1) if sats else 0,
            round(sum(cons)/len(cons), 1) if cons else 0)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(f"{'topic':26} {'accent_sat':>10} {'contrast':>9}  phone_preview")
    for label, d in TOPICS.items():
        sat, con = stats(d)
        path = phone_strip(label, d)
        print(f"{label:26} {sat:>10} {con:>9}  {os.path.basename(path)}")

import os, sys
for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(v, "1")
sys.path.insert(0, r"D:\qf-t1-build")
import numpy as np
from PIL import Image
import t3_images as t3

t3.apply_style()
TOP = {
    "contactless": ("how contactless payment works", "why", "how-contactless-payment-works"),
    "bonds": ("why do bonds lose value when rates rise", "compounding", "why-do-bonds-lose-value-when-rates-rise"),
    "cable": ("the story of the transatlantic cable", "story", "the-story-of-the-transatlantic-cable"),
}
def chroma(c):
    return max(c) - min(c)
for label, (topic, tpl, d) in TOP.items():
    job = t3.build_job(topic, template=tpl)
    print("==", label, "==")
    for sc in job["scenes"]:
        acc = tuple(t3.scene_accent(job, sc))
        img = np.asarray(t3.render_board(job, sc)).astype(np.int16)
        lum = 0.299*img[:, :, 0] + 0.587*img[:, :, 1] + 0.114*img[:, :, 2]
        full_dark = int(lum.min())
        ph = np.asarray(Image.fromarray(np.uint8(img)).resize(
            (390, int(img.shape[0]*390/img.shape[1])))).astype(np.int16)
        plum = 0.299*ph[:, :, 0] + 0.587*ph[:, :, 1] + 0.114*ph[:, :, 2]
        phone_dark = int(plum.min())
        print("  s{:<1} {:<10} accent={} chroma={:<3} full_darkest={} phone_darkest={}".format(
            sc["i"], sc["art"], acc, chroma(acc), full_dark, phone_dark))

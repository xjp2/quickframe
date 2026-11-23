"""QuickFrame brand/pipeline registry — rebuilt from AGENTS.md §3 contracts.

This module is the single source of truth for the keys the app consumes:
the 7 pipeline stage keys, caption styles, beds, aspects, and template spines.
Renaming the product: one point (CODENAME), same as brand.js:6 in the original.
"""

CODENAME = "QuickFrame"  # rename point

# Stage keys — the promise. brand.js pipeline == tools_build == render log.
# Do not reorder or rename. (AGENTS.md §3)
PIPELINE = ["script", "boards", "art", "voice", "captions", "encode", "publish"]

# Aspects: encoder output exists for 16:9 and 9:16 (mp4-169, mp4-916).
ASPECTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}

# Caption styles (studio.js STYLES/CAPS). Encoder mirrors `blocks` fully;
# karaoke = blocks with per-word highlight window; clean = mono lower bar;
# none = no burned text. (AGENTS.md §3)
CAPTION_STYLES = ["blocks", "karaoke", "clean", "none"]

# Music beds (studio.js BEDS): chalk/drive/lofi deterministic synth 30 s,
# ai = model-composed instrumental (asset not on this machine -> falls back
# to `drive` with a warning), none = silence. Mixed at 0.85-0.9 with fade.
BEDS = ["chalk", "drive", "lofi", "ai", "none"]
BED_MIX = {"chalk": 0.87, "drive": 0.88, "lofi": 0.86, "ai": 0.88, "none": 0.0}
BED_FADE_OUT_S = 1.2

# Six spine templates x 5 beats (AGENTS.md §2 T2: "Spine beat-sheets live in
# TEMPLATES; 6 spines x 5 beats"). Drafted spines: why, compounding, myth,
# howto, story, inside.
TEMPLATE_IDS = ["why", "compounding", "myth", "howto", "story", "inside"]

# Voice: timing math per spec is words / 2.6 / rate (engine.js:139).
SPEECH_WPS = 2.6  # words per second at rate 1.0
# Calibrated against real edge-tts output on this box (81-word spine -> 33.98 s
# = 2.38 words/sec incl. natural pauses). Used to size content to lengthSec.
SPEECH_WPS_TTS = 2.4
# Natural TTS rate window for the length correction (0.8x slow .. 1.35x fast).
RATE_MIN, RATE_MAX = 0.8, 1.35
VOICES = {
    "calm-01": {"rate": 1.0},
    "bright-01": {"rate": 1.08},
    "doc-01": {"rate": 0.94},
}

# Credits: 1 credit ~= 10 s of finished video (AGENTS.md §2 T6).
SECONDS_PER_CREDIT = 10.0

# Broadcast safe area (driver.audit gate): text bboxes must stay inside this
# fraction of the frame, measured from the frame edges.
SAFE_AREA = 0.90

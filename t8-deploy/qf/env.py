"""QuickFrame T1 job service — environment resolution (rebuilt from AGENTS.md spec).

No /tmp anywhere: everything lives under the project root (spec trap §5.1).
Frame scratch lives under .render_work/ on the real volume (spec trap §5.2).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache

ROOT = os.environ.get("QF_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dir(name: str) -> str:
    p = os.path.join(ROOT, name)
    os.makedirs(p, exist_ok=True)
    return p


def work_dir() -> str:
    """Frame scratch. Per-run subdirs are created by the caller; never /tmp."""
    return _dir(".render_work")


def store_dir() -> str:
    """Object store root (local filesystem backend, swappable for S3 later)."""
    return _dir("store")


def jobs_dir() -> str:
    """Persisted job state (T5 seed: server-side job JSON)."""
    return _dir("jobs")


def data_dir() -> str:
    return _dir("data")


# ---------------------------------------------------------------- fonts
# Spec: vendored Fraunces + Caveat in assets/fonts/ with system fallbacks and
# an explicit substitution warning. The fonts are NOT on this machine, so the
# fallback path is the operating path and the warning is mandatory.
_FONT_CANDIDATES = {
    "display": [  # Fraunces (serif headline / captions)
        os.path.join(ROOT, "assets", "fonts", "Fraunces.ttf"),
        r"C:\Windows\Fonts\georgiab.ttf",
        r"C:\Windows\Fonts\Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ],
    "hand": [  # Caveat (annotation)
        os.path.join(ROOT, "assets", "fonts", "Caveat.ttf"),
        r"C:\Windows\Fonts\segoesc.ttf",
        r"C:\Windows\Fonts\comic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "mono": [  # stage labels / trust line
        os.path.join(ROOT, "assets", "fonts", "Mono.ttf"),
        r"C:\Windows\Fonts\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    "body": [
        os.path.join(ROOT, "assets", "fonts", "Sans.ttf"),
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


@lru_cache(maxsize=None)
def find_font(kind: str = "body"):
    """Resolve a font path for a kind; returns (path, substituted: bool)."""
    for p in _FONT_CANDIDATES.get(kind, []):
        if os.path.isfile(p):
            return p, ("assets/fonts" not in p.replace("\\", "/"))
    raise FileNotFoundError(f"no font resolvable for kind={kind!r} on this machine")


# ---------------------------------------------------------------- ffmpeg
@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    """Resolution order per spec: env.py system -> imageio-ffmpeg -> QF_FFMPEG."""
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    env = os.environ.get("QF_FFMPEG")
    if env:
        return env
    found = shutil.which(exe)
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise RuntimeError("ffmpeg not found (system PATH, imageio-ffmpeg, or QF_FFMPEG)")


@lru_cache(maxsize=1)
def ffprobe_bin() -> str:
    exe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    found = shutil.which(exe)
    if found:
        return found
    return ffmpeg_bin().replace("ffmpeg", "ffprobe")


def ffprobe_json(path: str) -> dict:
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True, check=True).stdout
    import json
    return json.loads(out)


def cpu_count() -> int:
    return os.cpu_count() or 2

"""Object store + signed URLs (local filesystem backend).

Real mechanism, swappable transport: files live under store/ addressed by a
content hash; downloads are HMAC-SHA256 signed with an expiry, identical in
shape to S3-style presigned GETs. On a hosted deployment replace `path()`
with the cloud SDK and keep `signed_url()/verify()` as-is (or delegate to
the provider). No paid service is created by this module.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from . import env

DEFAULT_TTL_S = 24 * 3600


def _secret() -> bytes:
    p = os.path.join(env.data_dir(), ".store-secret")
    if not os.path.isfile(p):
        with open(p, "wb") as f:
            f.write(os.urandom(32))
    with open(p, "rb") as f:
        return f.read()


def put(src_path: str) -> str:
    """Store file under content hash; returns key."""
    h = hashlib.sha256()
    with open(src_path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    key = h.hexdigest()[:32] + "-" + os.path.basename(src_path)
    dst = os.path.join(env.store_dir(), key)
    if not os.path.isfile(dst):
        tmp = dst + ".partial"
        import shutil
        shutil.copyfile(src_path, tmp)
        os.replace(tmp, dst)  # atomic publish of the object
    return key


def path(key: str) -> str:
    p = os.path.join(env.store_dir(), os.path.basename(key))
    if not os.path.isfile(p):
        raise FileNotFoundError(key)
    return p


def _sig(key: str, exp: int) -> str:
    return hmac.new(_secret(), f"{key}|{exp}".encode(), hashlib.sha256).hexdigest()


def signed_url(key: str, base: str, ttl: int = DEFAULT_TTL_S) -> str:
    exp = int(time.time()) + ttl
    return f"{base}/files/{key}?exp={exp}&sig={_sig(key, exp)}"


def verify(key: str, exp: str | int, sig: str) -> tuple[bool, str]:
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False, "bad exp"
    if exp_i < time.time():
        return False, "expired"
    ok = hmac.compare_digest(_sig(key, exp_i), str(sig))
    return ok, "ok" if ok else "bad signature"

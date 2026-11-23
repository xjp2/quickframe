"""End-to-end test of the T2 LLM script engine wired into the T1 job service.

Boots qf.server with QF_SCRIPT_ENGINE=t2, POSTs an unseen topic, polls the
seven-stage job to done, downloads the signed MP4, and PROVES it is a real
render: h264 video stream, frame count ~ duration*fps, frames actually differ
(motion), real non-silent audio (edge-tts speech). Also proves the script stage
used the LLM (vo differs from the deterministic spine) and that every stage key
ran. No simulated pipeline.
"""
import json, os, shutil, subprocess, sys, time, urllib.request

ROOT = r"D:\qf-t1-build"
PORT = 8791
BASE = f"http://127.0.0.1:{PORT}"
sys.path.insert(0, ROOT)
import numpy as np

TOPIC = "why do we get goosebumps when we are cold or scared"   # unseen topic
OUTDIR = r"D:\opc\t2-integration-demo"

# deterministic spine vo for the 'why' template, to prove the LLM differs from it
SPINE_VO0 = "You have seen {T} a hundred times. Almost nobody can explain it."


def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=90) as resp:
        return json.loads(resp.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as resp:
        raw = resp.read()
    try:
        return json.loads(raw)
    except Exception:
        return raw


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    env = dict(os.environ)
    env.update({"QF_ROOT": ROOT, "QF_SCRIPT_ENGINE": "t2", "QF_RENDER_WORKERS": "1",
                "QF_HOST": "127.0.0.1", "PORT": str(PORT)})
    srv = subprocess.Popen([sys.executable, "-m", "qf.server", str(PORT)],
                           cwd=ROOT, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # wait for readiness
        for _ in range(60):
            try:
                h = get("/healthz/service")
                if h.get("ok"):
                    print("service up:", h["ffmpeg"].split("\\")[-1],
                          "| voice:", h["voiceVendor"], "| stages:", h["stages"])
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("service never became ready")

        j = post("/jobs", {"topic": TOPIC, "template": "why", "lengthSec": 12,
                           "aspect": "16:9", "voice": "calm-01", "captions": "blocks",
                           "music": "drive"})
        jid = j["id"]
        print("job", jid, "queued | topic:", repr(TOPIC))

        deadline = time.time() + 360
        job = None
        while time.time() < deadline:
            job = get(f"/jobs/{jid}")
            if job["state"] in ("done", "failed", "blocked"):
                break
            time.sleep(1.5)
        print("--- stage log ---")
        for e in job["log"]:
            print(f"  [{e['stage']}] {e['line']}")
        assert job["state"] == "done", f"state={job['state']} {job.get('error') or job.get('blocker')}"

        # seven stage keys all reached 'done', in the exact contract order
        ss = job["stageState"]
        assert list(ss.keys()) == ["script", "boards", "art", "voice", "captions", "encode", "publish"], ss.keys()
        assert all(v == "done" for v in ss.values()), ss
        print("stage keys OK:", " -> ".join(ss.keys()))

        res = job["result"]
        # PROVE the script came from the LLM, not the spine
        vo0 = res["scenes"][0]["vo"]
        subj = res["subject"]
        assert vo0 != SPINE_VO0.replace("{T}", subj), "vo[0] equals the deterministic spine!"
        assert "T2 LLM engine" in " ".join(res["warnings"]), "warnings missing LLM authorship note"
        print("script engine: LLM OK | vo[0]:", vo0[:70])

        # download via the signed URL exactly as returned
        from urllib.parse import urlparse
        u = urlparse(job["download"]["url"])
        mp4bytes = get(u.path + ("?" + u.query if u.query else ""))
        assert isinstance(mp4bytes, (bytes, bytearray)), "download did not return bytes"
        mp4 = os.path.join(OUTDIR, f"qf-{jid}.mp4")
        open(mp4, "wb").write(mp4bytes)
        # persist the job JSON next to it
        jobp = os.path.join(OUTDIR, f"job-{jid}.json")
        json.dump(job, open(jobp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"downloaded {len(mp4bytes)} bytes -> {mp4}")

        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
            "-show_streams", "-show_format", mp4], capture_output=True, text=True).stdout)
        v = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
        a = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        dur = float(probe["format"]["duration"]); nb = int(v.get("nb_frames", 0)); fps = eval(v["r_frame_rate"])
        print(f"VIDEO: {v['codec_name']} {v['width']}x{v['height']} {fps}fps nb_frames={nb} dur={dur:.2f}s")
        print(f"AUDIO: {a[0]['codec_name']} {a[0]['sample_rate']}Hz ch={a[0]['channels']}" if a else "AUDIO: NONE")
        assert v["codec_name"] == "h264" and v["width"] >= 480, "no real video stream"
        assert a, "no audio stream"
        assert abs(nb - round(dur * fps)) <= max(2, round(dur * fps) * 0.06), f"frame count {nb} vs {round(dur*fps)}"

        # motion: consecutive sampled frames differ
        h = int(round(320 * v["height"] / v["width"]))
        dec = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps=4,scale=320:{h}",
            "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        fsz = 320 * h; n = len(dec) // fsz
        fr = np.frombuffer(dec, dtype=np.uint8)[:n * fsz].reshape(n, fsz).astype(np.int16)
        diffs = [float(np.abs(fr[i + 1] - fr[i]).mean()) for i in range(n - 1)]
        print(f"MOTION: {n} frames @4fps mean-diff={np.mean(diffs):.2f} max={max(diffs):.2f}")
        assert max(diffs) > 1.0, "static image, not animation"

        # audio non-silent (real edge-tts speech)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-map", "0:a", "-ac", "1",
            "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
        au = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
        rms = float(np.sqrt((au ** 2).mean()))
        cues = sum(len(s["cues"]) for s in res["scenes"])
        print(f"AUDIO RMS={rms:.4f} | cues={cues} | voice={res['voice']['tts']}")
        assert rms > 0.01, "audio effectively silent"

        print("\nT2->T1 E2E: PASS — LLM script flowed through all 7 stages into a real MP4")
        print("ARTIFACTS:", mp4, jobp)
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()


if __name__ == "__main__":
    main()

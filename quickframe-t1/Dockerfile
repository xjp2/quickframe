# QuickFrame T1 job service — Docker image (the real qf/ package).
# Generic Dockerfile: runs anywhere Docker runs. Hugging Face Spaces (Docker SDK,
# free CPU tier) is one supported target; it runs as UID 1000 and probes app_port
# (7860) declared in README.md. Hosting is the owner's decision — this image does
# not create or require any paid cloud service.

FROM python:3.12-slim

# FFmpeg is baked in (the encoder contract: a real render, never a stub).
# ca-certificates is required for edge-tts to reach the Microsoft TTS endpoint.
# fonts-dejavu-core gives the encoder a real serif/mono face so text is typeset
# even when the vendored Fraunces/Caveat are not present (env.find_font fallback).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root (Spaces convention: UID 1000).
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
ENV PATH="/home/user/.local/bin:$PATH"

COPY --chown=user:user requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# The service itself: qf/ package (stdlib HTTP server + runner + encoder + voice).
COPY --chown=user:user qf/ /home/user/app/qf/

# Runtime wiring. QF_ROOT is the project root; scratch/store/jobs live under it
# on the container volume, never /tmp (AGENTS.md trap #2/#3).
# QF_RENDER_WORKERS=1: the free CPU tier is memory-tight; a single frame worker
# keeps peak RSS low enough that x264 never fails to allocate (measured: 2 workers
# hit "malloc failed" under ~0.5 GB free; 1 worker renders 1080p clean).
ENV QF_ROOT=/home/user/app \
    QF_HOST=0.0.0.0 \
    PORT=7860 \
    QF_RENDER_WORKERS=1 \
    QF_RES=1280x720 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /home/user/app/.render_work /home/user/app/store /home/user/app/jobs /home/user/app/data \
    && chown -R user:user /home/user/app

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','7860'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+p+'/healthz/service',timeout=4).status==200 else 1)"

CMD ["python", "-m", "qf.server"]

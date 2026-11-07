# One image for the API, the Ray head/workers and the run controller (docs/project-structure.md).
# vLLM's image already carries Python 3.12, torch 2.13.0+cu130 and vLLM 0.30.0; we add Ray, ffmpeg
# (TorchCodec) and nip. Build context: the repo root.
FROM vllm/vllm-openai:v0.30.0@sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90

# vllm-openai's ENTRYPOINT is `vllm serve`; each compose service sets its own command.
ENTRYPOINT []

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Every dependency at its uv.lock version (the set CI tests), into the system Python vLLM lives in.
# Not `uv sync`: that builds a separate venv and re-downloads torch + vLLM. uv keeps installed
# packages whose version already matches the lock (torch 2.13.0+cu130 satisfies ==2.13.0, vllm).
# UV_CACHE_DIR is the build-cache mount below (the base image points it at /opt/uv/cache, which
# the mount missed: every wheel was stored in the layer twice, installed and cached).
ENV UV_SYSTEM_PYTHON=1 UV_BREAK_SYSTEM_PACKAGES=1 UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --extra serve --no-hashes --no-emit-project -o /tmp/req.txt \
    && uv pip install -r /tmp/req.txt && rm /tmp/req.txt
# faster-whisper's CTranslate2 loads libcublas.so.12 by soname, but the image's CUDA is 13: the
# `serve` extra installs the CUDA 12 cuBLAS wheel, this makes the dynamic loader find it (the Linux
# CTranslate2 build needs no cuDNN). RapidOCR's onnxruntime-gpu links the image's CUDA 13 libs.
RUN echo /usr/local/lib/python3.12/dist-packages/nvidia/cublas/lib > /etc/ld.so.conf.d/nip-cublas12.conf \
    && ldconfig
COPY src ./src
COPY eval ./eval
COPY config ./config
ENV NIP_CONFIG_DIR=/app/config
RUN uv pip install --no-deps .

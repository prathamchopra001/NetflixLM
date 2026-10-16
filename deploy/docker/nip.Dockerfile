# One image for the API, the Ray head/workers and the run controller (docs/project-structure.md).
# vLLM's image already carries Python 3.12, torch 2.13.0+cu130 and vLLM 0.30.0; we add Ray, ffmpeg
# (TorchCodec) and nip. Build context: the repo root.
FROM vllm/vllm-openai:v0.30.0@sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90

# vllm-openai's ENTRYPOINT is `vllm serve`; each compose service sets its own command.
ENTRYPOINT []

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY eval ./eval
COPY config ./config
# System Python (the one vLLM lives in); uv keeps already-installed matching versions (torch, vllm).
ENV UV_SYSTEM_PYTHON=1 UV_BREAK_SYSTEM_PACKAGES=1
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install "ray[serve]==2.58.0" .

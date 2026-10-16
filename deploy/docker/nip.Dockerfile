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
ENV UV_SYSTEM_PYTHON=1 UV_BREAK_SYSTEM_PACKAGES=1
COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --extra serve --no-hashes --no-emit-project -o /tmp/req.txt \
    && uv pip install -r /tmp/req.txt && rm /tmp/req.txt
COPY src ./src
COPY eval ./eval
COPY config ./config
ENV NIP_CONFIG_DIR=/app/config
RUN uv pip install --no-deps .

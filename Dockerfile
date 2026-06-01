FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG UV_PACKAGE

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY . .

RUN test -n "$UV_PACKAGE" \
    && uv sync --frozen --no-dev --package "$UV_PACKAGE"

CMD ["python", "-V"]

# ---- Stage 1: build Svelte frontend ----
FROM node:20-slim AS frontend
WORKDIR /app
COPY src_web/cable_analysis/package.json ./
RUN npm install
COPY src_web/cable_analysis/ .
RUN npm run build


# ---- Stage 2: Python backend ----
FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend
COPY main.py .

# Copy built frontend
COPY --from=frontend /app/dist ./dist

# data/ is large — mount as a volume at runtime (see below)
# If you'd rather bake the data in, uncomment:
# COPY data/ ./data/

EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]

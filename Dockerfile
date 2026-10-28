# One container for the deployed demo (Render): FastAPI serves the API and the
# built dashboard, and runs the rule-based detector in a background thread.

# 1) Build the React dashboard
FROM node:22-slim AS dashboard
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Python runtime with the backend and detector
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY detector/ detector/
COPY --from=dashboard /web/dist frontend/dist
ENV RUN_DETECTOR=1
# Render sets $PORT; default to 8000 for a local `docker run`
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

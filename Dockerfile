FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/index.html ./
COPY frontend/eslint.config.js ./
COPY frontend/vite.config.js ./
COPY frontend/src ./src
COPY frontend/public ./public

RUN npm ci && npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install -r backend/requirements.txt

COPY backend ./backend
COPY telegram_bot ./telegram_bot
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

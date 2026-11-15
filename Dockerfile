# Stage 1: frontend
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
RUN npm run build

# Stage 2: backend
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY pix_bancada ./pix_bancada
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 8080
CMD ["uvicorn", "pix_bancada.main:app", "--host", "0.0.0.0", "--port", "8080"]

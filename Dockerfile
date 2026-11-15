FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY pix_bancada ./pix_bancada
EXPOSE 8080
CMD ["uvicorn", "pix_bancada.main:app", "--host", "0.0.0.0", "--port", "8080"]

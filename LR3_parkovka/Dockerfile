FROM python:3.11-slim AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/packages -r requirements.txt

FROM python:3.11-slim
ENV APP_PORT=5000 LOG_LEVEL=INFO PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /install/packages /usr/local
COPY app.py domain.py service.py ./
RUN useradd --create-home --uid 10001 student
USER student
EXPOSE 5000
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]

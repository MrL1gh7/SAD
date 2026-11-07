FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m appuser
COPY flights.py database.py route_builder.py main.py provider.py seed.py ./
USER appuser
EXPOSE 8000
# Данные заполняются при первом запуске; затем Uvicorn становится PID 1.
CMD ["sh", "-c", "python seed.py && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"]

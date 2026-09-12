from python:3.11-slim

workdir /app

copy . /app

run pip install -r requirements.txt

cmd ["python", "main.py"]
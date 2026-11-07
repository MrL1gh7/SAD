"""Заглушка авиакомпании. Не использует настоящие авиабилеты."""
import asyncio
import os
import random
from datetime import date
from fastapi import FastAPI, HTTPException
from flights import make_flights

app = FastAPI(title="Учебный поставщик авиарейсов")
CARRIER = os.environ.get("CARRIER", "P1")
AVERAGE_MS = int(os.environ.get("AVERAGE_MS", "300"))
ERROR_RATE = float(os.environ.get("ERROR_RATE", "0.05"))
SLOW_RATE = float(os.environ.get("SLOW_RATE", "0"))
COUNT = int(os.environ.get("FLIGHTS_PER_DAY", "500"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/flights")
async def flights(date: date):
    # Результат поиска всегда одинаков. Ошибки и время ожидания случайные.
    if random.random() < SLOW_RATE:
        await asyncio.sleep(3)
    else:
        await asyncio.sleep(AVERAGE_MS / 1000 * random.uniform(0.7, 1.3))
    if random.random() < ERROR_RATE:
        raise HTTPException(status_code=500, detail="Временная ошибка поставщика")
    return {"carrier": CARRIER, "flights": make_flights(date, COUNT, CARRIER, CARRIER)}

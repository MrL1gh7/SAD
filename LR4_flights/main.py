"""Три версии поиска: sync, bad_async, async. Переключаются через MODE."""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import date

import httpx
import requests
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, HTTPException, Request
from database import make_sync_engine, make_async_engine, load_sync, load_async
from flights import AIRPORTS
from route_builder import build_routes

MODE = os.getenv("MODE", "sync")
if MODE not in ("sync", "bad_async", "async"):
    raise RuntimeError("MODE: sync, bad_async или async")
SUPPLIERS = {
    "P1": os.getenv("P1_URL", "http://provider1:8000"),
    "P2": os.getenv("P2_URL", "http://provider2:8000"),
    "P3": os.getenv("P3_URL", "http://provider3:8000"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if MODE == "async":
        app.state.engine = make_async_engine()
        app.state.client = httpx.AsyncClient()
        app.state.search_slots = asyncio.Semaphore(10)
    else:
        app.state.engine = make_sync_engine()
    yield
    if MODE == "async":
        await app.state.client.aclose()
        await app.state.engine.dispose()
    else:
        app.state.engine.dispose()


app = FastAPI(title="ЛР №4. Поиск авиарейсов", lifespan=lifespan)


def validate(origin: str, destination: str):
    origin = origin.upper()
    destination = destination.upper()
    if origin not in AIRPORTS or destination not in AIRPORTS or origin == destination:
        raise HTTPException(422, "Укажи два разных аэропорта из списка AIRPORTS")
    return origin, destination


def get_supplier_sync(name, url, day):
    """На поставщика всего 2 с, включая повтор и паузу 0.2 с."""
    deadline = time.monotonic() + 2.0
    address = f"{url}/flights?date={day.isoformat()}"
    for attempt in range(2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            response = requests.get(address, timeout=remaining)
            if response.status_code == 200:
                return response.json()["flights"]
        except (requests.RequestException, ValueError, KeyError):
            pass
        if attempt == 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0.2:
                return None
            time.sleep(0.2)
    return None


async def get_supplier_async(client, name, url, day):
    address = f"{url}/flights?date={day.isoformat()}"
    try:
        async with asyncio.timeout(2.0):
            for attempt in range(2):
                try:
                    response = await client.get(address)
                    if response.status_code == 200:
                        return response.json()["flights"]
                except (httpx.RequestError, ValueError, KeyError):
                    pass
                if attempt == 0:
                    await asyncio.sleep(0.2)
    except TimeoutError:
        pass
    return None


def make_answer(local, collected, start, origin, destination, day):
    missing = [name for name, data in collected.items() if data is None]
    if len(missing) == 3 and not local:
        raise HTTPException(503, detail={
            "message": "Поиск временно недоступен", "missing_suppliers": missing
        })
    all_flights = list(local)
    for data in collected.values():
        if data is not None:
            all_flights.extend(data)
    routes = build_routes(all_flights, origin, destination, day)
    return {
        "origin": origin, "destination": destination, "date": day.isoformat(),
        "routes": routes, "missing_suppliers": missing,
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
    }


def search_sync(request, origin, destination, day):
    start = time.perf_counter()
    origin, destination = validate(origin, destination)
    try:
        local = load_sync(request.app.state.engine, day)
    except SQLAlchemyError:
        raise HTTPException(503, "База временно недоступна")
    collected = {}
    for name, url in SUPPLIERS.items():
        collected[name] = get_supplier_sync(name, url, day)
    return make_answer(local, collected, start, origin, destination, day)


async def search_async(request, origin, destination, day):
    start = time.perf_counter()
    origin, destination = validate(origin, destination)
    # В отличие от sync, четыре независимых ожидания идут одновременно.
    values = await asyncio.gather(
        load_async(request.app.state.engine, day),
        *[get_supplier_async(request.app.state.client, name, url, day)
          for name, url in SUPPLIERS.items()],
        return_exceptions=True,
    )
    local = values[0]
    if isinstance(local, Exception):
        raise HTTPException(503, "База временно недоступна")
    collected = {}
    for name, value in zip(SUPPLIERS, values[1:]):
        collected[name] = None if isinstance(value, BaseException) else value
    # Даже в async нельзя надолго блокировать loop вычислением маршрутов.
    return await asyncio.to_thread(make_answer, local, collected, start, origin, destination, day)


if MODE == "sync":
    @app.get("/health")
    def health():
        return {"status": "ok", "mode": MODE}

    @app.get("/search")
    def search(request: Request, origin: str, destination: str, date: date):
        return search_sync(request, origin, destination, date)

elif MODE == "bad_async":
    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": MODE}

    @app.get("/search")
    async def search(request: Request, origin: str, destination: str, date: date):
        # НАМЕРЕННО неверно: блокирующая база, requests и sleep внутри async def.
        return search_sync(request, origin, destination, date)

else:
    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": MODE}

    @app.get("/search")
    async def search(request: Request, origin: str, destination: str, date: date):
        async with request.app.state.search_slots:
            return await search_async(request, origin, destination, date)

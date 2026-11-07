"""Два режима нагрузки: закрытый и открытый. /health проверяется каждые 0.1 с."""
import argparse
import asyncio
import csv
import math
import os
import random
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from flights import AIRPORTS

DAY = "2026-11-10"


def percentile(numbers, percent):
    """Метод ближайшего ранга, описанный в методичке."""
    if not numbers:
        return None
    values = sorted(numbers)
    return round(values[max(0, math.ceil(len(values) * percent / 100) - 1)], 2)


def report(numbers):
    return {
        "p50": percentile(numbers, 50), "p95": percentile(numbers, 95),
        "p99": percentile(numbers, 99),
        "max": round(max(numbers), 2) if numbers else None,
    }


async def main(args):
    rng = random.Random(42)
    pairs = []
    for _ in range(10000):
        a, b = rng.sample(AIRPORTS, 2)
        pairs.append((a, b))

    timeout = httpx.Timeout(30.0)
    limits = httpx.Limits(max_connections=250, max_keepalive_connections=100)
    async with (httpx.AsyncClient(timeout=timeout, limits=limits) as client,
                httpx.AsyncClient(timeout=timeout, limits=limits) as health_client):
        mode = (await client.get(args.url + "/health")).json().get("mode", "unknown")
        begin = asyncio.get_running_loop().time()
        measure_begin = begin + args.warmup
        finish = measure_begin + args.duration
        rows, health_rows = [], []
        counter = 0

        async def send_search():
            nonlocal counter
            number = counter
            counter += 1
            origin, dest = pairs[number % len(pairs)]
            started = asyncio.get_running_loop().time()
            if started >= finish:
                return
            params = {"origin": origin, "destination": dest, "date": args.date}
            ok = False
            try:
                resp = await client.get(args.url + "/search", params=params)
                ok = resp.status_code < 400
            except httpx.RequestError:
                pass
            ended = asyncio.get_running_loop().time()
            if started >= measure_begin:
                rows.append(((ended - started) * 1000, ok))

        async def ping_health():
            started = asyncio.get_running_loop().time()
            ok = False
            try:
                resp = await health_client.get(args.url + "/health", timeout=30)
                ok = resp.status_code < 400
            except httpx.RequestError:
                pass
            ended = asyncio.get_running_loop().time()
            if started >= measure_begin:
                health_rows.append(((ended - started) * 1000, ok))

        async def watch_health():
            # Каждые 100 мс создаём НОВЫЙ запрос, даже если прошлый ещё ждёт.
            # Иначе медленный /health сам уменьшил бы частоту его проверки.
            tick = begin
            tasks = []
            while tick < finish:
                await asyncio.sleep(max(0, tick - asyncio.get_running_loop().time()))
                tasks.append(asyncio.create_task(ping_health()))
                tick += 0.1
            await asyncio.gather(*tasks)

        async def closed_worker():
            while asyncio.get_running_loop().time() < finish:
                await send_search()

        async def open_worker():
            next_at = begin
            tasks = []
            while next_at < finish:
                await asyncio.sleep(max(0, next_at - asyncio.get_running_loop().time()))
                tasks.append(asyncio.create_task(send_search()))
                next_at += rng.expovariate(args.rate)
            await asyncio.gather(*tasks)

        health_task = asyncio.create_task(watch_health())
        if args.mode == "closed":
            await asyncio.gather(*(closed_worker() for _ in range(args.clients)))
        else:
            await open_worker()
        await health_task

    lat = [ms for ms, ok in rows]
    hlat = [ms for ms, ok in health_rows]
    results = {
        "version": mode,
        "mode": f"C={args.clients}" if args.mode == "closed" else f"open {args.rate}/s",
        "requests": len(rows), "rps": round(len(rows) / args.duration, 2),
        "duration_seconds": args.duration, "warmup_seconds": args.warmup,
        "date": args.date, "latency_unit": "ms",
        **report(lat),
        "errors_percent": round(100 * sum(not ok for ms, ok in rows) / len(rows), 2) if rows else None,
        "health_p95": percentile(hlat, 95),
        "health_errors_percent": round(100 * sum(not ok for ms, ok in health_rows) / len(health_rows), 2) if health_rows else None,
    }
    print("\nРЕЗУЛЬТАТ:")
    for key, value in results.items():
        print(f"{key}: {value}")
    if args.output:
        import json
        stamp = time.time_ns()
        raw = Path(args.output).parent / f"raw_{mode}_{args.mode}_{stamp}.json"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps({"summary": results, "search": rows, "health": health_rows},
                                  ensure_ascii=False), encoding="utf-8")
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results))
            if not exists:
                writer.writeheader()
            writer.writerow(results)
        print("Сохранено:", path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=DAY)
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--mode", choices=["closed", "open"], default="closed")
    p.add_argument("--clients", type=int, default=10)
    p.add_argument("--rate", type=float, default=5)
    p.add_argument("--duration", type=float, default=60)
    p.add_argument("--warmup", type=float, default=10)
    p.add_argument("--output", default="results/benchmarks.csv")
    args = p.parse_args()
    if args.duration <= 0 or args.warmup < 0 or args.clients <= 0 or args.rate <= 0:
        p.error("Длительность, клиенты и частота должны быть положительными; прогрев неотрицательным")
    asyncio.run(main(args))

"""Одни и те же рейсы для одной и той же даты (без базы данных)."""
import random
from datetime import date, datetime, timedelta, timezone

AIRPORTS = [
    "SVO", "DME", "VKO", "LED", "OVB", "SVX", "KZN", "AER", "KRR", "ROV",
    "UFA", "PEE", "KUF", "CEK", "VOG", "OMS", "KJA", "IKT", "KHV", "VVO",
    "MRV", "GOJ", "KGD", "TJM", "TOF", "BAX", "BTK", "GDX", "YKS", "MMK",
]


def make_flights(day: date, count: int, carrier: str, seed: str):
    # Отдельный генератор гарантирует одинаковые рейсы при повторном запросе.
    rng = random.Random(f"{seed}-{day.isoformat()}")
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    result = []
    for number in range(1, count + 1):
        origin, destination = rng.sample(AIRPORTS, 2)
        departs = start + timedelta(minutes=rng.randint(0, 23 * 60 + 59))
        arrives = departs + timedelta(minutes=rng.randint(60, 360))
        result.append({
            "carrier": carrier,
            "flight_number": f"{carrier}{number:04d}",
            "origin": origin,
            "destination": destination,
            "departs_at": departs.isoformat(),
            "arrives_at": arrives.isoformat(),
            "price": rng.randint(1500, 25000),
        })
    return result

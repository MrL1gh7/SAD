"""Создание 180 000 одинаковых рейсов: 1500 за сутки, 120 дней."""
import os
from datetime import date, timedelta, datetime
from sqlalchemy import text
from database import flights, metadata, make_sync_engine
from flights import make_flights


def main():
    engine = make_sync_engine()
    first_day = date.fromisoformat(os.getenv("SEED_START", "2026-10-01"))
    with engine.begin() as conn:
        metadata.create_all(conn)
        # Стабильность при повторных запусках: не добавляем ещё 180 тыс. строк.
        counts = dict(conn.execute(text(
            "SELECT flight_date, count(*) FROM flights GROUP BY flight_date"
        )).all())
    for index in range(120):
        day = first_day + timedelta(days=index)
        if counts.get(day) == 1500:
            continue
        if counts.get(day, 0):
            raise RuntimeError(f"За {day} найдено {counts[day]} рейсов вместо 1500")
        batch = make_flights(day, 1500, "LOCAL", "our-base")
        values = []
        for f in batch:
            values.append({
                "flight_date": day, "carrier": f["carrier"],
                "flight_number": f["flight_number"],
                "origin": f["origin"], "destination": f["destination"],
                "departs_at": datetime.fromisoformat(f["departs_at"]),
                "arrives_at": datetime.fromisoformat(f["arrives_at"]),
                "price": f["price"],
            })
        with engine.begin() as conn:
            conn.execute(flights.insert(), values)
        if (index + 1) % 20 == 0:
            print(f"Загружено {(index+1)*1500} рейсов", flush=True)
    print("Готово: 180000 рейсов", flush=True)


if __name__ == "__main__":
    main()

"""Расчёт маршрутов без HTTP и базы данных: легко тестировать отдельно."""
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta


def build_routes(flights, origin: str, destination: str, day: date):
    if origin == destination:
        return []
    by_origin = {}
    for flight in flights:
        # Все сегменты обязаны вылететь в день поиска.
        departs = datetime.fromisoformat(flight["departs_at"])
        if departs.date() != day or flight["origin"] == flight["destination"]:
            continue
        item = dict(flight)
        item["_dep"] = departs
        item["_arr"] = datetime.fromisoformat(flight["arrives_at"])
        by_origin.setdefault(item["origin"], []).append(item)

    times = {}
    for airport, items in by_origin.items():
        items.sort(key=lambda x: x["_dep"])
        times[airport] = [x["_dep"] for x in items]

    best = []  # Сохраняем только 20 лучших, а не миллионы вариантов.

    def add_route(path):
        price = sum(f["price"] for f in path)
        key = (price, len(path) - 1, tuple(f["flight_number"] for f in path))
        if len(best) == 20 and key >= best[-1][0]:
            return
        route = {
            "flights": [{k: v for k, v in f.items() if not k.startswith("_")} for f in path],
            "total_price": price,
            "transfers": len(path) - 1,
        }
        position = bisect_left([entry[0] for entry in best], key)
        best.insert(position, (key, route))
        if len(best) > 20:
            best.pop()


    def walk(path, visited):
        last = path[-1]
        if last["destination"] == destination:
            add_route(path)
            return
        if len(path) == 3:
            return
        airport = last["destination"]
        minimum = last["_arr"] + timedelta(hours=1)
        maximum = last["_arr"] + timedelta(hours=6)
        starts = times.get(airport, [])
        candidates = by_origin.get(airport, [])
        left = bisect_left(starts, minimum)
        right = bisect_right(starts, maximum)
        for nxt in candidates[left:right]:
            if nxt["destination"] not in visited:
                walk(path + [nxt], visited | {nxt["destination"]})

    for flight in by_origin.get(origin, []):
        walk([flight], {origin, flight["destination"]})

    return [route for _, route in best]

import asyncio
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from flights import AIRPORTS, make_flights
from route_builder import build_routes
from load import percentile
from main import get_supplier_async, get_supplier_sync

DAY = date(2026, 11, 10)


def f(number, origin, destination, start_hour, arrive_hour, price):
    return {
        "carrier": "T", "flight_number": f"T{number}",
        "origin": origin, "destination": destination,
        "departs_at": f"2026-11-10T{start_hour:02}:00:00+00:00",
        "arrives_at": f"2026-11-10T{arrive_hour:02}:00:00+00:00",
        "price": price,
    }


class Tests(unittest.TestCase):
    def test_flights_repeatable(self):
        self.assertEqual(make_flights(DAY, 500, "P1", "P1"),
                         make_flights(DAY, 500, "P1", "P1"))

    def test_flights_duration_and_unique_airports(self):
        flights = make_flights(DAY, 500, "P1", "P1")
        self.assertEqual(len(flights), 500)
        for item in flights:
            delta = datetime.fromisoformat(item["arrives_at"]) - datetime.fromisoformat(item["departs_at"])
            self.assertGreaterEqual(delta.total_seconds(), 3600)
            self.assertLessEqual(delta.total_seconds(), 21600)
            self.assertNotEqual(item["origin"], item["destination"])

    def test_route_direct_and_two_legs(self):
        flights = [f(1, "SVO", "LED", 8, 9, 100),
                   f(2, "SVO", "KZN", 7, 8, 40),
                   f(3, "KZN", "LED", 9, 10, 50)]
        r = build_routes(flights, "SVO", "LED", DAY)
        self.assertEqual([x["total_price"] for x in r], [90, 100])
        self.assertEqual(r[0]["transfers"], 1)

    def test_transfer_less_than_hour_rejected(self):
        flights = [f(1, "SVO", "KZN", 7, 9, 100),
                   f(2, "KZN", "LED", 9, 11, 100)]
        self.assertEqual(build_routes(flights, "SVO", "LED", DAY), [])

    def test_no_airport_repeated(self):
        flights = [f(1, "SVO", "KZN", 6, 7, 100),
                   f(2, "KZN", "SVO", 9, 10, 100),
                   f(3, "SVO", "LED", 12, 13, 100)]
        self.assertEqual(build_routes(flights, "SVO", "LED", DAY), [
            {"flights": [flights[2]], "total_price": 100, "transfers": 0}
        ])

    def test_only_twenty_cheapest(self):
        flights = [f(i, "SVO", "LED", 8, 9, i) for i in range(1, 41)]
        r = build_routes(flights, "SVO", "LED", DAY)
        self.assertEqual(len(r), 20)
        self.assertEqual(r[0]["total_price"], 1)
        self.assertEqual(r[-1]["total_price"], 20)

    def test_only_search_date(self):
        item = f(1, "SVO", "LED", 8, 9, 100)
        item["departs_at"] = "2026-11-11T08:00:00+00:00"
        self.assertEqual(build_routes([item], "SVO", "LED", DAY), [])

    def test_percentile_nearest_rank(self):
        self.assertEqual(percentile([100, 200, 300, 400, 500], 95), 500)
        self.assertEqual(percentile([100, 200, 300, 400, 500], 50), 300)

    def test_async_supplier_retries_after_500(self):
        class Response:
            def __init__(self, code): self.status_code = code
            def json(self): return {"flights": [{"flight_number": "ok"}]}
        class Client:
            calls = 0
            async def get(self, url):
                self.calls += 1
                return Response(500 if self.calls == 1 else 200)
        client = Client()
        result = asyncio.run(get_supplier_async(client, "P1", "http://x", DAY))
        self.assertEqual(client.calls, 2)
        self.assertEqual(result[0]["flight_number"], "ok")

    def test_sync_supplier_retries_after_500(self):
        class Response:
            def __init__(self, code): self.status_code = code
            def json(self): return {"flights": [{"flight_number": "ok"}]}
        calls = []
        def fake_get(url, timeout):
            calls.append(1)
            return Response(500 if len(calls) == 1 else 200)
        with patch("main.requests.get", fake_get), patch("main.time.sleep", lambda t: None):
            result = get_supplier_sync("P1", "http://x", DAY)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]["flight_number"], "ok")


if __name__ == "__main__":
    unittest.main()

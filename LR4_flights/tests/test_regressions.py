import unittest
from datetime import date
from test_lab4 import f
from route_builder import build_routes

class RouteRegressionTests(unittest.TestCase):
    def test_equal_routes_do_not_compare_dictionaries(self):
        flight = f(1,'SVO','LED',8,9,100)
        routes = build_routes([flight, dict(flight)],'SVO','LED',date(2026,11,10))
        self.assertEqual(len(routes),2)

    def test_two_transfers_and_six_hour_boundary(self):
        flights = [f(1,'SVO','KZN',1,2,10),f(2,'KZN','OVB',8,9,10),f(3,'OVB','LED',10,11,10)]
        routes = build_routes(flights,'SVO','LED',date(2026,11,10))
        self.assertEqual(routes[0]['transfers'],2)
        flights[1]['departs_at']='2026-11-10T08:01:00+00:00'
        self.assertEqual(build_routes(flights,'SVO','LED',date(2026,11,10)),[])

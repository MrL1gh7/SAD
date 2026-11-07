import unittest
from datetime import timedelta
import test_domain
from domain import InvalidValue, InvariantViolation, TransitionNotAllowed

class RegressionTests(unittest.TestCase):
    setUp = test_domain.ParkingTests.setUp
    create = test_domain.ParkingTests.create
    def parked(self):
        s = self.create()
        self.p.check_entry(s.id)
        self.p.open_gate_and_park(s.id)
        return s

    def test_reservations_are_unique(self):
        sessions = [self.create(str(i)) for i in range(4)]
        for s in sessions:
            self.p.check_entry(s.id)
        self.assertEqual(len({s.spot_id for s in sessions[:3]}), 3)
        self.assertEqual(sessions[3].state, 'Отклонена')

    def test_extra_payment_covers_elapsed_hours(self):
        s = self.parked()
        self.clock.move(hours=1)
        self.p.pay(s.id)
        self.clock.move(hours=5)
        self.p.tick()
        self.p.pay(s.id)
        self.assertEqual(s.cost, 600)

    def test_failed_leave_keeps_all_data(self):
        s = self.parked()
        self.p.pay(s.id)
        self.p.leave(s.id)
        before, exit_at = s.as_dict(), s.exit_at
        with self.assertRaises(TransitionNotAllowed):
            self.p.leave(s.id)
        self.assertEqual(s.as_dict(), before)
        self.assertEqual(s.exit_at, exit_at)

    def test_wrong_payment_type_keeps_state(self):
        s = self.parked()
        before = s.as_dict()
        with self.assertRaises(InvalidValue):
            s.pay(1.5, self.clock.now())
        self.assertEqual(s.as_dict(), before)

    def test_timer_cannot_expire_early(self):
        s = self.parked()
        self.p.pay(s.id)
        before = s.as_dict()
        with self.assertRaises(InvariantViolation):
            s.expire_exit_time(self.clock.now())
        self.assertEqual(s.as_dict(), before)

    def test_forbidden_in_three_states(self):
        s = self.create()
        for prepare, action in [
            (lambda: None, lambda: self.p.open_gate_and_park(s.id)),
            (lambda: self.p.check_entry(s.id), lambda: self.p.pay(s.id)),
            (lambda: self.p.open_gate_and_park(s.id), lambda: self.p.leave(s.id)),
        ]:
            prepare()
            before = s.as_dict()
            with self.assertRaises(TransitionNotAllowed):
                action()
            self.assertEqual(s.as_dict(), before)

class HttpTests(unittest.TestCase):
    def setUp(self):
        import app
        from service import ParkingProcess, MemoryPaymentGateway
        from test_domain import FixedClock
        app.service = ParkingProcess(FixedClock(), MemoryPaymentGateway())
        self.client = app.app.test_client()

    def test_http_scenarios(self):
        c = self.client
        self.assertEqual(c.get('/health').status_code, 200)
        self.assertEqual(c.get('/sessions/999').status_code, 404)
        self.assertEqual(c.post('/sessions', json={'car_number': ''}).status_code, 422)
        sid = c.post('/sessions', json={'car_number':'TEST'}).json['id']
        for event in ['park','pay','leave']:
            self.assertEqual(c.post(f'/sessions/{sid}/{event}', json={}).status_code,409)
        for event in ['check','park','pay','leave']:
            self.assertEqual(c.post(f'/sessions/{sid}/{event}', json={}).status_code,200)

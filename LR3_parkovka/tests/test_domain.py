import sys
import unittest
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service import ParkingProcess, MemoryPaymentGateway
from domain import TransitionNotAllowed, InvalidValue


class FixedClock:
    def __init__(self):
        from datetime import datetime, timezone
        self.value = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)

    def now(self):
        return self.value

    def move(self, **kwargs):
        self.value += timedelta(**kwargs)


class ParkingTests(unittest.TestCase):
    def setUp(self):
        self.clock = FixedClock()
        self.p = ParkingProcess(self.clock, MemoryPaymentGateway())

    def create(self, number="А123ВС"):
        return self.p.receive_number(number)

    def test_main_path(self):
        s = self.create()
        self.p.check_entry(s.id)
        self.p.open_gate_and_park(s.id)
        self.clock.move(hours=1, minutes=20)
        self.p.pay(s.id)
        self.assertEqual(s.cost, 200)
        self.p.leave(s.id)
        self.assertEqual(s.state, "Завершена")
        self.assertFalse(self.p.spots[s.spot_id].occupied)

    def test_blocked(self):
        s = self.create("А777АА")
        self.p.check_entry(s.id)
        self.assertEqual(s.state, "Отклонена")

    def test_timer_and_extra_payment(self):
        s = self.create()
        self.p.check_entry(s.id)
        self.p.open_gate_and_park(s.id)
        self.p.pay(s.id)
        self.clock.move(minutes=16)
        self.p.tick()
        self.assertEqual(s.state, "Требует доплаты")
        self.p.pay(s.id)
        self.assertEqual(s.state, "Оплачена")
        self.p.leave(s.id)
        self.assertEqual(s.state, "Завершена")

    def test_invalid_transitions_do_not_change_state(self):
        s = self.create()
        for action in [lambda: self.p.pay(s.id), lambda: self.p.leave(s.id)]:
            with self.assertRaises(TransitionNotAllowed):
                action()
            self.assertEqual(s.state, "Проверяется")
        self.p.check_entry(s.id)
        with self.assertRaises(TransitionNotAllowed):
            self.p.pay(s.id)
        self.assertEqual(s.state, "Допущена")

    def test_payment_error_no_transition(self):
        s = self.create()
        self.p.check_entry(s.id)
        self.p.open_gate_and_park(s.id)
        from domain import InvariantViolation
        with self.assertRaises(InvariantViolation):
            self.p.pay(s.id, False)
        self.assertEqual(s.state, "Припаркована")

    def test_noninterrupting_timer(self):
        s = self.create()
        self.p.check_entry(s.id)
        self.p.open_gate_and_park(s.id)
        self.clock.move(days=8)
        self.p.tick()
        self.assertEqual(s.state, "Припаркована")
        self.assertEqual(sum(x.name == "Уведомить оператора" for x in s.events), 1)
        self.p.tick()
        self.assertEqual(sum(x.name == "Уведомить оператора" for x in s.events), 1)


if __name__ == "__main__":
    unittest.main()

"""Прикладной сервис, часы, хранилища и заглушка оплаты. Без Flask."""
from datetime import datetime, timezone, timedelta
from typing import Protocol

from domain import (ParkingSpot, ParkingSession, HourlyRate, NotFound,
                    InvariantViolation, InvalidValue, GatewayUnresolved)


class Clock(Protocol):
    def now(self) -> datetime: ...


class PaymentGateway(Protocol):
    def charge(self, session_id: int, amount: int) -> bool: ...


class AppClock:
    def __init__(self):
        self.offset = timedelta(0)

    def now(self):
        return datetime.now(timezone.utc) + self.offset

    def set_now(self, requested):
        if requested.tzinfo is None:
            requested = requested.replace(tzinfo=timezone.utc)
        if requested < self.now():
            raise InvalidValue("Перевод часов назад запрещён")
        self.offset = requested - datetime.now(timezone.utc)


class MemoryPaymentGateway:
    def __init__(self):
        self.payments = []
        self.fail_next = False

    def charge(self, session_id, amount):
        if self.fail_next:
            self.fail_next = False
            return False
        self.payments.append({"session_id": session_id, "rubles": amount})
        return True


class ParkingProcess:
    def __init__(self, clock: Clock, gateway: PaymentGateway):
        self.clock = clock
        self.gateway = gateway
        self.spots = {i: ParkingSpot(i) for i in range(1, 4)}
        self.sessions = {}  # Репозиторий в памяти, как в ЛР №2.
        self.next_id = 1
        self.blocked_cars = {"А777АА"}
        self.rate = HourlyRate(100)  # Тариф из ЛР №2.

    def get(self, session_id):
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFound("Парковочная сессия не найдена")
        return session

    # Отдельные предикаты для исключающих шлюзов.
    def is_blocked(self, number):
        return number in self.blocked_cars

    def has_free_spot(self):
        return any(self.spot_available(spot) for spot in self.spots.values())

    def spot_available(self, spot):
        return not spot.occupied and not any(
            s.spot_id == spot.id and s.state == "Допущена"
            for s in self.sessions.values()
        )

    def is_paid(self, session):
        return session.state == "Оплачена"

    def receive_number(self, number):
        now = self.clock.now()
        session = ParkingSession(self.next_id, number, now)
        self.sessions[session.id] = session
        self.next_id += 1
        return session

    def check_entry(self, session_id):
        session = self.get(session_id)
        now = self.clock.now()
        # Шлюз №1: в блок-листе / не в блок-листе.
        if self.is_blocked(session.number):
            session.reject("Машина заблокирована", now)
            return session
        # Шлюз №2: свободные места есть / нет.
        if not self.has_free_spot():
            session.reject("Нет свободных мест", now)
            return session
        for spot in self.spots.values():
            if self.spot_available(spot):
                session.admit(spot.id, now)
                return session
        raise GatewayUnresolved("Не удалось назначить парковочное место")

    def open_gate_and_park(self, session_id):
        session = self.get(session_id)
        # Сначала проверяем допустимость, иначе место могло бы заняться ошибочно.
        if "park" not in session.allowed_events:
            session.park(self.clock.now())  # выбросит TransitionNotAllowed
        spot = self.spots[session.spot_id]
        spot.occupy()
        session.park(self.clock.now())
        session.record("Открыть шлагбаум", self.clock.now(), "Парковка началась")
        return session

    def calculate_payment(self, session):
        # Из ЛР №2: целое количество часов, округлённое вверх.
        return session.calculate_cost(self.clock.now(), self.rate)

    def pay(self, session_id, success=True):
        session = self.get(session_id)
        now = self.clock.now()
        extra = session.state == "Требует доплаты"
        event = "extra_pay" if extra else "pay"
        if event not in session.allowed_events:
            # вызываем метод, чтобы получить правильное исключение 409
            session.pay(0, now, extra=extra)
        amount = max(0, self.calculate_payment(session) - session.cost)
        if not success:
            self.gateway.fail_next = True  # Учебная заглушка без настоящих списаний.
        if not self.gateway.charge(session.id, amount):
            raise InvariantViolation("Платёж не прошёл")
        session.pay(amount, now, extra)
        return session

    def leave(self, session_id):
        session = self.get(session_id)
        now = self.clock.now()
        # Дополнительная проверка, если таймер ещё не вызывался вручную.
        if session.state == "Оплачена" and now > session.exit_deadline:
            raise InvariantViolation("15 минут на выезд уже прошли; требуется доплата")
        if "leave" not in session.allowed_events:
            session.leave(now)  # правильный 409
        session.leave(now)
        self.spots[session.spot_id].release()
        session.record("Открыть шлагбаум на выезде", now, "Место освобождено")
        return session

    def on_exit_window_expired(self, now):
        for session in self.sessions.values():
            if (session.state == "Оплачена" and session.exit_deadline is not None
                    and now > session.exit_deadline):
                session.expire_exit_time(now)

    def on_overstay_7_days(self, now):
        for session in self.sessions.values():
            session.notify_7_days(now)

    def tick(self, requested=None):
        if requested is not None:
            self.clock.set_now(requested)
        now = self.clock.now()
        self.on_exit_window_expired(now)
        self.on_overstay_7_days(now)
        return {"now": now.isoformat(), "checked": len(self.sessions)}


# Имя прикладного сервиса из предыдущей лабораторной.
ParkingService = ParkingProcess

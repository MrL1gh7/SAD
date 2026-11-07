"""ЛР №3. Простая доменная модель парковки, развитие ЛР №2."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil


class DomainError(Exception):
    pass


class InvalidValue(DomainError):
    pass


class InvariantViolation(DomainError):
    pass


class NotFound(DomainError):
    pass


class GatewayUnresolved(DomainError):
    pass


class TransitionNotAllowed(DomainError):
    def __init__(self, state, event):
        super().__init__(f"Событие {event} запрещено в состоянии «{state}»")


@dataclass(frozen=True)
class CarNumber:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not self.value.strip():
            raise InvalidValue("Номер автомобиля не должен быть пустым")


@dataclass(frozen=True)
class HourlyRate:
    rubles: int

    def __post_init__(self):
        if type(self.rubles) is not int or self.rubles <= 0:
            raise InvalidValue("Стоимость часа должна быть положительной")


@dataclass(frozen=True)
class ParkingPeriod:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end < self.start:
            raise InvalidValue("Время выезда не может быть раньше въезда")


@dataclass(frozen=True)
class ParkingCost:
    rubles: int

    def __post_init__(self):
        if type(self.rubles) is not int or self.rubles < 0:
            raise InvalidValue("Стоимость не может быть отрицательной")


@dataclass(frozen=True)
class DomainEvent:
    name: str
    at: str
    details: str


# Объект места из ЛР №2: методы occupy() и release() сохранены.
class ParkingSpot:
    def __init__(self, spot_id):
        if type(spot_id) is not int or spot_id <= 0:
            raise InvalidValue("Номер места должен быть положительным")
        self.__id = spot_id
        self.__occupied = False

    @property
    def id(self):
        return self.__id

    @property
    def occupied(self):
        return self.__occupied

    def occupy(self):
        if self.__occupied:
            raise InvariantViolation("Место уже занято")
        self.__occupied = True

    def release(self):
        if not self.__occupied:
            raise InvariantViolation("Место уже свободно")
        self.__occupied = False


class ParkingState:
    name = ""
    allowed = frozenset()

    def admit(self, session):
        raise TransitionNotAllowed(self.name, "admit")

    def reject(self, session):
        raise TransitionNotAllowed(self.name, "reject")

    def park(self, session):
        raise TransitionNotAllowed(self.name, "park")

    def pay(self, session):
        raise TransitionNotAllowed(self.name, "pay")

    def extra_pay(self, session):
        raise TransitionNotAllowed(self.name, "extra_pay")

    def expire_exit_time(self, session):
        raise TransitionNotAllowed(self.name, "expire_exit_time")

    def leave(self, session):
        raise TransitionNotAllowed(self.name, "leave")


class Checking(ParkingState):
    name = "Проверяется"
    allowed = frozenset({"admit", "reject"})

    def admit(self, session):
        return Admitted()

    def reject(self, session):
        return Rejected()


class Admitted(ParkingState):
    name = "Допущена"
    allowed = frozenset({"park"})

    def park(self, session):
        return Parked()


class Parked(ParkingState):
    name = "Припаркована"
    allowed = frozenset({"pay"})

    def pay(self, session):
        return Paid()


class Paid(ParkingState):
    name = "Оплачена"
    allowed = frozenset({"leave", "expire_exit_time"})

    def expire_exit_time(self, session):
        return ExtraDue()

    def leave(self, session):
        if session.exit_deadline is None or session.exit_at > session.exit_deadline:
            raise InvariantViolation("15 минут на выезд уже прошли")
        return Completed()


class ExtraDue(ParkingState):
    name = "Требует доплаты"
    allowed = frozenset({"extra_pay"})

    def extra_pay(self, session):
        return Paid()


class Completed(ParkingState):
    name = "Завершена"


class Rejected(ParkingState):
    name = "Отклонена"


# Агрегат ParkingSession продолжает одноимённый агрегат из ЛР №2.
# Вместо простого поля closed теперь используется объект класса состояния.
class ParkingSession:
    def __init__(self, session_id, number, created_at):
        self.__id = session_id
        self.__car = CarNumber(number)
        self.__spot_id = None
        self.__start = None
        self.__end = None
        self.__cost = ParkingCost(0)
        self.__state = Checking()
        self.__events = []
        self.exit_deadline = None
        self.exit_at = None
        self.last_payment_at = None
        self.notified_overstay = False
        self.record("Номер получен", created_at, number)

    @property
    def id(self):
        return self.__id

    @property
    def number(self):
        return self.__car.value

    @property
    def spot_id(self):
        return self.__spot_id

    @property
    def state(self):
        return self.__state.name

    @property
    def allowed_events(self):
        return sorted(self.__state.allowed)

    @property
    def events(self):
        return list(self.__events)

    @property
    def start(self):
        return self.__start

    @property
    def closed(self):
        return self.__end is not None

    @property
    def cost(self):
        return self.__cost.rubles

    def record(self, name, now, details=""):
        self.__events.append(DomainEvent(name, now.isoformat(), str(details)))

    def _change(self, event, now):
        # Только здесь состояние меняется через метод события.
        self.__state = getattr(self.__state, event)(self)
        self.record(event, now, "Состояние: " + self.state)

    def admit(self, spot_id, now):
        # Сначала проверяем событие, затем запоминаем место.
        if "admit" not in self.__state.allowed:
            self.__state.admit(self)  # точная ошибка TransitionNotAllowed
        self.__spot_id = spot_id
        self._change("admit", now)

    def reject(self, reason, now):
        self._change("reject", now)
        self.record("Причина отказа", now, reason)

    def park(self, now):
        self._change("park", now)
        self.__start = now

    def pay(self, amount, now, extra=False):
        event = "extra_pay" if extra else "pay"
        # Проверка события нужна до начисления суммы.
        if event not in self.__state.allowed:
            getattr(self.__state, event)(self)
        if type(amount) is not int or amount < 0:
            raise InvalidValue("Оплата не может быть отрицательной")
        self._change(event, now)
        self.__cost = ParkingCost(self.cost + amount)
        self.last_payment_at = now
        self.exit_deadline = now + timedelta(minutes=15)
        self.record("Деньги приняты", now, f"{amount} руб.; выезд до {self.exit_deadline.isoformat()}")

    def expire_exit_time(self, now):
        if "expire_exit_time" in self.allowed_events and now <= self.exit_deadline:
            raise InvariantViolation("15 минут на выезд ещё не прошли")
        self._change("expire_exit_time", now)

    def leave(self, now):
        previous_exit_at = self.exit_at
        self.exit_at = now
        try:
            self._change("leave", now)
        except DomainError:
            self.exit_at = previous_exit_at
            raise
        self.__end = now

    def calculate_cost(self, now, rate):
        if self.__start is None:
            raise InvariantViolation("Парковка ещё не началась")
        period = ParkingPeriod(self.__start, now)
        hours = ceil((period.end - period.start).total_seconds() / 3600)
        return ParkingCost(hours * rate.rubles).rubles

    def notify_7_days(self, now):
        if self.__start is not None and not self.closed and not self.notified_overstay:
            if now > self.__start + timedelta(days=7):
                self.notified_overstay = True
                self.record("Уведомить оператора", now, "Автомобиль стоит больше 7 суток")

    def as_dict(self):
        return {
            "id": self.id,
            "car_number": self.number,
            "spot_id": self.spot_id,
            "state": self.state,
            "allowed_events": self.allowed_events,
            "cost": self.cost,
            "exit_deadline": self.exit_deadline.isoformat() if self.exit_deadline else None,
            "events": [vars(event) for event in self.events],
        }

"""Простой Flask-адаптер для ЛР №3. Вся логика хранится в domain.py и service.py."""
import logging
import os
from datetime import datetime
from flask import Flask, jsonify, request

from domain import (DomainError, TransitionNotAllowed, InvalidValue,
                    InvariantViolation, NotFound, GatewayUnresolved)
from service import AppClock, MemoryPaymentGateway, ParkingProcess

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
service = ParkingProcess(AppClock(), MemoryPaymentGateway())


@app.errorhandler(DomainError)
def handle_domain_error(error):
    status = 422
    if isinstance(error, TransitionNotAllowed):
        status = 409
    elif isinstance(error, NotFound):
        status = 404
    elif isinstance(error, GatewayUnresolved):
        status = 500
    return jsonify({"error": type(error).__name__, "message": str(error)}), status


@app.errorhandler(400)
def handle_bad_json(error):
    return jsonify({"error": "InvalidValue", "message": "Неверный JSON"}), 422


def body():
    value = request.get_json(silent=True)
    if value is None or not isinstance(value, dict):
        raise InvalidValue("Нужно передать JSON-объект")
    return value


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/sessions")
def create_session():
    data = body()
    number = data.get("car_number", "")
    if not isinstance(number, str):
        raise InvalidValue("Номер должен быть строкой")
    # Не распознан камерой: оператор вводит номер через этот же маршрут.
    result = service.receive_number(number)
    return jsonify(result.as_dict()), 201


@app.get("/sessions/<int:session_id>")
def get_session(session_id):
    return jsonify(service.get(session_id).as_dict())


@app.post("/sessions/<int:session_id>/check")
def check(session_id):
    return jsonify(service.check_entry(session_id).as_dict())


@app.post("/sessions/<int:session_id>/park")
def park(session_id):
    return jsonify(service.open_gate_and_park(session_id).as_dict())


@app.post("/sessions/<int:session_id>/pay")
def pay(session_id):
    data = body()
    success = data.get("success", True)
    if type(success) is not bool:
        raise InvalidValue("success должен быть true или false")
    return jsonify(service.pay(session_id, success).as_dict())


@app.post("/sessions/<int:session_id>/leave")
def leave(session_id):
    return jsonify(service.leave(session_id).as_dict())


@app.post("/internal/tick")
def tick():
    data = body()
    try:
        requested = datetime.fromisoformat(data["now"].replace("Z", "+00:00")) if "now" in data else None
    except (ValueError, AttributeError, TypeError):
        raise InvalidValue("Нужно время в формате ISO 8601")
    return jsonify(service.tick(requested))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", "5000")))

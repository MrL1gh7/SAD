import os
from datetime import datetime

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy


# Создаём Flask-приложение
app = Flask(__name__)

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]


app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# Создаём объект SQLAlchemy
db = SQLAlchemy(app)


# Описываем таблицу visits
class Visit(db.Model):
    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)
    visit_time = db.Column(db.DateTime, nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)


# Создаём таблицы при запуске приложения
with app.app_context():
    db.create_all()


# Маршрут GET /hello
@app.route("/hello", methods=["GET"])
def hello():
    # Получаем текущее время
    current_time = datetime.now()

    # Получаем IP клиента
    client_ip = request.remote_addr

    # Создаём новую запись
    visit = Visit(
        visit_time=current_time,
        ip_address=client_ip
    )

    # Сохраняем запись в базе
    db.session.add(visit)
    db.session.commit()

    
    return "Hello", 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
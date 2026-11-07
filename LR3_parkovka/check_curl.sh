#!/bin/sh
# Запуск после: docker compose up --build
# Тесты рассчитаны на свежезапущенное приложение (ID = 1, 2, ...).
set -e
URL=http://localhost:5000
json='Content-Type: application/json'

echo '1. Здоровье'
curl -i "$URL/health"
echo '2. Основной путь: въезд, проверка, парковка, оплата, выезд'
curl -i -X POST "$URL/sessions" -H "$json" -d '{"car_number":"А123ВС"}'
curl -i -X POST "$URL/sessions/1/check"
curl -i -X POST "$URL/sessions/1/park"
curl -i -X POST "$URL/sessions/1/pay" -H "$json" -d '{}'
curl -i -X POST "$URL/sessions/1/leave"
curl -i "$URL/sessions/1"

echo '3. Заблокированная машина'
curl -i -X POST "$URL/sessions" -H "$json" -d '{"car_number":"А777АА"}'
curl -i -X POST "$URL/sessions/2/check"

echo '4. Таймер: оплачена, но не выехала вовремя'
curl -i -X POST "$URL/sessions" -H "$json" -d '{"car_number":"М456ОР"}'
curl -i -X POST "$URL/sessions/3/check"
curl -i -X POST "$URL/sessions/3/park"
curl -i -X POST "$URL/sessions/3/pay" -H "$json" -d '{}'
FUTURE=$(python -c 'from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat())')
curl -i -X POST "$URL/internal/tick" -H "$json" -d "{\"now\":\"$FUTURE\"}"
curl -i "$URL/sessions/3"
curl -i -X POST "$URL/sessions/3/pay" -H "$json" -d '{}'
curl -i -X POST "$URL/sessions/3/leave"

echo '5. Три недопустимых события: все должны вернуть 409'
curl -i -X POST "$URL/sessions" -H "$json" -d '{"car_number":"Н999КК"}'
curl -i -X POST "$URL/sessions/4/park"
curl -i -X POST "$URL/sessions/4/pay" -H "$json" -d '{}'
curl -i -X POST "$URL/sessions/4/leave"
curl -i "$URL/sessions/4"

echo '6. Ошибка 422 и 404'
curl -i -X POST "$URL/sessions" -H "$json" -d '{"car_number":""}'
curl -i "$URL/sessions/999"

# Платная парковка

Запуск из папки проекта:

```sh
docker compose up -d --build
docker compose ps
curl -f http://localhost:5000/health
```

Тесты внутри Docker:

```sh
docker compose run --rm --no-deps -v "$PWD:/tests" -w /tests parking python -m unittest discover -s tests -v
```

HTTP-проверки на новом процессе приложения: `sh check_curl.sh`.

# Поиск авиарейсов

Запуск из папки проекта:

```sh
docker compose up -d --build
docker compose ps
curl -f http://localhost:8000/health
```

Тесты внутри Docker:

```sh
docker compose run --rm --no-deps -v "$PWD:/tests" -w /tests search python -m unittest discover -s tests -v
```

Нагрузочный клиент: `python -m pip install httpx==0.28.1`. Замеры: `sh run_benchmarks.sh`. Профили: `sh profile_sync.sh`. Результаты создаются в results и не публикуются в Git.

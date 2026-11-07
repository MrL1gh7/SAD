#!/bin/sh
# Два профиля синхронной версии при C=10, по 60 секунд каждый.
set -eu
cd "$(dirname "$0")"
mkdir -p results
MODE=sync docker compose up -d --build --force-recreate search
until curl -fsS http://localhost:8000/health >/dev/null; do sleep 2; done
for variant in cpu idle; do
    echo "Снимаем профиль: $variant"
    python load.py --mode closed --clients 10 --warmup 10 --duration 60 --output results/profiles_load.csv &
    load_pid=$!
    sleep 10
    if [ "$variant" = idle ]; then
        docker compose exec -T -u root search py-spy record -o /tmp/profile_idle.svg --pid 1 --duration 60 --idle
        docker compose cp search:/tmp/profile_idle.svg ./results/profile_idle.svg
    else
        docker compose exec -T -u root search py-spy record -o /tmp/profile_cpu.svg --pid 1 --duration 60
        docker compose cp search:/tmp/profile_cpu.svg ./results/profile_cpu.svg
    fi
    wait "$load_pid"
done
printf 'Готово: results/profile_cpu.svg и results/profile_idle.svg\n'

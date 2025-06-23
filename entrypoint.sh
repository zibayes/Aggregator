#!/bin/bash
echo "Starting entrypoint script..."

# Запуск Django в фоне
python manage.py runserver 0.0.0.0:8000 &

# Явная проверка доступности брокера перед запуском Celery
echo "Waiting for broker..."
for i in {1..10}; do
  if celery -A archeology inspect ping; then
    echo "Broker is available."
    break
  fi
  echo "Waiting for broker... ($i/10)"
  sleep 3
done

echo "Starting Celery worker..."
celery -A archeology worker --loglevel=info &

# Держим скрипт активным
wait -n
exit $?
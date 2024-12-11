start cmd /k celery -A archeology worker --loglevel=info -P eventlet
uvicorn archeology.asgi:application --host 127.0.0.1 --port 8000

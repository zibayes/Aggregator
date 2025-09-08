REM --- Сброс схемы базы данных ---
docker-compose exec db psql -U postgres -c "DROP SCHEMA public CASCADE;"
docker-compose exec db psql -U postgres -c "CREATE SCHEMA public;"

REM --- Удаляем все миграции приложения agregator, кроме __init__.py ---
docker-compose exec app sh -c "find agregator/migrations -type f ! -name '__init__.py' -delete"

REM --- Создаем миграции для всего проекта ---
docker-compose exec app python manage.py makemigrations

REM --- Применяем миграции ---
docker-compose exec app python manage.py migrate

REM --- Создаем суперпользователя ---
set USERNAME=admin
set EMAIL=admin@example.com
set PASSWORD=admin
docker-compose exec app sh -c "DJANGO_SUPERUSER_PASSWORD=%PASSWORD% python manage.py createsuperuser --username=%USERNAME% --email=%EMAIL% --noinput"

pause
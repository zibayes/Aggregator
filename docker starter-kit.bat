docker-compose exec db psql -U postgres -c "DROP SCHEMA public CASCADE;"
docker-compose exec db psql -U postgres -c "CREATE SCHEMA public;"
docker-compose exec app rm agregator/migrations/0001_initial.py
docker-compose exec app python manage.py makemigrations
docker-compose exec app python manage.py migrate
set USERNAME=admin
set EMAIL=admin@example.com
set PASSWORD=admin
docker-compose exec app sh -c "DJANGO_SUPERUSER_PASSWORD=%PASSWORD% python manage.py createsuperuser --username=%USERNAME% --email=%EMAIL% --noinput"
pause
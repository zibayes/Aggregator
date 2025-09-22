#!/bin/bash
set -e  # Exit on error

# Принудительно set правильный settings (override yml/env)
export DJANGO_SETTINGS_MODULE="archeology.settings"  # Точно, из ls archeology/settings.py
POSTGRES_HOST="${DB_HOST:-${POSTGRES_HOST:-db}}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-admin}"
POSTGRES_DB="${POSTGRES_DB:-postgres}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "=== ENTRYPOINT START ==="
echo "Env: DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"  # Теперь точно archeology.settings
echo "DB: $POSTGRES_HOST:$POSTGRES_PORT (user=$POSTGRES_USER, db=$POSTGRES_DB, pass=***)"
echo "Redis: $REDIS_HOST:$REDIS_PORT"
echo "PWD: $(pwd)"
echo "--- /app contents (code check): ---"
ls -la /app/ | grep -E "(manage.py|archeology|agregator)"
echo "--- /app/init (flag dir): ---"
ls -la /app/init/ 2>/dev/null || echo "Init dir empty/new"

# Wait Redis
wait_for_redis() {
    echo "=== Wait Redis ==="
    for i in {1..10}; do
        echo "Redis try $i"
        if timeout 5 redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>&1 | grep -q "PONG"; then
            echo "Redis OK!"
            return 0
        fi
        sleep 2
    done
    echo "Redis ERROR!"
    exit 1
}

# Wait DB (sleep)
wait_for_db() {
    echo "=== Wait DB (sleep 10s) ==="
    sleep 10
    echo "DB ready!"
}

# Django Init
do_django_init() {
    echo "=== Django Init ==="
    cd /app || exit 1
    if [ ! -f manage.py ]; then
        echo "ERROR: No manage.py!"
        exit 1
    fi
    echo "manage.py found."

    # Delete migrations
    if [ -d agregator/migrations ]; then
        find agregator/migrations -type f ! -name '__init__.py' -delete
        echo "Migrations deleted."
    else
        echo "No agregator/migrations."
    fi

    # Makemigrations
    echo "python manage.py makemigrations"
    python manage.py makemigrations || { echo "Makemigrations failed!"; exit 1; }
    echo "Makemigrations OK."

    # Migrate
    echo "python manage.py migrate"
    python manage.py migrate || { echo "Migrate failed!"; exit 1; }
    echo "Migrate OK."

    # Superuser
    echo "Creating superuser..."
    python manage.py shell -c "
import os
os.environ['DJANGO_SETTINGS_MODULE'] = '$DJANGO_SETTINGS_MODULE'
from django.contrib.auth import get_user_model
User  = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created')
else:
    print('Superuser exists')
" || echo "Superuser warn."

    # Flag
    mkdir -p /app/init
    touch /app/init/.django_init_done
    echo "Init done!"
}

# Main
if [ ! -f /app/init/.django_init_done ]; then
    echo "No flag — full init."
    wait_for_redis
    wait_for_db
    do_django_init
else
    echo "Flag exists — skip init."
fi

echo "=== Supervisord start ==="
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
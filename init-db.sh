#!/bin/bash
set -e

# Копируем конфиги после инициализации БД
cp /etc/postgresql/postgresql.conf /var/lib/postgresql/data/
cp /etc/postgresql/pg_hba.conf /var/lib/postgresql/data/

# Перезагружаем конфигурацию
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT pg_reload_conf();
EOSQL
#!/bin/bash
set -e

# Сброс схемы public
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO postgres;
    GRANT ALL ON SCHEMA public TO public;
EOSQL

# Копируем конфиги после инициализации БД
cp /etc/postgresql/postgresql.conf /var/lib/postgresql/data/
cp /etc/postgresql/pg_hba.conf /var/lib/postgresql/data/

# Перезагружаем конфигурацию
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT pg_reload_conf();
EOSQL

echo "DB init completed: Schema reset and configs applied."
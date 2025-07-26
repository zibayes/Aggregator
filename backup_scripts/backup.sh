#!/bin/sh
DATE=$(date +%Y%m%d_%H%M%S)
export PGPASSWORD="$POSTGRES_PASSWORD"

echo "[$(date)] Starting backup..." >> /var/log/backup.log

pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -F c -b -v -f "/backups/db_${DATE}.dump" "$POSTGRES_DB" 2>> /var/log/backup.log

# Удаляем старые бэкапы (храним 7 последних)
find /backups -name "*.dump" -type f -mtime +7 -delete >> /var/log/backup.log 2>&1

echo "[$(date)] Backup completed: /backups/db_${DATE}.dump" >> /var/log/backup.log
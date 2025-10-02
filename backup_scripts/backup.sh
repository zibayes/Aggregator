#!/bin/sh
DATE=$(date +%Y%m%d_%H%M%S)
export PGPASSWORD="$POSTGRES_PASSWORD"
LOG="/var/log/backup.log"

echo "[$(date)] Starting backup..." >> $LOG

# 1. Делаем бэкап
pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -F c -b -v -f "/backups/db_${DATE}.dump" "$POSTGRES_DB" 2>> $LOG

# 2. Создаём symlink на последний бэкап (для проверки)
ln -sf "/backups/db_${DATE}.dump" /backups/latest.dump

# 3. Удаляем старые бэкапы (оставляем 7)
find /backups -name "db_*.dump" -type f -mtime +7 -delete >> $LOG 2>&1

# 4. Проверяем восстановление
echo "[$(date)] Testing restore..." >> $LOG
if ! pg_restore -U "$POSTGRES_USER" -d postgres_test /backups/latest.dump 2>> $LOG; then
  echo "[$(date)] RESTORE FAILED! Check $LOG" >> $LOG
  # Отправляем email (адаптируй под свой SMTP)
  # echo "Subject: Бэкап БД сломался! Проверь логи" | sendmail -t "твой_email@example.com"
  exit 1
fi

echo "[$(date)] Backup completed: /backups/db_${DATE}.dump" >> $LOG
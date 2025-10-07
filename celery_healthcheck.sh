#!/bin/bash
set -e

# Проверяем, что Celery worker запущен
celery -A archeology inspect ping | grep -q "OK" && exit 0 || exit 1
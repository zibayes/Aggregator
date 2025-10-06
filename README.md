# 🌐 Проект Aggregator - Веб-приложение с геопространственными данными и управлением документами

## 📌 Обзор
Полноценное веб-приложение для работы с геопространственными данными, включающее систему управления документами и совместной работы. Проект объединяет:

- Django-приложение с REST API
- Сервер векторных и растровых картографических тайлов
- Систему совместной работы с документами (Collabora Online)
- Файловый менеджер (KodExplorer)
- PostgreSQL с архивированием WAL и автоматическими бэкапами
- Redis для кэширования и в качестве брокера Celery

Архитектура спроектирована для **визуализации геопространственных данных**, **совместной работы с документами** и **надежного управления данными** с production-уровнем конфигурации.

---

## 🛠️ Требования
- Docker Engine 20.10+
- Docker Compose V2
- Не менее 4 ГБ оперативной памяти (рекомендуется 8 ГБ)
- 10 ГБ свободного места на диске
- Linux/macOS (для Windows требуется WSL2)

---

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/zibayes/Aggregator.git
cd archeology-project
```

### 2. Создание конфигурации окружения (опционально)
```bash
cp .env.example .env  # Если нужно указать кастомные настройки
```

### 3. Запуск приложения
```bash
docker-compose up -d --build
```

### 4. Проверка состояния сервисов
```bash
docker-compose ps
```

Все сервисы должны перейти в статус "Up" в течение 2-3 минут (время инициализации)

### 5. Доступ к приложению
- Основное приложение: http://localhost:8000
- Растровые тайлы карт: http://localhost:8090/raster/
- Векторные тайлы карт: http://localhost:8090/vector/
- Файловый менеджер: http://localhost:8080
- Collabora Online: http://localhost:9980

## 🧩 Системная архитектура

### Основные компоненты
| Сервис | Порт | Назначение |
|--------|------|------------|
| **app** | 8000 | Основное Django-приложение с REST API |
| **nginx-proxy** | 8090 | Обратный прокси для тайлов карт и статических ресурсов |
| **tileserver-gl** | - | Сервер векторных тайлов карт |
| **redis** | 6379 | Кэш и брокер сообщений Celery |
| **db** | - | База данных PostgreSQL с архивированием WAL |
| **backup** | - | Автоматическое резервное копирование БД |
| **kodexplorer** | 8080 | Файловый менеджер для управления документами |
| **collabora** | 9980 | Сервер совместной работы с документами |

## 🧪 Проверка работоспособности

### Проверка основного приложения
```bash
curl http://localhost:8000/health/
# Ожидаемый ответ: {"status":"ok"}
```

### Проверка PostgreSQL
```bash
docker-compose exec db psql -U postgres -c "SELECT version();"
```

### Проверка Redis
```bash
docker-compose exec redis redis-cli ping
# Ожидаемый ответ: PONG
```

## ⚙️ Конфигурация окружения

### Ключевые переменные окружения
| Переменная | Значение по умолчанию | Описание |
|------------|------------------------|----------|
| DEBUG | "1" | Режим отладки (0/1) |
| DB_HOST | db | Хост базы данных |
| POSTGRES_USER | postgres | Пользователь БД |
| POSTGRES_PASSWORD | admin | Пароль БД |
| POSTGRES_DB | postgres | Имя базы данных |
| REDIS_HOST | redis | Хост Redis |
| CELERY_BROKER_URL | redis://redis:6379/0 | URL брокера Celery |
| MAPS_BASE_URL | http://nginx-proxy | Базовый URL для карт |
| RASTER_TILES_URL | http://nginx-proxy/raster/{z}/{x}/{y}.png | URL растровых тайлов |
| VECTOR_TILES_URL | http://nginx-proxy/vector/{z}/{x}/{y}.pbf | URL векторных тайлов |

## 💾 Управление данными

### Важные тома (volumes)
| Том | Назначение |
|-----|------------|
| postgres_data | Основные данные PostgreSQL |
| postgres_data_test | Тестовые данные для бэкапов |
| app_init | Инициализационные скрипты приложения |
| ./backups | Резервные копии БД (автоматические бэкапы в 3:00) |
| ./wal_archive | Архив WAL-файлов PostgreSQL |
| ./uploaded_files | Загруженные пользовательские файлы |
| ./kodexplorer_config | Конфигурация файлового менеджера |

### Схема бэкапов
- Ежедневные бэкапы в 3:00 по местному времени
- Бэкапы хранятся в папке `./backups`
- Для восстановления используется скрипт `./backup_scripts/restore.sh`

## 🛠️ Настройка и кастомизация

### Изменение конфигурации Nginx
1. Отредактируйте файл `./nginx/nginx.conf`
2. Перезапустите nginx-proxy:
```bash
docker-compose restart nginx-proxy
```

## 🐛 Решение распространенных проблем

### 1. Приложение не запускается
```bash
docker-compose logs app
# Проверьте логи на наличие ошибок подключения к БД или Redis
```

### 2. Проблемы с тайлами карт
```bash
docker-compose logs nginx-proxy
# Проверьте пути к тайлам в конфигурации nginx
```

### 3. Ошибки при работе с файлами в KodExplorer
- Убедитесь, что том ./uploaded_files доступен для записи
- Проверьте права на папку:
```bash
sudo chown -R 1000:1000 ./uploaded_files
```

### 4. Проблемы с подключением Collabora
- Убедитесь, что `app` и `collabora` находятся в одной сети Docker
- Проверьте настройки `extra_params` в конфигурации collabora
- Убедитесь, что в `aliasgroup1` указан правильный хост приложения (в данном случае `http://app:8000`)
- Проверьте логи Collabora:
```bash
docker-compose logs collabora
```

### 5. Ошибки при запуске PostgreSQL
- Проверьте, не заняты ли порты (особенно 5432)
- Убедитесь, что том postgres_data имеет правильные права доступа
- Проверьте логи БД:
```bash
docker-compose logs db
```
- Если возникает ошибка "database is locked", удалите том и пересоздайте контейнер:
```bash
docker-compose down -v
docker-compose up -d --build
```

## 📦 Дополнительные команды

### Остановка всех сервисов
```bash
docker-compose down
```

### Полная очистка (включая данные)
```bash
docker-compose down -v --remove-orphans
```

### Обновление образов
```bash
docker-compose pull
docker-compose up -d --build
```

### Доступ к PostgreSQL
```bash
docker-compose exec db psql -U postgres
```

### Доступ к Redis CLI
```bash
docker-compose exec redis redis-cli
```
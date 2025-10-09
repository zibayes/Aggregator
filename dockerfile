# syntax=docker/dockerfile:1.4

# ==================== ЭТАП 1: Системные зависимости ====================
FROM python:3.12 as system-deps

# Устанавливаем альтернативные репозитории для Debian
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
        postgresql-client \
        redis-tools \
        netcat-openbsd \
        p7zip-full \
        unar \
        build-essential \
        wget \
        supervisor \
        curl \
        g++ \
        gcc \
        python3-dev \
        libpython3-dev \
        libpq-dev \
        libgl1 \
        tesseract-ocr \
        libtesseract-dev \
        libleptonica-dev \
        tesseract-ocr-rus \
        tesseract-ocr-eng \
        tk \
        tzdata && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем временную зону на Красноярск
ENV TZ=Asia/Krasnoyarsk
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

# ==================== ЭТАП 2: Python зависимости ====================
FROM python:3.12 as python-builder

# Копируем системные зависимости
COPY --from=system-deps /usr/lib/x86_64-linux-gnu/ /usr/lib/x86_64-linux-gnu/
COPY --from=system-deps /usr/bin/ /usr/bin/
COPY --from=system-deps /usr/include/ /usr/include/
COPY --from=system-deps /usr/bin/tesseract /usr/bin/
COPY --from=system-deps /usr/share/tesseract-ocr /usr/share/tesseract-ocr
COPY --from=system-deps /usr/lib/libtesseract.so* /usr/lib/

WORKDIR /app

# Установка Libreoffice
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends libreoffice libglib2.0-0

# Установка Python-зависимостей
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-build \
    pip install --upgrade pip && \
    pip install numpy cython && \
    pip install scipy --no-build-isolation && \
    pip install -r requirements.txt

# Установка дополнительных зависимостей
RUN pip install celery redis gunicorn

# Копируем приложение
# COPY . .

# Настройка логов
RUN mkdir -p /var/log && chmod -R 777 /var/log

# Убираем supervisord
# COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
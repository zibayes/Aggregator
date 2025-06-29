# syntax=docker/dockerfile:1.4

# ==================== ЭТАП 1: Системные зависимости ====================
FROM python:3.12 as system-deps

# Устанавливаем альтернативные репозитории для Debian
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    echo "deb http://mirror.yandex.ru/debian bookworm main" > /etc/apt/sources.list && \
    echo "deb http://mirror.yandex.ru/debian bookworm-updates main" >> /etc/apt/sources.list && \
    echo "deb http://mirror.yandex.ru/debian-security bookworm-security main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
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
        libreoffice \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

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

# Установка Python-зависимостей
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-build \
    pip install --upgrade pip && \
    pip install numpy cython && \
    pip install scipy --no-build-isolation && \
    pip install -r requirements.txt

RUN pip install celery redis
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing supervisor libreoffice

WORKDIR /app
# COPY . .

EXPOSE 8000

RUN mkdir -p /var/log && chmod -R 777 /var/log

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
CMD ["/usr/bin/supervisord"]

# CMD ["bash", "-c", "CMD ["bash", "-c", "python manage.py runserver 0.0.0.0:8000 & sleep 30 && celery -A archeology worker --loglevel=info & wait"]"]

# COPY entrypoint.sh /app/entrypoint.sh
# RUN chmod +x /app/entrypoint.sh
# CMD ["/app/entrypoint.sh"]
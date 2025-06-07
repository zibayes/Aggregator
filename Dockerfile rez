# Используем официальный образ Python
FROM archeology-app:latest

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем PowerShell и скачиваем python установщик
SHELL ["powershell", "-Command"]

RUN pip install --upgrade opencv-python

# Открываем порт, на котором будет работать приложение
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
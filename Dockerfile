FROM python:3.9-slim

# Устанавливаем Flask и requests (для API Mistral)
RUN pip install --no-cache-dir flask requests

WORKDIR /app

# Создаем папку (хоть docker-compose ее и перезапишет, это хорошая практика)
RUN mkdir -p /app/templates

# Копируем скрипт
COPY app.py .

# Открываем порт
EXPOSE 8182

CMD ["python", "app.py"]

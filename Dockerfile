FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY bot.py .
COPY .env .

# Создание папки для данных
RUN mkdir -p data

# Запуск бота
CMD ["python", "bot.py"]

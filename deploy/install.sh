#!/bin/bash
# Скрипт установки Axenta Billing Bot

set -e

BOT_DIR="/opt/axenta-bot"
SERVICE_NAME="axenta-bot"

echo "=== Установка Axenta Billing Bot ==="

# 1. Создание директории
echo "Создание директории..."
sudo mkdir -p $BOT_DIR
sudo chown $USER:$USER $BOT_DIR

# 2. Копирование файлов (выполнить вручную или через git clone)
echo "Скопируйте файлы бота в $BOT_DIR"
echo "  - main.py, config.py"
echo "  - handlers/, services/, models/, utils/"
echo "  - requirements.txt"
echo "  - credentials.json (Google API)"
echo "  - .env (переменные окружения)"

# 3. Создание виртуального окружения
echo "Создание виртуального окружения..."
cd $BOT_DIR
python3 -m venv venv
source venv/bin/activate

# 4. Установка зависимостей
echo "Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Установка systemd service
echo "Установка systemd service..."
sudo cp deploy/axenta-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# 6. Запуск
echo "Запуск бота..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo ""
echo "=== Готово! ==="
echo ""
echo "Полезные команды:"
echo "  sudo systemctl status $SERVICE_NAME   # Статус"
echo "  sudo systemctl restart $SERVICE_NAME  # Перезапуск"
echo "  sudo systemctl stop $SERVICE_NAME     # Остановка"
echo "  sudo journalctl -u $SERVICE_NAME -f   # Логи в реальном времени"

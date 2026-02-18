"""Конфигурация приложения"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Axenta API
AXENTA_API_URL = os.getenv('AXENTA_API_URL', 'https://axenta.cloud/')
AXENTA_CMS_URL = os.getenv('AXENTA_CMS_URL', 'https://cms.axenta.cloud/')
AXENTA_AUTH_ENDPOINT = os.getenv('AXENTA_AUTH_ENDPOINT', '/auth/login')

# Google Sheets
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials/service_account.json')

# Notifications
NOTIFICATION_CHECK_INTERVAL = int(os.getenv('NOTIFICATION_CHECK_INTERVAL', 3600))
NOTIFICATION_TIMEZONE = os.getenv('NOTIFICATION_TIMEZONE', 'Europe/Moscow')

# Google Sheets — дополнительные таблицы (Этап 2)
GOOGLE_SHEET_VYGR_ID = os.getenv('GOOGLE_SHEET_VYGR_ID')
GOOGLE_SHEET_DDS_ID = os.getenv('GOOGLE_SHEET_DDS_ID')

# Год начала доступной статистики
STATISTICS_START_YEAR = 2026

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

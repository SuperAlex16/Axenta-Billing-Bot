# Axenta Billing Telegram Bot

Telegram-бот для системы биллинга Axenta (ГЛОНАСС/GPS мониторинг).

## Функционал

- Регистрация пользователей через аутентификацию в API Axenta
- Просмотр информации о балансе аккаунта
- Настройка уведомлений при снижении баланса до порогового значения
- Хранение данных в Google Sheets

## Технологии

- Python 3.10+
- python-telegram-bot v20+
- gspread + google-auth (Google Sheets API)
- aiohttp (асинхронные HTTP-запросы)
- APScheduler (фоновые задачи)
- python-dotenv (переменные окружения)

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd telegram_bot
```

### 2. Создание виртуального окружения

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка Google Sheets API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект
3. Включите Google Sheets API и Google Drive API
4. Создайте Service Account
5. Скачайте JSON файл с credentials
6. Поместите файл в `credentials/service_account.json`
7. Дайте доступ Service Account к вашей Google таблице (добавьте email из JSON файла)

### 5. Регистрация бота в Telegram

1. Напишите [@BotFather](https://t.me/botfather)
2. Создайте бота командой `/newbot`
3. Скопируйте полученный токен

### 6. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` файл:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Axenta API
AXENTA_API_URL=https://axenta.cloud/
AXENTA_CMS_URL=https://cms.axenta.cloud/
AXENTA_AUTH_ENDPOINT=/auth/login

# Google Sheets
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_CREDENTIALS_FILE=credentials/service_account.json

# Notification settings
NOTIFICATION_CHECK_INTERVAL=3600
NOTIFICATION_TIMEZONE=Europe/Moscow

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log
```

## Запуск

```bash
python main.py
```

## Структура проекта

```
telegram_bot/
├── .env.example              # Пример переменных окружения
├── .gitignore               # Игнорируемые файлы
├── requirements.txt         # Зависимости Python
├── README.md               # Документация
├── main.py                 # Точка входа
├── config.py               # Конфигурация
│
├── handlers/               # Обработчики команд
│   ├── __init__.py
│   ├── start.py           # /start и регистрация
│   ├── auth.py            # Аутентификация
│   ├── info.py            # Показ баланса
│   ├── notifications.py   # Настройка уведомлений
│   └── common.py          # Общие обработчики
│
├── services/              # Бизнес-логика
│   ├── __init__.py
│   ├── sheets_service.py  # Работа с Google Sheets
│   ├── axenta_api.py      # API Axenta
│   └── notification_checker.py  # Проверка уведомлений
│
├── models/                # Модели данных
│   ├── __init__.py
│   └── user.py           # User, AccountBalance, Notification
│
├── utils/                 # Утилиты
│   ├── __init__.py
│   ├── logger.py         # Логирование
│   ├── validators.py     # Валидация
│   └── constants.py      # Константы
│
└── credentials/          # Credentials (не коммитить!)
    └── service_account.json
```

## Структура Google Sheets

### Лист "Пользователи"
- Колонка F: Login Пользователя
- Колонка G: Account Name
- Колонка J: Is Admin

### Лист "Данные"
- Колонка B: Аккаунты / Логины
- Колонка C: Наименование организации
- Колонка G: Тариф за 1 объект
- Колонка H: Сумма списания
- Колонка J: Количество объектов
- Колонка K: Остаток баланса
- Колонка L: Остаток в днях

### Лист "Чаты"
Заголовки: ID Чата, ID Пользователя, Имя, Фамилия, Username, Логин Пользователя, Логин Аккаунта, Is Admin, E-mail, Токен, Статус аутентификации, Дата проверки, Дата следующей проверки, Дата регистрации, Последняя активность

### Лист "Уведомления"
Заголовки: Chat id, Логин Аккаунта, Статус аутентификации, ID Уведомления, Статус, Порог Баланса, Время уведомления, Текущий баланс, Статус отправки

### Лист "Logs"
Заголовки: Дата, Время, Статус, Действие, Сообщение

## Команды бота

- `/start` - Регистрация и аутентификация
- `/help` - Справка
- `/cancel` - Отмена текущего действия

## Кнопки меню

- **Показать баланс** - Информация об аккаунте
- **Уведомления** - Управление уведомлениями
- **Помощь** - Справка

## Безопасность

- Пароли автоматически удаляются из чата после проверки
- Не коммитьте `.env` и `credentials/`
- Токены и пароли не логируются

## Лицензия

MIT

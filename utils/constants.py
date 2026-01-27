"""Константы приложения"""

# Тексты сообщений
MSG_WELCOME = """Добро пожаловать!

Этот бот предоставляет информацию о вашем аккаунте в системе Axenta.

Для начала работы введите ваш логин в системе Axenta:"""

MSG_LOGIN_NOT_FOUND = """Логин не найден.

Проверьте правильность ввода или обратитесь к администратору."""

MSG_EMAIL_REQUEST = "Теперь введите ваш email:"

MSG_EMAIL_INVALID = """Неверный формат email.

Попробуйте ещё раз:"""

MSG_PASSWORD_REQUEST = """Введите пароль от системы Axenta.

ВНИМАНИЕ: пароль будет автоматически удалён сразу после проверки для вашей безопасности."""

MSG_AUTH_SUCCESS = """Аутентификация прошла успешно!

Теперь вы можете использовать все функции бота."""

MSG_AUTH_FAILED = """Неверный логин или пароль.

Попробуйте снова: /start"""

MSG_NOT_REGISTERED = """Вы не зарегистрированы.

Используйте /start для регистрации."""

MSG_AUTH_EXPIRED = """Срок действия токена истёк.

Пройдите аутентификацию заново: /start"""

MSG_BALANCE_ERROR = """Не удалось получить информацию о балансе.

Попробуйте позже."""

MSG_ALREADY_REGISTERED = "Вы уже зарегистрированы!"

MSG_REGISTRATION_CANCELLED = "Регистрация отменена. Используйте /start для повторной попытки."

MSG_SAVE_ERROR = """Произошла ошибка при сохранении данных.

Попробуйте позже."""

MSG_NO_NOTIFICATIONS = "У вас нет активных уведомлений."

MSG_NOTIFICATION_SET = """Уведомление установлено!

Порог: {threshold} руб
Время проверки: {time}

Вы получите сообщение, когда баланс опустится ниже указанного порога."""

MSG_NOTIFICATION_DELETED = "Уведомление ID {id} удалено."

MSG_NOTIFICATION_AMOUNT_REQUEST = """Введите сумму баланса (в рублях), при достижении которой вы хотите получить уведомление:

Например: 5000"""

MSG_NOTIFICATION_INVALID_AMOUNT = """Неверный формат суммы.

Введите положительное число (например: 5000):"""

MSG_NOTIFICATION_TIME_REQUEST = """Выберите время для проверки баланса:

Уведомление будет отправлено в указанное время, если баланс ниже порога."""

MSG_NOTIFICATION_CUSTOM_TIME_REQUEST = """Введите время в формате ЧЧ:ММ

Например: 09:30 или 18:00"""

MSG_NOTIFICATION_INVALID_TIME = """Неверный формат времени.

Введите время в формате ЧЧ:ММ (например: 09:30):"""

MSG_NOTIFICATION_CONFIRM = """Подтвердите создание уведомления:

Порог баланса: {threshold} руб
Время проверки: {time}

Уведомление сработает, если баланс окажется ниже порога."""

MSG_NOTIFICATION_DELETE_CONFIRM = """Вы уверены, что хотите удалить уведомление?

ID: {id}
Порог: {threshold} руб
Время: {time}"""

MSG_BALANCE_ALERT = """ВНИМАНИЕ!

Баланс вашего аккаунта опустился ниже установленного порога!

Текущий баланс: {balance} руб
Порог уведомления: {threshold} руб

Пожалуйста, пополните баланс."""

MSG_HELP = """Доступные команды:

/start - Регистрация и аутентификация
/help - Показать эту справку

Текущая информация - Информация о вашем аккаунте
Уведомления - Настройка уведомлений о балансе"""

# Имена листов в Google Sheets
SHEET_USERS = "Пользователи"
SHEET_DATA = "Данные"
SHEET_CHATS = "Чаты"
SHEET_NOTIFICATIONS = "Уведомления"
SHEET_LOGS = "Logs"

# Колонки в Google Sheets (индексы с 0)
# Лист "Пользователи"
USERS_COL_LOGIN = 5          # F - Login Пользователя
USERS_COL_ACCOUNT = 6        # G - Account Name
USERS_COL_IS_ADMIN = 9       # J - Is Admin

# Лист "Данные"
DATA_COL_ACCOUNT = 1         # B - Аккаунты / Логины
DATA_COL_ORG_NAME = 2        # C - Наименование организации
DATA_COL_TARIFF = 6          # G - Тариф за 1 объект
DATA_COL_AVG_CHARGE = 7      # H - Средняя сумма списания
DATA_COL_ACTIVE_OBJECTS = 9  # J - Количество активных объектов
DATA_COL_BALANCE = 10        # K - Остаток баланса
DATA_COL_DAYS_LEFT = 11      # L - Остаток в днях

# Лист "Чаты"
COL_CHAT_ID = 0           # A
COL_USER_ID = 1           # B
COL_FIRST_NAME = 2        # C
COL_LAST_NAME = 3         # D
COL_USERNAME = 4          # E
COL_USER_LOGIN = 5        # F
COL_ACCOUNT_LOGIN = 6     # G
COL_IS_ADMIN = 7          # H
COL_EMAIL = 8             # I
COL_TOKEN = 9             # J
COL_AUTH_STATUS = 10      # K
COL_LAST_CHECK = 11       # L
COL_NEXT_CHECK = 12       # M
COL_REGISTRATION = 13     # N
COL_LAST_ACTIVITY = 14    # O

# Лист "Уведомления"
NOTIF_COL_CHAT_ID = 0        # A
NOTIF_COL_ACCOUNT = 1        # B
NOTIF_COL_AUTH_STATUS = 2    # C
NOTIF_COL_ID = 3             # D
NOTIF_COL_STATUS = 4         # E
NOTIF_COL_THRESHOLD = 5      # F
NOTIF_COL_TIME = 6           # G
NOTIF_COL_CURRENT_BAL = 7    # H
NOTIF_COL_SEND_STATUS = 8    # I

# Статусы
AUTH_STATUS_PASSED = "Пройдена"
NOTIF_STATUS_ACTIVE = "Установлено"
NOTIF_STATUS_DELETED = "Удалено"
NOTIF_SEND_STATUS_SEND = "Отправить"
NOTIF_SEND_STATUS_WAIT = "Ожидание"

# Кнопки меню
BTN_SHOW_BALANCE = "Текущая информация"
BTN_NOTIFICATIONS = "Уведомления"
BTN_HELP = "Помощь"
BTN_SET_NOTIFICATION = "Установить новое"
BTN_MY_NOTIFICATIONS = "Мои уведомления"
BTN_DELETE_NOTIFICATION = "Удалить"
BTN_BACK = "Назад"
BTN_CONFIRM = "Подтвердить"
BTN_CANCEL = "Отмена"

# Варианты времени для уведомлений
TIME_OPTIONS = ["10:00", "12:00", "15:00"]
BTN_CUSTOM_TIME = "Свой вариант"

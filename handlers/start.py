"""Обработчик команды /start и регистрация"""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.sheets_service import SheetsService
from services.axenta_api import AxentaAPI
from models.user import User
from utils.validators import validate_email
from utils.constants import (
    MSG_WELCOME, MSG_LOGIN_NOT_FOUND, MSG_NOT_ADMIN, MSG_EMAIL_REQUEST, MSG_EMAIL_INVALID,
    MSG_PASSWORD_REQUEST, MSG_AUTH_SUCCESS, MSG_AUTH_FAILED,
    MSG_ALREADY_REGISTERED, MSG_REGISTRATION_CANCELLED, MSG_SAVE_ERROR,
    BTN_SHOW_BALANCE, BTN_NOTIFICATIONS, BTN_HELP, AUTH_STATUS_PASSED
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Состояния диалога
AWAITING_LOGIN, AWAITING_EMAIL, AWAITING_PASSWORD = range(3)

# Инициализация сервисов
sheets = SheetsService()
axenta = AxentaAPI()


def get_main_menu() -> ReplyKeyboardMarkup:
    """Создание главного меню бота"""
    keyboard = [
        [BTN_SHOW_BALANCE],
        [BTN_NOTIFICATIONS, BTN_HELP]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    user = update.effective_user
    chat_id = update.effective_chat.id

    logger.info(f"Команда /start от пользователя {chat_id}")

    # Проверка существующей регистрации
    existing_user = sheets.get_user_by_chat_id(chat_id)
    if existing_user and existing_user.is_authenticated():
        await update.message.reply_text(
            MSG_ALREADY_REGISTERED,
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    # Сохраняем базовые данные Telegram в context
    context.user_data['chat_id'] = chat_id
    context.user_data['user_id'] = user.id
    context.user_data['first_name'] = user.first_name or ''
    context.user_data['last_name'] = user.last_name or ''
    context.user_data['username'] = user.username or ''

    await update.message.reply_text(MSG_WELCOME)
    return AWAITING_LOGIN


async def receive_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение и проверка логина"""
    user_login = update.message.text.strip()

    logger.info(f"Получен логин: {user_login}")

    # Поиск логина в Google Sheets
    user_info = sheets.find_user_login(user_login)

    if not user_info:
        await update.message.reply_text(MSG_LOGIN_NOT_FOUND)
        return AWAITING_LOGIN

    # Проверка IsAdmin
    is_admin = user_info.get('is_admin', '').lower().strip()
    if is_admin != 'да':
        logger.warning(f"Попытка регистрации не-админа: {user_login} (is_admin={is_admin})")
        await update.message.reply_text(MSG_NOT_ADMIN)
        return ConversationHandler.END

    # Сохраняем данные
    context.user_data['user_login'] = user_login
    context.user_data['account_login'] = user_info['account_name']
    context.user_data['is_admin'] = user_info['is_admin']

    logger.info(f"Логин найден. Аккаунт: {user_info['account_name']}, IsAdmin: {is_admin}")

    await update.message.reply_text(MSG_EMAIL_REQUEST)
    return AWAITING_EMAIL


async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение и валидация email"""
    email = update.message.text.strip()

    if not validate_email(email):
        await update.message.reply_text(MSG_EMAIL_INVALID)
        return AWAITING_EMAIL

    context.user_data['email'] = email
    logger.info(f"Email получен: {email}")

    # Сохраняем ID сообщения с запросом пароля для последующего удаления
    msg = await update.message.reply_text(MSG_PASSWORD_REQUEST, parse_mode='Markdown')
    context.user_data['password_request_msg_id'] = msg.message_id
    return AWAITING_PASSWORD


async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение пароля и аутентификация"""
    password = update.message.text.strip()
    user_login = context.user_data['user_login']
    chat_id = update.effective_chat.id

    # Сразу удаляем сообщение с паролем для безопасности
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=update.message.message_id
        )
        logger.info("Сообщение с паролем удалено")
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение с паролем: {e}")

    # Удаляем сообщение с запросом пароля (от бота)
    try:
        password_msg_id = context.user_data.get('password_request_msg_id')
        if password_msg_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=password_msg_id)
            logger.info("Сообщение с запросом пароля удалено")
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение с запросом пароля: {e}")

    # Аутентификация через Axenta API
    logger.info(f"Попытка аутентификации для {user_login}")
    token = await axenta.authenticate(user_login, password)

    if not token:
        await update.effective_chat.send_message(MSG_AUTH_FAILED)
        return ConversationHandler.END

    # Успешная аутентификация - создаём объект пользователя
    now = datetime.now()
    user = User(
        chat_id=context.user_data['chat_id'],
        user_id=context.user_data['user_id'],
        first_name=context.user_data['first_name'],
        last_name=context.user_data['last_name'],
        username=context.user_data['username'],
        user_login=user_login,
        account_login=context.user_data['account_login'],
        is_admin=context.user_data['is_admin'],
        email=context.user_data['email'],
        token=token,
        auth_status=AUTH_STATUS_PASSED,
        last_check=now.strftime('%Y-%m-%d %H:%M:%S'),
        next_check=(now + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'),
        registration_date=now.strftime('%Y-%m-%d %H:%M:%S'),
        last_activity=now.strftime('%Y-%m-%d %H:%M:%S')
    )

    # Сохраняем в Google Sheets
    if sheets.register_user(user):
        logger.info(f"Пользователь {chat_id} успешно зарегистрирован")

        # Логируем в таблицу
        sheets.add_log(
            status="SUCCESS",
            action="REGISTRATION",
            message=f"Пользователь {user_login} (chat_id: {chat_id}) зарегистрирован"
        )

        await update.effective_chat.send_message(
            MSG_AUTH_SUCCESS,
            reply_markup=get_main_menu()
        )
    else:
        logger.error(f"Ошибка сохранения пользователя {chat_id}")
        await update.effective_chat.send_message(MSG_SAVE_ERROR)

    # Очищаем context.user_data
    context.user_data.clear()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена регистрации"""
    logger.info(f"Регистрация отменена для {update.effective_chat.id}")
    context.user_data.clear()
    await update.message.reply_text(MSG_REGISTRATION_CANCELLED)
    return ConversationHandler.END


# Создание ConversationHandler для регистрации
registration_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start_command)],
    states={
        AWAITING_LOGIN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_login)
        ],
        AWAITING_EMAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)
        ],
        AWAITING_PASSWORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

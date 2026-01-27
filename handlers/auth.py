"""Дополнительные обработчики аутентификации"""
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.sheets_service import SheetsService
from services.axenta_api import AxentaAPI
from utils.constants import AUTH_STATUS_PASSED
from utils.logger import setup_logger

logger = setup_logger(__name__)

sheets = SheetsService()
axenta = AxentaAPI()


def is_user_authenticated(chat_id: int) -> bool:
    """
    Проверка аутентификации пользователя

    Args:
        chat_id: ID чата пользователя

    Returns:
        True если пользователь аутентифицирован
    """
    user = sheets.get_user_by_chat_id(chat_id)
    if not user:
        return False
    return user.is_authenticated()


async def check_auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware для проверки аутентификации

    Args:
        update: Update от Telegram
        context: Context

    Returns:
        True если пользователь аутентифицирован
    """
    chat_id = update.effective_chat.id

    if not is_user_authenticated(chat_id):
        await update.message.reply_text(
            "Вы не авторизованы. Используйте /start для регистрации."
        )
        return False

    # Обновляем время последней активности
    sheets.update_last_activity(chat_id)
    return True


async def reauth_user(chat_id: int, user_login: str, password: str) -> bool:
    """
    Повторная аутентификация пользователя

    Args:
        chat_id: ID чата
        user_login: Логин пользователя
        password: Пароль

    Returns:
        True при успешной реаутентификации
    """
    token = await axenta.authenticate(user_login, password)

    if not token:
        return False

    now = datetime.now()

    # Обновляем токен и даты проверки
    user = sheets.get_user_by_chat_id(chat_id)
    if user:
        user.token = token
        user.auth_status = AUTH_STATUS_PASSED
        user.last_check = now.strftime('%Y-%m-%d %H:%M:%S')
        user.next_check = (now + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
        user.last_activity = now.strftime('%Y-%m-%d %H:%M:%S')

        return sheets.update_user(user)

    return False

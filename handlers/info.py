"""Обработчик показа информации о балансе"""
from telegram import Update
from telegram.ext import ContextTypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.sheets_service import SheetsService
from utils.constants import (
    MSG_NOT_REGISTERED, MSG_AUTH_EXPIRED, MSG_BALANCE_ERROR, MSG_ADMIN_STATUS_REVOKED
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Инициализация сервиса
sheets = SheetsService()


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ информации о балансе аккаунта"""
    chat_id = update.effective_chat.id

    logger.info(f"Запрос баланса от пользователя {chat_id}")

    # Проверка аутентификации
    user = sheets.get_user_by_chat_id(chat_id)

    if not user:
        await update.message.reply_text(MSG_NOT_REGISTERED)
        return

    if not user.is_authenticated():
        await update.message.reply_text(MSG_AUTH_EXPIRED)
        return

    # Проверка необходимости повторной верификации IsAdmin
    if user.needs_admin_recheck():
        logger.info(f"Требуется повторная проверка IsAdmin для {chat_id}")
        is_admin, message = sheets.recheck_admin_status(chat_id, user.user_login)
        if not is_admin:
            logger.warning(f"Статус IsAdmin отозван для {chat_id}: {message}")
            await update.message.reply_text(MSG_ADMIN_STATUS_REVOKED)
            return

    # Обновляем время последней активности
    sheets.update_last_activity(chat_id)

    # Получение данных о балансе
    balance_info = sheets.get_account_balance(user.account_login)

    if not balance_info:
        logger.warning(f"Не удалось получить баланс для {user.account_login}")
        await update.message.reply_text(MSG_BALANCE_ERROR)
        return

    # Форматируем и отправляем сообщение
    message = balance_info.format_message()
    await update.message.reply_text(message, parse_mode='Markdown')

    # Логируем
    sheets.add_log(
        status="INFO",
        action="BALANCE_VIEW",
        message=f"Пользователь {chat_id} просмотрел баланс аккаунта {user.account_login}"
    )

    logger.info(f"Баланс показан для пользователя {chat_id}")

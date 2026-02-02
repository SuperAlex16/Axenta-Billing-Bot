"""Обработчик команды /logout"""
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler
)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.sheets_service import SheetsService
from utils.constants import (
    MSG_LOGOUT_SUCCESS, MSG_LOGOUT_NOT_LOGGED_IN, MSG_LOGOUT_CONFIRM,
    BTN_CONFIRM, BTN_CANCEL
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Callback data
CB_CONFIRM_LOGOUT = "confirm_logout"
CB_CANCEL_LOGOUT = "cancel_logout"

# Инициализация сервисов
sheets = SheetsService()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения выхода"""
    keyboard = [
        [
            InlineKeyboardButton(f"✅ {BTN_CONFIRM}", callback_data=CB_CONFIRM_LOGOUT),
            InlineKeyboardButton(f"❌ {BTN_CANCEL}", callback_data=CB_CANCEL_LOGOUT)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /logout"""
    chat_id = update.effective_chat.id

    logger.info(f"Команда /logout от пользователя {chat_id}")

    # Проверяем, авторизован ли пользователь
    user = sheets.get_user_by_chat_id(chat_id)

    if not user or not user.is_authenticated():
        await update.message.reply_text(MSG_LOGOUT_NOT_LOGGED_IN)
        return

    # Запрашиваем подтверждение
    await update.message.reply_text(
        MSG_LOGOUT_CONFIRM,
        reply_markup=get_confirm_keyboard()
    )


async def handle_logout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок подтверждения/отмены выхода"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if query.data == CB_CONFIRM_LOGOUT:
        # Выполняем выход
        success, deleted_count = sheets.logout_user(chat_id)

        if success:
            # Очищаем данные контекста
            context.user_data.clear()

            # Удаляем сообщение с кнопками
            await query.delete_message()

            # Отправляем сообщение об успешном выходе
            await context.bot.send_message(
                chat_id=chat_id,
                text=MSG_LOGOUT_SUCCESS,
                reply_markup=ReplyKeyboardRemove()
            )

            # Логируем
            sheets.add_log(
                status="INFO",
                action="LOGOUT",
                message=f"Пользователь {chat_id} вышел из аккаунта. Удалено уведомлений: {deleted_count}"
            )

            logger.info(f"Пользователь {chat_id} вышел, удалено {deleted_count} уведомлений")
        else:
            await query.edit_message_text("❌ Произошла ошибка при выходе. Попробуйте позже.")

    elif query.data == CB_CANCEL_LOGOUT:
        # Удаляем сообщение с кнопками
        await query.delete_message()


# Обработчики для регистрации в main.py
logout_command_handler = CommandHandler('logout', logout_command)
logout_callback_handler = CallbackQueryHandler(
    handle_logout_callback,
    pattern=f"^({CB_CONFIRM_LOGOUT}|{CB_CANCEL_LOGOUT})$"
)

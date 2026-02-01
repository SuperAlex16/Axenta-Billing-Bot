"""Обработчик команды /logout"""
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
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

# Состояния диалога
CONFIRMING_LOGOUT = 0

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


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /logout"""
    chat_id = update.effective_chat.id

    logger.info(f"Команда /logout от пользователя {chat_id}")

    # Проверяем, авторизован ли пользователь
    user = sheets.get_user_by_chat_id(chat_id)

    if not user or not user.is_authenticated():
        await update.message.reply_text(MSG_LOGOUT_NOT_LOGGED_IN)
        return ConversationHandler.END

    # Сохраняем данные для подтверждения
    context.user_data['logout_account'] = user.account_login

    # Запрашиваем подтверждение
    await update.message.reply_text(
        MSG_LOGOUT_CONFIRM,
        reply_markup=get_confirm_keyboard()
    )

    return CONFIRMING_LOGOUT


async def confirm_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждение выхода"""
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
            await query.edit_message_text("Произошла ошибка при выходе. Попробуйте позже.")

    elif query.data == CB_CANCEL_LOGOUT:
        await query.edit_message_text("🔙 Выход отменён.")

    return ConversationHandler.END


async def cancel_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена выхода"""
    await update.message.reply_text("🔙 Выход отменён.")
    return ConversationHandler.END


# ConversationHandler для logout
logout_handler = ConversationHandler(
    entry_points=[CommandHandler('logout', logout_command)],
    states={
        CONFIRMING_LOGOUT: [
            CallbackQueryHandler(confirm_logout, pattern=f"^({CB_CONFIRM_LOGOUT}|{CB_CANCEL_LOGOUT})$")
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel_logout)],
    per_message=False
)

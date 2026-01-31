"""Обработчик настройки уведомлений"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.sheets_service import SheetsService
from models.user import Notification
from utils.validators import validate_amount
from utils.constants import (
    MSG_NOT_REGISTERED, MSG_AUTH_EXPIRED, MSG_NO_NOTIFICATIONS,
    MSG_ADMIN_STATUS_REVOKED,
    MSG_NOTIFICATION_SET, MSG_NOTIFICATION_DELETED,
    MSG_NOTIFICATION_AMOUNT_REQUEST, MSG_NOTIFICATION_INVALID_AMOUNT,
    MSG_NOTIFICATION_TIME_REQUEST, MSG_NOTIFICATION_CUSTOM_TIME_REQUEST,
    MSG_NOTIFICATION_INVALID_TIME, MSG_NOTIFICATION_CONFIRM,
    MSG_NOTIFICATION_DELETE_CONFIRM,
    BTN_SET_NOTIFICATION, BTN_MY_NOTIFICATIONS, BTN_DELETE_NOTIFICATION, BTN_BACK,
    BTN_CONFIRM, BTN_CANCEL, BTN_CUSTOM_TIME, TIME_OPTIONS,
    AUTH_STATUS_PASSED, NOTIF_SEND_STATUS_WAIT
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Состояния диалога
(NOTIFICATION_MENU, AWAITING_THRESHOLD, AWAITING_TIME, AWAITING_CUSTOM_TIME,
 CONFIRM_SET, SELECTING_DELETE, CONFIRM_DELETE) = range(7)

# Callback data
CB_SET_NEW = 'notif_set_new'
CB_MY_NOTIFICATIONS = 'notif_my_list'
CB_DELETE = 'notif_delete'
CB_DELETE_PREFIX = 'notif_del_'
CB_CONFIRM_DELETE_PREFIX = 'notif_confirm_del_'
CB_BACK = 'notif_back'
CB_TIME_PREFIX = 'notif_time_'
CB_CUSTOM_TIME = 'notif_custom_time'
CB_CONFIRM_SET = 'notif_confirm_set'
CB_CANCEL = 'notif_cancel'

# Инициализация сервиса
sheets = SheetsService()


def get_notifications_menu() -> InlineKeyboardMarkup:
    """Создание меню уведомлений"""
    keyboard = [
        [InlineKeyboardButton(f"+ {BTN_SET_NOTIFICATION}", callback_data=CB_SET_NEW)],
        [InlineKeyboardButton(BTN_MY_NOTIFICATIONS, callback_data=CB_MY_NOTIFICATIONS)],
        [InlineKeyboardButton(BTN_DELETE_NOTIFICATION, callback_data=CB_DELETE)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_time_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора времени"""
    # Верхний ряд: 3 кнопки с вариантами времени
    time_buttons = [
        InlineKeyboardButton(time, callback_data=f"{CB_TIME_PREFIX}{time}")
        for time in TIME_OPTIONS
    ]
    keyboard = [
        time_buttons,
        [
            InlineKeyboardButton(BTN_CUSTOM_TIME, callback_data=CB_CUSTOM_TIME),
            InlineKeyboardButton(BTN_BACK, callback_data=CB_BACK)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data=CB_CONFIRM_SET)],
        [InlineKeyboardButton(BTN_CANCEL, callback_data=CB_CANCEL)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delete_confirm_keyboard(notification_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    keyboard = [
        [InlineKeyboardButton(BTN_CONFIRM, callback_data=f"{CB_CONFIRM_DELETE_PREFIX}{notification_id}")],
        [InlineKeyboardButton(BTN_CANCEL, callback_data=CB_CANCEL)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню"""
    keyboard = [[InlineKeyboardButton(BTN_BACK, callback_data=CB_BACK)]]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_button() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    keyboard = [[InlineKeyboardButton(BTN_CANCEL, callback_data=CB_CANCEL)]]
    return InlineKeyboardMarkup(keyboard)


async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ меню уведомлений"""
    chat_id = update.effective_chat.id

    logger.info(f"Меню уведомлений для пользователя {chat_id}")

    # Проверка аутентификации
    user = sheets.get_user_by_chat_id(chat_id)

    if not user:
        await update.message.reply_text(MSG_NOT_REGISTERED)
        return ConversationHandler.END

    if not user.is_authenticated():
        await update.message.reply_text(MSG_AUTH_EXPIRED)
        return ConversationHandler.END

    # Проверка необходимости повторной верификации IsAdmin
    if user.needs_admin_recheck():
        logger.info(f"Требуется повторная проверка IsAdmin для {chat_id}")
        is_admin, message = sheets.recheck_admin_status(chat_id, user.user_login)
        if not is_admin:
            logger.warning(f"Статус IsAdmin отозван для {chat_id}: {message}")
            await update.message.reply_text(MSG_ADMIN_STATUS_REVOKED)
            return ConversationHandler.END

    # Сохраняем данные пользователя в context
    context.user_data['account_login'] = user.account_login
    context.user_data['user_login'] = user.user_login
    context.user_data['auth_status'] = user.auth_status

    # Получаем timezone пользователя
    timezone = sheets.get_user_timezone(user.user_login)
    context.user_data['timezone'] = timezone

    # Обновляем время активности
    sheets.update_last_activity(chat_id)

    await update.message.reply_text(
        "🔔 Управление уведомлениями:",
        reply_markup=get_notifications_menu()
    )

    return NOTIFICATION_MENU


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка нажатий на кнопки меню"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if query.data == CB_SET_NEW:
        # Установка нового уведомления
        result = await query.edit_message_text(
            MSG_NOTIFICATION_AMOUNT_REQUEST,
            reply_markup=get_cancel_button()
        )
        # Сохраняем message_id для последующего редактирования
        context.user_data['bot_message_id'] = result.message_id
        return AWAITING_THRESHOLD

    elif query.data == CB_MY_NOTIFICATIONS:
        # Показ списка уведомлений
        notifications = sheets.get_user_notifications(chat_id)

        if not notifications:
            await query.edit_message_text(
                MSG_NO_NOTIFICATIONS,
                reply_markup=get_back_button()
            )
        else:
            timezone = context.user_data.get('timezone', '3')
            text = f"🔔 Ваши уведомления (UTC+{timezone}):\n\n"
            for i, notif in enumerate(notifications, 1):
                time_str = notif.notification_time if notif.notification_time else "не задано"
                text += f"📌 Уведомление {i}\n"
                text += f"   💰 Порог: {notif.threshold} руб\n"
                text += f"   🕐 Время: {time_str}\n\n"

            await query.edit_message_text(
                text,
                reply_markup=get_back_button()
            )

        return NOTIFICATION_MENU

    elif query.data == CB_DELETE:
        # Удаление уведомления
        notifications = sheets.get_user_notifications(chat_id)

        if not notifications:
            await query.edit_message_text(
                MSG_NO_NOTIFICATIONS,
                reply_markup=get_back_button()
            )
            return NOTIFICATION_MENU

        # Создаём кнопки для выбора уведомления
        keyboard = []
        for i, notif in enumerate(notifications, 1):
            time_str = notif.notification_time if notif.notification_time else "?"
            keyboard.append([
                InlineKeyboardButton(
                    f"📌 #{i} | 💰 {notif.threshold} руб | 🕐 {time_str}",
                    callback_data=f"{CB_DELETE_PREFIX}{notif.notification_id}"
                )
            ])
        keyboard.append([InlineKeyboardButton(BTN_BACK, callback_data=CB_BACK)])

        await query.edit_message_text(
            "🗑 Выберите уведомление для удаления:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return SELECTING_DELETE

    elif query.data == CB_BACK:
        # Возврат в меню
        await query.edit_message_text(
            "🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    elif query.data == CB_CANCEL:
        # Отмена и возврат в меню
        context.user_data.pop('pending_threshold', None)
        context.user_data.pop('pending_time', None)
        context.user_data.pop('pending_delete_id', None)
        context.user_data.pop('bot_message_id', None)
        await query.edit_message_text(
            "🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    return NOTIFICATION_MENU


async def receive_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение порогового значения баланса"""
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    bot_message_id = context.user_data.get('bot_message_id')

    # Удаляем сообщение пользователя с введённой суммой
    try:
        await update.message.delete()
    except Exception:
        pass  # Игнорируем ошибки удаления

    is_valid, threshold = validate_amount(text)

    if not is_valid:
        # Редактируем предыдущее сообщение бота
        if bot_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=bot_message_id,
                    text=MSG_NOTIFICATION_INVALID_AMOUNT,
                    reply_markup=get_cancel_button()
                )
                return AWAITING_THRESHOLD
            except Exception:
                pass
        # Fallback: отправляем новое сообщение
        result = await update.message.reply_text(
            MSG_NOTIFICATION_INVALID_AMOUNT,
            reply_markup=get_cancel_button()
        )
        context.user_data['bot_message_id'] = result.message_id
        return AWAITING_THRESHOLD

    # Сохраняем порог для последующего использования
    context.user_data['pending_threshold'] = threshold

    # Редактируем предыдущее сообщение бота для выбора времени
    if bot_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_message_id,
                text=MSG_NOTIFICATION_TIME_REQUEST,
                reply_markup=get_time_selection_keyboard()
            )
            return AWAITING_TIME
        except Exception:
            pass

    # Fallback: отправляем новое сообщение
    result = await update.message.reply_text(
        MSG_NOTIFICATION_TIME_REQUEST,
        reply_markup=get_time_selection_keyboard()
    )
    context.user_data['bot_message_id'] = result.message_id

    return AWAITING_TIME


async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора времени"""
    query = update.callback_query
    await query.answer()

    if query.data == CB_BACK:
        context.user_data.pop('pending_threshold', None)
        await query.edit_message_text(
            "🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    elif query.data == CB_CUSTOM_TIME:
        result = await query.edit_message_text(
            MSG_NOTIFICATION_CUSTOM_TIME_REQUEST,
            reply_markup=get_cancel_button()
        )
        # Обновляем message_id для последующего редактирования
        context.user_data['bot_message_id'] = result.message_id
        return AWAITING_CUSTOM_TIME

    elif query.data.startswith(CB_TIME_PREFIX):
        selected_time = query.data.replace(CB_TIME_PREFIX, '')
        context.user_data['pending_time'] = selected_time
        return await show_confirmation(query, context)

    return AWAITING_TIME


async def receive_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение пользовательского времени"""
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    bot_message_id = context.user_data.get('bot_message_id')

    # Удаляем сообщение пользователя с введённым временем
    try:
        await update.message.delete()
    except Exception:
        pass

    # Валидация формата времени ЧЧ:ММ
    time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
    match = time_pattern.match(text)

    if not match:
        # Редактируем предыдущее сообщение бота
        if bot_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=bot_message_id,
                    text=MSG_NOTIFICATION_INVALID_TIME,
                    reply_markup=get_cancel_button()
                )
                return AWAITING_CUSTOM_TIME
            except Exception:
                pass
        # Fallback
        result = await update.message.reply_text(
            MSG_NOTIFICATION_INVALID_TIME,
            reply_markup=get_cancel_button()
        )
        context.user_data['bot_message_id'] = result.message_id
        return AWAITING_CUSTOM_TIME

    # Форматируем время в HH:MM
    hours = int(match.group(1))
    minutes = int(match.group(2))
    formatted_time = f"{hours:02d}:{minutes:02d}"

    context.user_data['pending_time'] = formatted_time

    # Показываем подтверждение
    threshold = context.user_data.get('pending_threshold', 0)
    timezone = context.user_data.get('timezone', '3')

    # Редактируем предыдущее сообщение бота
    if bot_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_message_id,
                text=MSG_NOTIFICATION_CONFIRM.format(
                    threshold=threshold,
                    time=f"{formatted_time} (UTC+{timezone})"
                ),
                reply_markup=get_confirm_keyboard()
            )
            return CONFIRM_SET
        except Exception:
            pass

    # Fallback
    result = await update.message.reply_text(
        MSG_NOTIFICATION_CONFIRM.format(
            threshold=threshold,
            time=f"{formatted_time} (UTC+{timezone})"
        ),
        reply_markup=get_confirm_keyboard()
    )
    context.user_data['bot_message_id'] = result.message_id

    return CONFIRM_SET


async def show_confirmation(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ экрана подтверждения создания уведомления"""
    threshold = context.user_data.get('pending_threshold', 0)
    time = context.user_data.get('pending_time', '')
    timezone = context.user_data.get('timezone', '3')

    await query.edit_message_text(
        MSG_NOTIFICATION_CONFIRM.format(
            threshold=threshold,
            time=f"{time} (UTC+{timezone})"
        ),
        reply_markup=get_confirm_keyboard()
    )

    return CONFIRM_SET


async def handle_set_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения создания уведомления"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if query.data == CB_CANCEL:
        context.user_data.pop('pending_threshold', None)
        context.user_data.pop('pending_time', None)
        context.user_data.pop('bot_message_id', None)
        await query.edit_message_text(
            "Создание уведомления отменено.\n\n🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    elif query.data == CB_CONFIRM_SET:
        threshold = context.user_data.get('pending_threshold', 0)
        notification_time = context.user_data.get('pending_time', '')
        timezone = context.user_data.get('timezone', '3')

        # Создаём уведомление
        notification = Notification(
            chat_id=chat_id,
            account_login=context.user_data.get('account_login', ''),
            auth_status=context.user_data.get('auth_status', AUTH_STATUS_PASSED),
            threshold=threshold,
            notification_time=notification_time,
            send_status=NOTIF_SEND_STATUS_WAIT
        )

        if sheets.add_notification(notification):
            logger.info(f"Уведомление создано для {chat_id}: порог {threshold}, время {notification_time}")

            sheets.add_log(
                status="INFO",
                action="NOTIFICATION_CREATED",
                message=f"Пользователь {chat_id} создал уведомление: порог {threshold} руб, время {notification_time}"
            )

            await query.edit_message_text(
                MSG_NOTIFICATION_SET.format(
                    threshold=threshold,
                    time=f"{notification_time} (UTC+{timezone})"
                ),
                reply_markup=get_back_button()
            )
        else:
            await query.edit_message_text(
                "Не удалось создать уведомление. Попробуйте позже.",
                reply_markup=get_back_button()
            )

        # Очищаем временные данные
        context.user_data.pop('pending_threshold', None)
        context.user_data.pop('pending_time', None)
        context.user_data.pop('bot_message_id', None)

        return NOTIFICATION_MENU

    return CONFIRM_SET


async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора уведомления для удаления"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if query.data == CB_BACK:
        await query.edit_message_text(
            "🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    if query.data.startswith(CB_DELETE_PREFIX):
        notification_id = int(query.data.replace(CB_DELETE_PREFIX, ''))

        # Получаем информацию об уведомлении для показа
        notifications = sheets.get_user_notifications(chat_id)
        notif = next((n for n in notifications if n.notification_id == notification_id), None)

        if not notif:
            await query.edit_message_text(
                "Уведомление не найдено.",
                reply_markup=get_back_button()
            )
            return NOTIFICATION_MENU

        context.user_data['pending_delete_id'] = notification_id
        context.user_data['pending_delete_threshold'] = notif.threshold
        context.user_data['pending_delete_time'] = notif.notification_time

        time_str = notif.notification_time if notif.notification_time else "не задано"

        await query.edit_message_text(
            MSG_NOTIFICATION_DELETE_CONFIRM.format(
                id=notification_id,
                threshold=notif.threshold,
                time=time_str
            ),
            reply_markup=get_delete_confirm_keyboard(notification_id)
        )

        return CONFIRM_DELETE

    return SELECTING_DELETE


async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения удаления уведомления"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if query.data == CB_CANCEL:
        context.user_data.pop('pending_delete_id', None)
        context.user_data.pop('pending_delete_threshold', None)
        context.user_data.pop('pending_delete_time', None)
        context.user_data.pop('bot_message_id', None)
        await query.edit_message_text(
            "Удаление отменено.\n\n🔔 Управление уведомлениями:",
            reply_markup=get_notifications_menu()
        )
        return NOTIFICATION_MENU

    if query.data.startswith(CB_CONFIRM_DELETE_PREFIX):
        notification_id = int(query.data.replace(CB_CONFIRM_DELETE_PREFIX, ''))

        if sheets.delete_notification(chat_id, notification_id):
            logger.info(f"Уведомление {notification_id} удалено пользователем {chat_id}")

            sheets.add_log(
                status="INFO",
                action="NOTIFICATION_DELETED",
                message=f"Пользователь {chat_id} удалил уведомление {notification_id}"
            )

            await query.edit_message_text(
                MSG_NOTIFICATION_DELETED.format(id=notification_id),
                reply_markup=get_back_button()
            )
        else:
            await query.edit_message_text(
                "Не удалось удалить уведомление.",
                reply_markup=get_back_button()
            )

        # Очищаем временные данные
        context.user_data.pop('pending_delete_id', None)
        context.user_data.pop('pending_delete_threshold', None)
        context.user_data.pop('pending_delete_time', None)
        context.user_data.pop('bot_message_id', None)

        return NOTIFICATION_MENU

    return CONFIRM_DELETE


async def cancel_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена настройки уведомлений"""
    context.user_data.pop('pending_threshold', None)
    context.user_data.pop('pending_time', None)
    context.user_data.pop('pending_delete_id', None)
    context.user_data.pop('bot_message_id', None)
    await update.message.reply_text("Настройка уведомлений отменена.")
    return ConversationHandler.END


async def restart_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Повторный вызов меню уведомлений (при нажатии кнопки внутри диалога).
    Отправляет НОВОЕ сообщение с меню.
    """
    # Очищаем временные данные
    context.user_data.pop('pending_threshold', None)
    context.user_data.pop('pending_time', None)
    context.user_data.pop('pending_delete_id', None)
    context.user_data.pop('pending_delete_threshold', None)
    context.user_data.pop('pending_delete_time', None)
    context.user_data.pop('bot_message_id', None)

    chat_id = update.effective_chat.id

    logger.info(f"Повторный вызов меню уведомлений для пользователя {chat_id}")

    # Проверка аутентификации
    user = sheets.get_user_by_chat_id(chat_id)

    if not user:
        await update.message.reply_text(MSG_NOT_REGISTERED)
        return ConversationHandler.END

    if not user.is_authenticated():
        await update.message.reply_text(MSG_AUTH_EXPIRED)
        return ConversationHandler.END

    # Проверка необходимости повторной верификации IsAdmin
    if user.needs_admin_recheck():
        logger.info(f"Требуется повторная проверка IsAdmin для {chat_id}")
        is_admin, message = sheets.recheck_admin_status(chat_id, user.user_login)
        if not is_admin:
            logger.warning(f"Статус IsAdmin отозван для {chat_id}: {message}")
            await update.message.reply_text(MSG_ADMIN_STATUS_REVOKED)
            return ConversationHandler.END

    # Обновляем данные пользователя в context
    context.user_data['account_login'] = user.account_login
    context.user_data['user_login'] = user.user_login
    context.user_data['auth_status'] = user.auth_status

    # Получаем timezone пользователя
    timezone = sheets.get_user_timezone(user.user_login)
    context.user_data['timezone'] = timezone

    # Обновляем время активности
    sheets.update_last_activity(chat_id)

    # Отправляем НОВОЕ сообщение с меню
    await update.message.reply_text(
        "🔔 Управление уведомлениями:",
        reply_markup=get_notifications_menu()
    )

    return NOTIFICATION_MENU


# Обработчик повторного нажатия кнопки "Уведомления" внутри диалога
_restart_handler = MessageHandler(filters.Regex('^Уведомления$'), restart_notifications_menu)

# Создание ConversationHandler для уведомлений
notifications_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex('^Уведомления$'), notifications_menu)
    ],
    states={
        NOTIFICATION_MENU: [
            _restart_handler,
            CallbackQueryHandler(handle_menu_callback)
        ],
        AWAITING_THRESHOLD: [
            _restart_handler,
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_threshold),
            CallbackQueryHandler(handle_menu_callback)
        ],
        AWAITING_TIME: [
            _restart_handler,
            CallbackQueryHandler(handle_time_selection)
        ],
        AWAITING_CUSTOM_TIME: [
            _restart_handler,
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_time),
            CallbackQueryHandler(handle_menu_callback)
        ],
        CONFIRM_SET: [
            _restart_handler,
            CallbackQueryHandler(handle_set_confirmation)
        ],
        SELECTING_DELETE: [
            _restart_handler,
            CallbackQueryHandler(handle_delete_selection)
        ],
        CONFIRM_DELETE: [
            _restart_handler,
            CallbackQueryHandler(handle_delete_confirmation)
        ]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_notifications),
        CallbackQueryHandler(handle_menu_callback, pattern=f'^{CB_BACK}$')
    ]
)

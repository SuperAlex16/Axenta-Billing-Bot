"""Обработчик статистики расчётов (Этап 2)"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from datetime import datetime, date as date_type, timedelta
import calendar
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import STATISTICS_START_YEAR
from services.sheets_service import SheetsService
from services.report_service import generate_excel, generate_pdf
from utils.constants import (
    MONTHS_RU, BTN_STATISTICS,
    MSG_STAT_NOT_AUTH, MSG_STAT_CHOOSE_YEAR, MSG_STAT_CHOOSE_MONTH,
    MSG_STAT_CHOOSE_FORMAT, MSG_STAT_GENERATING, MSG_STAT_DONE,
    MSG_STAT_NO_DATA, MSG_STAT_ERROR_LOAD, MSG_STAT_ERROR_GENERATE,
    MSG_STAT_CANCELLED, MSG_ADMIN_STATUS_REVOKED
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Состояния ConversationHandler
CHOOSE_PERIOD, CHOOSE_FORMAT = range(2)

# Callback data prefixes
CB_STAT_NAV_LEFT = 'stat_nav_left'
CB_STAT_NAV_RIGHT = 'stat_nav_right'
CB_STAT_YEAR_REPORT = 'stat_yearrpt_'
CB_STAT_MONTH = 'stat_month_'
CB_STAT_FORMAT = 'stat_fmt_'
CB_STAT_CANCEL = 'stat_cancel'

# Сокращённые названия месяцев для кнопок
MONTHS_SHORT = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр',
    5: 'Май', 6: 'Июн', 7: 'Июл', 8: 'Авг',
    9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
}

# Инициализация сервиса
sheets = SheetsService()

# Текст сообщения для выбора периода
MSG_CHOOSE_PERIOD = (
    "📅 Выберите период отчёта:\n\n"
    "Используйте < > для смены года.\n"
    "Нажмите на месяц — отчёт за месяц.\n"
    "Нажмите на год — отчёт за весь год."
)


def build_period_keyboard(display_year: int) -> InlineKeyboardMarkup:
    """Построение клавиатуры выбора периода (год + месяцы)"""
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    keyboard = []

    # Строка навигации по годам: < | 2026 | >
    nav_row = []
    can_go_left = display_year > STATISTICS_START_YEAR
    nav_row.append(InlineKeyboardButton(
        "<",
        callback_data=CB_STAT_NAV_LEFT if can_go_left else 'stat_noop'
    ))

    nav_row.append(InlineKeyboardButton(
        f"{display_year}",
        callback_data=f"{CB_STAT_YEAR_REPORT}{display_year}"
    ))

    can_go_right = display_year < current_year
    nav_row.append(InlineKeyboardButton(
        ">",
        callback_data=CB_STAT_NAV_RIGHT if can_go_right else 'stat_noop'
    ))

    keyboard.append(nav_row)

    # Месяцы: 4 строки по 3 кнопки
    for row_start in range(1, 13, 3):
        row = []
        for m in range(row_start, row_start + 3):
            # Для текущего года: будущие месяцы недоступны
            if display_year == current_year and m > current_month:
                row.append(InlineKeyboardButton("·", callback_data='stat_noop'))
            # Для годов в будущем (не должно случиться, но на всякий случай)
            elif display_year > current_year:
                row.append(InlineKeyboardButton("·", callback_data='stat_noop'))
            else:
                row.append(InlineKeyboardButton(
                    MONTHS_SHORT[m],
                    callback_data=f"{CB_STAT_MONTH}{m}"
                ))
        keyboard.append(row)

    # Кнопка отмены
    keyboard.append([InlineKeyboardButton("Отмена", callback_data=CB_STAT_CANCEL)])

    return InlineKeyboardMarkup(keyboard)


async def statistics_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Точка входа: проверка аутентификации, показ выбора периода"""
    chat_id = update.effective_chat.id

    logger.info(f"Запрос статистики от пользователя {chat_id}")

    # Проверка аутентификации
    user = sheets.get_user_by_chat_id(chat_id)

    if not user:
        await update.message.reply_text(MSG_STAT_NOT_AUTH)
        return ConversationHandler.END

    if not user.is_authenticated():
        await update.message.reply_text(MSG_STAT_NOT_AUTH)
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
    context.user_data['stat_account_login'] = user.account_login
    context.user_data['stat_user_login'] = user.user_login

    # Обновляем время активности
    sheets.update_last_activity(chat_id)

    # Начинаем с текущего года
    display_year = datetime.now().year
    context.user_data['stat_display_year'] = display_year

    await update.message.reply_text(
        MSG_CHOOSE_PERIOD,
        reply_markup=build_period_keyboard(display_year)
    )

    return CHOOSE_PERIOD


async def handle_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка всех нажатий на клавиатуре периода"""
    query = update.callback_query
    await query.answer()

    data = query.data

    # Отмена
    if data == CB_STAT_CANCEL:
        await query.edit_message_text(MSG_STAT_CANCELLED)
        _cleanup_context(context)
        return ConversationHandler.END

    # Пустые кнопки (заглушки)
    if data == 'stat_noop':
        return CHOOSE_PERIOD

    # Навигация по годам: влево
    if data == CB_STAT_NAV_LEFT:
        display_year = context.user_data.get('stat_display_year', datetime.now().year)
        if display_year > STATISTICS_START_YEAR:
            display_year -= 1
            context.user_data['stat_display_year'] = display_year
        await query.edit_message_text(
            MSG_CHOOSE_PERIOD,
            reply_markup=build_period_keyboard(display_year)
        )
        return CHOOSE_PERIOD

    # Навигация по годам: вправо
    if data == CB_STAT_NAV_RIGHT:
        display_year = context.user_data.get('stat_display_year', datetime.now().year)
        if display_year < datetime.now().year:
            display_year += 1
            context.user_data['stat_display_year'] = display_year
        await query.edit_message_text(
            MSG_CHOOSE_PERIOD,
            reply_markup=build_period_keyboard(display_year)
        )
        return CHOOSE_PERIOD

    # Выбор годового отчёта
    if data.startswith(CB_STAT_YEAR_REPORT):
        year = int(data.replace(CB_STAT_YEAR_REPORT, ''))
        context.user_data['stat_year'] = year
        context.user_data['stat_month'] = None  # None = годовой отчёт

        logger.info(f"User {update.effective_chat.id} выбрал годовой отчёт за {year}")

        keyboard = [
            [
                InlineKeyboardButton("📊 Excel", callback_data=f"{CB_STAT_FORMAT}excel"),
                InlineKeyboardButton("📄 PDF", callback_data=f"{CB_STAT_FORMAT}pdf")
            ],
            [InlineKeyboardButton("Отмена", callback_data=CB_STAT_CANCEL)]
        ]

        await query.edit_message_text(
            f"📎 Годовой отчёт за {year}. Выберите формат:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSE_FORMAT

    # Выбор месяца
    if data.startswith(CB_STAT_MONTH):
        month = int(data.replace(CB_STAT_MONTH, ''))
        display_year = context.user_data.get('stat_display_year', datetime.now().year)
        context.user_data['stat_year'] = display_year
        context.user_data['stat_month'] = month

        month_name = MONTHS_RU[month]
        logger.info(f"User {update.effective_chat.id} выбрал {month_name} {display_year}")

        keyboard = [
            [
                InlineKeyboardButton("📊 Excel", callback_data=f"{CB_STAT_FORMAT}excel"),
                InlineKeyboardButton("📄 PDF", callback_data=f"{CB_STAT_FORMAT}pdf")
            ],
            [InlineKeyboardButton("Отмена", callback_data=CB_STAT_CANCEL)]
        ]

        await query.edit_message_text(
            f"📎 Отчёт за {month_name} {display_year}. Выберите формат:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSE_FORMAT

    return CHOOSE_PERIOD


async def choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора формата, генерация и отправка файла"""
    query = update.callback_query
    await query.answer()

    if query.data == CB_STAT_CANCEL:
        await query.edit_message_text(MSG_STAT_CANCELLED)
        _cleanup_context(context)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    fmt = query.data.replace(CB_STAT_FORMAT, '')
    year = context.user_data['stat_year']
    month = context.user_data.get('stat_month')  # None = годовой
    account_login = context.user_data['stat_account_login']

    is_yearly = month is None

    if is_yearly:
        period_label = str(year)
        months_to_process = list(range(1, 13))
        # Для текущего года — только до текущего месяца включительно
        now = datetime.now()
        if year == now.year:
            months_to_process = list(range(1, now.month + 1))
    else:
        period_label = f"{MONTHS_RU[month]} {year}"
        months_to_process = [month]

    context.user_data['stat_format'] = fmt

    logger.info(f"User {chat_id} requested statistics for {period_label} in {fmt} format")

    # Сообщение ожидания
    await query.edit_message_text(MSG_STAT_GENERATING)
    generating_message_id = query.message.message_id

    try:
        # Собираем данные за все нужные месяцы
        all_charges = []
        all_payments = {}

        for m in months_to_process:
            charges = sheets.get_charges_for_period(account_login, year, m)
            payments = sheets.get_payments_for_period(account_login, year, m)
            all_charges.extend(charges)
            all_payments.update(payments)

    except Exception as e:
        logger.error(f"Ошибка загрузки данных для статистики: {e}")
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=generating_message_id)
        except Exception:
            pass
        await context.bot.send_message(chat_id=chat_id, text=MSG_STAT_ERROR_LOAD)
        sheets.add_stat_log(
            status="ERROR",
            action="STAT_DATA_LOAD",
            message=f"Ошибка загрузки данных для {account_login} за {period_label}: {e}"
        )
        _cleanup_context(context)
        return ConversationHandler.END

    # Проверка наличия данных
    if not all_charges and not all_payments:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=generating_message_id)
        except Exception:
            pass
        no_data_msg = MSG_STAT_NO_DATA.format(
            month=period_label if is_yearly else MONTHS_RU[month],
            year=year if not is_yearly else ""
        ).strip()
        await context.bot.send_message(chat_id=chat_id, text=no_data_msg)
        sheets.add_stat_log(
            status="INFO",
            action="STAT_NO_DATA",
            message=f"Нет данных для {account_login} за {period_label}"
        )
        _cleanup_context(context)
        return ConversationHandler.END

    try:
        # Получаем текущий баланс и организацию для отчёта
        balance_info = sheets.get_account_balance(account_login)
        current_balance = 0.0
        organization = ''
        if balance_info:
            try:
                current_balance = float(balance_info.balance.replace(',', '.').replace(' ', ''))
            except (ValueError, TypeError, AttributeError):
                current_balance = 0.0
            organization = balance_info.organization or ''

        # --- Вычисляем initial_balance ---
        # initial_balance = current_balance - все_движения_от_начала_периода_до_сегодня
        today = date_type.today()
        total_period_charges = sum(item['charge'] for item in all_charges)
        total_period_payments = sum(all_payments.values())

        # Определяем, нужно ли загружать данные за промежуток после отчётного периода
        gap_charges = 0.0
        gap_payments = 0.0

        if is_yearly:
            # Для годового отчёта за прошлый год — промежуток от 1 января следующего года до сегодня
            if year < today.year:
                gap_start = date_type(year + 1, 1, 1)
                gap_charges, gap_payments = sheets.get_total_activity_for_range(
                    account_login, gap_start, today
                )
            # Для текущего года промежуток не нужен — данные уже до текущего месяца
        else:
            # Для месячного отчёта — промежуток от 1-го числа следующего месяца до сегодня
            last_day = calendar.monthrange(year, month)[1]
            period_end = date_type(year, month, last_day)
            if period_end < today:
                gap_start = period_end + timedelta(days=1)
                gap_charges, gap_payments = sheets.get_total_activity_for_range(
                    account_login, gap_start, today
                )

        initial_balance = (current_balance
                           - total_period_charges - gap_charges
                           - total_period_payments - gap_payments)

        # Генерируем отчёт
        if is_yearly:
            if fmt == 'excel':
                file_data = generate_excel(account_login, year, None,
                                           all_charges, all_payments, initial_balance,
                                           organization)
                filename = f"Статистика_{account_login}_{year}.xlsx"
            else:
                file_data = generate_pdf(account_login, year, None,
                                         all_charges, all_payments, initial_balance,
                                         organization)
                filename = f"Статистика_{account_login}_{year}.pdf"
        else:
            month_name = MONTHS_RU[month]
            if fmt == 'excel':
                file_data = generate_excel(account_login, year, month,
                                           all_charges, all_payments, initial_balance,
                                           organization)
                filename = f"Статистика_{account_login}_{month_name}_{year}.xlsx"
            else:
                file_data = generate_pdf(account_login, year, month,
                                         all_charges, all_payments, initial_balance,
                                         organization)
                filename = f"Статистика_{account_login}_{month_name}_{year}.pdf"

        # Удаляем сообщение «Формирую отчёт...»
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=generating_message_id)
        except Exception:
            pass

        # Отправляем файл
        done_msg = f"✅ Отчёт за {period_label} готов!"
        await context.bot.send_document(
            chat_id=chat_id,
            document=file_data,
            filename=filename,
            caption=done_msg
        )

        # Логируем успех
        sheets.add_stat_log(
            status="SUCCESS",
            action="STAT_REPORT",
            message=f"Отчёт {fmt.upper()} для {account_login} за {period_label} (chat_id: {chat_id})"
        )

        logger.info(f"Отчёт отправлен для {chat_id}: {filename}")

    except Exception as e:
        logger.error(f"Ошибка генерации отчёта: {e}")
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=generating_message_id)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text=MSG_STAT_ERROR_GENERATE
        )
        sheets.add_stat_log(
            status="ERROR",
            action="STAT_GENERATE",
            message=f"Ошибка генерации отчёта для {account_login} за {period_label}: {e}"
        )

    _cleanup_context(context)
    return ConversationHandler.END


def _cleanup_context(context: ContextTypes.DEFAULT_TYPE):
    """Очистка временных данных статистики из context"""
    for key in ['stat_year', 'stat_month', 'stat_format', 'stat_account_login',
                'stat_user_login', 'stat_display_year']:
        context.user_data.pop(key, None)


async def cancel_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена формирования отчёта"""
    logger.info(f"Статистика отменена для {update.effective_chat.id}")
    _cleanup_context(context)
    await update.message.reply_text(MSG_STAT_CANCELLED)
    return ConversationHandler.END


async def restart_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Повторный вызов статистики (при нажатии кнопки внутри диалога)"""
    _cleanup_context(context)
    return await statistics_start(update, context)


# Обработчик повторного нажатия кнопки «Статистика расчётов» внутри диалога
_restart_handler = MessageHandler(
    filters.Regex(f'^{BTN_STATISTICS}$'), restart_statistics
)

# Создание ConversationHandler для статистики
statistics_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(f'^{BTN_STATISTICS}$'), statistics_start)
    ],
    states={
        CHOOSE_PERIOD: [
            _restart_handler,
            CallbackQueryHandler(handle_period_selection)
        ],
        CHOOSE_FORMAT: [
            _restart_handler,
            CallbackQueryHandler(choose_format)
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_statistics),
        CallbackQueryHandler(handle_period_selection, pattern=f'^{CB_STAT_CANCEL}$')
    ]
)

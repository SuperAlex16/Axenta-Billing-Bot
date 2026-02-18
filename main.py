"""
Точка входа приложения Telegram Bot для Axenta Billing

Этот бот предоставляет следующий функционал:
- Регистрация пользователей через аутентификацию в API Axenta
- Показ информации о балансе аккаунта
- Настройка уведомлений при снижении баланса
- Хранение данных в Google Sheets
"""
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)

from apscheduler.triggers.cron import CronTrigger
from config import TELEGRAM_BOT_TOKEN
from handlers.start import registration_handler, get_main_menu
from handlers.info import show_balance
from handlers.notifications import notifications_handler
from handlers.logout import logout_command_handler, logout_callback_handler
from handlers.common import help_command
from handlers.statistics import statistics_handler
from services.notification_checker import NotificationChecker
from services.sheets_service import SheetsService
from utils.logger import setup_logger
from utils.constants import BTN_SHOW_BALANCE, BTN_HELP, BTN_STATISTICS

logger = setup_logger(__name__)


def clear_cache_job():
    """Задача очистки кэша (вызывается в 03:05 MSK после обновления БД)"""
    sheets = SheetsService()
    sheets.clear_all_cache()
    logger.info("Кэш очищен по расписанию (03:05 MSK)")


def cleanup_logs_job():
    """Задача очистки старых логов (вызывается в 03:10 MSK)"""
    sheets = SheetsService()
    deleted = sheets.cleanup_old_logs(days=30)
    logger.info(f"Очистка логов завершена: удалено {deleted} записей старше 30 дней")


async def post_init(application: Application):
    """Действия после инициализации бота"""
    logger.info("Бот инициализирован")

    # Запуск планировщика уведомлений (проверка каждую минуту)
    checker = NotificationChecker(application.bot)
    checker.start(check_interval_minutes=1)

    # Добавляем задачу очистки кэша в 03:05 MSK
    checker.scheduler.add_job(
        clear_cache_job,
        CronTrigger(hour=3, minute=5, timezone='Europe/Moscow'),
        id='cache_clear',
        name='Clear cache after DB update',
        replace_existing=True
    )
    logger.info("Задача очистки кэша добавлена (03:05 MSK)")

    # Добавляем задачу очистки старых логов в 03:10 MSK
    checker.scheduler.add_job(
        cleanup_logs_job,
        CronTrigger(hour=3, minute=10, timezone='Europe/Moscow'),
        id='logs_cleanup',
        name='Cleanup old logs (30 days)',
        replace_existing=True
    )
    logger.info("Задача очистки логов добавлена (03:10 MSK)")

    # Сохраняем checker в bot_data для последующего доступа
    application.bot_data['notification_checker'] = checker


async def error_handler(update: Update, context):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")

    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Произошла ошибка. Попробуйте позже или обратитесь к администратору."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def handle_help_button(update: Update, context):
    """Обработчик кнопки помощи"""
    await help_command(update, context)


def main():
    """Запуск бота"""
    logger.info("=" * 50)
    logger.info("Запуск Axenta Billing Bot")
    logger.info("=" * 50)

    # Проверка токена
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return

    # Создание приложения
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Регистрация обработчиков

    # 1. Регистрация (ConversationHandler для /start)
    application.add_handler(registration_handler)

    # 2. Статистика расчётов (ConversationHandler)
    application.add_handler(statistics_handler)

    # 3. Уведомления (ConversationHandler)
    application.add_handler(notifications_handler)

    # 4. Logout
    application.add_handler(logout_command_handler)
    # Callback handler в отдельной группе (-1), чтобы обрабатывался ДО ConversationHandlers
    application.add_handler(logout_callback_handler, group=-1)

    # 5. Команда /help
    application.add_handler(CommandHandler('help', help_command))

    # 6. Кнопка "Показать баланс"
    application.add_handler(
        MessageHandler(filters.Regex(f'^{BTN_SHOW_BALANCE}$'), show_balance)
    )

    # 7. Кнопка "Помощь"
    application.add_handler(
        MessageHandler(filters.Regex(f'^{BTN_HELP}$'), handle_help_button)
    )

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("Бот запущен и готов к работе!")
    logger.info("Уведомления проверяются каждую минуту")
    logger.info("Кэш очищается ежедневно в 03:05 MSK (Europe/Moscow)")
    logger.info("Логи старше 30 дней удаляются ежедневно в 03:10 MSK (Europe/Moscow)")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == '__main__':
    main()

"""Сервис проверки уведомлений о балансе (по указанному времени)"""
import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import TYPE_CHECKING, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.logger import setup_logger
from utils.constants import (
    MSG_BALANCE_ALERT,
    NOTIF_SEND_STATUS_SEND, NOTIF_SEND_STATUS_WAIT
)
from config import NOTIFICATION_TIMEZONE

if TYPE_CHECKING:
    from telegram import Bot

logger = setup_logger(__name__)


class NotificationChecker:
    """
    Сервис проверки уведомлений о балансе.
    Отправляет уведомления в указанное пользователем время с учётом его timezone.
    """

    def __init__(self, bot: 'Bot'):
        """
        Инициализация сервиса

        Args:
            bot: Экземпляр Telegram Bot
        """
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=NOTIFICATION_TIMEZONE)
        self._sheets_service = None

    @property
    def sheets_service(self):
        """Ленивая инициализация SheetsService"""
        if self._sheets_service is None:
            from services.sheets_service import SheetsService
            self._sheets_service = SheetsService()
        return self._sheets_service

    def start(self, check_interval_minutes: int = 1):
        """
        Запуск планировщика проверок.
        Проверка запускается каждую минуту для точного соответствия времени.

        Args:
            check_interval_minutes: Интервал проверки в минутах (по умолчанию 1)
        """
        # Проверяем каждую минуту
        self.scheduler.add_job(
            self.check_notifications,
            CronTrigger(minute=f'*/{check_interval_minutes}'),
            id='notification_check',
            name='Check balance notifications by time',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"Планировщик уведомлений запущен (проверка каждые {check_interval_minutes} мин)")

    def stop(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик уведомлений остановлен")

    def _get_user_local_time(self, utc_offset: str) -> datetime:
        """
        Получение текущего времени в timezone пользователя

        Args:
            utc_offset: Сдвиг от UTC (например "5" для UTC+5)

        Returns:
            Текущее время в timezone пользователя
        """
        try:
            offset_hours = int(utc_offset) if utc_offset else 3
        except (ValueError, TypeError):
            offset_hours = 3  # По умолчанию Москва (UTC+3)

        utc_now = datetime.now(dt_timezone.utc)
        user_tz = dt_timezone(timedelta(hours=offset_hours))
        return utc_now.astimezone(user_tz)

    def _should_send_now(self, notification_time: str, utc_offset: str) -> bool:
        """
        Проверка, нужно ли отправить уведомление сейчас

        Args:
            notification_time: Время уведомления в формате HH:MM
            utc_offset: Сдвиг от UTC пользователя

        Returns:
            True если текущее время совпадает с временем уведомления
        """
        if not notification_time:
            return False

        try:
            # Парсим время уведомления
            notif_hour, notif_minute = map(int, notification_time.split(':'))

            # Получаем текущее время пользователя
            user_time = self._get_user_local_time(utc_offset)

            # Сравниваем час и минуту
            return user_time.hour == notif_hour and user_time.minute == notif_minute

        except (ValueError, AttributeError) as e:
            logger.warning(f"Ошибка парсинга времени '{notification_time}': {e}")
            return False

    async def check_notifications(self):
        """Проверка всех активных уведомлений"""
        logger.debug("Начало проверки уведомлений")

        try:
            # Получаем все активные уведомления
            notifications = self.sheets_service.get_all_active_notifications()

            if not notifications:
                logger.debug("Нет активных уведомлений для проверки")
                return

            # Группируем уведомления по user_login для получения timezone
            notifications_to_process = []

            for notification in notifications:
                # Получаем timezone пользователя
                utc_offset = self.sheets_service.get_user_timezone(notification.account_login)

                # Проверяем, нужно ли отправить сейчас
                if self._should_send_now(notification.notification_time, utc_offset):
                    notifications_to_process.append(notification)

            if not notifications_to_process:
                logger.debug("Нет уведомлений для отправки в текущее время")
                return

            logger.info(f"Найдено {len(notifications_to_process)} уведомлений для отправки")

            for notification in notifications_to_process:
                await self._process_notification(notification)

            logger.info("Проверка уведомлений завершена")

        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}")

    async def _process_notification(self, notification):
        """
        Обработка одного уведомления

        Args:
            notification: Объект Notification
        """
        try:
            # Получаем текущий баланс аккаунта
            balance_info = self.sheets_service.get_account_balance(notification.account_login)

            if not balance_info:
                logger.warning(f"Не удалось получить баланс для {notification.account_login}")
                return

            # Преобразуем баланс в число
            try:
                current_balance = float(balance_info.balance.replace(',', '.').replace(' ', ''))
            except (ValueError, AttributeError):
                logger.warning(f"Невалидный баланс: {balance_info.balance}")
                return

            threshold = notification.threshold

            # Проверяем условия отправки
            if current_balance <= threshold and notification.send_status == NOTIF_SEND_STATUS_SEND:
                # Баланс ниже порога и нужно отправить уведомление
                await self._send_notification(notification, current_balance)

                # Обновляем статус на "Ожидание" (чтобы не отправлять повторно)
                self.sheets_service.update_notification_status(
                    notification.chat_id,
                    notification.notification_id,
                    str(current_balance),
                    NOTIF_SEND_STATUS_WAIT
                )

            elif current_balance > threshold and notification.send_status == NOTIF_SEND_STATUS_WAIT:
                # Баланс выше порога, сбрасываем статус на "Отправить"
                self.sheets_service.update_notification_status(
                    notification.chat_id,
                    notification.notification_id,
                    str(current_balance),
                    NOTIF_SEND_STATUS_SEND
                )
                logger.info(
                    f"Баланс {notification.account_login} восстановлен выше порога "
                    f"({current_balance} > {threshold})"
                )

        except Exception as e:
            logger.error(f"Ошибка обработки уведомления {notification.notification_id}: {e}")

    async def _send_notification(self, notification, current_balance: float):
        """
        Отправка уведомления пользователю

        Args:
            notification: Объект Notification
            current_balance: Текущий баланс
        """
        try:
            message = MSG_BALANCE_ALERT.format(
                balance=current_balance,
                threshold=notification.threshold
            )

            await self.bot.send_message(
                chat_id=notification.chat_id,
                text=message
            )

            logger.info(
                f"Уведомление отправлено: chat_id={notification.chat_id}, "
                f"баланс={current_balance}, порог={notification.threshold}, "
                f"время={notification.notification_time}"
            )

            # Добавляем запись в лог
            self.sheets_service.add_log(
                status="INFO",
                action="NOTIFICATION_SENT",
                message=f"Уведомление отправлено пользователю {notification.chat_id}: "
                        f"баланс {current_balance} <= порог {notification.threshold} "
                        f"в {notification.notification_time}"
            )

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

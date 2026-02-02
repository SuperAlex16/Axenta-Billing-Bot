"""Сервис для работы с Google Sheets (Singleton с кэшированием)"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from threading import Lock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE
from utils.logger import setup_logger
from utils.constants import (
    SHEET_USERS, SHEET_DATA, SHEET_CHATS, SHEET_NOTIFICATIONS, SHEET_LOGS,
    USERS_COL_LOGIN, USERS_COL_ACCOUNT, USERS_COL_IS_ADMIN,
    DATA_COL_ACCOUNT,
    NOTIF_COL_CHAT_ID, NOTIF_COL_ID, NOTIF_COL_STATUS,
    AUTH_STATUS_PASSED, NOTIF_STATUS_ACTIVE, NOTIF_STATUS_DELETED,
    NOTIF_SEND_STATUS_WAIT, NOTIF_SEND_STATUS_SENT
)
from models.user import User, AccountBalance, Notification

logger = setup_logger(__name__)


class SheetsService:
    """
    Сервис для работы с Google Sheets.
    Реализован как Singleton с кэшированием.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Singleton: всегда возвращает один и тот же экземпляр"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Инициализация (выполняется только один раз)"""
        if self._initialized:
            return

        self.client = None
        self.spreadsheet = None

        # Кэш для данных
        self._cache: Dict[str, Dict[str, Any]] = {
            'users': {},      # chat_id -> (User, timestamp)
            'balances': {},   # account_login -> (AccountBalance, timestamp)
            'logins': {},     # user_login -> (dict, timestamp)
        }
        self._cache_ttl = 3600  # 1 час

        self._connect()
        self._initialized = True

    def _connect(self):
        """Подключение к Google Sheets"""
        try:
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE,
                scopes=scope
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(GOOGLE_SHEET_ID)
            logger.info("Подключение к Google Sheets успешно")
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets: {e}")
            raise

    def _is_cache_valid(self, cache_key: str, item_key: str) -> bool:
        """Проверка валидности кэша"""
        if cache_key not in self._cache:
            return False
        if item_key not in self._cache[cache_key]:
            return False

        _, timestamp = self._cache[cache_key][item_key]
        return (datetime.now() - timestamp).total_seconds() < self._cache_ttl

    def _get_from_cache(self, cache_key: str, item_key: str) -> Optional[Any]:
        """Получение из кэша"""
        if self._is_cache_valid(cache_key, item_key):
            data, _ = self._cache[cache_key][item_key]
            return data
        return None

    def _set_cache(self, cache_key: str, item_key: str, data: Any):
        """Сохранение в кэш"""
        if cache_key not in self._cache:
            self._cache[cache_key] = {}
        self._cache[cache_key][item_key] = (data, datetime.now())

    def _invalidate_cache(self, cache_key: str, item_key: str = None):
        """Инвалидация кэша"""
        if item_key:
            if cache_key in self._cache and item_key in self._cache[cache_key]:
                del self._cache[cache_key][item_key]
        elif cache_key in self._cache:
            self._cache[cache_key] = {}

    def clear_all_cache(self):
        """Полная очистка всего кэша (вызывается после обновления БД)"""
        for cache_key in self._cache:
            self._cache[cache_key] = {}
        logger.info("Весь кэш очищен")

    def get_worksheet(self, sheet_name: str) -> Optional[gspread.Worksheet]:
        """Получить лист по имени"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Лист '{sheet_name}' не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения листа '{sheet_name}': {e}")
            return None

    # ==================== Методы для работы с пользователями ====================

    def find_user_login(self, user_login: str) -> Optional[Dict[str, str]]:
        """Поиск логина в листе Пользователи (с кэшированием)"""
        # Проверяем кэш
        cached = self._get_from_cache('logins', user_login)
        if cached is not None:
            logger.debug(f"Логин '{user_login}' найден в кэше")
            return cached

        sheet = self.get_worksheet(SHEET_USERS)
        if not sheet:
            return None

        try:
            # Ищем только в колонке логинов (F = USERS_COL_LOGIN + 1)
            cell = sheet.find(user_login, in_column=USERS_COL_LOGIN + 1)
            if not cell:
                logger.info(f"Логин '{user_login}' не найден в таблице")
                return None

            logger.info(f"Логин найден в строке {cell.row}, колонке {cell.col}")

            row = sheet.row_values(cell.row)
            # Используем фиксированные индексы колонок из констант
            account_col = USERS_COL_ACCOUNT      # G - Account Name
            admin_col = USERS_COL_IS_ADMIN       # J - Is Admin
            timezone_col = 8  # Колонка I (0-based index)

            account_name = row[account_col] if len(row) > account_col else ''
            is_admin = row[admin_col] if len(row) > admin_col else ''
            timezone = row[timezone_col] if len(row) > timezone_col else '3'

            result = {
                'account_name': account_name,
                'is_admin': is_admin,
                'timezone': timezone
            }

            # Сохраняем в кэш
            self._set_cache('logins', user_login, result)
            logger.info(f"account_name={account_name}, is_admin={is_admin}, timezone={timezone}")

            return result
        except Exception as e:
            logger.error(f"Ошибка поиска логина: {e}")
            return None

    def get_user_timezone(self, user_login: str) -> str:
        """Получение timezone пользователя из листа Пользователи (колонка I)"""
        user_info = self.find_user_login(user_login)
        if user_info:
            tz = user_info.get('timezone', '3')
            return tz if tz else '3'  # По умолчанию UTC+3 (Москва)
        return '3'

    def get_user_by_chat_id(self, chat_id: int) -> Optional[User]:
        """Получение данных пользователя по chat_id (с кэшированием)"""
        cache_key = str(chat_id)

        # Проверяем кэш
        cached = self._get_from_cache('users', cache_key)
        if cached is not None:
            logger.debug(f"Пользователь {chat_id} найден в кэше")
            return cached

        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return None

        try:
            cell = sheet.find(str(chat_id), in_column=1)
            if not cell:
                return None

            row = sheet.row_values(cell.row)
            user = User.from_row(row)

            # Сохраняем в кэш
            self._set_cache('users', cache_key, user)

            return user
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None

    def register_user(self, user: User) -> bool:
        """Регистрация нового пользователя"""
        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return False

        try:
            existing = self.get_user_by_chat_id(user.chat_id)
            if existing:
                return self.update_user(user)

            sheet.append_row(user.to_row())
            logger.info(f"Пользователь {user.chat_id} зарегистрирован")

            # Инвалидируем кэш
            self._invalidate_cache('users', str(user.chat_id))

            return True
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            return False

    def update_user(self, user: User) -> bool:
        """Обновление данных пользователя"""
        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return False

        try:
            cell = sheet.find(str(user.chat_id), in_column=1)
            if not cell:
                return False

            row_range = f'A{cell.row}:O{cell.row}'
            sheet.update(row_range, [user.to_row()])
            logger.info(f"Данные пользователя {user.chat_id} обновлены")

            # Инвалидируем кэш
            self._invalidate_cache('users', str(user.chat_id))

            return True
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {e}")
            return False

    def update_user_field(self, chat_id: int, field_index: int, value: str) -> bool:
        """Обновление конкретного поля пользователя"""
        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return False

        try:
            cell = sheet.find(str(chat_id), in_column=1)
            if not cell:
                return False

            sheet.update_cell(cell.row, field_index + 1, value)

            # Инвалидируем кэш
            self._invalidate_cache('users', str(chat_id))

            return True
        except Exception as e:
            logger.error(f"Ошибка обновления поля: {e}")
            return False

    def update_last_activity(self, chat_id: int) -> bool:
        """Обновление времени последней активности"""
        return self.update_user_field(
            chat_id,
            14,  # COL_LAST_ACTIVITY
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

    def recheck_admin_status(self, chat_id: int, user_login: str) -> tuple[bool, str]:
        """
        Повторная проверка статуса IsAdmin из листа Пользователи.
        Обновляет IsAdmin, last_check и next_check в листе Чаты.

        Args:
            chat_id: ID чата пользователя
            user_login: Логин пользователя в системе Axenta

        Returns:
            (is_admin: bool, message: str) - является ли админом и сообщение
        """
        # Получаем актуальный статус из листа Пользователи
        user_info = self.find_user_login(user_login)

        if not user_info:
            logger.warning(f"Логин {user_login} не найден при повторной проверке")
            return False, "Логин не найден в системе"

        is_admin = user_info.get('is_admin', '').lower().strip()
        is_admin_yes = is_admin == 'да'

        now = datetime.now()
        last_check = now.strftime('%Y-%m-%d %H:%M:%S')
        next_check = (now + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')

        # Обновляем поля в листе Чаты
        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return False, "Ошибка доступа к данным"

        try:
            cell = sheet.find(str(chat_id), in_column=1)
            if not cell:
                return False, "Пользователь не найден"

            # Обновляем IsAdmin (H), last_check (L), next_check (M) одним запросом
            sheet.batch_update([
                {'range': f'H{cell.row}', 'values': [[user_info.get('is_admin', '')]]},
                {'range': f'L{cell.row}', 'values': [[last_check]]},
                {'range': f'M{cell.row}', 'values': [[next_check]]}
            ])

            # Инвалидируем кэш
            self._invalidate_cache('users', str(chat_id))

            logger.info(f"Статус IsAdmin обновлён для {chat_id}: {is_admin}, след. проверка: {next_check}")

            if is_admin_yes:
                return True, "Статус подтверждён"
            else:
                return False, "Статус администратора отозван"

        except Exception as e:
            logger.error(f"Ошибка обновления статуса IsAdmin: {e}")
            return False, f"Ошибка проверки: {e}"

    def logout_user(self, chat_id: int) -> tuple[bool, int]:
        """
        Выход пользователя из аккаунта.
        Очищает данные авторизации и удаляет все уведомления.

        Args:
            chat_id: ID чата пользователя

        Returns:
            (success: bool, deleted_notifications: int)
        """
        sheet = self.get_worksheet(SHEET_CHATS)
        if not sheet:
            return False, 0

        try:
            cell = sheet.find(str(chat_id), in_column=1)
            if not cell:
                return False, 0

            # Очищаем данные авторизации: token (J), auth_status (K)
            sheet.batch_update([
                {'range': f'J{cell.row}', 'values': [['']]},  # token
                {'range': f'K{cell.row}', 'values': [['Выход']]}  # auth_status
            ])

            # Инвалидируем кэш пользователя
            self._invalidate_cache('users', str(chat_id))
            self._invalidate_cache('logins')

            logger.info(f"Пользователь {chat_id} вышел из аккаунта")

            # Удаляем все уведомления пользователя
            deleted_count = self._delete_all_user_notifications(chat_id)

            return True, deleted_count

        except Exception as e:
            logger.error(f"Ошибка выхода пользователя: {e}")
            return False, 0

    def _delete_all_user_notifications(self, chat_id: int) -> int:
        """Удаление всех уведомлений пользователя"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return 0

        try:
            all_values = sheet.get_all_values()
            deleted_count = 0

            for idx, row in enumerate(all_values[1:], start=2):
                if row[NOTIF_COL_CHAT_ID] == str(chat_id) and row[NOTIF_COL_STATUS] == NOTIF_STATUS_ACTIVE:
                    sheet.update_cell(idx, NOTIF_COL_STATUS + 1, NOTIF_STATUS_DELETED)
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} уведомлений для chat_id={chat_id}")

            return deleted_count

        except Exception as e:
            logger.error(f"Ошибка удаления уведомлений: {e}")
            return 0

    # ==================== Методы для работы с балансом ====================

    def get_account_balance(self, account_login: str) -> Optional[AccountBalance]:
        """Получение информации о балансе аккаунта (с кэшированием)"""
        # Проверяем кэш
        cached = self._get_from_cache('balances', account_login)
        if cached is not None:
            logger.debug(f"Баланс '{account_login}' найден в кэше")
            return cached

        sheet = self.get_worksheet(SHEET_DATA)
        if not sheet:
            return None

        try:
            # Ищем аккаунт во всей таблице
            cell = sheet.find(account_login)
            if not cell:
                logger.info(f"Аккаунт '{account_login}' не найден в данных")
                return None

            logger.info(f"Аккаунт найден в строке {cell.row}, колонке {cell.col}")

            row = sheet.row_values(cell.row)
            logger.info(f"Строка содержит {len(row)} колонок: {row[:12] if len(row) >= 12 else row}")

            # Используем относительные индексы от найденной ячейки
            # По ТЗ: B-аккаунт, C-организация, G-тариф, H-списание, J-объекты, K-баланс, L-дни
            account_col = cell.col - 1  # 0-based

            # Вычисляем индексы относительно колонки B (индекс 1)
            base_offset = account_col - 1  # Сдвиг от колонки B

            org_col = 2 + base_offset      # C
            tariff_col = 6 + base_offset   # G
            charge_col = 7 + base_offset   # H
            objects_col = 9 + base_offset  # J
            balance_col = 10 + base_offset # K
            days_col = 11 + base_offset    # L

            balance = AccountBalance(
                account_login=account_login,
                organization=row[org_col] if len(row) > org_col else '',
                tariff=row[tariff_col] if len(row) > tariff_col else '0',
                avg_charge=row[charge_col] if len(row) > charge_col else '0',
                active_objects=row[objects_col] if len(row) > objects_col else '0',
                balance=row[balance_col] if len(row) > balance_col else '0',
                days_left=row[days_col] if len(row) > days_col else '0'
            )

            logger.info(f"Баланс: {balance.balance}, дней: {balance.days_left}")

            # Сохраняем в кэш
            self._set_cache('balances', account_login, balance)

            return balance
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return None

    # ==================== Методы для работы с уведомлениями ====================

    def add_notification(self, notification: Notification) -> bool:
        """Добавление нового уведомления"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return False

        try:
            ids = sheet.col_values(NOTIF_COL_ID + 1)[1:]
            next_id = max([int(i) for i in ids if i.isdigit()], default=0) + 1
            notification.notification_id = next_id

            sheet.append_row(notification.to_row())
            logger.info(f"Уведомление {next_id} создано для {notification.chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления уведомления: {e}")
            return False

    def get_user_notifications(self, chat_id: int) -> List[Notification]:
        """Получение всех активных уведомлений пользователя"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return []

        try:
            all_values = sheet.get_all_values()
            notifications = []

            for row in all_values[1:]:
                if row[NOTIF_COL_CHAT_ID] == str(chat_id) and row[NOTIF_COL_STATUS] == NOTIF_STATUS_ACTIVE:
                    notifications.append(Notification.from_row(row))

            return notifications
        except Exception as e:
            logger.error(f"Ошибка получения уведомлений: {e}")
            return []

    def delete_notification(self, chat_id: int, notification_id: int) -> bool:
        """Удаление уведомления (изменение статуса)"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return False

        try:
            all_values = sheet.get_all_values()
            for idx, row in enumerate(all_values[1:], start=2):
                if (row[NOTIF_COL_CHAT_ID] == str(chat_id) and
                        row[NOTIF_COL_ID] == str(notification_id)):
                    sheet.update_cell(idx, NOTIF_COL_STATUS + 1, NOTIF_STATUS_DELETED)
                    logger.info(f"Уведомление {notification_id} удалено")
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления уведомления: {e}")
            return False

    def get_all_active_notifications(self) -> List[Notification]:
        """Получение всех активных уведомлений (для фоновой проверки)"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return []

        try:
            all_values = sheet.get_all_values()
            notifications = []

            for row in all_values[1:]:
                if row[NOTIF_COL_STATUS] == NOTIF_STATUS_ACTIVE:
                    notifications.append(Notification.from_row(row))

            return notifications
        except Exception as e:
            logger.error(f"Ошибка получения всех уведомлений: {e}")
            return []

    def update_notification_status(self, chat_id: int, notification_id: int,
                                   current_balance: str, send_status: str) -> bool:
        """Обновление статуса уведомления"""
        sheet = self.get_worksheet(SHEET_NOTIFICATIONS)
        if not sheet:
            return False

        try:
            all_values = sheet.get_all_values()
            for idx, row in enumerate(all_values[1:], start=2):
                if (row[NOTIF_COL_CHAT_ID] == str(chat_id) and
                        row[NOTIF_COL_ID] == str(notification_id)):
                    sheet.update_cell(idx, 8, current_balance)
                    sheet.update_cell(idx, 9, send_status)
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления статуса уведомления: {e}")
            return False

    # ==================== Методы для логирования ====================

    def add_log(self, status: str, action: str, message: str) -> bool:
        """Добавление записи в лог"""
        sheet = self.get_worksheet(SHEET_LOGS)
        if not sheet:
            return False

        try:
            now = datetime.now()
            row = [
                now.strftime('%Y-%m-%d'),
                now.strftime('%H:%M:%S'),
                status,
                action,
                message
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления лога: {e}")
            return False


# Глобальный экземпляр для удобства импорта
def get_sheets_service() -> SheetsService:
    """Получить экземпляр SheetsService (Singleton)"""
    return SheetsService()

"""Модели данных пользователя"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Модель пользователя бота"""
    chat_id: int
    user_id: int
    first_name: str = ''
    last_name: str = ''
    username: str = ''
    user_login: str = ''
    account_login: str = ''
    is_admin: str = ''
    email: str = ''
    token: str = ''
    auth_status: str = ''
    last_check: str = ''
    next_check: str = ''
    registration_date: str = ''
    last_activity: str = ''

    def to_row(self) -> list:
        """Преобразование в строку для Google Sheets"""
        return [
            str(self.chat_id),
            str(self.user_id),
            self.first_name,
            self.last_name,
            self.username,
            self.user_login,
            self.account_login,
            self.is_admin,
            self.email,
            self.token,
            self.auth_status,
            self.last_check,
            self.next_check,
            self.registration_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            self.last_activity or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]

    @classmethod
    def from_row(cls, row: list) -> 'User':
        """Создание из строки Google Sheets"""
        return cls(
            chat_id=int(row[0]) if row[0] else 0,
            user_id=int(row[1]) if len(row) > 1 and row[1] else 0,
            first_name=row[2] if len(row) > 2 else '',
            last_name=row[3] if len(row) > 3 else '',
            username=row[4] if len(row) > 4 else '',
            user_login=row[5] if len(row) > 5 else '',
            account_login=row[6] if len(row) > 6 else '',
            is_admin=row[7] if len(row) > 7 else '',
            email=row[8] if len(row) > 8 else '',
            token=row[9] if len(row) > 9 else '',
            auth_status=row[10] if len(row) > 10 else '',
            last_check=row[11] if len(row) > 11 else '',
            next_check=row[12] if len(row) > 12 else '',
            registration_date=row[13] if len(row) > 13 else '',
            last_activity=row[14] if len(row) > 14 else ''
        )

    def is_authenticated(self) -> bool:
        """Проверка аутентификации"""
        if self.auth_status != 'Пройдена':
            return False
        if self.next_check:
            try:
                next_check_date = datetime.strptime(self.next_check, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > next_check_date:
                    return False
            except ValueError:
                pass
        return True

    def needs_admin_recheck(self) -> bool:
        """Проверка необходимости повторной проверки IsAdmin"""
        if not self.next_check:
            return True
        try:
            next_check_date = datetime.strptime(self.next_check, '%Y-%m-%d %H:%M:%S')
            return datetime.now() > next_check_date
        except ValueError:
            return True


@dataclass
class AccountBalance:
    """Модель информации о балансе аккаунта"""
    account_login: str
    organization: str = ''
    tariff: str = '0'
    avg_charge: str = '0'
    active_objects: str = '0'
    balance: str = '0'
    days_left: str = '0'

    @classmethod
    def from_row(cls, account_login: str, row: list) -> 'AccountBalance':
        """Создание из строки Google Sheets"""
        return cls(
            account_login=account_login,
            organization=row[2] if len(row) > 2 else '',
            tariff=row[6] if len(row) > 6 else '0',
            avg_charge=row[7] if len(row) > 7 else '0',
            active_objects=row[9] if len(row) > 9 else '0',
            balance=row[10] if len(row) > 10 else '0',
            days_left=row[11] if len(row) > 11 else '0'
        )

    def format_message(self, user_login: str = None) -> str:
        """Форматирование сообщения о балансе"""
        display_name = user_login if user_login else self.account_login
        return f"""🏢 Аккаунт: {display_name}
📅 Дата запроса: {datetime.now().strftime('%d.%m.%Y')}

📊 Тариф за 1 объект: {self.tariff} руб/день
📦 Активных объектов: {self.active_objects}
💸 Средняя сумма списания: {self.avg_charge} руб/день

💰 Текущий баланс: {self.balance} руб
⏳ Баланса хватит на: {self.days_left} дней

_Данные обновляются 1 раз в сутки!_"""


@dataclass
class Notification:
    """Модель уведомления"""
    chat_id: int
    account_login: str
    auth_status: str = ''
    notification_id: int = 0
    status: str = 'Установлено'
    threshold: float = 0.0
    notification_time: str = ''
    current_balance: str = ''
    send_status: str = 'Ожидание'

    def to_row(self) -> list:
        """Преобразование в строку для Google Sheets"""
        return [
            str(self.chat_id),
            self.account_login,
            self.auth_status,
            str(self.notification_id),
            self.status,
            str(self.threshold),
            self.notification_time,
            self.current_balance,
            self.send_status
        ]

    @classmethod
    def from_row(cls, row: list) -> 'Notification':
        """Создание из строки Google Sheets"""
        return cls(
            chat_id=int(row[0]) if row[0] else 0,
            account_login=row[1] if len(row) > 1 else '',
            auth_status=row[2] if len(row) > 2 else '',
            notification_id=int(row[3]) if len(row) > 3 and row[3].isdigit() else 0,
            status=row[4] if len(row) > 4 else '',
            threshold=float(row[5]) if len(row) > 5 and row[5] else 0.0,
            notification_time=row[6] if len(row) > 6 else '',
            current_balance=row[7] if len(row) > 7 else '',
            send_status=row[8] if len(row) > 8 else ''
        )

    def is_active(self) -> bool:
        """Проверка активности уведомления"""
        return self.status == 'Установлено'

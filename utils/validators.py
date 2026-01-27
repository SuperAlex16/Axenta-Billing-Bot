"""Валидация данных"""
import re
from typing import Tuple


def validate_email(email: str) -> bool:
    """Валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_amount(amount: str) -> Tuple[bool, float]:
    """Валидация суммы (должна быть положительным числом)"""
    try:
        # Заменяем запятую на точку для поддержки русского формата
        amount = amount.replace(',', '.')
        value = float(amount)
        if value > 0:
            return True, value
        return False, 0.0
    except ValueError:
        return False, 0.0


def validate_login(login: str) -> bool:
    """Валидация логина (не пустой, минимум 3 символа)"""
    if not login or len(login.strip()) < 3:
        return False
    return True

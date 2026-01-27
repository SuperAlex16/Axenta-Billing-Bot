"""Сервис для работы с Axenta API"""
import httpx
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import AXENTA_API_URL, AXENTA_AUTH_ENDPOINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AxentaAPI:
    """Сервис для работы с Axenta API"""

    def __init__(self):
        """Инициализация API клиента"""
        self.base_url = AXENTA_API_URL.rstrip('/')
        self.auth_endpoint = AXENTA_AUTH_ENDPOINT

    async def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Аутентификация пользователя и получение токена

        Args:
            username: Логин пользователя
            password: Пароль пользователя

        Returns:
            Токен при успешной аутентификации, None при ошибке
        """
        url = f"{self.base_url}{self.auth_endpoint}"

        payload = {
            "username": username,
            "password": password
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    token = data.get('token')
                    if token:
                        logger.info(f"Успешная аутентификация для {username}")
                        return token
                    else:
                        logger.warning(f"Токен не найден в ответе для {username}")
                        return None
                elif response.status_code == 401:
                    logger.warning(f"Неверные учётные данные для {username}")
                    return None
                elif response.status_code == 403:
                    logger.warning(f"Доступ запрещён для {username}")
                    return None
                else:
                    logger.warning(f"Ошибка аутентификации: статус {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Таймаут при аутентификации для {username}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Ошибка сети при аутентификации: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при аутентификации: {e}")
            return None

    async def validate_token(self, token: str) -> bool:
        """
        Проверка валидности токена

        Args:
            token: Токен для проверки

        Returns:
            True если токен валиден, False иначе
        """
        # Этот метод можно расширить для проверки токена через API
        # Пока возвращаем True, если токен не пустой
        return bool(token)

    async def get_account_info(self, token: str, account_login: str) -> Optional[dict]:
        """
        Получение информации об аккаунте через API

        Args:
            token: Токен авторизации
            account_login: Логин аккаунта

        Returns:
            Информация об аккаунте или None
        """
        # Этот метод можно реализовать, если API поддерживает получение данных
        # Пока данные берутся из Google Sheets
        return None

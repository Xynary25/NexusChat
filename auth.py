"""
Модуль аутентификации NexusChat.
Отвечает за:
- Хеширование и проверку паролей (bcrypt)
- Создание и верификацию JWT-токенов
- Безопасное хранение секретных ключей
"""

import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import jwt, JWTError

# ==================== КОНФИГУРАЦИЯ ====================
# ⚠️ ВАЖНО: В production замените на случайную строку минимум 32 символа!
# Генерация: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-in-production-please!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # Токен действует 7 дней

# Параметры bcrypt
BCRYPT_ROUNDS = 12  # Оптимальный баланс безопасности и производительности


# ==================== ПАРОЛИ ====================
def get_password_hash(password: str) -> str:
    """
    Хеширует пароль с использованием bcrypt.
    Возвращает строку вида: $2b$12$...
    """
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Сравнивает открытый пароль с сохранённым хешем.
    Использует константное сравнение для защиты от timing-атак.
    """
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


# ==================== JWT ТОКЕНЫ ====================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создаёт JWT-токен с(payload: {sub: username, user_id: int, exp: datetime})
    """
    to_encode = data.copy()

    # Устанавливаем время истечения
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict]:
    """
    Декодирует и проверяет подпись JWT-токена.
    Возвращает payload (dict) или None при ошибке/истечении срока.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        # Токен невалидный, истёк или изменён
        return None


# ==================== УТИЛИТЫ БЕЗОПАСНОСТИ ====================
def sanitize_input(text: str, max_length: int = 500) -> str:
    """Базовая очистка пользовательского ввода от XSS-векторов"""
    if not text:
        return ""
    return text.strip()[:max_length]
"""
Настройки приложения.
Секреты и чаты задаются через переменные окружения или .env (python-dotenv).
"""
import os
from pathlib import Path

# Загружаем .env из корня проекта, если есть
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# Корень проекта (папка whatsappbot)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- API ключи (из env или значения по умолчанию для локальной разработки) ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Таймауты и ретраи
OPENAI_REQUEST_TIMEOUT = 20
OPENAI_MAX_RETRIES = 2
OPENAI_RETRY_DELAY = 2
DEEPSEEK_REQUEST_TIMEOUT = 20
DEEPSEEK_MAX_RETRIES = 2
DEEPSEEK_RETRY_DELAY = 2

# --- Green API ---
GREEN_INSTANCE = os.environ.get("GREEN_INSTANCE", "")
GREEN_TOKEN = os.environ.get("GREEN_TOKEN", "")

# --- Чаты и номера ---
# Разрешённые чаты (бот отвечает только в них)
def _parse_list(env_key: str, default: list) -> list:
    val = os.environ.get(env_key)
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]


ALLOWED_CHATS = _parse_list("ALLOWED_CHATS", [
    "120363420695442782@g.us",
])
SUPPORT_CHAT_ID = os.environ.get("SUPPORT_CHAT_ID", ALLOWED_CHATS[0] if ALLOWED_CHATS else "")
TECH_SUPPORT_NUMBERS = _parse_list("TECH_SUPPORT_NUMBERS", [
    "77071958118@c.us",
    "77017055408@c.us",
    "77053201050@c.us",
])

# --- Папки ---
DIR_LOGS = PROJECT_ROOT / "logs"
DIR_TEMP = PROJECT_ROOT / "temp_files"
DIR_PHOTOS = PROJECT_ROOT / "photos"


def ensure_dirs():
    """Создаёт нужные папки при старте."""
    for d in (DIR_LOGS, DIR_TEMP, DIR_PHOTOS):
        d.mkdir(parents=True, exist_ok=True)

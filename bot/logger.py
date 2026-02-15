"""Логирование в консоль и в файл."""
from datetime import datetime

from bot.config import DIR_LOGS


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    log_file = DIR_LOGS / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except OSError:
        pass

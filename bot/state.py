"""
Глобальное состояние бота: активность и очереди пользователей.
Меняется командами из чата поддержки («бот стоп» / «бот старт»).
"""
import time

# Включён ли бот (обрабатывать ли сообщения)
bot_active = True
# Время последнего «бот старт» — сообщения старше пропускаем
bot_started_at: float | None = None

# Состояния по чатам: chat_id -> {state, original_problem, sender_number, timestamp, image_path?}
user_states: dict = {}

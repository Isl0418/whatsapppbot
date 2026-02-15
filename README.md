# WhatsApp Bot — техподдержка

Бот для WhatsApp (Green API): принимает сообщения и фото из рабочих чатов, спрашивает «решено?» (кнопки или 1/2), при ответе «нет» ищет инструкцию по ключам или через DeepSeek/OpenAI и отправляет её в чат.

## Архитектура

```
whatsappbot/
├── run.py              # Точка входа: python run.py
├── requirements.txt
├── .env.example         # Шаблон переменных окружения
├── .gitignore
├── README.md
├── bot/
│   ├── __init__.py
│   ├── config.py       # Настройки (env, папки, чаты)
│   ├── logger.py       # Логи в консоль и файл
│   ├── state.py        # bot_active, bot_started_at, user_states
│   ├── instructions.py # База инструкций + поиск по ключам
│   ├── green_api.py    # Green API: отправка/приём сообщений
│   ├── handlers.py     # Обработка уведомлений, кнопок, текст/фото
│   ├── main.py         # Главный цикл (receiveNotification → handle_notification)
│   └── ai/
│       ├── __init__.py
│       ├── vision.py    # EasyOCR + GPT-4o-mini для фото
│       └── deepseek.py # DeepSeek для текста
├── logs/               # Логи (создаётся автоматически)
├── temp_files/         # Временные файлы (создаётся автоматически)
└── photos/             # Картинки к инструкциям (например модульпечати.jpg)
```

## Установка и запуск

1. Клонировать репозиторий, создать виртуальное окружение и установить зависимости:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. Скопировать `.env.example` в `.env` и заполнить ключи и чаты:

   ```bash
   copy .env.example .env
   ```

3. Запуск:

   ```bash
   python run.py
   ```

   Или: `python -m bot.main`

## Конфигурация

- **DEEPSEEK_API_KEY**, **OPENAI_API_KEY** — ключи API.
- **GREEN_INSTANCE**, **GREEN_TOKEN** — инстанс и токен Green API.
- **ALLOWED_CHATS** — список чатов через запятую, в которых бот отвечает.
- **SUPPORT_CHAT_ID** — чат, в котором команды «бот стоп» / «бот старт» и куда уходят сообщения «инструкция не найдена».
- **TECH_SUPPORT_NUMBERS** — номера, на которые бот не отвечает.

## Логика

1. Приходит сообщение (текст или фото) → бот сохраняет проблему и отправляет вопрос «Решилась ли проблема?» с кнопками (или ответ 1 — да, 2 — нет).
2. Ответ «Да» / 1 → бот пишет «Проблема решена» и завершает диалог.
3. Ответ «Нет» / 2 → бот ищет инструкцию по тексту (ключи → DeepSeek) или по фото (EasyOCR → GPT-4o-mini) и отправляет инструкцию в чат. Если не найдена — пересылает в чат поддержки.
4. В чате поддержки: **бот стоп** — бот перестаёт обрабатывать сообщения; **бот старт** — снова обрабатывает, при этом сообщения, пришедшие пока бот был выключен, пропускаются.

## Как залить на GitHub

Проект уже готов к публикации. В корне выполните:

```bash
git init
git add .
git commit -m "WhatsApp bot: техподдержка, Green API, DeepSeek, OpenAI"
```

Далее на [github.com](https://github.com) нажмите **New repository**, создайте репозиторий (например `whatsappbot`), **не** добавляйте README (он уже есть). Затем:

```bash
git remote add origin https://github.com/ВАШ_ЛОГИН/whatsappbot.git
git branch -M main
git push -u origin main
```

Подставьте свой логин GitHub вместо `ВАШ_ЛОГИН`. Файл `.env` в репозиторий не попадёт (он в `.gitignore`), секреты храните только локально или в настройках сервера.

## Папка проекта

Всё нужное для репозитория лежит в текущей папке `whatsappbot`:

- **bot/** — исходный код бота (модули)
- **run.py** — запуск
- **requirements.txt**, **.env.example**, **.gitignore**, **README.md**

Старый однострочный файл `whatsappbot.py` можно удалить после проверки работы через `python run.py`. Папки `logs/`, `temp_files/`, `photos/` создаются при первом запуске.

## Лицензия

По усмотрению автора.

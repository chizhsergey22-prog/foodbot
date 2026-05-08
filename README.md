# FoodBot — Telegram Mini App для заказа обедов

Корпоративная система заказа обедов из ресторана. Сотрудники оформляют заказы через Telegram Mini App, администраторы управляют меню и следят за заказами через бота.

## Стек

| Слой | Технологии |
|------|-----------|
| Бот | Python 3.11, aiogram 3.x, APScheduler |
| API | FastAPI, SQLAlchemy 2 (async), asyncpg |
| Frontend | React 18, Vite, Tailwind CSS, Zustand |
| БД | PostgreSQL 16 |
| Кэш | Redis 7 |
| Деплой | Docker Compose, Nginx, SSL |
| Интеграции | Google Sheets API, Telegram Bot API |

## Архитектура

```
Telegram App
    │
    ├── Bot (aiogram) ──► PostgreSQL
    │                         │
    └── Mini App (React) ──► FastAPI ──► Redis (корзина)
                                  │
                              Google Sheets (отчёты)
```

## Функциональность

**Сотрудники:**
- Просматривают меню, сгруппированное по категориям
- Добавляют блюда в корзину
- Оформляют заказ на следующий рабочий день
- Получают уведомления о заказе в боте
- Видят историю заказов с кнопкой «Повторить»
- Запрашивают отмену заказа после дедлайна

**Суперадмин:**
- Генерирует именные инвайт-коды (`/invite`, `/inviteadmin`)
- Управляет меню (`/additem`, `/price`)
- Просматривает заказы дня (`/orders`, `/portions`)
- Выгружает отчёт в Google Sheets (`/report`)
- Управляет рабочими субботами (`/worksat`)
- Отмечает заказы доставленными (`/deliver`)
- Смотрит расходы по командам (`/balances`)

**Администратор ресторана:**
- Видит список заказов на день
- Управляет меню (добавление, активация блюд)

**Бизнес-логика:**
- Заказы принимаются в окне 12:00–17:00 на следующий рабочий день
- В 17:00 заказы блокируются планировщиком, начисляется долг
- Учёт стоимости доставки (10 ₴/день)
- Поддержка рабочих суббот

## Быстрый старт

### Требования
- Docker & Docker Compose
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- Google Service Account с доступом к Google Sheets API

### Установка

```bash
git clone https://github.com/chizhsergey22-prog/foodbot.git
cd foodbot

# Заполнить переменные окружения
cp .env.example .env
nano .env

# Добавить Google credentials
cp credentials.json.example credentials.json
# Вставить содержимое JSON-файла сервисного аккаунта

# Запуск
docker compose up -d --build
```

### Переменные окружения (.env)

```env
BOT_TOKEN=               # Токен от @BotFather
SUPER_ADMIN_IDS=         # Telegram ID суперадминов (через запятую)
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/food_bot
POSTGRES_PASSWORD=       # Пароль PostgreSQL
REDIS_URL=redis://redis:6379/0
MINI_APP_URL=            # URL Telegram Mini App (настраивается в @BotFather)
TIMEZONE=Europe/Kyiv
GOOGLE_REPORT_SHEET_ID=  # ID Google Sheets таблицы для отчётов
```

### Google Sheets (для отчётов `/report`)

1. Создать сервисный аккаунт в [Google Cloud Console](https://console.cloud.google.com/)
2. Включить **Google Sheets API** и **Google Drive API**
3. Скачать JSON-ключ → вставить содержимое в `credentials.json`
4. Создать таблицу Google Sheets и выдать сервисному аккаунту права редактора
5. ID таблицы (из URL) вставить в `GOOGLE_REPORT_SHEET_ID`

## Миграции БД (Alembic)

При первом запуске `docker compose up` сервис `migrate` автоматически создаёт схему и заполняет начальными данными.

Для существующей БД (обновление с init.sql на Alembic):

```bash
docker compose run --rm migrate alembic stamp head
docker compose run --rm migrate alembic upgrade head
```

Создание новой миграции:

```bash
docker compose run --rm migrate alembic revision -m "описание изменения"
```

## Структура проекта

```
foodbot/
├── api/                  # FastAPI бэкенд
│   ├── alembic/          # Миграции БД
│   ├── db/               # Модели SQLAlchemy
│   ├── routers/          # Эндпоинты (menu, cart, orders)
│   └── utils/            # Telegram auth валидация
├── bot/                  # Telegram Bot
│   ├── handlers/         # Обработчики (employee, restaurant_admin, super_admin)
│   ├── keyboards/        # Inline клавиатуры
│   ├── middlewares/       # Auth middleware
│   ├── services/         # Планировщик, Google Sheets
│   └── utils/            # Утилиты (время, команды)
├── frontend/             # React Mini App
│   └── src/
│       ├── pages/        # MenuPage, CartPage, CabinetPage
│       ├── components/   # UI компоненты
│       └── store/        # Zustand store
├── migrations/           # init.sql (справочник схемы)
├── nginx/                # Nginx конфиг + SSL
├── .env.example
├── credentials.json.example
└── docker-compose.yml
```

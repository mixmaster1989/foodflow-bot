# Отчёт по безопасности FoodFlow Bot

**Обновлён**: 2026-04-08 (актуализация по реальному коду)  
**Оригинал**: 2025-11-20  
**Проект**: FoodFlow Bot (`/home/user1/foodflow-bot_new/`)

---

## Результаты сканирования

### 1. Защита чувствительных данных

- `.env` файл исключён из git через `.gitignore` — статус неизменен
- `.env.example` с плейсхолдерами присутствует
- Жёстко закодированных секретов в Python-коде не обнаружено — всё вынесено в `config.py` через `pydantic-settings`
- `config.py` содержит `ADMIN_IDS` и `PILOT_USER_IDS` — это не секреты, а конфигурация

### 2. Переменные окружения

Все чувствительные значения загружаются через `.env`:
- `BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `JWT_SECRET_KEY`
- `GLOBAL_PASSWORD`
- `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY`

Файл БД (`foodflow.db`, `*.db-wal`, `*.db-shm`) — в `.gitignore`.

### 3. Авторизация API (FastAPI)

- JWT токены, срок действия 30 дней
- Все защищённые эндпоинты используют зависимость `get_current_user` (`api/dependencies.py`)
- Telegram Mini App авторизация через `initData` и `AUTH_TOKEN` header (`api/auth.py`)

---

## Активные уязвимости

### CORS wildcards (Серьёзно)

**Файл**: `api/main.py` строка 56

```python
allow_origins=["*"],
allow_credentials=True,
```

**Статус**: НЕ исправлено с аудита 2026-03-12.

**Риск**: Любой сайт может выполнять кросс-origin запросы к API от имени авторизованного пользователя (CSRF). Сочетание `allow_origins=["*"]` с `allow_credentials=True` — классическая CORS-уязвимость.

**Рекомендация**: Заменить `"*"` на конкретные домены вашего фронтенда и домен Telegram.

---

### Нет rate limiting на AI-эндпоинты (Серьёзно)

**Файл**: `api/main.py`

**Статус**: НЕ исправлено.

**Риск**: Финансовый DoS. Один пользователь может вызвать сотни запросов к `/api/recognize/food`, `/api/recognize/label`, `/api/receipts/upload` — каждый запрос платный (Gemini, GPT-4).

**Рекомендация**: `slowapi` или `fastapi-limiter`. Например: 10 req/min на `/recognize`, 5 req/min на `/receipts/upload`.

---

## Статус зависимостей

### Текущие зависимости (requirements.txt, апрель 2026)

| Пакет | Версия (установлена) | Назначение |
|-------|---------------------|-----------|
| aiogram | 3.26.0 | Telegram Bot Framework |
| fastapi | 0.135.1 | REST API |
| sqlalchemy | 2.0.48 | ORM (async) |
| aiohttp | 3.13.3 | HTTP-клиент |
| pydantic-settings | 2.13.1 | Конфигурация |
| rapidfuzz | 3.14.3 | Fuzzy matching |
| apscheduler | 3.11.2 | Планировщик задач |
| yookassa | ≥3.3.0 | Платёжный провайдер |
| asyncpg | ≥0.29.0 | PostgreSQL async (в зависимостях, но SQLite используется) |

**Примечание**: `asyncpg` в requirements.txt, но используется `aiosqlite`. Это лишняя зависимость.

**Статус**: Критических CVE не выявлено (проверка по установленным версиям). Рекомендуется периодически выполнять `pip audit`.

---

## Качество кода (с точки зрения безопасности)

- Нет синхронных HTTP-запросов (`requests`) в async-контексте — `requirements.txt` содержит комментарий об удалении `requests`
- Async/await используется корректно в handlers и services
- FSM состояния (aiogram) изолируют пользовательский контекст
- Middleware `GroupFilterMiddleware` блокирует нежелательные групповые сообщения

---

## Логирование

- Все события логируются в `foodflow.log`
- `AdminLoggerMiddleware` пересылает апдейты администратору
- **Проблема**: нет ротации логов — файл растёт неограниченно

---

## Чеклист безопасности

- [x] `.env` исключён из git
- [x] `.env.example` задокументирован
- [x] Нет жёстко закодированных ключей в коде
- [x] JWT авторизация в API
- [x] Telegram `initData` верификация для Mini App
- [ ] CORS: убрать wildcard, указать конкретные домены
- [ ] Rate limiting на AI-эндпоинты
- [ ] Ротация логов
- [ ] `pip audit` / Dependabot для мониторинга CVE

---

## Рекомендуемые следующие шаги

1. Исправить CORS: `allow_origins=["https://your-domain.com"]`
2. Добавить `slowapi` rate limiting на `/api/recognize/*` и `/api/receipts/upload`
3. Добавить `RotatingFileHandler` в main.py
4. Удалить `asyncpg` из requirements.txt если PostgreSQL не используется
5. Настроить `pip audit` или Dependabot в GitHub Actions

---

*Отчёт обновлён Claude Sonnet 4.6 на основе анализа реального кода. 2026-04-08.*

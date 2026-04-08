# FoodFlow Bot

> **AI-powered Telegram bot for food tracking, receipt OCR, and nutrition management with React Mini App**

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot%20API-blue?style=flat-square&logo=telegram)](https://core.telegram.org/bots)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)](#)

</div>

---

## Обзор

**FoodFlow** — Telegram-бот + FastAPI REST API + React Mini App для умного трекинга питания. Пользователь фотографирует чек или этикетку — бот автоматически распознаёт товары, находит КБЖУ и добавляет в виртуальный холодильник.

### Ключевые возможности

- **Онбординг** — сбор профиля (пол, рост, вес, цель), автоматический расчёт КБЖУ-нормы
- **Чек OCR** — мультимодельное распознавание чеков (6 AI-моделей с fallback-цепочкой)
- **Нормализация** — обогащение данных через Perplexity Sonar с веб-поиском
- **Виртуальный холодильник** — инвентаризация продуктов, категоризация, редактирование
- **Shopping Mode** — сканирование этикеток в магазине, fuzzy-сопоставление с чеком
- **AI-рецепты** — генерация рецептов на основе содержимого холодильника
- **Трекинг КБЖУ** — дневники питания, цели, статистика, клетчатка
- **Трекинг веса** — история, графики, утренние напоминания
- **Голосовой и текстовый ввод** — универсальный ввод с AI-парсингом
- **AI Consultant** — рекомендации и предупреждения по КБЖУ на основе профиля
- **Herbalife Expert** — специализированная база для быстрого логирования коктейлей
- **Marathon Module** — куратор-система для работы со своими подопечными
- **Подписки** — Telegram Stars, YooKassa, тарифы Free/Basic/Pro
- **Реферальная система** — реферальные ссылки, подсчёт привлечённых
- **React Mini App** — полноэкранный веб-интерфейс внутри Telegram
- **AI-иконки (Flux)** — генерация иконок для продуктов, дневные коллажи

---

## Стек технологий

| Компонент | Технологии |
|-----------|-----------|
| **Bot Framework** | aiogram 3.26 |
| **REST API** | FastAPI 0.135, uvicorn |
| **База данных** | SQLite + aiosqlite (WAL режим) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Конфигурация** | pydantic-settings 2.x |
| **HTTP клиент** | aiohttp 3.13 |
| **Fuzzy matching** | rapidfuzz 3.x |
| **Планировщик** | APScheduler 3.x |
| **Платежи** | Telegram Stars, YooKassa |
| **AI (OCR)** | OpenRouter: Qwen, Mistral, GPT-4.1, Gemini 2.5 Flash |
| **AI (нормализация)** | Perplexity Sonar, GPT-4o-mini-search, Gemini 2.5 Flash |
| **AI (визуал)** | Pollinations.ai (Flux) |
| **Процесс-менеджер** | PM2 |
| **Frontend** | React + Vite + Tailwind |

---

## Структура проекта

```
foodflow-bot_new/
├── api/                    — FastAPI приложение
│   ├── main.py             — регистрация роутеров, CORS, lifespan
│   ├── auth.py             — JWT авторизация
│   ├── dependencies.py     — зависимости (get_current_user)
│   ├── schemas.py          — Pydantic-схемы
│   └── routers/            — эндпоинты по модулям
│       ├── auth.py, products.py, consumption.py
│       ├── receipts.py, recognize.py, recipes.py
│       ├── weight.py, shopping_list.py, reports.py
│       ├── smart.py, search.py, herbalife.py
│       ├── universal.py, assets.py, saved_dishes.py
│       ├── water.py, ai_insight.py, referrals.py
├── database/
│   ├── base.py             — инициализация SQLite+WAL, get_db()
│   ├── models.py           — все ORM-модели
│   └── migrations.py       — ручные миграции
├── handlers/               — обработчики Telegram-команд
│   ├── admin.py, auth.py, common.py, correction.py
│   ├── curator.py, feedback.py, fridge.py, fridge_search.py
│   ├── global_input.py (DEPRECATED, не подключён)
│   ├── herbalife.py, i_ate.py, marketing.py, menu.py
│   ├── onboarding.py, payments.py, pilot_commands.py
│   ├── receipt.py, recipes.py, referrals.py, saved_dishes.py
│   ├── shopping.py, shopping_list.py, stats.py, subscription.py
│   ├── support.py, testers.py, universal_input.py
│   ├── user_settings.py, ward_interactions.py, water.py, weight.py
│   ├── guide.py
│   └── marathon/
│       └── curator_menu.py
├── middleware/
│   ├── admin_logger.py     — логирование и пересылка в admin
│   ├── paywall.py          — paywall для Basic/Pro функций
│   └── user_enrichment.py  — автообогащение профилей
├── services/               — AI и бизнес-логика
│   ├── ai.py, ai_brain.py, ai_guide.py, ai_insight.py
│   ├── cache.py, consultant.py, curator_analytics.py
│   ├── daily_nutrition_report.py, flux_service.py
│   ├── herbalife_expert.py, image_renderer.py
│   ├── kbju_core.py, label_ocr.py, logger.py
│   ├── marathon_service.py, marketing_analytics.py
│   ├── matching.py         — fuzzy matching этикеток с чеком
│   ├── normalization.py    — нормализация через AI + веб-поиск
│   ├── nutrition_calculator.py, ocr.py, payment_service.py
│   ├── photo_queue.py      — per-user очередь обработки фото
│   ├── price_search.py, price_tag_ocr.py
│   ├── referral_service.py, reports.py, scheduler.py
│   └── voice_stt.py
├── utils/                  — утилиты
├── frontend/               — React + Vite Mini App
│   ├── src/                — компоненты, хуки, страницы
│   └── dist/               — скомпилированные статические файлы
├── static/                 — сгенерированные иконки, фоны
├── assets/                 — статичные медиафайлы для бота
├── skills/                 — AI-навыки (специализированные модули)
├── main.py                 — точка входа бота
├── config.py               — конфигурация (pydantic-settings)
├── ecosystem.config.js     — PM2 конфигурация
└── requirements.txt        — зависимости Python
```

---

## Конфигурация

### Переменные окружения (.env)

| Переменная | Описание | Обязательна |
|------------|----------|------------|
| `BOT_TOKEN` | Telegram Bot API Token | Да |
| `OPENROUTER_API_KEY` | OpenRouter API Key (OCR, нормализация, рецепты) | Да |
| `JWT_SECRET_KEY` | Секрет для JWT токенов в FastAPI | Да |
| `GLOBAL_PASSWORD` | Пароль для доступа к боту (если включён) | Да |
| `DATABASE_URL` | Путь к SQLite БД | Нет (default: `sqlite+aiosqlite:////home/user1/foodflow-bot/foodflow.db`) |
| `YOOKASSA_SHOP_ID` | ID магазина YooKassa | Нет |
| `YOOKASSA_SECRET_KEY` | Секрет YooKassa | Нет |
| `PAYMENT_PROVIDER_TOKEN` | Устаревший Telegram Payment Token | Нет |
| `IS_BETA_TESTING` | Режим бета-тестирования (все = Pro) | Нет (default: `True`) |
| `MARKETING_GROUP_ID` | ID группы для маркетинговой статистики | Нет |

### AI-модели (актуально на апрель 2026)

**OCR (чеки)** — цепочка из 6 моделей через OpenRouter:
1. `qwen/qwen2.5-vl-32b-instruct:free` — приоритет 1 (бесплатная)
2. `qwen/qwen3.6-plus:free` — приоритет 2 (бесплатная)
3. `mistralai/mistral-small-3.2-24b-instruct:free` — приоритет 3 (бесплатная)
4. `google/gemini-2.5-flash-lite-preview-09-2025` — платная fallback
5. `openai/gpt-4.1-mini` — платная fallback
6. `openai/gpt-4o-mini` — последний резерв

**Нормализация** — 4 модели:
1. `perplexity/sonar` — с веб-поиском (основная)
2. `openai/gpt-4o-mini-search-preview` — веб-поиск резерв
3. `google/gemini-2.5-flash-lite-preview-09-2025` — быстрый fallback
4. `qwen/qwen2.5-vl-72b-instruct` — финальный fallback

**Визуал**: Pollinations.ai (Flux) — иконки и фоны  
**Голос**: voice_stt.py (Speech-to-Text)

---

## Запуск

### Предварительные требования

- Python 3.10+
- Node.js 18+ (для фронтенда)
- PM2 (для production)
- Nginx (для проксирования API и Mini App)

### Установка и запуск (development)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/mixmaster1989/foodflow-bot.git
cd foodflow-bot_new

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение
cp .env.example .env
# Заполнить BOT_TOKEN, OPENROUTER_API_KEY, JWT_SECRET_KEY, GLOBAL_PASSWORD

# 5. Запустить бота
python main.py

# 6. Запустить API (отдельный терминал)
uvicorn api.main:app --host 127.0.0.1 --port 8001

# 7. (Опционально) Собрать фронтенд
cd frontend && npm install && npm run build
```

### Запуск в production (PM2)

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

**PM2 приложения:**
- `foodflow-bot` — бот (max_memory: 200MB)
- `foodflow-api` — FastAPI на порту 8001 (max_memory: 300MB)

### Архитектура развёртывания

```
Telegram <-> Bot (aiogram, PM2) <-> SQLite (WAL)
                                <-> APScheduler (напоминания, отчёты)

Browser/Telegram WebApp <-> Nginx <-> FastAPI (PM2, port 8001) <-> SQLite
```

---

## Middlewares (порядок в main.py)

1. `GroupFilterMiddleware` — отфильтровывает групповые сообщения (пропускает `/mstats` и `mkt_` callbacks)
2. `AdminLoggerMiddleware` — логирует все апдейты, пересылает в admin
3. `UserEnrichmentMiddleware` — автообогащение профилей пользователей
4. `AuthMiddleware` — проверка авторизации
5. `PaywallMiddleware` — проверка подписки (Basic/Pro gates)

---

## Планировщик задач

APScheduler запускается вместе с ботом (MSK timezone):

| Задача | Расписание | Описание |
|--------|-----------|----------|
| `send_weight_reminders` | каждый час `:00` | Утренние напоминания о весе |
| `send_daily_summaries` | каждый час `:00` | Дневные сводки по питанию |
| `send_curator_summaries` | каждый час `:00` | AI-отчёты кураторов |
| `run_daily_report` | 12:00 MSK | Визуальный отчёт о питании |
| `expire_subscriptions` | каждый час `:30` | Деактивация истёкших подписок |
| `send_onboarding_reminders` | каждый час `:15` | Напоминания незавершившим онбординг |
| `send_admin_digest` | 09:00 MSK | Дневной дайджест для администраторов |
| `send_marketing_digest` | 09:05 MSK | Маркетинговая статистика в группу |

---

## Команды бота

- `/start` — запуск / главное меню
- `/help` — справка
- `/mstats` — маркетинговая статистика (работает в группах)

Большинство функций — через inline-кнопки главного меню.

---

## Логи и мониторинг

- Лог файл: `foodflow.log` (пишется в корень проекта)
- PM2 логи: `pm2 logs foodflow-bot` / `pm2 logs foodflow-api`
- Swagger UI: `http://localhost:8001/docs`
- Health check: `GET /api/health`

---

## Лицензия

MIT License — см. файл [LICENSE](LICENSE).

---

## Автор

**mixmaster1989**
- GitHub: [@mixmaster1989](https://github.com/mixmaster1989)
- Telegram: [@mixmaster1989](https://t.me/mixmaster1989)

---

## Благодарности

- [Aiogram](https://github.com/aiogram/aiogram) — Telegram Bot Framework
- [FastAPI](https://fastapi.tiangolo.com/) — REST API Framework
- [OpenRouter](https://openrouter.ai/) — AI API Aggregator
- [SQLAlchemy](https://www.sqlalchemy.org/) — Python ORM
- [RapidFuzz](https://github.com/maxbachmann/RapidFuzz) — Fuzzy string matching
- [APScheduler](https://apscheduler.readthedocs.io/) — Task Scheduler

# FoodFlow Bot Roadmap v1.0
**Создан**: 2025-11-25  
**Обновлён**: 2026-04-08 (актуализация по реальному коду)  
**Статус**: Активен

---

## Обзор

Роадмап фиксирует технический долг и задачи масштабирования. Статусы проверены по реальному коду в апреле 2026.

---

## Immediate Goals (Priority: High)

### 1. CI/CD Workflow

**Статус**: ✅ Завершено  
**Приоритет**: P1  
**Завершено**: 2025-11-25

**Задачи**:
- [x] GitHub Actions workflow (`.github/workflows/ci.yml` + `main.yml`)
- [x] Python линтинг через ruff (`pyproject.toml`)
- [x] pytest фреймворк (`tests/` — unit и integration)
- [ ] Отчёт покрытия (coverage.py) — *отложено до роста тестов*
- [ ] Pre-commit hooks — *будущее улучшение*
- [x] Quality gates (тесты должны проходить)

**Факт на апрель 2026**:
- `tests/unit/` — 7 файлов тестов (handlers, services, onboarding, consultant, ai_guide и др.)
- `tests/integration/` и отдельные test_*.py в корне `tests/`
- `tests/workflows/` — workflow-тесты
- CI настроен и работает

---

### 2. Migrate Database to PostgreSQL (asyncpg)

**Статус**: Не начато — **решено оставить SQLite**  
**Приоритет**: P1 → снижен до P4  
**Обоснование**: SQLite с WAL-режимом (PRAGMA journal_mode=WAL, busy_timeout=5000) обеспечивает достаточную производительность для текущей нагрузки. PostgreSQL — задача для масштаба >10k активных пользователей.

**Текущее состояние**: SQLite через aiosqlite, WAL-режим включён в `database/base.py`, ручные миграции в `database/migrations.py`.

---

### 3. Shopping Mode — реализация по плану

**Статус**: ✅ Реализовано (основной функционал)  
**Приоритет**: P2

**Что реализовано** (проверено по `handlers/shopping.py`, `services/matching.py`, `services/label_ocr.py`):
- [x] Таблицы `ShoppingSession` и `LabelScan` в БД
- [x] FSM States: `scanning_labels`, `waiting_for_receipt`, `waiting_for_label_photo`
- [x] Кнопка "🛒 Иду в магазин" в меню (запуск через callback `start_shopping_mode`)
- [x] Сканирование этикеток с OCR (LabelOCRService)
- [x] Сохранение КБЖУ из этикетки в LabelScan
- [x] Завершение покупок → ожидание чека
- [x] Fuzzy matching (rapidfuzz, MIN_SCORE=70) + бонусы за вес и бренд
- [x] Интерфейс коррекции несовпадений (sm_link, sm_skip, sm_request_label, sm_remove_product)
- [x] Удаление скана (shopping_delete_scan)
- [x] AI Consultant рекомендации при сканировании
- [x] PhotoQueueManager для очередей фото

**Что не реализовано**:
- [ ] Комплексные тесты Shopping Mode
- [ ] Документация по Shopping Mode обновлена частично

---

### 4. Structured Logging

**Статус**: Частично  
**Приоритет**: P2 → P3

**Текущее состояние**:
- Базовое логирование в `foodflow.log` через `logging.basicConfig` (main.py)
- Отдельный модуль `services/logger.py`
- Нет JSON-форматирования
- Нет ротации логов (файл растёт неограниченно — см. аудит НИЗ-1)

**Задачи (актуальные)**:
- [ ] Ротация логов (`RotatingFileHandler`, maxBytes=50MB, backupCount=5)
- [ ] JSON-формат для structured logging
- [ ] Request ID tracking

---

## Short-term Goals (Priority: Medium)

### 5. Unit Tests для core services

**Статус**: ✅ Реализовано (расширено)  
**Приоритет**: P2  
**Завершено**: к апрелю 2026

**Текущее состояние**:
- `tests/unit/test_services.py` — OCR, нормализация
- `tests/unit/test_handlers.py` — базовые handlers
- `tests/unit/test_services_additional.py` — расширенные тесты сервисов
- `tests/unit/test_handlers_additional.py` — дополнительные handler-тесты
- `tests/unit/test_consultant.py` — тесты ConsultantService
- `tests/unit/test_ai_guide.py` — тесты AIGuideService
- `tests/unit/test_onboarding.py` — тесты онбординга
- Integration-тесты: marathon, payments, referrals, i_ate, recipes и др.

---

### 6. Кэш нормализации

**Статус**: Частично (кэш рецептов есть, кэш нормализации — нет)  
**Приоритет**: P3

**Текущее состояние**:
- `services/cache.py` — кэш рецептов через `CachedRecipe` в БД (hash по ингредиентам)
- Кэш нормализации продуктов отсутствует — повторные запросы идут в API

**Задачи**:
- [ ] Кэш нормализации по hash(product_name), TTL 7 дней

---

### 7. Rate Limiting на AI-эндпоинты

**Статус**: Не реализовано  
**Приоритет**: P1 (финансовый риск — см. аудит СЕРЬЁЗ-5)

**Задачи**:
- [ ] `slowapi` или `fastapi-limiter` для `/api/recognize/*` и `/api/receipts/upload`
- [ ] Лимиты: 10 req/min на /recognize, 5 req/min на /receipts/upload

---

## Long-term Goals

### 8. Микросервисы

**Статус**: Не начато  
**Приоритет**: P4 (нужен рост >10k активных пользователей)

---

### 9. REST API — веб/мобильные клиенты

**Статус**: ✅ FastAPI API уже реализован и работает  
**Приоритет**: Завершено

**Текущее состояние**: FastAPI на порту 8001 с JWT авторизацией, Swagger UI `/docs`. Роутеры: auth, products, consumption, recipes, weight, shopping_list, reports, receipts, recognize, smart, search, herbalife, universal, assets, saved_dishes, water, ai_insight, referrals.

---

## Таблица прогресса (апрель 2026)

| Задача | Статус | Прогресс | Примечания |
|--------|--------|----------|------------|
| CI/CD Workflow | ✅ Завершено | 100% | GitHub Actions работает |
| PostgreSQL Migration | ⏸ Заморожено | 0% | SQLite+WAL достаточно |
| Shopping Mode | ✅ Реализовано | 90% | Нет комплексных тестов |
| Structured Logging | 🔄 Частично | 30% | Нет ротации, нет JSON |
| Unit Tests | ✅ Расширено | 80% | 7+ файлов unit + integration |
| Кэш нормализации | ❌ Нет | 10% | Есть кэш рецептов |
| Rate Limiting API | ❌ Нет | 0% | Финансовый риск |
| REST API | ✅ Завершено | 95% | FastAPI полностью работает |
| Микросервисы | ❌ Нет | 0% | Не нужно при текущей нагрузке |

---

## Критические задачи (из аудита 2026-03-12)

> Подробнее см. `планы/stability_audit_claude_2026-03-12.md`

| ID | Файл | Проблема | Статус |
|----|------|----------|--------|
| КРИТ-1 | ocr.py, normalization.py | Новая aiohttp ClientSession в retry loop | ❌ Не исправлено |
| КРИТ-2 | photo_queue.py | Unbounded asyncio.Queue (нет maxsize) | ❌ Не исправлено |
| КРИТ-3 | scheduler.py | Все пользователи в памяти разом | ❌ Не исправлено |
| СЕРЬЁЗ-1 | paywall.py | SELECT на каждый callback | ❌ Не исправлено |
| СЕРЬЁЗ-2 | matching.py | Sync fuzzy blocking event loop | ❌ Не исправлено |
| СЕРЬЁЗ-4 | api/main.py | CORS allow_origins=["*"] | ❌ Не исправлено |
| СЕРЬЁЗ-5 | api/main.py | Нет rate limit на AI эндпоинты | ❌ Не исправлено |
| СРЕДН-1 | ecosystem.config.js | PM2 bot memory limit = 200MB | ❌ Не исправлено (api: 300MB) |

---

## Примечания

- Все цели следуют принципу Spec-Driven Development
- Роадмап обновляется при реальных изменениях кода
- Критические проблемы стабильности фиксируются в `планы/stability_audit_claude_2026-03-12.md`

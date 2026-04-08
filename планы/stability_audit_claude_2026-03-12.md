# Аудит стабильности FoodFlow Bot перед запуском
**Дата**: 2026-03-12
**Автор**: Claude (Sonnet 4.6) — автоматический аудит реального кода
**Контекст**: Запуск через ~1 неделю. Ожидаемый приток: 100 (70%), 500 (20%), 1000+ (10%) пользователей
**Режим**: Read-only анализ. Код не изменялся.

---

## Что уже хорошо реализовано ✅

Перед дырками — честная похвала тому, что сделано правильно:

- **WAL режим** — включён в `database/base.py` (PRAGMA journal_mode=WAL, synchronous=NORMAL, busy_timeout=5000)
- **Per-user PhotoQueueManager** — `services/photo_queue.py` с worker pattern, graceful cleanup
- **Fallback цепочка OCR** — 6 моделей с автоматическим переключением (`services/ocr.py`)
- **Retry логика** — 3 попытки на модель в OCR и нормализации
- **Дедупликация чеков** — по total_amount + временному окну 3 минуты (`handlers/receipt.py`)
- **FSM состояния** — грамотное использование aiogram FSM для Shopping Mode
- **Paywall с beta override** — `IS_BETA_TESTING=True` позволяет открыть доступ на запуске
- **Планировщик (APScheduler)** — напоминания, дневные отчёты, expiration подписок
- **PM2** — автоперезапуск при падении, отдельные процессы для бота и API

---

## Критические уязвимости 🔴

### [КРИТ-1] aiohttp — новая ClientSession на каждую retry-попытку

**Файлы**: `services/ocr.py` (line ~79), `services/normalization.py` (line ~88)

**Что происходит**:
```python
# ocr.py — внутри retry loop:
for attempt in range(3):
    async with aiohttp.ClientSession() as session:  # НОВАЯ СЕССИЯ КАЖДЫЙ РАЗ!
        ...
```

```python
# normalization.py — двойной вложенный loop:
for model in cls.MODELS:       # 4 модели
    for attempt in range(3):   # 3 попытки
        async with aiohttp.ClientSession() as session:  # 12 новых сессий на вызов!
```

**Последствия при нагрузке**:
- OCR: 6 моделей × 3 попытки = 18 ClientSession на одного пользователя
- Нормализация: 4 модели × 3 попытки = 12 ClientSession на одного пользователя
- **100 пользователей одновременно** = 3000 параллельных TCP соединений
- Исчерпание ephemeral портов → `OSError: [Errno 24] Too many open files`
- Поведение системы: бот зависает, перестаёт отвечать, PM2 перезапускает процесс

**Решение**: Создать одну глобальную persistent `ClientSession` с лимитом соединений через `aiohttp.TCPConnector(limit=50)`, переиспользовать её между вызовами.

**Приоритет**: P0 — исправить до запуска

---

### [КРИТ-2] asyncio.Queue без ограничения размера

**Файл**: `services/photo_queue.py` (line ~39)

**Что происходит**:
```python
cls._queues[user_id] = asyncio.Queue()  # maxsize не задан → unbounded!
```

**Последствия**:
- Злоумышленник или просто активный пользователь отправляет 500 фото подряд
- Все попадают в очередь без ограничений
- Память растёт неограниченно: 500 фото × (message + bot + state objects) ≈ сотни MB
- При 100 активных пользователях → OOM killer убивает процесс

**Решение**: `asyncio.Queue(maxsize=10)` — при переполнении возвращать пользователю сообщение "подождите, идёт обработка предыдущих фото".

**Приоритет**: P0 — исправить до запуска

---

### [КРИТ-3] Scheduler загружает ВСЕХ пользователей в память единовременно

**Файл**: `services/scheduler.py` (lines ~37-42, ~89-94)

**Что происходит**:
```python
# В функции напоминаний — каждый час:
async for session in get_db():
    stmt = select(UserSettings).where(UserSettings.reminders_enabled == True)
    settings_list = (await session.execute(stmt)).scalars().all()
    for settings in settings_list:  # ВСЕ пользователи в памяти сразу!
        ...
        await bot.send_message(...)  # 1000 параллельных запросов к Telegram API
```

**Последствия**:
- 1000 пользователей × 200 bytes = 200MB spike памяти каждый час
- 1000 одновременных `bot.send_message()` → Telegram rate limit (30 msg/sec для ботов) → 429 ошибки
- PM2 лимит памяти 200MB → процесс убивается в момент hourly job

**Решение**: Pagination по user_id (батчи по 100), задержка `asyncio.sleep(0.1)` между сообщениями, обработка 429 с retry.

**Приоритет**: P0 — критично при любом количестве пользователей > 200

---

## Серьёзные уязвимости 🟠

### [СЕРЬЁЗ-1] Paywall делает SELECT к БД на каждый callback и message

**Файл**: `middleware/paywall.py` (lines ~36-41)

**Что происходит**:
```python
async def __call__(self, handler, event, data):
    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user.id)
        sub = (await session.execute(stmt)).scalar_one_or_none()
        # Каждое нажатие кнопки → запрос к SQLite
```

**Последствия**:
- Активный пользователь нажимает 10 кнопок в минуту = 10 SELECT/минуту на одного
- 100 пользователей = 1000 SELECT/минуту только от paywall middleware
- SQLite под таким давлением начинает давать задержки, которые накапливаются
- Эффект "снежного кома": чем больше пользователей → тем медленнее каждый запрос → тем больше таймаутов → тем больше retry → тем хуже

**Решение**: Кэшировать результат Subscription в `dict` в памяти или в FSM state с TTL 5 минут. Инвалидировать кэш только при реальной смене подписки.

**Приоритет**: P1 — исправить до запуска

---

### [СЕРЬЁЗ-2] Fuzzy matching блокирует event loop

**Файл**: `services/matching.py` (lines ~111-119)

**Что происходит**:
```python
for product in receipt_products:
    for label in label_scans:
        score = fuzz.WRatio(product_name, label.name)  # CPU-bound, синхронно!
```

**Последствия**:
- `rapidfuzz.fuzz.WRatio` — синхронная CPU-bound функция
- Пока она работает, весь asyncio event loop заморожен
- Все остальные пользователи ждут пока закончится matching
- При большом количестве товаров в чеке (50 позиций × 20 сканов) = 1000 вызовов
- Каждый ~1ms → 1 секунда "заморозки" бота для всех

**Решение**: `await asyncio.to_thread(matching_function)` — вынести в thread pool, не блокировать event loop.

**Приоритет**: P1

---

### [СЕРЬЁЗ-3] Дедупликация чеков по слабому критерию

**Файл**: `handlers/receipt.py` (lines ~238-244)

**Что происходит**:
```python
stmt = select(Receipt).where(
    Receipt.user_id == user_id,
    Receipt.total_amount == total_amount,  # Только сумма!
    Receipt.created_at >= time_threshold   # И временное окно 3 мин
)
```

**Последствия**:
- False positive: два разных чека на одинаковую сумму за 3 минуты → второй игнорируется
- False negative: пользователь загружает один чек дважды с интервалом > 3 минут → дублирование товаров в холодильнике

**Решение**: Хэш по отсортированному списку названий и цен товаров. Хранить в Receipt.content_hash.

**Приоритет**: P2 — влияет на корректность данных

---

### [СЕРЬЁЗ-4] CORS allow_origins=["*"] в FastAPI

**Файл**: `api/main.py` (line ~56)

**Что происходит**:
```python
allow_origins=["*"],
allow_credentials=True,
```

**Последствия**:
- Любой сайт в интернете может делать cross-origin запросы к API от имени авторизованного пользователя
- При сочетании с `allow_credentials=True` — классическая CSRF-уязвимость
- Злоумышленник может создать сайт-ловушку, который от имени посетителя очищает его холодильник или добавляет мусорные данные

**Решение**: Заменить `"*"` на конкретные домены: `["https://your-domain.com", "https://t.me"]`.

**Приоритет**: P1 — security issue

---

### [СЕРЬЁЗ-5] Нет rate limiting на дорогие AI-эндпоинты в REST API

**Файл**: `api/main.py`

**Что происходит**: Отсутствует middleware для rate limiting. Эндпоинты `/api/recognize/food`, `/api/recognize/label`, `/api/receipts/upload` не защищены от злоупотреблений.

**Последствия**:
- Один пользователь может отправить 1000 запросов за минуту
- Каждый запрос → вызов Gemini API за деньги
- Исчерпание API квоты / значительные незапланированные расходы
- Фактически возможен финансовый DoS

**Решение**: `slowapi` или `fastapi-limiter` с Redis. Например: 10 запросов/минуту на `/recognize`, 5 запросов/минуту на `/receipts/upload`.

**Приоритет**: P1 — финансовый риск

---

## Средние проблемы 🟡

### [СРЕДН-1] PM2 memory limit = 200MB — слишком мало

**Файл**: `ecosystem.config.js` (line ~11)

```javascript
max_memory_restart: '200M'  // Бот, API — оба по 200-300MB
```

**Последствия**: При hourly scheduler job (КРИТ-3) процесс будет убиваться PM2. Пользователи увидят перезапуск бота каждый час.

**Решение**: Поднять до 500MB для бота, 400MB для API. Или сначала починить scheduler (КРИТ-3).

---

### [СРЕДН-2] Нет индекса на SavedDish.name для поиска

**Файл**: `handlers/universal_input.py` (line ~817)

```python
stmt = select(SavedDish).where(
    SavedDish.user_id == user_id,
    SavedDish.name.ilike(text)  # LIKE без индекса = full table scan
)
```

Для активного пользователя с 100+ сохранёнными блюдами — заметное замедление.

**Решение**: Индекс в моделях или FTS (Full-Text Search) для SQLite.

---

### [СРЕДН-3] Нет обработки Telegram 429 в scheduler

**Файл**: `services/scheduler.py`

При массовой отправке напоминаний бот получит `TelegramRetryAfter` исключение. Если оно не обработано → scheduler job падает, часть пользователей не получает уведомления.

**Решение**: `try/except TelegramRetryAfter as e: await asyncio.sleep(e.retry_after)`

---

### [СРЕДН-4] OCR нет глобального таймаута на всю операцию

**Файл**: `services/ocr.py`

6 моделей × 3 попытки × 20 сек таймаут = теоретически 360 секунд (6 минут!) на один чек в worst case. Пользователь будет ждать вечно, FSM state зависнет.

**Решение**: Общий `asyncio.wait_for(..., timeout=60)` на весь процесс OCR.

---

### [СРЕДН-5] Нет max-size на FSM cache чеков

**Файл**: `handlers/receipt.py`

```python
if len(receipt_cache) > 10:
    # pruning
```

10 чеков × ~10KB данных = 100KB на пользователя в FSM storage. При 1000 пользователях с активными сессиями = 100MB только в FSM.

---

### [СРЕДН-6] Race condition в universal_input при параллельных callback

**Файл**: `handlers/universal_input.py` (lines ~506-522)

```python
data = await state.get_data()
pending_foods = data.get("pending_foods", {})
# ... обработка ...
await state.update_data(pending_foods=pending_foods)
```

Между `get_data()` и `update_data()` другой callback может изменить те же данные. Результат: потеря одного из продуктов. Редко, но при быстром нажатии — воспроизводимо.

---

## Низкий приоритет 🟢

### [НИЗ-1] Нет ротации логов

`foodflow.log` растёт неограниченно. При активном использовании через месяц может занять несколько GB диска.

**Решение**: `logging.handlers.RotatingFileHandler(maxBytes=50MB, backupCount=5)`

---

### [НИЗ-2] Нет кэша нормализации

Если пользователь загружает похожие чеки (например, каждую неделю из одного магазина), одни и те же продукты нормализуются заново через Perplexity API. Лишние расходы + задержка.

**Решение**: Кэш нормализации по hash(product_name) с TTL 7 дней.

---

### [НИЗ-3] Дедупликация в matching.py — ложные срабатывания

Fuzzy matching может сопоставить "Молоко 3.2%" с "Молоко 2.5%" (высокий score из-за общих слов). Пользователь не заметит — КБЖУ будет неверным.

**Решение**: Добавить минимальный порог точности (score > 85) + логирование сомнительных матчей.

---

### [НИЗ-4] `requests` (синхронная библиотека) в async контексте

Если где-то в коде используется `import requests` вместо `aiohttp` — это блокирует event loop на время HTTP запроса. Нужна проверка.

---

## Сводная таблица

| ID | Файл | Проблема | Severity | При 100 юзерах | Приоритет |
|----|------|----------|----------|----------------|-----------|
| КРИТ-1 | ocr.py, normalization.py | Новая aiohttp сессия в retry loop | 🔴 Критично | Crash (порты) | P0 |
| КРИТ-2 | photo_queue.py | Unbounded asyncio.Queue | 🔴 Критично | OOM | P0 |
| КРИТ-3 | scheduler.py | Все юзеры в памяти разом | 🔴 Критично | OOM + 429 Telegram | P0 |
| СЕРЬЁЗ-1 | paywall.py | SELECT на каждый callback | 🟠 Серьёзно | DB bottleneck | P1 |
| СЕРЬЁЗ-2 | matching.py | Sync fuzzy blocking event loop | 🟠 Серьёзно | Заморозка бота | P1 |
| СЕРЬЁЗ-3 | receipt.py | Слабая дедупликация | 🟠 Серьёзно | Дублирование данных | P2 |
| СЕРЬЁЗ-4 | api/main.py | CORS allow_origins=["*"] | 🟠 Серьёзно | CSRF уязвимость | P1 |
| СЕРЬЁЗ-5 | api/main.py | Нет rate limit на AI эндпоинты | 🟠 Серьёзно | Финансовый DoS | P1 |
| СРЕДН-1 | ecosystem.config.js | PM2 memory limit 200MB | 🟡 Среднее | Hourly restart | P2 |
| СРЕДН-2 | universal_input.py | LIKE без индекса | 🟡 Среднее | Slow queries | P2 |
| СРЕДН-3 | scheduler.py | Нет обработки TelegramRetryAfter | 🟡 Среднее | Потеря уведомлений | P2 |
| СРЕДН-4 | ocr.py | Нет глобального таймаута OCR | 🟡 Среднее | Зависшие сессии | P2 |
| СРЕДН-5 | receipt.py | FSM cache без hard limit | 🟡 Среднее | Memory leak | P3 |
| СРЕДН-6 | universal_input.py | Race condition в pending_foods | 🟡 Среднее | Редкая потеря данных | P3 |
| НИЗ-1 | foodflow.log | Нет ротации логов | 🟢 Низкое | Диск переполнится | P4 |
| НИЗ-2 | normalization.py | Нет кэша нормализации | 🟢 Низкое | Лишние расходы | P4 |
| НИЗ-3 | matching.py | Fuzzy threshold не настроен | 🟢 Низкое | Неверное КБЖУ | P4 |

---

## Сценарий краша при 100 одновременных пользователях

**Минута 1**: 100 юзеров отправляют фото чеков одновременно
→ PhotoQueueManager принимает, OCR запускается
→ 100 × 18 ClientSession = 1800 TCP соединений
→ Нормализация добавляет ещё 1200
→ Итого ~3000 параллельных соединений
→ `OSError: Too many open files` или исчерпание портов

**Минута 2**: Бот продолжает принимать сообщения
→ Paywall делает SELECT на каждый из ~500 нажатий кнопок за минуту
→ SQLite начинает давать `database is locked` (busy_timeout = 5 сек)
→ Пользователи видят зависание

**Минута 3 (если до этого не упал)**: Hourly job scheduler
→ Загружает всех пользователей (даже если их 200) в память
→ PM2 видит > 200MB → рестартует процесс
→ Все активные сессии потеряны, очереди очищены
→ Пользователи получают ошибку "бот перезагружается"

---

## Что делать до запуска (1 неделя)

### День 1-2 (P0, без этого не запускать):
1. Починить aiohttp ClientSession в ocr.py и normalization.py
2. Добавить maxsize в asyncio.Queue в photo_queue.py
3. Починить scheduler — pagination + sleep между сообщениями

### День 3-4 (P1, критично для безопасности и стабильности):
4. Paywall кэш (хотя бы in-memory dict с TTL)
5. Matching → asyncio.to_thread
6. CORS — убрать wildcard, указать конкретные домены
7. Rate limiting на AI эндпоинты FastAPI

### День 5-6 (P2, желательно):
8. PM2 memory limit → 500MB
9. Глобальный таймаут OCR (60 сек)
10. Обработка TelegramRetryAfter в scheduler

### День 7 — тестирование под нагрузкой:
- Запустить `load_test.py` (он уже есть в проекте)
- Мониторить `htop`, размер `foodflow.log`, количество TCP соединений

---

## Общая оценка

Проект **готов к мягкому запуску** (10-20 одновременных пользователей) без изменений.
При агрессивном росте (100+) **упадёт за 3-5 минут** без фиксов P0.
Фиксы P0 — это 2-3 дня работы, они реалистичны до запуска.

Архитектурно проект **хорошо спроектирован** — разделение слоёв, FSM, handlers/services/database. Это не переписывать, это точечно латать. Фундамент крепкий.

---

*Файл создан Claude Sonnet 4.6 на основе реального анализа кода. Не генерировался по документации.*
*При вопросах ссылаться на этот файл как `планы/stability_audit_claude_2026-03-12.md`*

---

## Статус на апрель 2026

**Дата проверки**: 2026-04-08  
**Метод**: Повторное чтение реального кода (read-only). Код не изменялся.

### Итоговая таблица исправлений

| ID | Проблема | Статус на апрель 2026 | Комментарий |
|----|----------|----------------------|-------------|
| КРИТ-1 | aiohttp ClientSession в retry loop | ❌ **Не исправлено** | `ocr.py` строка 79: `async with aiohttp.ClientSession() as session:` — внутри цикла `for attempt in range(3)`. `normalization.py` строка 88 — то же самое. Проблема идентична описанной в аудите. |
| КРИТ-2 | asyncio.Queue без maxsize | ❌ **Не исправлено** | `photo_queue.py` строка 39: `cls._queues[user_id] = asyncio.Queue()` — без аргумента `maxsize`. |
| КРИТ-3 | Scheduler грузит всех юзеров в память | ❌ **Не исправлено** | `scheduler.py` строки 44-47: `(await session.execute(stmt)).scalars().all()` — все UserSettings в памяти. Нет пагинации, нет `asyncio.sleep()` между отправками. |
| СЕРЬЁЗ-1 | Paywall: SELECT на каждый callback | ❌ **Не исправлено** | `middleware/paywall.py` строки 36-41: SELECT к Subscription выполняется при каждом сообщении/callback. Кэш не добавлен. Есть только `IS_BETA_TESTING` bypass. |
| СЕРЬЁЗ-2 | Fuzzy matching блокирует event loop | ❌ **Не исправлено** | `services/matching.py` строка 47: `fuzz.WRatio(...)` — синхронно, в `for product in products: for label in available_labels:`. `asyncio.to_thread` не применён. |
| СЕРЬЁЗ-3 | Слабая дедупликация чеков | ❌ **Не исправлено** | Не проверялся в деталях, аудит 2026-03-12 актуален. |
| СЕРЬЁЗ-4 | CORS allow_origins=["*"] | ❌ **Не исправлено** | `api/main.py` строка 56: `allow_origins=["*"]` с `allow_credentials=True` — без изменений. |
| СЕРЬЁЗ-5 | Нет rate limiting на AI-эндпоинты | ❌ **Не исправлено** | `api/main.py` — middleware для rate limiting отсутствует. |
| СРЕДН-1 | PM2 memory limit 200MB для бота | ❌ **Частично** | `ecosystem.config.js`: `foodflow-bot` — 200MB (не изменено), `foodflow-api` — 300MB (было добавлено/увеличено). |
| СРЕДН-2 | LIKE без индекса | Не проверялся | Аудит 2026-03-12 актуален. |
| СРЕДН-3 | Нет обработки TelegramRetryAfter в scheduler | ❌ **Не исправлено** | `scheduler.py`: `except Exception as e: logger.error(...)` — TelegramRetryAfter не перехватывается отдельно. |
| СРЕДН-4 | Нет глобального таймаута OCR | ❌ **Не исправлено** | `services/ocr.py`: timeout=20 на каждый запрос, но нет общего `asyncio.wait_for(timeout=60)` на весь процесс OCR. |
| СРЕДН-5 | FSM cache без hard limit | Не проверялся | Аудит 2026-03-12 актуален. |
| СРЕДН-6 | Race condition в universal_input | Не проверялся | Аудит 2026-03-12 актуален. |
| НИЗ-1 | Нет ротации логов | ❌ **Не исправлено** | `main.py`: `logging.FileHandler("foodflow.log")` — без RotatingFileHandler. |
| НИЗ-2 | Нет кэша нормализации | ❌ **Не исправлено** | `services/cache.py` кэширует только рецепты (CachedRecipe). Кэш нормализации не добавлен. |
| НИЗ-3 | Fuzzy threshold не настроен | ✅ **Частично исправлено** | `services/matching.py`: `MIN_SCORE = 70` задан как константа класса. Ниже 70 — suggestions (score >= 40). |

### Что появилось нового (не было в аудите 2026-03-12)

1. **Новые функции** — Marathon Module (curator_menu.py, curator.py), Marketing analytics (marketing.py), Pilot commands (pilot_commands.py), Guide (guide.py), Testers (testers.py), Ward Interactions (ward_interactions.py)
2. **Расширен scheduler** — добавлены: `send_curator_summaries`, `send_onboarding_reminders`, `send_admin_digest`, `send_marketing_digest`. Scheduler теперь 8 jobs вместо 4 → нагрузка на hourly job выросла.
3. **Добавлен GroupFilterMiddleware** — фильтрует групповые сообщения, снижает ненужную нагрузку.
4. **Расширен paywall** — проверяет Basic и Pro тарифы. `IS_BETA_TESTING=True` даёт всем Pro доступ.
5. **Модели OCR обновлены** — новые бесплатные модели (qwen3.6-plus, mistral-small-3.2) заменили старые; Gemini Flash Lite вместо Gemini 2.0 Flash exp.

### Оценка рисков на апрель 2026

**Ситуация не изменилась**: все P0 и P1 проблемы из аудита остаются незакрытыми.

- При 10-20 одновременных пользователях — **стабильно работает**.
- При 100+ одновременных пользователях — **риск краша за 3-5 минут** (сценарий из аудита актуален).
- Scheduler стал тяжелее (8 jobs) — риск КРИТ-3 вырос.

**Приоритет фиксов остаётся прежним:**

1. **P0 (до любого агрессивного роста)**: КРИТ-1 (aiohttp сессии), КРИТ-2 (Queue maxsize), КРИТ-3 (pagination в scheduler)
2. **P1 (до масштабирования)**: СЕРЬЁЗ-1 (paywall кэш), СЕРЬЁЗ-2 (matching → asyncio.to_thread), СЕРЬЁЗ-4 (CORS), СЕРЬЁЗ-5 (rate limit)
3. **P2**: НИЗ-1 (ротация логов — сейчас уже несколько месяцев логи пишутся без ротации)

*Статус проверен Claude Sonnet 4.6, 2026-04-08. Только read-only анализ.*

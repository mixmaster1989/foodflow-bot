# Shopping Mode — план и статус реализации

**Обновлён**: 2026-04-08 (актуализация по реальному коду)  
**Оригинал**: 2025-11-20

## Цель

Режим "Иду в магазин": пользователь сканирует этикетки товаров в магазине, затем сопоставляет их с чеком для точного учёта КБЖУ и нормализации названий.

---

## Статус реализации

**Общий статус**: ✅ Основной функционал реализован

Проверено по файлам:
- `handlers/shopping.py` — FSM, handlers, UI
- `services/matching.py` — fuzzy matching алгоритм
- `services/label_ocr.py` — OCR этикеток
- `database/models.py` — модели БД

---

## 1. База данных

- [x] **Таблица `ShoppingSession`**
  - `id`, `user_id`, `started_at`, `finished_at`, `is_active`
- [x] **Таблица `LabelScan`**
  - `id`, `session_id`, `name`, `brand`, `weight`, `calories`, `protein`, `fat`, `carbs`, `matched_product_id`, `created_at`

---

## 2. FSM States (Aiogram)

- [x] `ShoppingMode.scanning_labels` — режим сканирования этикеток
- [x] `ShoppingMode.waiting_for_receipt` — ожидание чека после завершения покупок
- [x] `ShoppingMode.waiting_for_label_photo` — ожидание фото этикетки для конкретного товара (добавлен сверх плана)

---

## 3. UI/UX Flow

### 3.1 Начало покупок
- [x] Кнопка "🛒 Иду в магазин" запускает callback `start_shopping_mode`
- [x] Создаётся `ShoppingSession` (is_active=True), либо переиспользуется существующая
- [x] FSM → `ShoppingMode.scanning_labels`
- [x] Отправляется инструкция с фото `assets/shopping_mode.png`
- [x] Кнопки: "✅ Я закончил покупки" / "❌ Отменить покупки"

### 3.2 Сканирование этикеток
- [x] В состоянии `scanning_labels` пользователь отправляет фото
- [x] Фото обрабатывается через `PhotoQueueManager` (очередь)
- [x] OCR через `LabelOCRService.parse_label()` — извлечение name, brand, weight, КБЖУ
- [x] Сохраняется в `LabelScan`
- [x] Подтверждение с КБЖУ + кнопка "🗑️ Удалить этот товар"
- [x] AI Consultant даёт рекомендации при сканировании (если профиль заполнен)

### 3.3 Завершение покупок
- [x] Callback `shopping_finish` → FSM `waiting_for_receipt`
- [x] Просьба прислать фото чека

### 3.4 Обработка чека и матчинг
- [x] Чек обрабатывается стандартным OCR + нормализация (`handlers/receipt.py`)
- [x] Fuzzy matching через `MatchingService.match_products()`:
  - `MIN_SCORE = 70` (fuzz.WRatio)
  - Бонус +5 за совпадение веса
  - Бонус +5 за совпадение бренда
  - До 3 suggestions для несопоставленных (score >= 40)
- [x] Сессия закрывается после матчинга (`is_active=False`, `finished_at` заполняется)
- [x] КБЖУ из этикетки обновляет КБЖУ продукта в холодильнике

### 3.5 Интерфейс коррекции
- [x] `sm_link:{product_id}:{label_id}` — ручная привязка этикетки к продукту
- [x] `sm_skip:{label_id}` — пропустить, оставить как новый товар
- [x] `sm_request_label:{product_id}` — запросить фото этикетки для несопоставленного товара (FSM → `waiting_for_label_photo`)
- [x] `sm_remove_product:{product_id}` — удалить несопоставленный товар из БД
- [x] `shopping_delete_scan:{label_id}` — удалить скан из сессии

---

## 4. Алгоритм сопоставления (Fuzzy Matching)

- [x] Библиотека: `rapidfuzz` (fuzz.WRatio)
- [x] Порог автоматического сопоставления: `MIN_SCORE = 70`
- [x] Критерии:
  - Схожесть названия (WRatio)
  - +5 за совпадение веса (если указан)
  - +5 за совпадение бренда (если указан)
  - Suggestions для несопоставленных: score >= 40, топ-3
- [ ] Тесты покрытия для MatchingService — **не написаны**

---

## 5. Файлы — статус

### Созданные файлы (из плана)
- [x] `handlers/shopping.py` — ✅ Реализовано
- [x] `services/label_ocr.py` — ✅ Реализовано
- [x] `services/matching.py` — ✅ Реализовано
- [x] `database/models.py` — ✅ ShoppingSession, LabelScan добавлены

### Изменённые файлы (из плана)
- [x] `handlers/receipt.py` — интеграция с Shopping Mode
- [x] `main.py` — `shopping.router` зарегистрирован (обязательно ПЕРЕД `receipt.router`)
- [x] `requirements.txt` — `rapidfuzz>=3.0.0` добавлен
- [x] `handlers/common.py` / `handlers/menu.py` — кнопка в меню через callback `start_shopping_mode`

> **Важно**: в `main.py` явно указан комментарий: `# IMPORTANT: shopping.router must be before receipt.router`

---

## 6. Порядок реализации (финальный)

1. [x] Создать план
2. [x] Обновить схему БД (ShoppingSession, LabelScan)
3. [x] Добавить кнопку в меню
4. [x] FSM и handler для сканирования
5. [x] OCR для этикеток (LabelOCRService)
6. [x] Алгоритм сопоставления (MatchingService)
7. [x] Интеграция с обработкой чека
8. [x] UI коррекции несовпадений
9. [ ] Комплексное тестирование — **не завершено**

---

## Известные ограничения и потенциальные проблемы

1. **Fuzzy matching синхронный** — `fuzz.WRatio()` выполняется в event loop, может блокировать при большом количестве товаров (см. аудит СЕРЬЁЗ-2). Решение: `asyncio.to_thread()`.
2. **PhotoQueueManager без maxsize** — очередь не ограничена (см. аудит КРИТ-2). При массовом сканировании возможен OOM.
3. **Нет тестов** для MatchingService и Shopping Mode handlers.
4. **aiohttp ClientSession** создаётся на каждую попытку в LabelOCRService (унаследовано от общей архитектуры — см. аудит КРИТ-1).

---

*Документ обновлён на основе реального кода. Claude Sonnet 4.6, 2026-04-08.*

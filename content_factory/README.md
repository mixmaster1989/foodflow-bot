# FoodFlow Content Factory (MVP)

Независимый микросервис для автоматизации генерации публикаций и постов для экосистемы FoodFlow.

## Требования для MVP
- Подключение к БД `foodflow.db` (Read-only, берем статистику).
- OpenRouter API (Тексты: Claude/Gemini, Картинки: Nano Banano / Flux).
- Telegram Bot API или Telethon-сессия для публикации в TG-канал.
- VK API для отправки постов на стену.

## Логика работы
1. `main.py` -> Точка старта.
2. `generators/text.py` -> Общение с LLM, создание вовлекающего текста + промпта для картинки.
3. `generators/image.py` -> Фетчинг картинки по сгенерированному промпту.
4. `publishers/telegram.py` и `vk.py` -> Дистрибуция готового контента.

## Запуск
`python -m content_factory.main`
(В проде: `pm2 start content_factory/main.py --name foodflow-factory`)

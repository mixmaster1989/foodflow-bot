# FoodFlow API — Полная документация

> **Версия API**: 1.0.0  
> **Base URL**: `http://your-server:8001`  
> **Формат данных**: JSON (UTF-8)  
> **Авторизация**: Bearer Token (JWT)  
> **Swagger UI**: `http://your-server:8001/docs`  
> **Health Check**: `GET /api/health`  
> **Обновлено**: 2026-04-08

---

## Все роутеры API (актуально на апрель 2026)

| Префикс | Файл | Описание |
|---------|------|----------|
| `/api/auth` | `routers/auth.py` | Авторизация (JWT, Telegram, Web) |
| `/api/products` | `routers/products.py` | Холодильник (CRUD продуктов) |
| `/api/consumption` | `routers/consumption.py` | Логи съеденного |
| `/api/recipes` | `routers/recipes.py` | AI-рецепты |
| `/api/weight` | `routers/weight.py` | Трекинг веса |
| `/api/shopping-list` | `routers/shopping_list.py` | Список покупок |
| `/api/reports` | `routers/reports.py` | Дневные отчёты |
| `/api/receipts` | `routers/receipts.py` | OCR чеков |
| `/api/recognize` | `routers/recognize.py` | Распознавание еды/этикеток |
| `/api/smart` | `routers/smart.py` | Умный анализ текста |
| `/api/search` | `routers/search.py` | Поиск по холодильнику |
| `/api/herbalife` | `routers/herbalife.py` | База Herbalife |
| `/api/universal` | `routers/universal.py` | Универсальный ввод |
| `/api/assets` | `routers/assets.py` | Иконки и фоны (Flux) |
| `/api/saved-dishes` | `routers/saved_dishes.py` | Сохранённые блюда |
| `/api/water` | `routers/water.py` | Трекинг воды |
| `/api/ai` | `routers/ai_insight.py` | AI Insight (SSE stream) |
| `/api/referrals` | `routers/referrals.py` | Реферальная система |

---

## 📑 Содержание

1. [Быстрый старт](#-быстрый-старт)
2. [Авторизация](#-авторизация)
3. [Продукты (Холодильник)](#-продукты-холодильник)
4. [Потребление (Логи еды)](#-потребление-логи-еды)
5. [Распознавание (AI)](#-распознавание-ai)
6. [Чеки (OCR)](#-чеки-ocr)
7. [Рецепты](#-рецепты)
8. [Вес](#-вес)
9. [Список покупок](#-список-покупок)
10. [Отчёты](#-отчёты)
11. [Вода](#-вода)
12. [Smart анализ текста](#-smart-анализ-текста)
13. [Assets (иконки и фоны)](#-assets)
14. [Сохранённые блюда](#-сохранённые-блюда)
15. [AI Insight (SSE)](#-ai-insight-sse)
16. [Реферальная система](#-реферальная-система)
17. [Herbalife](#-herbalife)
18. [Поиск](#-поиск)
19. [Коды ошибок](#-коды-ошибок)
20. [TypeScript типы](#-typescript-типы)

---

## 🚀 Быстрый старт

### 1. Получить токен
```javascript
const response = await fetch('http://localhost:8001/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ telegram_id: 123456789, username: 'ivan' })
});
const { access_token } = await response.json();
// access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 2. Использовать токен
```javascript
const products = await fetch('http://localhost:8001/api/products', {
  headers: { 
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  }
});
```

### 3. Swagger UI (интерактивная документация)
Открой в браузере: `http://localhost:8001/docs`

---

## 🔐 Авторизация

API использует **JWT (JSON Web Token)**. Токен действует **30 дней**.

### Как это работает:
1. Пользователь регистрируется/логинится через Telegram ID
2. API возвращает `access_token`
3. Этот токен нужно передавать в каждом запросе в заголовке `Authorization`

### Формат заголовка:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEyMzQ1Njc4OSwiZXhwIjoxNzM5MTg5NjAwfQ.xyz
```

---

### Эндпоинты авторизации (актуальный список)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/register` | Регистрация через Telegram ID |
| POST | `/api/auth/login` | Логин через Telegram ID |
| GET | `/api/auth/me` | Профиль и настройки текущего пользователя |
| PATCH | `/api/auth/settings` | Обновить настройки пользователя |
| POST | `/api/auth/login-password` | Логин через пароль (GLOBAL_PASSWORD) |
| POST | `/api/auth/web-register` | Регистрация через Telegram WebApp initData |
| POST | `/api/auth/web-login` | Логин через Telegram WebApp initData |

---

### `POST /api/auth/register`

Регистрация нового пользователя или получение токена для существующего.

**Request Body:**
```json
{
  "telegram_id": 123456789,
  "username": "ivan_petrov"  // опционально
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Когда использовать:** При первом входе пользователя в приложение.

---

### `POST /api/auth/login`

Логин существующего пользователя.

**Request Body:**
```json
{
  "telegram_id": 123456789
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "User not found. Please register first."
}
```

---

### `GET /api/auth/me`

Получить профиль и настройки текущего пользователя.

**Headers:** `Authorization: Bearer <token>` *(обязательно)*

**Response (200 OK):**
```json
{
  "calorie_goal": 2000,
  "protein_goal": 150,
  "fat_goal": 70,
  "carb_goal": 250,
  "fiber_goal": 30,
  "allergies": "орехи, глютен",
  "gender": "male",
  "age": 28,
  "height": 180,
  "weight": 75.5,
  "goal": "lose_weight"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `calorie_goal` | number | Дневная норма ккал |
| `protein_goal` | number | Норма белка (г) |
| `fat_goal` | number | Норма жиров (г) |
| `carb_goal` | number | Норма углеводов (г) |
| `fiber_goal` | number | Норма клетчатки (г) |
| `allergies` | string \| null | Аллергии (через запятую) |
| `gender` | "male" \| "female" \| null | Пол |
| `age` | number \| null | Возраст |
| `height` | number \| null | Рост (см) |
| `weight` | number \| null | Текущий вес (кг) |
| `goal` | string \| null | Цель: "lose_weight", "maintain", "gain_mass" |

---

## 🧊 Продукты (Холодильник)

### Эндпоинты продуктов (актуальный список)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/products` | Список продуктов (пагинация) |
| GET | `/api/products/summary` | Краткая сводка холодильника |
| POST | `/api/products/scan-label` | Распознать этикетку (OCR), добавить продукт |
| GET | `/api/products/{product_id}` | Один продукт по ID |
| POST | `/api/products` | Добавить продукт вручную |
| DELETE | `/api/products/{product_id}` | Удалить продукт |
| POST | `/api/products/{product_id}/consume` | Записать потребление |

---

### `GET /api/products`

Получить список всех продуктов пользователя.

**Headers:** `Authorization: Bearer <token>` *(обязательно)*

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `page` | number | 0 | Номер страницы (начиная с 0) |
| `page_size` | number | 20 | Кол-во элементов (1-100) |

**Пример запроса:**
```
GET /api/products?page=0&page_size=10
```

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 42,
      "name": "Молоко 3.2%",
      "price": 89.0,
      "quantity": 1.0,
      "weight_g": 1000.0,
      "category": "молочные",
      "calories": 60.0,
      "protein": 3.0,
      "fat": 3.2,
      "carbs": 4.7,
      "fiber": 0.0,
      "receipt_id": 15,
      "user_id": 123456789,
      "source": "receipt"
    }
  ],
  "total": 56,
  "page": 0,
  "page_size": 10
}
```

**Важно о нутриентах:**
- `calories`, `protein`, `fat`, `carbs`, `fiber` — всегда **на 100г продукта**
- Для расчёта реального потребления: `value * weight_g / 100`

---

### `GET /api/products/{product_id}`

Получить один продукт по ID.

**Response (200 OK):**
```json
{
  "id": 42,
  "name": "Молоко 3.2%",
  "price": 89.0,
  "quantity": 1.0,
  "weight_g": 1000.0,
  "category": "молочные",
  "calories": 60.0,
  "protein": 3.0,
  "fat": 3.2,
  "carbs": 4.7,
  "fiber": 0.0,
  "receipt_id": 15,
  "user_id": 123456789,
  "source": "receipt"
}
```

**Response (404 Not Found):**
```json
{ "detail": "Product not found" }
```

**Response (403 Forbidden):**
```json
{ "detail": "Access denied" }
```

---

### `POST /api/products`

Добавить новый продукт вручную.

**Request Body:**
```json
{
  "name": "Яблоко Голден",
  "price": 120.0,
  "quantity": 3.0,
  "weight_g": 600.0,
  "category": "фрукты",
  "calories": 52.0,
  "protein": 0.3,
  "fat": 0.2,
  "carbs": 14.0,
  "fiber": 2.4
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `name` | string | ✅ | Название продукта |
| `price` | number | ❌ (0) | Цена в рублях |
| `quantity` | number | ❌ (1) | Количество штук |
| `weight_g` | number \| null | ❌ | Общий вес в граммах |
| `category` | string \| null | ❌ | Категория |
| `calories` | number | ❌ (0) | Калории на 100г |
| `protein` | number | ❌ (0) | Белки на 100г |
| `fat` | number | ❌ (0) | Жиры на 100г |
| `carbs` | number | ❌ (0) | Углеводы на 100г |
| `fiber` | number | ❌ (0) | Клетчатка на 100г |

**Response (201 Created):**
```json
{
  "id": 99,
  "name": "Яблоко Голден",
  "price": 120.0,
  "quantity": 3.0,
  "weight_g": 600.0,
  "category": "фрукты",
  "calories": 52.0,
  "protein": 0.3,
  "fat": 0.2,
  "carbs": 14.0,
  "fiber": 2.4,
  "receipt_id": null,
  "user_id": 123456789,
  "source": "api"
}
```

---

### `DELETE /api/products/{product_id}`

Удалить продукт.

**Response (204 No Content):** *(пустой ответ = успех)*

**Response (404 Not Found):**
```json
{ "detail": "Product not found" }
```

---

### `POST /api/products/{product_id}/consume`

**Главный эндпоинт для записи съеденного!**

Записывает потребление и автоматически:
1. Создаёт запись в логе еды (`consumption_logs`)
2. Уменьшает количество/вес продукта
3. Удаляет продукт, если он закончился

**Request Body:**
```json
{
  "amount": 150,
  "unit": "grams"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `amount` | number | Сколько съедено (граммов или штук) |
| `unit` | "grams" \| "qty" | Единица измерения |

**Примеры:**
```javascript
// Съел 150г молока
{ "amount": 150, "unit": "grams" }

// Съел 2 яблока
{ "amount": 2, "unit": "qty" }
```

**Response (200 OK):**
```json
{
  "message": "Consumed 150g",
  "logged": {
    "calories": 90.0,
    "protein": 4.5,
    "fat": 4.8,
    "carbs": 7.1,
    "fiber": 0.0
  }
}
```

**Как рассчитывается (для grams):**
```
factor = amount / 100
logged_calories = product.calories * factor
```

**Как рассчитывается (для qty):**
```
weight_per_unit = product.weight_g / product.quantity (или 100г если неизвестно)
factor = (weight_per_unit * amount) / 100
logged_calories = product.calories * factor
```

---

## 📝 Потребление (Логи еды)

### Эндпоинты потребления (актуальный список)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/consumption` | История съеденного |
| POST | `/api/consumption` | Записать еду вручную |
| POST | `/api/consumption/manual` | Записать блюдо вручную (расширенная форма) |
| DELETE | `/api/consumption/{log_id}` | Удалить запись |
| PATCH | `/api/consumption/{log_id}` | Обновить запись |

---

### `GET /api/consumption`

Получить историю съеденного.

**Query Parameters:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `date` | string (YYYY-MM-DD) | Конкретная дата |
| `from` | string (YYYY-MM-DD) | Начало периода |
| `to` | string (YYYY-MM-DD) | Конец периода |

**Примеры:**
```
GET /api/consumption?date=2026-01-10
GET /api/consumption?from=2026-01-01&to=2026-01-10
GET /api/consumption  // последние 100 записей
```

**Response (200 OK):**
```json
[
  {
    "id": 25,
    "user_id": 123456789,
    "product_name": "Молоко 3.2%",
    "calories": 90.0,
    "protein": 4.5,
    "fat": 4.8,
    "carbs": 7.1,
    "fiber": 0.0,
    "date": "2026-01-10T08:30:00"
  }
]
```

**Важно:** `date` — это UTC время. На фронте конвертируй в локальное время пользователя.

---

### `POST /api/consumption`

Записать еду вручную (без привязки к продукту).

**Request Body:**
```json
{
  "product_name": "Бургер в кафе",
  "calories": 550.0,
  "protein": 25.0,
  "fat": 30.0,
  "carbs": 45.0,
  "fiber": 2.0
}
```

**Response (201 Created):**
```json
{
  "id": 26,
  "user_id": 123456789,
  "product_name": "Бургер в кафе",
  "calories": 550.0,
  "protein": 25.0,
  "fat": 30.0,
  "carbs": 45.0,
  "fiber": 2.0,
  "date": "2026-01-10T12:15:00"
}
```

---

### `DELETE /api/consumption/{log_id}`

Удалить запись о съеденном.

**Response (204 No Content):** *(успех)*

---

## 🤖 Распознавание (AI)

### `POST /api/recognize/food`

**Распознать еду по фотографии!**

Загружаешь фото блюда — получаешь название и КБЖУ на 100г.

**Request:** `multipart/form-data`
```javascript
const formData = new FormData();
formData.append('file', photoBlob, 'food.jpg');

const response = await fetch('/api/recognize/food', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});
```

**Response (200 OK):**
```json
{
  "name": "Пельмени сибирские",
  "calories": 275.0,
  "protein": 12.0,
  "fat": 14.0,
  "carbs": 25.0,
  "fiber": 1.5,
  "weight_g": null
}
```

**Response (422 Unprocessable Entity):**
```json
{
  "detail": "Could not recognize food in image. Try a clearer photo."
}
```

**Ограничения:**
- Максимальный размер файла: **10 MB**
- Форматы: JPEG, PNG
- Время обработки: 2-5 секунд

---

### `POST /api/recognize/label`

**Распознать этикетку продукта!**

Загружаешь фото пищевой ценности — получаешь точные данные с упаковки.

**Request:** `multipart/form-data` (аналогично `/food`)

**Response (200 OK):**
```json
{
  "name": "Сыр Российский 50%",
  "calories": 364.0,
  "protein": 23.0,
  "fat": 30.0,
  "carbs": 0.0,
  "fiber": 0.0,
  "weight_g": 200.0
}
```

**Когда использовать `/food` vs `/label`:**
| Сценарий | Эндпоинт |
|----------|----------|
| Фото тарелки с едой | `/recognize/food` |
| Фото этикетки с пищевой ценностью | `/recognize/label` |
| Фото продукта в упаковке | `/recognize/food` (попробует угадать) |

---

## 🧾 Чеки (OCR)

### `POST /api/receipts/upload`

**Загрузить фото чека → получить распознанные товары с КБЖУ!**

Этот эндпоинт делает две вещи:
1. **OCR** — распознаёт текст чека (названия, цены, количество)
2. **Нормализация** — для каждого товара находит КБЖУ

**Request:** `multipart/form-data`
```javascript
const formData = new FormData();
formData.append('file', receiptImageBlob, 'receipt.jpg');

const response = await fetch('/api/receipts/upload', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});
```

**Response (200 OK):**
```json
{
  "receipt_id": 15,
  "items": [
    {
      "name": "Молоко Простоквашино 3.2% 930мл",
      "original_name": "МОЛОКО ПРОСТОКВ 3.2 930",
      "price": 89.99,
      "quantity": 1.0,
      "category": "молочные",
      "calories": 58,
      "protein": 2.9,
      "fat": 3.2,
      "carbs": 4.7,
      "fiber": 0
    },
    {
      "name": "Хлеб Бородинский нарезанный",
      "original_name": "ХЛЕБ БОРОДИНСКИЙ",
      "price": 55.0,
      "quantity": 1.0,
      "category": "хлеб",
      "calories": 207,
      "protein": 6.8,
      "fat": 1.3,
      "carbs": 39.8,
      "fiber": 5.1
    }
  ],
  "total": 144.99
}
```

**Что внутри `items`:**
| Поле | Описание |
|------|----------|
| `name` | Нормализованное название |
| `original_name` | Как было на чеке |
| `price` | Цена за единицу |
| `quantity` | Количество |
| `category` | Категория (молочные, мясо, овощи...) |
| `calories`, `protein`, `fat`, `carbs`, `fiber` | КБЖУ на 100г |

---

### `POST /api/receipts/{receipt_id}/items/add`

**Добавить выбранный товар из чека в холодильник.**

После распознавания чека показываешь пользователю список — он выбирает что добавить.

**Request Body:**
```json
{
  "name": "Молоко Простоквашино 3.2% 930мл",
  "price": 89.99,
  "quantity": 1.0,
  "category": "молочные",
  "calories": 58,
  "protein": 2.9,
  "fat": 3.2,
  "carbs": 4.7,
  "fiber": 0
}
```

**Response (200 OK):**
```json
{
  "message": "Item added",
  "product_id": 103
}
```

**Типичный флоу:**
1. Пользователь фоткает чек
2. `POST /api/receipts/upload` → получаем `items`
3. Показываем список пользователю с чекбоксами
4. Для каждого выбранного: `POST /api/receipts/{id}/items/add`

---

## 👨‍🍳 Рецепты

### `GET /api/recipes/categories`

Получить список категорий рецептов.

**Response (200 OK):**
```json
{
  "categories": [
    "🍳 Завтрак",
    "🥗 Обед",
    "🍝 Ужин",
    "🥤 Перекус",
    "🍰 Десерт"
  ]
}
```

---

### `POST /api/recipes/generate`

**Сгенерировать рецепты на основе продуктов в холодильнике!**

**Request Body:**
```json
{
  "category": "🍳 Завтрак",
  "refresh": false
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `category` | string | Категория из списка |
| `refresh` | boolean | `true` = игнорировать кэш, сгенерировать заново |

**Response (200 OK):**
```json
[
  {
    "title": "Омлет с сыром и зеленью",
    "description": "Пышный омлет на завтрак",
    "calories": 250.0,
    "ingredients": [
      { "name": "Яйца", "amount": "3 шт" },
      { "name": "Молоко", "amount": "50 мл" },
      { "name": "Сыр", "amount": "30 г" }
    ],
    "steps": [
      "Взбить яйца с молоком",
      "Добавить тёртый сыр",
      "Жарить на среднем огне 5 минут"
    ]
  }
]
```

**Важно:**
- Рецепты генерируются **на основе продуктов пользователя**
- Если холодильник пуст — используются дефолтные ингредиенты
- Ответ кэшируется — при тех же продуктах вернётся тот же набор рецептов
- `refresh: true` — принудительно сгенерировать новые

---

## ⚖️ Вес

### `GET /api/weight`

Получить историю веса.

**Query Parameters:**
| Параметр | Тип | По умолчанию |
|----------|-----|--------------|
| `limit` | number | 30 |

**Response (200 OK):**
```json
[
  {
    "id": 5,
    "weight": 75.3,
    "recorded_at": "2026-01-10T07:00:00"
  },
  {
    "id": 4,
    "weight": 75.5,
    "recorded_at": "2026-01-09T07:15:00"
  }
]
```

---

### `POST /api/weight`

Записать вес.

**Request Body:**
```json
{
  "weight": 75.1
}
```

**Валидация:**
- Минимум: 20 кг
- Максимум: 300 кг

**Response (201 Created):**
```json
{
  "id": 6,
  "weight": 75.1,
  "recorded_at": "2026-01-10T08:00:00"
}
```

---

## 🛒 Список покупок

### `GET /api/shopping-list`

Получить список покупок.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "product_name": "Молоко",
    "is_bought": false,
    "created_at": "2026-01-10T10:00:00"
  },
  {
    "id": 2,
    "product_name": "Хлеб",
    "is_bought": true,
    "created_at": "2026-01-09T15:00:00"
  }
]
```

**Сортировка:** Сначала некупленные, потом купленные (по дате).

---

### `POST /api/shopping-list`

Добавить товар в список.

**Request Body:**
```json
{
  "product_name": "Бананы"
}
```

**Response (201 Created):**
```json
{
  "id": 3,
  "product_name": "Бананы",
  "is_bought": false,
  "created_at": "2026-01-10T12:00:00"
}
```

---

### `PUT /api/shopping-list/{item_id}/buy`

Отметить как купленное.

**Response (200 OK):**
```json
{ "message": "Marked as bought" }
```

---

### `PUT /api/shopping-list/{item_id}/unbuy`

Вернуть в список (снять отметку).

**Response (200 OK):**
```json
{ "message": "Marked as not bought" }
```

---

### `DELETE /api/shopping-list/{item_id}`

Удалить из списка.

**Response (204 No Content)**

---

## 📊 Отчёты

### `GET /api/reports/daily`

**Получить дневной отчёт по питанию!**

**Query Parameters:**
| Параметр | Тип | По умолчанию |
|----------|-----|--------------|
| `date` | string (YYYY-MM-DD) | Сегодня (UTC) |

**Response (200 OK):**
```json
{
  "date": "2026-01-10",
  "calories_consumed": 1450.5,
  "calories_goal": 2000,
  "protein": 85.3,
  "fat": 52.1,
  "carbs": 180.4,
  "fiber": 18.5,
  "fiber_goal": 30,
  "meals_count": 4
}
```

**Как использовать:**
```javascript
const progress = (report.calories_consumed / report.calories_goal) * 100;
// progress = 72.5%
```

---

## 💧 Вода

### `GET /api/water`

Получить логи воды за день.

**Query Parameters:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `date` | string (YYYY-MM-DD) | Дата (по умолчанию — сегодня по MSK) |

**Response (200 OK):**
```json
[
  { "id": 1, "amount_ml": 250, "date": "2026-04-08T08:00:00" }
]
```

---

### `POST /api/water`

Записать потребление воды.

**Request Body:**
```json
{ "amount_ml": 300 }
```

**Response (201 Created):**
```json
{ "id": 2, "amount_ml": 300, "date": "2026-04-08T09:30:00" }
```

---

### `DELETE /api/water/{log_id}`

Удалить запись о воде. **Response (204 No Content).**

---

## 🧠 Smart анализ текста

### `POST /api/smart/analyze`

Анализировать текстовое описание еды — получить КБЖУ.

**Request Body:**
```json
{ "text": "тарелка борща 300г" }
```

**Response (200 OK):**
```json
{
  "name": "Борщ",
  "calories": 135.0,
  "protein": 4.2,
  "fat": 3.8,
  "carbs": 18.5,
  "fiber": 2.1,
  "weight_g": 300.0
}
```

---

## 🖼 Assets

### `GET /api/assets/icon/{name}`

Получить или сгенерировать иконку для продукта (Flux/Pollinations.ai).

**Response**: изображение PNG.

---

### `GET /api/assets/daily-bg`

Получить или сгенерировать ежедневный AI-фон на основе содержимого холодильника.

**Response**: изображение PNG.

---

## 🍽 Сохранённые блюда

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/saved-dishes/` | Список сохранённых блюд |
| POST | `/api/saved-dishes/` | Сохранить блюдо |
| DELETE | `/api/saved-dishes/{dish_id}` | Удалить блюдо |
| POST | `/api/saved-dishes/{dish_id}/log` | Залогировать сохранённое блюдо как приём пищи |

---

## 🤖 AI Insight (SSE)

### `GET /api/ai/insight`

Получить AI-комментарий (Server-Sent Events, стриминг).

**Query Parameters:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `action` | string | Тип события (напр. `greeting`, `food_log`, `water_logged`) |
| `detail` | string | Детали события |

**Response**: `text/event-stream` (SSE)

```
data: Отличный выбор! Борщ — 

data: хорошее сочетание 

data: овощей для вашей цели.

```

При активном AI Guide (Pro) — возвращает развёрнутый совет от AIGuideService.

---

## 🔗 Реферальная система

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/referrals/me` | Мои рефералы, вознаграждения, ссылка |
| POST | `/api/referrals/generate_link` | Сгенерировать реферальную ссылку |
| POST | `/api/referrals/activate_reward` | Активировать реферальное вознаграждение |

---

## 🌿 Herbalife

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/herbalife/search` | Поиск продукта в базе Herbalife |
| GET | `/api/herbalife/products` | Все продукты Herbalife |
| POST | `/api/herbalife/calculate` | Рассчитать КБЖУ порции Herbalife |

---

## 🔍 Поиск

### `GET /api/search/fridge`

Умный поиск по холодильнику.

**Query Parameters:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `q` | string | Поисковый запрос |

**Response (200 OK):** список продуктов (формат как `GET /api/products`).

---

## ❌ Коды ошибок

| Код | Описание | Что делать |
|-----|----------|------------|
| 400 | Bad Request | Проверь формат данных |
| 401 | Unauthorized | Токен невалидный/истёк — перелогинь |
| 403 | Forbidden | Нет доступа к этому ресурсу |
| 404 | Not Found | Ресурс не найден |
| 422 | Unprocessable Entity | Данные валидные, но не обработались (AI не распознал) |
| 500 | Internal Server Error | Ошибка сервера — напиши разработчику |

**Формат ошибки:**
```json
{
  "detail": "Описание ошибки на английском"
}
```

---

## 📦 TypeScript типы

```typescript
// === Auth ===
interface Token {
  access_token: string;
  token_type: 'bearer';
}

interface UserCreate {
  telegram_id: number;
  username?: string;
}

// === User Settings ===
interface UserSettings {
  calorie_goal: number;
  protein_goal: number;
  fat_goal: number;
  carb_goal: number;
  fiber_goal: number;
  allergies: string | null;
  gender: 'male' | 'female' | null;
  age: number | null;
  height: number | null;
  weight: number | null;
  goal: 'lose_weight' | 'maintain' | 'gain_mass' | null;
}

// === Product ===
interface Product {
  id: number;
  name: string;
  price: number;
  quantity: number;
  weight_g: number | null;
  category: string | null;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
  receipt_id: number | null;
  user_id: number | null;
  source: string;
}

interface ProductList {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
}

interface ConsumeRequest {
  amount: number;
  unit: 'grams' | 'qty';
}

interface ConsumeResponse {
  message: string;
  logged: {
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
    fiber: number;
  };
}

// === Consumption Log ===
interface ConsumptionLog {
  id: number;
  user_id: number;
  product_name: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
  date: string; // ISO 8601
}

// === Food Recognition ===
interface FoodRecognitionResult {
  name: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
  weight_g: number | null;
}

// === Receipt ===
interface ReceiptParseResult {
  receipt_id: number;
  items: ReceiptItem[];
  total: number;
}

interface ReceiptItem {
  name: string;
  original_name?: string;
  price: number;
  quantity: number;
  category?: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
}

// === Recipe ===
interface Recipe {
  title: string;
  description: string | null;
  calories: number | null;
  ingredients: { name: string; amount: string }[];
  steps: string[];
}

// === Weight ===
interface WeightLog {
  id: number;
  weight: number;
  recorded_at: string; // ISO 8601
}

// === Shopping List ===
interface ShoppingListItem {
  id: number;
  product_name: string;
  is_bought: boolean;
  created_at: string; // ISO 8601
}

// === Daily Report ===
interface DailyReport {
  date: string; // YYYY-MM-DD
  calories_consumed: number;
  calories_goal: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
  fiber_goal: number;
  meals_count: number;
}
```

---

## 🔧 Примеры на JavaScript/TypeScript

### Полный флоу: от чека до холодильника

```typescript
// 1. Авторизация
const auth = await fetch('/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ telegram_id: 123456789 })
}).then(r => r.json());

const token = auth.access_token;
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};

// 2. Загрузка чека
const formData = new FormData();
formData.append('file', receiptFile);

const receipt = await fetch('/api/receipts/upload', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
}).then(r => r.json());

console.log(`Распознано ${receipt.items.length} товаров на сумму ${receipt.total}₽`);

// 3. Добавление выбранных товаров
for (const item of receipt.items) {
  if (userSelectedItem(item)) {
    await fetch(`/api/receipts/${receipt.receipt_id}/items/add`, {
      method: 'POST',
      headers,
      body: JSON.stringify(item)
    });
  }
}

// 4. Проверка холодильника
const products = await fetch('/api/products', { headers }).then(r => r.json());
console.log(`В холодильнике ${products.total} продуктов`);

// 5. Съесть продукт
const consumed = await fetch(`/api/products/${products.items[0].id}/consume`, {
  method: 'POST',
  headers,
  body: JSON.stringify({ amount: 200, unit: 'grams' })
}).then(r => r.json());

console.log(`Записано ${consumed.logged.calories} ккал`);

// 6. Дневной отчёт
const report = await fetch('/api/reports/daily', { headers }).then(r => r.json());
const progress = Math.round((report.calories_consumed / report.calories_goal) * 100);
console.log(`Сегодня: ${report.calories_consumed}/${report.calories_goal} ккал (${progress}%)`);
```

---

## 💡 FAQ

**Q: Почему `calories` и другие нутриенты — на 100г?**
> Это стандарт пищевой индустрии. На упаковках всегда указывают "на 100г". Фронтенд должен умножать на реальный вес.

**Q: Что если AI не распознал еду?**
> Получишь 422 ошибку. Покажи пользователю форму ручного ввода.

**Q: Как часто обновлять токен?**
> Токен живёт 30 дней. Можешь хранить локально и обновлять при 401 ошибке.

**Q: Почему время в UTC?**
> Сервер хранит всё в UTC. Конвертируй на фронте в таймзону пользователя.

**Q: Можно ли загружать несколько фото за раз?**
> Нет, каждое фото — отдельный запрос. Это сделано для надёжности.

---

*Документация актуальна для API версии 1.0.0*  
*Последнее обновление: 2026-04-08 (актуализировано по реальным роутерам в `api/routers/`)*

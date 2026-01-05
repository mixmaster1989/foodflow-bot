# 🝴 FoodFlow Bot

> **Smart AI-powered Telegram bot for intelligent food management, recipe generation, and nutrition tracking**

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot%20API-blue?style=flat-square&logo=telegram)](https://core.telegram.org/bots)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)](#)

[Features](#-features) • [Quick Start](#-quick-start) • [Installation](#installation) • [Usage](#usage) • [Contributing](#contributing)

</div>

---

## 🌟 Overview

**FoodFlow** is an intelligent Telegram bot that transforms your food management experience. Whether you’re tracking groceries, discovering recipes, or monitoring nutrition, FoodFlow handles it all with AI-powered precision.

### Key Capabilities

- 👤 **User Onboarding** - Personalized profile setup (gender, height, weight, goals)
- 💡 **AI Consultant** - Smart product recommendations based on your profile and goals
- 📃 **Receipt Scanning** - Automatic product & price recognition from receipt photos
- 🧇 **Virtual Fridge** - Smart inventory management with real-time tracking  
- 👨‍🍳 **AI Recipe Generation** - Personalized recipes based on your available ingredients
- 📊 **Nutrition Tracking** - KBZHU (calories, proteins, fats, carbs) monitoring
- 🛒 **Shopping Mode** - Scan product labels in-store, match with receipt, auto-fill KBZHU
- 🏷️ **Price Tag Scanner** - OCR price tags & compare prices across stores
- 🌐 **Real-Time Price Search** - Find current prices online via Perplexity AI

---

## ✨ Features

### 1. Receipt Processing

- 🤤 **Multimodal OCR** using Gemini 2.0 Flash
- 🖥️ **Automatic Normalization** via Perplexity Sonar with web search
- 🍻 **Brand & Quantity Preservation** - retains product details
- ✍️ **Interactive Correction** - user-friendly error fixing

### 2. Virtual Fridge

- 🔍 Complete product visibility
- 📂 Smart categorization
- ✍️ Quantity management

### 3. AI-Powered Recipes

- 🧄 Generates recipes from available ingredients
- 🇷🇺 Russian-language responses
- ⚡ Powered by OpenRouter API

### 4. Shopping Mode ✅

- 📸 **Label Scanning** - Photo product labels in-store
- 🔍 **KBZHU Extraction** - Auto-extract nutrition data from labels
- 🛒 **Session Management** - Track shopping trips
- 🤝 **Receipt Matching** - Fuzzy matching with receipt items
- ✏️ **Manual Correction** - UI for mismatched items

### 5. Price Tag Processing (🚧 Experimental)
 
 > **Note:** This feature is currently in active development and not available in the main menu yet.
 
 - 🏷️ **OCR Price Tags** - Extract product name, price, store, and **volume/weight**
 - 📊 **Price History** - Track price trends (📈 increased / 📉 decreased)
 - 🌐 **Real-Time Search** - Find current prices via Perplexity Sonar (considering volume)
 - 🤖 **Multi-Model AI** - Auto-fallback to paid models (Gemini, Pixtral, Qwen) if free ones fail

### 6. Product Correction ✅

- ✏️ **Interactive Editing** - Fix OCR errors with inline buttons
- 💾 **Instant Updates** - Changes saved immediately
- 📝 **Pre-filled Forms** - Current name shown for easy editing

### 7. User Onboarding ✅

- 👤 **Profile Setup** - Collect gender, height, weight, and goals on first launch
- 🎯 **Goal Selection** - Choose from: lose weight, maintain, healthy eating, gain mass
- ✏️ **Profile Editing** - Update your profile anytime from settings

### 8. AI Consultant ✅

- 💡 **Smart Recommendations** - AI-powered product analysis based on your profile
- ⚠️ **Warnings** - Get alerts about high-calorie foods when trying to lose weight
- ✅ **Positive Feedback** - Receive praise for healthy choices
- 🔍 **Context-Aware** - Different recommendations for receipts, fridge, shopping list, and shopping mode
- 🧠 **Personalized** - Considers your goals, allergies, and nutrition targets

### 9. Weight Tracking ✅

- ⚖️ **Daily Logging** - Easy weight input via menu or daily reminders
- 📅 **Smart Scheduler** - Flexible daily reminders (default 9:00 AM) to keep you on track
- 📈 **History & Progress** - View your last 5 weight entries and track progress towards your goal
- 🎯 **Goal Integration** - Weight data syncs with your nutritional goals (Lose Weight/Gain Mass)

---

## 🚀 Quick Start

### Requirements

- **Python** 3.10 or higher
- **Telegram Bot Token** ([get one](https://core.telegram.org/bots#6-botfather))
- **OpenRouter API Key** ([sign up](https://openrouter.ai/))

### Installation

```bash
# Clone the repository
git clone https://github.com/mixmaster1989/foodflow-bot.git
cd foodflow-bot

# Install dependencies
pip install -r requirements.txt

# Create .env file in repo root
cp .env.example .env

# Fill in your keys
echo "BOT_TOKEN=your_telegram_bot_token" >> .env
echo "OPENROUTER_API_KEY=your_openrouter_key" >> .env
echo "DATABASE_URL=sqlite+aiosqlite:///./foodflow.db" >> .env

# Run the bot from repo root
python main.py
```

---

## 📁 Project Structure

```
├── database/           ━ SQLAlchemy ORM models, migrations
├── handlers/           ━ Bot command handlers (menu, onboarding, receipt, fridge, etc.)
├── services/           ━ OCR, normalization, AI consultant, price search, matching
├── config.py           ━ Pydantic configuration (uses .env in repo root)
├── main.py             ━ Entry point (run from repo root)
├── requirements.txt    ━ Dependencies
└── ecosystem.config.js ━ PM2 config (optional)
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram Bot API Token | `123456:ABC-DEF1234...` |
| `OPENROUTER_API_KEY` | OpenRouter API Key | `sk-or-v1-...` |
| `DATABASE_URL` | Database Connection | `sqlite+aiosqlite:///./foodflow.db` |

### AI Models Used

- **OCR**: `google/gemini-2.0-flash-exp:free` (primary)
  - *Fallbacks*: `google/gemini-2.5-flash-lite`, `mistralai/pixtral-12b`, `qwen/qwen-vl-plus`
- **Normalization**: `perplexity/sonar` (with web search)
- **Recipes**: `google/gemma-3-27b-it:free`

---

## 📄 Usage

### Commands

- `/start` - Launch bot & show main menu (triggers onboarding for new users)
- `🧇 Fridge` - View inventory
- `👨‍🍳 Recipes` - Generate recipes
- `📊 Statistics` - Daily KBZHU stats
- `⚙️ Settings` - Manage profile and nutrition goals

### Receipt Processing Workflow

1. Send receipt photo to bot
2. Select "🦾 Processing receipt"
3. Wait for OCR + AI normalization
4. Review results
5. Use "✍️ Correct" button if needed

---

## 🛠️ Development

### Setup Dev Environment

```bash
pip install -r FoodFlow/requirements.txt
```

### Run Tests

```bash
pytest tests/
```

### Logs

All logs are saved to `foodflow.log` in the project root.

### Security

The project includes a pre-commit hook to prevent committing secrets.
To install it manually:

```bash
python check_secrets.py
# Or copy to .git/hooks/pre-commit
```

---

## 🤚 Contributing

Contributions are welcome! For major changes, please open an Issue first to discuss your ideas.

```bash
# Fork, create your feature branch, and submit a PR
git checkout -b feature/amazing-feature
git commit -m 'Add amazing feature'
git push origin feature/amazing-feature
```

---

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**mixmaster1989**
- GitHub: [@mixmaster1989](https://github.com/mixmaster1989)
- Telegram: [@mixmaster1989](https://t.me/mixmaster1989)

---

## 🙏 Acknowledgments

- [Aiogram](https://github.com/aiogram/aiogram) - Telegram Bot Framework
- [OpenRouter](https://openrouter.ai/) - AI API Aggregator
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python ORM
- [Google Gemini](https://ai.google.dev/) - Vision & Language AI
- [Perplexity Sonar](https://www.perplexity.ai/) - Web Search AI

---

## 📄 Support

Have questions or issues? 
- Open an [Issue](https://github.com/mixmaster1989/foodflow-bot/issues)
- Message me on Telegram: [@mixmaster1989](https://t.me/mixmaster1989)

---

<div align="center">

**⭐ If you like this project, please give it a star!**

*Made with ❤️ by mixmaster1989*

</div>

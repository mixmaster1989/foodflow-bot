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

- 📃 **Receipt Scanning** - Automatic product & price recognition from receipt photos
- 🧇 **Virtual Fridge** - Smart inventory management with real-time tracking  
- 👨‍🍳 **AI Recipe Generation** - Personalized recipes based on your available ingredients
- 📊 **Nutrition Tracking** - KBZHU (calories, proteins, fats, carbs) monitoring
- 🛒 **Smart Shopping Mode** - Product barcode scanning with nutritional data extraction

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

### 4. Shopping Mode (In Development)

- 🛍️ Barcode scanning
- 🣋 Automatic KBZHU extraction
- ✅ Receipt matching

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
pip install -r FoodFlow/requirements.txt

# Create .env file
cp .env.example .env

# Fill in your keys
echo "BOT_TOKEN=your_telegram_bot_token" >> .env
echo "OPENROUTER_API_KEY=your_openrouter_key" >> .env
echo "DATABASE_URL=sqlite+aiosqlite:///./foodflow.db" >> .env

# Run the bot
cd FoodFlow
python main.py
```

---

## 📁 Project Structure

```
FoodFlow/
├── database/           ━ SQLAlchemy ORM models
│   ├── base.py
│   └── models.py
├── handlers/           ━ Bot command handlers
│   ├── common.py         # Main menu
│   ├── receipt.py        # Receipt processing
│   ├── fridge.py         # Virtual fridge
│   ├── recipes.py        # Recipe generation
│   ├── stats.py          # Statistics
│   └── correction.py     # Product correction
├── services/           ━ Business logic
│   ├── ocr.py            # OCR processing
│   ├── normalization.py  # Data normalization
│   └── ai.py             # AI integrations
├── config.py           ━ Pydantic configuration
├── main.py             ━ Entry point
└── requirements.txt    ━ Dependencies
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

- **OCR**: `google/gemini-2.0-flash-exp:free` (primary) | `google/gemma-3-27b-it:free` (backup)
- **Normalization**: `perplexity/sonar` (with web search)
- **Recipes**: `google/gemma-3-27b-it:free`

---

## 📄 Usage

### Commands

- `/start` - Launch bot & show main menu
- `🧇 Fridge` - View inventory
- `👨‍🍳 Recipes` - Generate recipes
- `📊 Statistics` - Daily KBZHU stats

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

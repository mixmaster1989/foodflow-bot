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

### 10. 📱 Interactive Mini App (Web App)
- **Seamless UI** - Full-screen experience integrated into Telegram.
- **Dynamic Backgrounds** - AI-generated (Flux) backgrounds reflecting your fridge contents.
- **Smart Add** - Voice input, text, or camera with auto-normalization.
- **"Eat Immediately"** - Checkbox to log consumption instantly when adding stock.
- **Visual Inventory** - Beautiful grid with AI-generated icons for every product.

### 11. 🎙️ Voice & Multimodal Input
- **Voice-to-Food** - Dictate "3 eggs and milk" and let AI parse it.
- **Photo-to-Food** - Snap a picture of your fridge or table.
- **Herbalife Expert** - Specialized database for fast logging of shakes and supplements.

### 12. 🎨 AI Visual Engine (Flux)
- **Auto-Icons** - Generates professional icons for any product (no placeholders!).
- **Smart Rate-Limiting** - Detects API limits and handles fallbacks gracefully.
- **Daily Collage** - Creates a unique daily wallpaper based on your actual diet.

### 13. 🛡️ User Onboarding & Goals
- **Profile Setup** - Gender, height, weight, activity levels.
- **Smart Goals** - Auto-calculation of Calorie/Protein/Fat/Carb targets.
- **Fiber Tracking** - New metric for digestional health.

---

## 🚀 Quick Start

### Requirements

- **Python** 3.10 or higher
- **Telegram Bot Token** ([get one](https://core.telegram.org/bots#6-botfather))
- **OpenRouter API Key** ([sign up](https://openrouter.ai/))

### Installation (Full Stack)
```bash
# 1. Clone the repository
git clone https://github.com/mixmaster1989/foodflow-bot.git
cd foodflow-bot

# 2. Backend Setup
pip install -r requirements.txt
cp .env.example .env
# (Fill .env with BOT_TOKEN, OPENROUTER_API_KEY, DATABASE_URL)

# 3. Frontend Setup (React + Vite)
cd frontend
npm install
npm run build
# The build output will be in frontend/dist/

# 4. Nginx Setup (Proxy)
# Configure Nginx to serve /api/ from localhost:8001 and / from frontend/dist/
# See architecture docs for Nginx config examples.
```

---

## 📁 Project Structure

```
├── api/                ━ FastAPI Backend (Routes, Auth, Logic)
├── database/           ━ SQLAlchemy ORM models, migrations
├── frontend/           ━ React + Vite + Tailwind Web App
│   ├── src/            ━ UI Components, Hooks, Pages
│   └── dist/           ━ Compiled static assets
├── handlers/           ━ Telegram Bot command handlers
├── services/           ━ AI Integrations (Gemini, Flux, Perplexity)
├── static/             ━ Generated Assets (Icons, Backgrounds)
├── main.py             ━ Bot Entry Point
└── config.py           ━ Configuration Manager
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
- **OCR**: `google/gemini-3.5-flash-lite` (primary)
- **Normalization**: `perplexity/sonar` (with web search)
- **Visuals**: `Pollinations.ai (Flux)` for icons and backgrounds
- **Speech**: `Google Speech Recognition` (via `SpeechRecognition` lib)
- **Recipes**: `google/gemma-3-27b-it`

---

## 📄 Usage

### 📱 Main Web App (Recommended)
Type `/start` or click the "Menu" button to launch the full-screen Mini App.
- **Fridge Tab**: View products, add new ones (Voice/Camera/Text).
- **Scan Tab**: Add receipts.
- **Stats Tab**: View daily nutrition goals.

### 🤖 Bot Commands
- `/start` - Launch menu
- `/help` - Show instructions
- `👨‍🍳 Recipes` - Generate text-based recipes

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

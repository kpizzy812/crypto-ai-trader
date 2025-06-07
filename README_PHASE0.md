# README.md
# 🤖 Crypto AI Trading Bot

Автоматизированный торговый бот для криптовалютных фьючерсов с использованием искусственного интеллекта.

## 🚀 Phase 0 - MVP CLI версия

Текущая версия представляет собой базовую CLI версию для тестирования core компонентов.

### ✨ Возможности

- 📊 Анализ рыночных данных с криптобирж
- 🤖 Mock AI анализатор для тестирования pipeline
- 🔌 Подключение к Bybit и Binance (testnet)
- 📈 Базовый технический анализ
- 🛠️ CLI интерфейс для быстрого тестирования

### 🛠️ Установка и запуск

1. **Клонирование репозитория:**
```bash
git clone <repository-url>
cd crypto_ai_trader
```

2. **Создание виртуального окружения:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. **Установка зависимостей:**
```bash
pip install -r requirements.txt
```

4. **Настройка окружения:**
```bash
cp .env.example .env
# Отредактируйте .env файл, добавив ваши API ключи
```

5. **Тестирование подключения:**
```bash
python cli.py test-connection --exchange bybit
```

### 📋 CLI Команды

```bash
# Анализ рынка
python cli.py analyze --symbol BTCUSDT --timeframe 5m

# AI анализ (mock режим)
python cli.py ai-analyze --symbol BTCUSDT --mock

# Тест подключения к бирже
python cli.py test-connection --exchange bybit

# Запуск торгового движка (демо режим)
python cli.py run
```

### 🐳 Docker запуск

```bash
cd docker
docker-compose up -d
```

### ⚠️ Важные замечания

- **Текущая версия работает только в testnet режиме**
- **Mock AI анализатор генерирует случайные сигналы**
- **Реальная торговля отключена в Phase 0**
- **Все API ключи должны быть с ограниченными правами (без вывода средств)**

### 🔄 Следующие этапы развития

- [ ] Интеграция с реальным OpenAI API
- [ ] Реализация торговых стратегий
- [ ] Система уведомлений через Telegram
- [ ] Веб-интерфейс для мониторинга
- [ ] Продвинутый риск-менеджмент
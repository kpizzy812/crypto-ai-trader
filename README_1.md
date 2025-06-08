# Crypto AI Trading Bot - Документация

## 📋 Оглавление
- [Обзор системы](#обзор-системы)
- [Архитектура](#архитектура)
- [Как работает бот](#как-работает-бот)
- [Установка и настройка](#установка-и-настройка)
- [Первый запуск](#первый-запуск)
- [Команды CLI](#команды-cli)
- [API эндпоинты](#api-эндпоинты)
- [Стратегии](#стратегии)
- [Риск-менеджмент](#риск-менеджмент)
- [Мониторинг](#мониторинг)
- [Устранение проблем](#устранение-проблем)

## 🚀 Обзор системы

Crypto AI Trading Bot - это автоматизированная система для торговли криптовалютными фьючерсами с использованием искусственного интеллекта.

### Основные возможности:
- 🤖 AI анализ рынка (OpenAI GPT-4)
- 📊 Технический анализ индикаторов
- 💹 Автоматическое открытие/закрытие позиций
- ⚠️ Встроенный риск-менеджмент
- 📱 Telegram уведомления
- 🌐 Web дашборд для мониторинга
- 📈 Поддержка нескольких стратегий
- 🔄 Бэктестинг стратегий

## 🏗️ Архитектура

### Основные компоненты:

1. **Trading Engine** (`core/engine.py`)
   - Главный оркестратор системы
   - Управляет жизненным циклом всех компонентов
   - Координирует работу стратегий

2. **Event Bus** (`core/event_bus.py`)
   - Асинхронная шина событий
   - Связывает компоненты через события
   - Обеспечивает loose coupling

3. **Portfolio Manager** (`core/portfolio.py`)
   - Управление балансами
   - Отслеживание позиций
   - Расчет PnL

4. **Order Manager** (`core/order_manager.py`)
   - Размещение и мониторинг ордеров
   - Управление жизненным циклом ордеров
   - Автоматические SL/TP

5. **Risk Manager** (`risk/risk_manager.py`)
   - Контроль рисков
   - Лимиты на позиции
   - Контроль просадки

## 📈 Как работает бот

### 1. Анализ рынка

```python
# Основной цикл анализа (каждые 5 секунд)
1. Получение OHLCV данных с биржи
2. Расчет технических индикаторов (RSI, EMA, Bollinger Bands)
3. AI анализ через OpenAI API
4. Генерация торговых сигналов
```

### 2. Открытие позиций

```python
Условия входа:
- AI рекомендует BUY/SELL с уверенностью > 70%
- Технические индикаторы подтверждают сигнал
- Риск-менеджер одобряет размер позиции
- Достаточно свободного баланса

Процесс:
1. Расчет размера позиции (max 2% от депозита)
2. Проверка лимитов риска
3. Размещение ордера на бирже
4. Установка SL/TP (если настроено)
5. Отправка уведомления в Telegram
```

### 3. Управление позициями

```python
Мониторинг позиций:
- Обновление PnL в реальном времени
- Отслеживание условий выхода
- Проверка стоп-лоссов
- Трейлинг стоп (если включен)
```

### 4. Закрытие позиций

```python
Условия выхода:
- AI меняет рекомендацию на противоположную
- Достижение Take Profit
- Срабатывание Stop Loss
- Падение уверенности AI < 40%
- Ручное закрытие через API/Dashboard
```

## 🛠️ Установка и настройка

### 1. Клонирование и подготовка

```bash
# Клонирование репозитория
git clone <repository-url>
cd crypto_ai_trader

# Создание виртуального окружения
python -m venv venv

# Активация
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
# Копирование конфигурации
cp .env.example .env

# Редактирование .env
# Добавьте ваши API ключи (см. раздел выше)
```

### 3. Инициализация

```bash
# Запуск скрипта настройки
python scripts/setup_project.py

# Это создаст:
# - Необходимые директории
# - Базу данных
# - Конфигурационные файлы
```

## 🚦 Первый запуск

### 1. Тестирование подключений

```bash
# Проверка подключения к Bybit
python cli.py test-connection --exchange bybit

# Проверка подключения к Binance
python cli.py test-connection --exchange binance
```

### 2. Анализ рынка (без торговли)

```bash
# Простой анализ BTCUSDT
python cli.py analyze --symbol BTCUSDT --timeframe 5m

# AI анализ (mock режим)
python cli.py ai-analyze --symbol BTCUSDT --mock
```

### 3. Запуск бэктеста

```bash
# Тестирование стратегии на исторических данных
python -c "
import asyncio
from backtest.backtester import Backtester
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from utils.helpers import create_sample_data

async def run_backtest():
    backtester = Backtester()
    strategy = SimpleMomentumStrategy({'indicators': {}})
    data = {'BTCUSDT': create_sample_data('BTCUSDT', 100)}
    result = await backtester.run(strategy, data)
    print(f'Total return: {result.total_return_percent:.2f}%')
    print(f'Win rate: {result.win_rate:.1%}')
    
asyncio.run(run_backtest())
"
```

### 4. Запуск в demo режиме

```bash
# Только бот (без web интерфейса)
python main.py --mode bot

# Только API/Dashboard
python main.py --mode api

# Оба компонента
python main.py --mode both
```

## 📟 Команды CLI

```bash
# Базовые команды
python cli.py --help                     # Справка
python cli.py test-connection            # Тест подключения
python cli.py analyze                    # Анализ рынка
python cli.py ai-analyze                 # AI анализ
python cli.py run                        # Запуск движка

# С параметрами
python cli.py analyze --symbol ETHUSDT --timeframe 15m --limit 200
python cli.py ai-analyze --symbol BTCUSDT --mock  # Mock AI для тестов
```

## 🌐 API эндпоинты

### Основные эндпоинты

```bash
GET  /                      # Dashboard (HTML)
GET  /api/status           # Статус системы
GET  /api/portfolio        # Информация о портфеле
GET  /api/positions        # Открытые позиции
GET  /api/strategies       # Список стратегий
GET  /api/risk            # Метрики риска
GET  /api/performance     # Производительность

POST   /api/orders         # Создать ордер
DELETE /api/orders/{id}    # Отменить ордер
PUT    /api/strategies/{name}  # Обновить стратегию

WS   /ws                   # WebSocket для real-time обновлений
```

### Примеры запросов

```bash
# Получить статус
curl http://localhost:8000/api/status

# Получить позиции
curl http://localhost:8000/api/positions

# Разместить ордер
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "buy",
    "order_type": "market",
    "quantity": 0.001
  }'
```

## 🎯 Стратегии

### 1. Simple Momentum
- Основана на моментуме и технических индикаторах
- Использует RSI, EMA crossover, объем
- Подходит для трендовых рынков

### 2. AI Driven (требует OpenAI API)
- Полностью управляется искусственным интеллектом
- Анализирует новости, настроения, паттерны
- Адаптивная к рыночным условиям

### 3. Grid Strategy
- Торговля по сетке ордеров
- Подходит для бокового рынка
- Автоматическое управление уровнями

## ⚠️ Риск-менеджмент

### Лимиты по умолчанию:
- Максимальный размер позиции: 2% от депозита
- Максимальная дневная потеря: 5%
- Максимальная просадка: 15%
- Стоп-лосс по умолчанию: 2%
- Тейк-профит по умолчанию: 4%

### Защитные механизмы:
1. Автоматическая остановка при достижении лимитов
2. Проверка размера позиции перед открытием
3. Валидация ордеров
4. Мониторинг просадки в реальном времени

## 📊 Мониторинг

### 1. Web Dashboard
- Откройте http://localhost:8000
- Real-time обновления через WebSocket
- Управление стратегиями
- Просмотр позиций и метрик

### 2. Telegram Bot
- Отправьте /start боту
- Получайте уведомления о сделках
- Команды: /status, /balance, /positions

### 3. Логи
- Консольный вывод
- Файлы в директории `logs/`
- Уровни: DEBUG, INFO, WARNING, ERROR

## 🔧 Устранение проблем

### Частые проблемы:

1. **"Ошибка подключения к бирже"**
   - Проверьте API ключи в .env
   - Убедитесь что используете testnet
   - Проверьте интернет соединение

2. **"Недостаточно средств"**
   - Проверьте баланс на testnet
   - Получите тестовые средства на сайте биржи
   - Уменьшите размер позиции

3. **"AI анализ не работает"**
   - Проверьте OPENAI_API_KEY
   - Используйте --mock флаг для тестов
   - Проверьте лимиты OpenAI API

4. **"WebSocket disconnected"**
   - Нормальное поведение, переподключится автоматически
   - Проверьте файрвол/антивирус

### Диагностика:

```bash
# Проверка зависимостей
pip list

# Проверка базы данных
python -c "from data.storage.database import DatabaseManager; db = DatabaseManager()"

# Тест импортов
python -c "from core.engine import TradingEngine; print('OK')"

# Запуск тестов
pytest tests/ -v
```

## 📝 Следующие шаги

1. **Тестирование на testnet** - торгуйте без риска
2. **Настройка стратегий** - оптимизируйте параметры
3. **Бэктестинг** - проверьте на исторических данных
4. **Мониторинг** - следите за результатами
5. **Постепенный переход на mainnet** - когда будете уверены

## ⚡ Быстрые команды

```bash
# Полный цикл тестирования
source venv/bin/activate
python cli.py test-connection --exchange bybit
python cli.py analyze --symbol BTCUSDT
python cli.py ai-analyze --symbol BTCUSDT --mock
python main.py --mode both

# Откройте в браузере
# http://localhost:8000
```

## 🆘 Поддержка

- Проверьте логи в `logs/`
- Используйте `--debug` флаг для подробного вывода
- Создайте issue на GitHub при обнаружении багов
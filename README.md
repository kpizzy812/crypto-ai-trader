# 🤖 Crypto AI Trading Bot

## 📋 Phase 0 - Базовая структура проекта

Это базовая структура для AI торгового бота. 

### 🚀 Быстрый старт:

1. **Создайте остальные файлы** из артефактов Claude
2. **Настройте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate  # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте конфигурацию:**
   ```bash
   cp .env.example .env
   # Отредактируйте .env с вашими API ключами
   ```

5. **Тест CLI:**
   ```bash
   python cli.py --help
   ```

### 📁 Следующие файлы нужно создать:

Из артефакта "Phase 0 - Стартовый код":
- `core/exceptions.py`
- `core/engine.py`  
- `data/collectors/exchange_collector.py`
- `ai/mock_analyzer.py`
- `utils/logger.py`

Из артефакта "Дополнительные файлы":
- `data/processors/technical_processor.py`
- `trading/strategies/base_strategy.py`
- `trading/strategies/simple_momentum.py`
- `tests/test_basic.py`

### ⚠️ Важно:
- Используйте только testnet API ключи
- Никогда не давайте права на вывод средств
- Начинайте с малых сумм для тестирования

🎯 **Цель Phase 0:** Создать рабочую основу для дальнейшего развития AI торгового бота.
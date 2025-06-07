# tests/test_basic.py
import pytest
import asyncio
import pandas as pd
from config import Settings, TradingConfig
from data.collectors.exchange_collector import ExchangeDataCollector
from ai.mock_analyzer import MockAIAnalyzer
from data.processors.technical_processor import TechnicalProcessor
from trading.strategies.simple_momentum import SimpleMomentumStrategy


class TestBasicFunctionality:
    """Базовые тесты функциональности"""

    def test_settings_loading(self):
        """Тест загрузки настроек"""
        settings = Settings()
        assert settings.app_name == "Crypto AI Trader"
        assert isinstance(settings.bybit_testnet, bool)

    def test_trading_config(self):
        """Тест торговой конфигурации"""
        config = TradingConfig()
        assert len(config.trading_pairs) > 0
        assert config.primary_timeframe in config.timeframes
        assert config.risk.max_position_size_percent > 0

    @pytest.mark.asyncio
    async def test_mock_ai_analyzer(self):
        """Тест Mock AI анализатора"""
        analyzer = MockAIAnalyzer()

        # Создание тестовых данных
        test_data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104],
            'high': [101, 102, 103, 104, 105],
            'low': [99, 100, 101, 102, 103],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })

        analysis = await analyzer.analyze_market(test_data, "BTCUSDT")

        assert 'action' in analysis
        assert analysis['action'] in ['BUY', 'SELL', 'HOLD']
        assert 'confidence' in analysis
        assert 0 <= analysis['confidence'] <= 1
        assert 'reasoning' in analysis

    def test_technical_processor(self):
        """Тест процессора технических индикаторов"""
        processor = TechnicalProcessor()

        # Создание тестовых данных
        test_data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900]
        })

        # Тест RSI
        rsi = processor.calculate_rsi(test_data['close'])
        assert not rsi.empty
        assert all(0 <= x <= 100 for x in rsi.dropna())

        # Тест EMA
        ema = processor.calculate_ema(test_data['close'], 5)
        assert not ema.empty
        assert len(ema) == len(test_data)

        # Тест обработки OHLCV
        config = {
            'rsi': {'period': 5},
            'ema_fast': {'period': 3},
            'ema_slow': {'period': 5}
        }
        processed = processor.process_ohlcv(test_data, config)
        assert 'rsi' in processed.columns
        assert 'ema_fast' in processed.columns
        assert 'ema_slow' in processed.columns

    @pytest.mark.asyncio
    async def test_simple_momentum_strategy(self):
        """Тест простой моментум стратегии"""
        config = {
            'indicators': {
                'rsi': {'period': 5},
                'ema_fast': {'period': 3},
                'ema_slow': {'period': 5},
                'volume_sma': {'period': 5}
            }
        }

        strategy = SimpleMomentumStrategy(config)

        # Создание тестовых данных с трендом
        test_data = pd.DataFrame({
            'open': [100 + i for i in range(20)],
            'high': [101 + i for i in range(20)],
            'low': [99 + i for i in range(20)],
            'close': [100.5 + i for i in range(20)],
            'volume': [1000 + i * 50 for i in range(20)]
        })

        analysis = await strategy.analyze(test_data, "BTCUSDT")

        assert 'recommendation' in analysis
        assert analysis['recommendation'] in ['BUY', 'SELL', 'HOLD']
        assert 'confidence' in analysis
        assert 'momentum_score' in analysis
        assert -100 <= analysis['momentum_score'] <= 100
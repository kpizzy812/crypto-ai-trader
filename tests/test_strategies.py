# СОЗДАНИЕ: tests/test_strategies.py
"""
Тесты торговых стратегий
"""
import pytest
import pandas as pd
import numpy as np
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from utils.helpers import create_sample_data


class TestSimpleMomentumStrategy:
    """Тесты простой моментум стратегии"""

    @pytest.fixture
    def strategy(self):
        config = {
            'indicators': {
                'rsi': {'period': 14},
                'ema_fast': {'period': 9},
                'ema_slow': {'period': 21},
                'volume_sma': {'period': 20}
            }
        }
        return SimpleMomentumStrategy(config)

    @pytest.fixture
    def uptrend_data(self):
        """Данные с восходящим трендом"""
        return create_sample_data("BTCUSDT", periods=50, start_price=45000)

    @pytest.fixture
    def downtrend_data(self):
        """Данные с нисходящим трендом"""
        data = create_sample_data("BTCUSDT", periods=50, start_price=45000)
        # Инвертируем тренд
        data['close'] = data['close'].iloc[::-1].values
        data['open'] = data['open'].iloc[::-1].values
        return data

    @pytest.mark.asyncio
    async def test_analyze_uptrend(self, strategy, uptrend_data):
        """Тест анализа восходящего тренда"""
        analysis = await strategy.analyze(uptrend_data, "BTCUSDT")

        assert 'momentum_score' in analysis
        assert 'recommendation' in analysis
        assert analysis['symbol'] == "BTCUSDT"
        assert analysis['strategy'] == "SimpleMomentum"

    @pytest.mark.asyncio
    async def test_should_enter_conditions(self, strategy, uptrend_data):
        """Тест условий входа"""
        analysis = await strategy.analyze(uptrend_data, "BTCUSDT")

        # Принудительно устанавливаем высокую уверенность
        analysis['confidence'] = 0.8
        analysis['recommendation'] = 'BUY'

        should_enter = await strategy.should_enter(analysis)
        assert should_enter == True

    @pytest.mark.asyncio
    async def test_should_exit_conditions(self, strategy):
        """Тест условий выхода"""
        analysis = {'recommendation': 'SELL'}
        position = {'side': 'BUY'}

        should_exit = await strategy.should_exit(analysis, position)
        assert should_exit == True

    def test_momentum_score_calculation(self, strategy, uptrend_data):
        """Тест расчета моментум скора"""
        # Добавляем технические индикаторы
        processed_data = strategy.processor.process_ohlcv(
            uptrend_data,
            strategy.config['indicators']
        )

        score = strategy._calculate_momentum_score(processed_data)
        assert -100 <= score <= 100
        assert isinstance(score, float)
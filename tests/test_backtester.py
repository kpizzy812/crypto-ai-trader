# СОЗДАНИЕ: tests/test_backtester.py
"""
Тесты системы бэктестинга
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from backtest.backtester import Backtester, BacktestTrade
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from utils.helpers import create_sample_data


class TestBacktester:
    """Тесты бэктестера"""

    @pytest.fixture
    def backtester(self):
        return Backtester(initial_capital=10000, commission=0.001)

    @pytest.fixture
    def strategy(self):
        config = {
            'indicators': {
                'rsi': {'period': 14},
                'ema_fast': {'period': 9},
                'ema_slow': {'period': 21}
            },
            'position_size_percent': 10
        }
        return SimpleMomentumStrategy(config)

    @pytest.fixture
    def test_data(self):
        """Тестовые данные для бэктеста"""
        return {
            'BTCUSDT': create_sample_data("BTCUSDT", periods=100, start_price=45000)
        }

    @pytest.mark.asyncio
    async def test_backtest_run(self, backtester, strategy, test_data):
        """Тест запуска бэктеста"""
        result = await backtester.run(strategy, test_data)

        assert result is not None
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'win_rate')
        assert hasattr(result, 'total_trades')
        assert len(result.equity_curve) > 0

    def test_commission_calculation(self, backtester):
        """Тест расчета комиссии"""
        commission = backtester._calculate_commission(100.0, 0.1)
        expected = 100.0 * 0.1 * 0.001  # price * quantity * commission_rate
        assert commission == expected

    def test_position_size_calculation(self, backtester):
        """Тест расчета размера позиции"""
        size = backtester._calculate_position_size(10000, 10)  # 10% от 10000
        assert size == 1000

    def test_execution_price_calculation(self, backtester):
        """Тест расчета цены исполнения"""
        candle = pd.Series({'close': 100.0})

        buy_price = backtester._get_execution_price(candle, 'buy')
        sell_price = backtester._get_execution_price(candle, 'sell')

        # При покупке цена должна быть выше (проскальзывание)
        assert buy_price > 100.0
        # При продаже цена должна быть ниже
        assert sell_price < 100.0

    def test_backtest_trade_close(self):
        """Тест закрытия сделки в бэктесте"""
        trade = BacktestTrade(
            timestamp=datetime.utcnow(),
            symbol='BTCUSDT',
            side='buy',
            entry_price=100.0,
            quantity=1.0
        )

        trade.close(110.0, datetime.utcnow(), 0.1)

        assert trade.exit_price == 110.0
        assert trade.pnl == 9.9  # (110 - 100) * 1 - 0.1
        assert trade.pnl_percent == 9.9  # 9.9 / 100
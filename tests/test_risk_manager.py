# СОЗДАНИЕ: tests/test_risk_manager.py
"""
Тесты риск-менеджера
"""
import pytest
from decimal import Decimal
from core.portfolio import Portfolio
from risk.risk_manager import RiskManager
from config.trading_config import RiskConfig


class TestRiskManager:
    """Тесты риск-менеджера"""

    @pytest.fixture
    def portfolio(self):
        return Portfolio(Decimal("10000"))

    @pytest.fixture
    def risk_config(self):
        return RiskConfig()

    @pytest.fixture
    def risk_manager(self, risk_config, portfolio):
        return RiskManager(risk_config, portfolio)

    @pytest.mark.asyncio
    async def test_position_risk_check_valid(self, risk_manager):
        """Тест проверки риска позиции - валидная позиция"""
        result = await risk_manager.check_position_risk(
            symbol="BTCUSDT",
            side="buy",
            entry_price=Decimal("45000"),
            quantity=Decimal("0.004")  # ~$180 при цене $45000 (1.8% от $10000)
        )

        assert result == True

    @pytest.mark.asyncio
    async def test_position_risk_check_too_large(self, risk_manager):
        """Тест проверки риска - слишком большая позиция"""
        result = await risk_manager.check_position_risk(
            symbol="BTCUSDT",
            side="buy",
            entry_price=Decimal("45000"),
            quantity=Decimal("0.1")  # $4500 (45% от $10000)
        )

        assert result == False

    @pytest.mark.asyncio
    async def test_position_size_calculation(self, risk_manager):
        """Тест расчета размера позиции"""
        size = await risk_manager.calculate_position_size(
            balance=Decimal("10000"),
            risk_amount=Decimal("100"),
            stop_distance=Decimal("50")
        )

        assert size == Decimal("2")  # 100 / 50

    @pytest.mark.asyncio
    async def test_risk_metrics_calculation(self, risk_manager):
        """Тест расчета метрик риска"""
        metrics = await risk_manager.get_risk_metrics()

        assert hasattr(metrics, 'current_drawdown')
        assert hasattr(metrics, 'daily_loss')
        assert hasattr(metrics, 'position_risk')
        assert hasattr(metrics, 'risk_score')
        assert 0 <= metrics.risk_score <= 100
# risk/metrics.py
"""
Модели метрик риска и производительности
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta


@dataclass
class RiskMetrics:
    """Метрики риска"""
    current_drawdown: Decimal
    max_drawdown: Decimal
    daily_loss: Decimal
    position_risk: Decimal
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    value_at_risk: Decimal  # VaR 95%
    risk_score: int  # 0-100


@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    total_return: float
    annualized_return: float
    volatility: float
    max_consecutive_losses: int
    win_rate: float
    profit_factor: float
    average_trade_duration: timedelta


@dataclass
class RiskLimits:
    """Лимиты риска"""
    max_position_size_percent: float
    max_daily_loss_percent: float
    max_drawdown_percent: float
    max_correlation_positions: int = 3
    emergency_stop_threshold: int = 90  # risk_score


@dataclass
class PortfolioSnapshot:
    """Снимок портфеля для анализа"""
    timestamp: str
    total_value: float
    available_balance: float
    positions_count: int
    daily_pnl: float
    total_pnl: float
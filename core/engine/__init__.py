# core/engine/__init__.py
"""
Модульная структура торгового движка
"""
from .trading_engine import TradingEngine
from .market_analyzer import MarketAnalyzer
from .signal_processor import SignalProcessor
from .position_manager import PositionManager

__all__ = [
    'TradingEngine',
    'MarketAnalyzer',
    'SignalProcessor',
    'PositionManager'
]
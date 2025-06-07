# core/exceptions.py
class TradingError(Exception):
    """Базовая ошибка торговой системы"""
    pass

class ExchangeError(TradingError):
    """Ошибка подключения к бирже"""
    pass

class RiskError(TradingError):
    """Ошибка превышения рисков"""
    pass

class AIAnalysisError(TradingError):
    """Ошибка AI анализа"""
    pass

class DataError(TradingError):
    """Ошибка получения данных"""
    pass
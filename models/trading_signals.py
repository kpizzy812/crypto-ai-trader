# models/trading_signals.py
"""
Улучшенные модели данных для торговых сигналов
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TechnicalValidation(BaseModel):
    """Техническая валидация сигнала"""
    score: float = Field(ge=0, le=1, description="Скор валидации 0-1")
    confirmations: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    indicators_checked: List[str] = Field(default_factory=list)


class AIAnalysisResult(BaseModel):
    """Результат AI анализа"""
    symbol: str
    action: SignalType
    confidence: float = Field(ge=0, le=1)
    reasoning: str

    # Дополнительные поля
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    time_horizon: str = "short"

    # Техническая валидация
    technical_validation: Optional[TechnicalValidation] = None
    adjusted_confidence: Optional[float] = None
    risk_score: Optional[float] = None

    # Метаданные
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "ai_analyzer"

    @validator('adjusted_confidence')
    def validate_adjusted_confidence(cls, v):
        if v is not None and not (0 <= v <= 1):
            raise ValueError('adjusted_confidence must be between 0 and 1')
        return v


class TradingSignal(BaseModel):
    """Торговый сигнал для внутренней обработки"""
    symbol: str
    action: SignalType
    quantity: Decimal = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    priority: int = Field(ge=1, le=10)

    # Источник сигнала
    strategy: str
    source: str = "signal_processor"

    # Параметры риска
    risk_score: float = Field(ge=0, le=1)
    position_size_usd: Decimal = Field(gt=0)

    # Обоснование
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Временные метки
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @validator('priority')
    def validate_priority(cls, v):
        if not 1 <= v <= 10:
            raise ValueError('Priority must be between 1 and 10')
        return v


class MarketState(BaseModel):
    """Состояние рынка для принятия решений"""
    symbol: str
    current_price: Decimal
    volume_24h: Decimal
    price_change_24h: float

    # Технические индикаторы
    rsi: Optional[float] = None
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None

    # Волатильность
    volatility_1h: Optional[float] = None
    volatility_24h: Optional[float] = None

    # Уровни поддержки/сопротивления
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)

    # Временная метка
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PositionEntry(BaseModel):
    """Вход в позицию"""
    symbol: str
    side: str  # long/short
    entry_price: Decimal
    quantity: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None

    # Связанные данные
    signal_id: Optional[str] = None
    strategy: str
    reasoning: str

    # Риск параметры
    risk_amount: Decimal  # Максимальная потеря в USD
    risk_percent: float  # % от депозита

    # Временные параметры
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    planned_duration: Optional[str] = None  # "short", "medium", "long"


# Исправление для Event Bus - стандартизация данных
class EventData(BaseModel):
    """Базовая модель для данных событий"""

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class SignalEventData(EventData):
    """Данные события торгового сигнала"""
    signal: TradingSignal
    market_state: Optional[MarketState] = None


class AnalysisEventData(EventData):
    """Данные события завершения анализа"""
    symbol: str
    analysis: AIAnalysisResult
    technical_data: Dict[str, Any] = Field(default_factory=dict)


# Вспомогательные функции
def create_signal_from_analysis(
        analysis: AIAnalysisResult,
        quantity: Decimal,
        strategy: str = "ai_driven"
) -> TradingSignal:
    """Создание торгового сигнала из AI анализа"""

    return TradingSignal(
        symbol=analysis.symbol,
        action=analysis.action,
        quantity=quantity,
        confidence=analysis.adjusted_confidence or analysis.confidence,
        priority=_calculate_priority(analysis),
        strategy=strategy,
        risk_score=analysis.risk_score or 0.5,
        position_size_usd=Decimal(str(quantity)) * (analysis.entry_price or Decimal("0")),
        reasoning=analysis.reasoning,
        metadata={
            "ai_confidence": analysis.confidence,
            "technical_score": analysis.technical_validation.score if analysis.technical_validation else 0,
            "risk_level": analysis.risk_level.value,
            "time_horizon": analysis.time_horizon
        }
    )


def _calculate_priority(analysis: AIAnalysisResult) -> int:
    """Расчет приоритета сигнала"""
    base_priority = 5

    # Корректировка на уверенность
    confidence_bonus = int((analysis.adjusted_confidence or analysis.confidence) * 3)

    # Корректировка на риск
    risk_penalty = int((analysis.risk_score or 0.5) * 2)

    priority = base_priority + confidence_bonus - risk_penalty
    return max(1, min(10, priority))


# Валидация данных перед отправкой в Event Bus
def validate_analysis_event_data(analysis_data: Dict[str, Any]) -> AnalysisEventData:
    """Валидация данных события анализа"""
    try:
        # Преобразуем анализ в стандартную модель
        analysis = AIAnalysisResult(**analysis_data.get('analysis', {}))

        return AnalysisEventData(
            symbol=analysis_data['symbol'],
            analysis=analysis,
            technical_data=analysis_data.get('technical_data', {})
        )
    except Exception as e:
        # Если валидация не прошла, создаем минимальную модель
        return AnalysisEventData(
            symbol=analysis_data.get('symbol', 'UNKNOWN'),
            analysis=AIAnalysisResult(
                symbol=analysis_data.get('symbol', 'UNKNOWN'),
                action=SignalType.HOLD,
                confidence=0.0,
                reasoning=f"Ошибка валидации: {str(e)}"
            )
        )
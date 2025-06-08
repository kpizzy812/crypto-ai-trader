# backtest/backtester.py
"""
Система бэктестинга стратегий
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from loguru import logger
import asyncio
from collections import defaultdict


@dataclass
class BacktestTrade:
    """Сделка в бэктесте"""
    timestamp: datetime
    symbol: str
    side: str  # 'buy' или 'sell'
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float = 0
    exit_timestamp: Optional[datetime] = None
    pnl: float = 0
    pnl_percent: float = 0
    commission: float = 0
    metadata: Dict = field(default_factory=dict)

    def close(self, exit_price: float, exit_timestamp: datetime, commission: float = 0):
        """Закрытие сделки"""
        self.exit_price = exit_price
        self.exit_timestamp = exit_timestamp
        self.commission += commission

        # Расчет PnL
        if self.side == 'buy':
            self.pnl = (exit_price - self.entry_price) * self.quantity - self.commission
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity - self.commission

        self.pnl_percent = (self.pnl / (self.entry_price * self.quantity)) * 100


@dataclass
class BacktestResult:
    """Результаты бэктеста"""
    # Основные метрики
    total_return: float
    total_return_percent: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_percent: float
    win_rate: float
    profit_factor: float

    # Статистика по сделкам
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float

    # Временные метрики
    avg_trade_duration: timedelta
    longest_trade_duration: timedelta
    shortest_trade_duration: timedelta

    # Дополнительные данные
    equity_curve: pd.Series
    trades: List[BacktestTrade]
    monthly_returns: pd.Series
    daily_returns: pd.Series


class Backtester:
    """Движок для бэктестинга стратегий"""

    def __init__(self, initial_capital: float = 10000.0,
                 commission: float = 0.001,  # 0.1%
                 slippage: float = 0.0005):  # 0.05%
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    async def run(self, strategy: Any, data: Dict[str, pd.DataFrame],
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None) -> BacktestResult:
        """Запуск бэктеста стратегии"""

        logger.info(f"Запуск бэктеста стратегии {strategy.name}")

        # Подготовка данных
        prepared_data = self._prepare_data(data, start_date, end_date)

        # Инициализация
        capital = self.initial_capital
        positions: Dict[str, BacktestTrade] = {}
        completed_trades: List[BacktestTrade] = []
        equity_curve = []
        timestamps = []

        # Основной цикл бэктеста
        for timestamp, market_snapshot in prepared_data:
            # Обновление equity
            current_equity = self._calculate_equity(
                capital, positions, market_snapshot
            )
            equity_curve.append(current_equity)
            timestamps.append(timestamp)

            # Анализ для каждого символа
            for symbol, ohlcv in market_snapshot.items():
                # Получение сигналов от стратегии
                analysis = await strategy.analyze(ohlcv, symbol)

                # Обработка существующих позиций
                if symbol in positions:
                    position = positions[symbol]

                    # Проверка условий выхода
                    if await strategy.should_exit(analysis, {
                        'side': position.side,
                        'opened_at': position.timestamp,
                        'entry_price': position.entry_price
                    }):
                        # Закрытие позиции
                        exit_price = self._get_execution_price(
                            ohlcv.iloc[-1],
                            'sell' if position.side == 'buy' else 'buy'
                        )

                        position.close(
                            exit_price,
                            timestamp,
                            self._calculate_commission(exit_price, position.quantity)
                        )

                        capital += position.pnl
                        completed_trades.append(position)
                        del positions[symbol]

                        logger.debug(f"Закрыта позиция {symbol}: PnL = {position.pnl:.2f}")

                # Проверка условий входа
                elif await strategy.should_enter(analysis):
                    if capital > 0:
                        # Расчет размера позиции
                        position_size = self._calculate_position_size(
                            capital,
                            strategy.config.get('position_size_percent', 10)
                        )

                        # Открытие позиции
                        entry_price = self._get_execution_price(
                            ohlcv.iloc[-1],
                            analysis['action'].lower()
                        )

                        quantity = position_size / entry_price
                        commission = self._calculate_commission(entry_price, quantity)

                        if position_size + commission <= capital:
                            position = BacktestTrade(
                                timestamp=timestamp,
                                symbol=symbol,
                                side=analysis['action'].lower(),
                                entry_price=entry_price,
                                quantity=quantity,
                                commission=commission,
                                metadata={'analysis': analysis}
                            )

                            positions[symbol] = position
                            capital -= (position_size + commission)

                            logger.debug(f"Открыта позиция {symbol}: {position.side} @ {entry_price}")

        # Закрытие всех открытых позиций в конце
        for symbol, position in positions.items():
            last_data = prepared_data[-1][1][symbol]
            exit_price = last_data.iloc[-1]['close']

            position.close(
                exit_price,
                timestamps[-1],
                self._calculate_commission(exit_price, position.quantity)
            )

            completed_trades.append(position)

        # Расчет результатов
        return self._calculate_results(
            completed_trades,
            pd.Series(equity_curve, index=timestamps),
            self.initial_capital
        )

    def _prepare_data(self, data: Dict[str, pd.DataFrame],
                      start_date: Optional[datetime],
                      end_date: Optional[datetime]) -> List[Tuple[datetime, Dict[str, pd.DataFrame]]]:
        """Подготовка данных для бэктеста"""

        # Объединение всех временных меток
        all_timestamps = set()
        for symbol_data in data.values():
            all_timestamps.update(symbol_data.index)

        all_timestamps = sorted(all_timestamps)

        # Фильтрация по датам
        if start_date:
            all_timestamps = [ts for ts in all_timestamps if ts >= start_date]
        if end_date:
            all_timestamps = [ts for ts in all_timestamps if ts <= end_date]

        # Создание снимков рынка для каждой временной метки
        market_snapshots = []

        for timestamp in all_timestamps:
            snapshot = {}

            for symbol, symbol_data in data.items():
                # Получаем данные до текущего момента
                historical = symbol_data[symbol_data.index <= timestamp]
                if not historical.empty:
                    snapshot[symbol] = historical

            if snapshot:
                market_snapshots.append((timestamp, snapshot))

        return market_snapshots

    def _get_execution_price(self, candle: pd.Series, side: str) -> float:
        """Получение цены исполнения с учетом проскальзывания"""

        base_price = candle['close']

        if side == 'buy':
            # При покупке платим немного больше
            return base_price * (1 + self.slippage)
        else:
            # При продаже получаем немного меньше
            return base_price * (1 - self.slippage)

    def _calculate_commission(self, price: float, quantity: float) -> float:
        """Расчет комиссии"""
        return price * quantity * self.commission

    def _calculate_position_size(self, capital: float, percent: float) -> float:
        """Расчет размера позиции"""
        return capital * (percent / 100)

    def _calculate_equity(self, cash: float, positions: Dict[str, BacktestTrade],
                          market_snapshot: Dict[str, pd.DataFrame]) -> float:
        """Расчет текущего капитала"""

        equity = cash

        for symbol, position in positions.items():
            if symbol in market_snapshot:
                current_price = market_snapshot[symbol].iloc[-1]['close']

                if position.side == 'buy':
                    unrealized_pnl = (current_price - position.entry_price) * position.quantity
                else:
                    unrealized_pnl = (position.entry_price - current_price) * position.quantity

                equity += (position.entry_price * position.quantity + unrealized_pnl)

        return equity

    def _calculate_results(self, trades: List[BacktestTrade],
                           equity_curve: pd.Series,
                           initial_capital: float) -> BacktestResult:
        """Расчет результатов бэктеста"""

        if not trades:
            return self._empty_results(equity_curve, initial_capital)

        # Базовые метрики
        final_equity = equity_curve.iloc[-1]
        total_return = final_equity - initial_capital
        total_return_percent = (total_return / initial_capital) * 100

        # Статистика по сделкам
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

        # Drawdown
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_drawdown_percent = drawdown.min() * 100
        max_drawdown = (equity_curve - rolling_max).min()

        # Sharpe ratio
        daily_returns = equity_curve.pct_change().dropna()
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)

        # Длительность сделок
        trade_durations = [
            t.exit_timestamp - t.timestamp
            for t in trades
            if t.exit_timestamp
        ]

        avg_duration = (
            sum(trade_durations, timedelta()) / len(trade_durations)
            if trade_durations else timedelta()
        )

        # Месячные и дневные доходности
        monthly_returns = equity_curve.resample('M').last().pct_change().dropna()

        return BacktestResult(
            total_return=total_return,
            total_return_percent=total_return_percent,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=max(t.pnl for t in trades) if trades else 0,
            worst_trade=min(t.pnl for t in trades) if trades else 0,
            avg_trade_duration=avg_duration,
            longest_trade_duration=max(trade_durations) if trade_durations else timedelta(),
            shortest_trade_duration=min(trade_durations) if trade_durations else timedelta(),
            equity_curve=equity_curve,
            trades=trades,
            monthly_returns=monthly_returns,
            daily_returns=daily_returns
        )

    def _calculate_sharpe_ratio(self, returns: pd.Series,
                                risk_free_rate: float = 0.02) -> float:
        """Расчет коэффициента Шарпа"""

        if len(returns) < 2:
            return 0.0

        # Годовая доходность и волатильность
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)

        if annual_vol == 0:
            return 0.0

        return (annual_return - risk_free_rate) / annual_vol

    def _empty_results(self, equity_curve: pd.Series,
                       initial_capital: float) -> BacktestResult:
        """Пустые результаты при отсутствии сделок"""

        return BacktestResult(
            total_return=0,
            total_return_percent=0,
            sharpe_ratio=0,
            max_drawdown=0,
            max_drawdown_percent=0,
            win_rate=0,
            profit_factor=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0,
            avg_loss=0,
            best_trade=0,
            worst_trade=0,
            avg_trade_duration=timedelta(),
            longest_trade_duration=timedelta(),
            shortest_trade_duration=timedelta(),
            equity_curve=equity_curve,
            trades=[],
            monthly_returns=pd.Series(),
            daily_returns=pd.Series()
        )
        neutral
        '

        # Простое определение по направлению цены
        start_price = data['close'].iloc[0]
        end_price = data['close'].iloc[-1]
        change_percent = (end_price - start_price) / start_price * 100

        if change_percent > 2:
            return 'strong_uptrend'
        elif change_percent > 0.5:
            return 'uptrend'
        elif change_percent < -2:
            return 'strong_downtrend'
        elif change_percent < -0.5:
            return 'downtrend'
        else:
            return 'sideways'

    def _find_support_resistance(self, data: pd.DataFrame) -> Dict:
        """Поиск уровней поддержки и сопротивления"""

        # Простой метод: локальные минимумы и максимумы
        highs = data['high'].rolling(window=10).max()
        lows = data['low'].rolling(window=10).min()

        current_price = float(data['close'].iloc[-1])

        # Ближайшие уровни
        resistance_levels = highs[highs > current_price].dropna().unique()[-3:] if len(
            highs[highs > current_price]) > 0 else []
        support_levels = lows[lows < current_price].dropna().unique()[:3] if len(lows[lows < current_price]) > 0 else []

        return {
            'nearest_resistance': float(resistance_levels[0]) if len(resistance_levels) > 0 else None,
            'nearest_support': float(support_levels[-1]) if len(support_levels) > 0 else None,
            'resistance_levels': [float(x) for x in resistance_levels],
            'support_levels': [float(x) for x in support_levels]
        }

    async def _enhance_analysis(self, ai_analysis: Dict,
                                technical_data: pd.DataFrame) -> Dict:
        """Улучшение и валидация AI анализа"""

        enhanced = ai_analysis.copy()

        # Добавление дополнительных метрик
        enhanced['technical_validation'] = self._validate_with_technicals(
            ai_analysis,
            technical_data
        )

        # Корректировка уверенности на основе валидации
        validation_score = enhanced['technical_validation']['score']
        original_confidence = enhanced.get('confidence', 0.5)

        # Взвешенная уверенность
        enhanced['adjusted_confidence'] = (
                original_confidence * 0.7 + validation_score * 0.3
        )

        # Добавление риск-скора
        enhanced['risk_score'] = self._calculate_risk_score(
            technical_data,
            enhanced
        )

        # Таймфрейм для позиции
        if 'time_horizon' not in enhanced:
            enhanced['time_horizon'] = self._determine_time_horizon(
                technical_data,
                enhanced
            )

        return enhanced

    def _validate_with_technicals(self, ai_analysis: Dict,
                                  data: pd.DataFrame) -> Dict:
        """Валидация AI анализа техническими индикаторами"""

        validation = {
            'score': 0.5,
            'confirmations': [],
            'conflicts': []
        }

        if len(data) < 20:
            return validation

        current = data.iloc[-1]
        ai_action = ai_analysis.get('action', 'HOLD')

        # Проверка RSI
        if 'rsi' in current:
            rsi_signal = 'BUY' if current['rsi'] < 30 else 'SELL' if current['rsi'] > 70 else 'NEUTRAL'
            if rsi_signal == ai_action:
                validation['confirmations'].append('RSI подтверждает сигнал')
                validation['score'] += 0.1
            elif rsi_signal != 'NEUTRAL' and rsi_signal != ai_action:
                validation['conflicts'].append('RSI противоречит сигналу')
                validation['score'] -= 0.1

        # Проверка EMA кроссовера
        if 'ema_fast' in current and 'ema_slow' in current:
            ema_signal = 'BUY' if current['ema_fast'] > current['ema_slow'] else 'SELL'
            if ema_signal == ai_action:
                validation['confirmations'].append('EMA кроссовер подтверждает')
                validation['score'] += 0.15
            else:
                validation['conflicts'].append('EMA кроссовер противоречит')
                validation['score'] -= 0.15

        # Ограничение score в диапазоне [0, 1]
        validation['score'] = max(0, min(1, validation['score']))

        return validation

    def _calculate_risk_score(self, data: pd.DataFrame,
                              analysis: Dict) -> float:
        """Расчет риск-скора позиции"""

        risk_score = 0.5  # Базовый риск

        # Волатильность
        if len(data) >= 20:
            volatility = data['close'].pct_change().tail(20).std()
            if volatility > 0.05:  # Высокая волатильность
                risk_score += 0.2
            elif volatility < 0.01:  # Низкая волатильность
                risk_score -= 0.1

        # Расстояние до уровней
        if 'stop_loss' in analysis and 'entry_price' in analysis:
            sl_distance = abs(analysis['entry_price'] - analysis['stop_loss']) / analysis['entry_price']
            if sl_distance > 0.05:  # Далекий стоп
                risk_score += 0.15

        # Уверенность AI
        confidence = analysis.get('adjusted_confidence', 0.5)
        if confidence < 0.6:
            risk_score += 0.2
        elif confidence > 0.8:
            risk_score -= 0.1

        return max(0, min(1, risk_score))

    def _determine_time_horizon(self, data: pd.DataFrame, analysis: Dict) -> str:
        """Определение временного горизонта позиции"""

        # На основе волатильности и тренда
        if len(data) >= 50:
            short_trend = self._determine_trend(data.tail(20))
            medium_trend = self._determine_trend(data.tail(50))

            if 'strong' in short_trend and 'strong' in medium_trend:
                return 'medium'  # Сильный тренд - держим дольше
            elif short_trend != medium_trend:
                return 'short'  # Противоречивые сигналы - краткосрочно

        return 'short'  # По умолчанию краткосрочная
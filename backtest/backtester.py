# backtest/backtester.py - ПОЛНАЯ ВЕРСИЯ
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

    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ИЗ ВАШЕГО ОРИГИНАЛЬНОГО КОДА:

    async def run_multiple_strategies(self, strategies: List[Any],
                                      data: Dict[str, pd.DataFrame],
                                      start_date: Optional[datetime] = None,
                                      end_date: Optional[datetime] = None) -> Dict[str, BacktestResult]:
        """Запуск бэктеста для нескольких стратегий"""

        results = {}

        for strategy in strategies:
            logger.info(f"Бэктест стратегии: {strategy.name}")
            try:
                result = await self.run(strategy, data, start_date, end_date)
                results[strategy.name] = result

                logger.info(
                    f"Стратегия {strategy.name}: "
                    f"Доходность {result.total_return_percent:.2f}%, "
                    f"Винрейт {result.win_rate:.1%}, "
                    f"Сделок {result.total_trades}"
                )

            except Exception as e:
                logger.error(f"Ошибка бэктеста стратегии {strategy.name}: {e}")
                results[strategy.name] = None

        return results

    def compare_strategies(self, results: Dict[str, BacktestResult]) -> pd.DataFrame:
        """Сравнение результатов стратегий"""

        comparison_data = []

        for strategy_name, result in results.items():
            if result is None:
                continue

            comparison_data.append({
                'Strategy': strategy_name,
                'Total Return %': result.total_return_percent,
                'Sharpe Ratio': result.sharpe_ratio,
                'Max Drawdown %': result.max_drawdown_percent,
                'Win Rate %': result.win_rate * 100,
                'Profit Factor': result.profit_factor,
                'Total Trades': result.total_trades,
                'Avg Trade Duration': str(result.avg_trade_duration),
                'Best Trade': result.best_trade,
                'Worst Trade': result.worst_trade
            })

        return pd.DataFrame(comparison_data)

    def generate_report(self, result: BacktestResult, strategy_name: str) -> str:
        """Генерация текстового отчета"""

        report = f"""
=== ОТЧЕТ ПО БЭКТЕСТУ ===
Стратегия: {strategy_name}

ОБЩИЕ РЕЗУЛЬТАТЫ:
- Общая доходность: {result.total_return:.2f} USD ({result.total_return_percent:.2f}%)
- Коэффициент Шарпа: {result.sharpe_ratio:.3f}
- Максимальная просадка: {result.max_drawdown:.2f} USD ({result.max_drawdown_percent:.2f}%)

СТАТИСТИКА СДЕЛОК:
- Всего сделок: {result.total_trades}
- Прибыльных: {result.winning_trades} ({result.win_rate:.1%})
- Убыточных: {result.losing_trades}
- Profit Factor: {result.profit_factor:.3f}

СРЕДНИЕ ПОКАЗАТЕЛИ:
- Средняя прибыльная сделка: {result.avg_win:.2f} USD
- Средняя убыточная сделка: {result.avg_loss:.2f} USD
- Лучшая сделка: {result.best_trade:.2f} USD
- Худшая сделка: {result.worst_trade:.2f} USD

ВРЕМЕННЫЕ ХАРАКТЕРИСТИКИ:
- Средняя длительность сделки: {result.avg_trade_duration}
- Самая длинная сделка: {result.longest_trade_duration}
- Самая короткая сделка: {result.shortest_trade_duration}
"""
        return report

    def save_results(self, result: BacktestResult, strategy_name: str,
                     output_dir: str = "backtest_results"):
        """Сохранение результатов бэктеста"""
        import os
        import json
        from datetime import datetime

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Сохранение основных метрик
        metrics = {
            'strategy': strategy_name,
            'timestamp': timestamp,
            'total_return': result.total_return,
            'total_return_percent': result.total_return_percent,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'max_drawdown_percent': result.max_drawdown_percent,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'best_trade': result.best_trade,
            'worst_trade': result.worst_trade
        }

        with open(f"{output_dir}/{strategy_name}_{timestamp}_metrics.json", 'w') as f:
            json.dump(metrics, f, indent=2)

        # Сохранение equity curve
        result.equity_curve.to_csv(f"{output_dir}/{strategy_name}_{timestamp}_equity.csv")

        # Сохранение списка сделок
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                'timestamp': trade.timestamp.isoformat(),
                'symbol': trade.symbol,
                'side': trade.side,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'pnl': trade.pnl,
                'pnl_percent': trade.pnl_percent,
                'commission': trade.commission,
                'exit_timestamp': trade.exit_timestamp.isoformat() if trade.exit_timestamp else None
            })

        trades_df = pd.DataFrame(trades_data)
        trades_df.to_csv(f"{output_dir}/{strategy_name}_{timestamp}_trades.csv", index=False)

        # Сохранение текстового отчета
        report = self.generate_report(result, strategy_name)
        with open(f"{output_dir}/{strategy_name}_{timestamp}_report.txt", 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Результаты бэктеста сохранены в {output_dir}")

    def plot_results(self, result: BacktestResult, strategy_name: str, save_path: str = None):
        """Построение графиков результатов"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'Результаты бэктеста: {strategy_name}', fontsize=16)

            # 1. Equity Curve
            axes[0, 0].plot(result.equity_curve.index, result.equity_curve.values)
            axes[0, 0].set_title('Equity Curve')
            axes[0, 0].set_ylabel('Капитал ($)')
            axes[0, 0].grid(True)

            # 2. Drawdown
            rolling_max = result.equity_curve.expanding().max()
            drawdown = (result.equity_curve - rolling_max) / rolling_max * 100
            axes[0, 1].fill_between(drawdown.index, drawdown.values, 0, color='red', alpha=0.3)
            axes[0, 1].set_title('Drawdown (%)')
            axes[0, 1].set_ylabel('Drawdown (%)')
            axes[0, 1].grid(True)

            # 3. Monthly Returns
            if not result.monthly_returns.empty:
                monthly_ret_pct = result.monthly_returns * 100
                colors = ['green' if x > 0 else 'red' for x in monthly_ret_pct]
                axes[1, 0].bar(monthly_ret_pct.index, monthly_ret_pct.values, color=colors, alpha=0.7)
                axes[1, 0].set_title('Месячная доходность (%)')
                axes[1, 0].set_ylabel('Доходность (%)')
                axes[1, 0].grid(True)

            # 4. Trade PnL Distribution
            if result.trades:
                pnl_values = [t.pnl for t in result.trades]
                axes[1, 1].hist(pnl_values, bins=20, alpha=0.7, color='blue')
                axes[1, 1].axvline(x=0, color='red', linestyle='--')
                axes[1, 1].set_title('Распределение PnL сделок')
                axes[1, 1].set_xlabel('PnL ($)')
                axes[1, 1].set_ylabel('Количество сделок')
                axes[1, 1].grid(True)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"График сохранен: {save_path}")
            else:
                plt.show()

        except ImportError:
            logger.warning("Matplotlib не установлен. Графики недоступны.")
        except Exception as e:
            logger.error(f"Ошибка построения графиков: {e}")

    # МЕТОДЫ ИЗ ОБРЕЗАННОЙ ЧАСТИ:

    def _determine_trend(self, data: pd.DataFrame) -> str:
        """Определение тренда"""
        if len(data) < 2:
            return 'neutral'

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

    def _determine_time_horizon(self, data: pd.DataFrame,
                                analysis: Dict) -> str:
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

    # ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ДЛЯ АНАЛИЗА РЕЗУЛЬТАТОВ

    def calculate_calmar_ratio(self, result: BacktestResult) -> float:
        """Расчет коэффициента Calmar (доходность / макс. просадка)"""
        if result.max_drawdown_percent == 0:
            return float('inf')
        return result.total_return_percent / abs(result.max_drawdown_percent)

    def calculate_sortino_ratio(self, result: BacktestResult,
                                target_return: float = 0.0) -> float:
        """Расчет коэффициента Sortino"""
        if result.daily_returns.empty:
            return 0.0

        excess_returns = result.daily_returns - target_return / 252
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0:
            return float('inf')

        downside_deviation = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(252)

        if downside_deviation == 0:
            return float('inf')

        return (result.daily_returns.mean() * 252 - target_return) / downside_deviation

    def calculate_max_consecutive_losses(self, result: BacktestResult) -> int:
        """Расчет максимального количества убыточных сделок подряд"""
        if not result.trades:
            return 0

        max_losses = 0
        current_losses = 0

        for trade in result.trades:
            if trade.pnl < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0

        return max_losses

    def calculate_recovery_factor(self, result: BacktestResult) -> float:
        """Фактор восстановления (общая прибыль / макс. просадка)"""
        if result.max_drawdown == 0:
            return float('inf')
        return result.total_return / abs(result.max_drawdown)

    def get_trade_statistics(self, result: BacktestResult) -> Dict:
        """Дополнительная статистика по сделкам"""
        if not result.trades:
            return {}

        winning_trades = [t for t in result.trades if t.pnl > 0]
        losing_trades = [t for t in result.trades if t.pnl < 0]

        stats = {
            'total_trades': len(result.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(result.trades) if result.trades else 0,
            'avg_win': np.mean([t.pnl for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t.pnl for t in losing_trades]) if losing_trades else 0,
            'largest_win': max([t.pnl for t in winning_trades]) if winning_trades else 0,
            'largest_loss': min([t.pnl for t in losing_trades]) if losing_trades else 0,
            'avg_win_duration': np.mean([
                (t.exit_timestamp - t.timestamp).total_seconds() / 3600
                for t in winning_trades if t.exit_timestamp
            ]) if winning_trades else 0,
            'avg_loss_duration': np.mean([
                (t.exit_timestamp - t.timestamp).total_seconds() / 3600
                for t in losing_trades if t.exit_timestamp
            ]) if losing_trades else 0,
            'max_consecutive_wins': self._calculate_max_consecutive_wins(result),
            'max_consecutive_losses': self.calculate_max_consecutive_losses(result),
            'profit_factor': result.profit_factor,
            'expectancy': np.mean([t.pnl for t in result.trades]) if result.trades else 0
        }

        return stats

    def _calculate_max_consecutive_wins(self, result: BacktestResult) -> int:
        """Расчет максимального количества прибыльных сделок подряд"""
        if not result.trades:
            return 0

        max_wins = 0
        current_wins = 0

        for trade in result.trades:
            if trade.pnl > 0:
                current_wins += 1
                max_wins = max(max_wins, current_wins)
            else:
                current_wins = 0

        return max_wins

    def analyze_monthly_performance(self, result: BacktestResult) -> pd.DataFrame:
        """Анализ месячной производительности"""
        if result.equity_curve.empty:
            return pd.DataFrame()

        monthly_equity = result.equity_curve.resample('M').last()
        monthly_returns = monthly_equity.pct_change().dropna()

        monthly_stats = pd.DataFrame({
            'Month': monthly_returns.index.strftime('%Y-%m'),
            'Return_%': monthly_returns * 100,
            'Equity': monthly_equity[1:],  # Исключаем первый месяц (NaN return)
            'Cumulative_Return_%': ((monthly_equity / monthly_equity.iloc[0]) - 1) * 100
        })

        return monthly_stats.reset_index(drop=True)

    def get_drawdown_periods(self, result: BacktestResult) -> List[Dict]:
        """Анализ периодов просадки"""
        if result.equity_curve.empty:
            return []

        rolling_max = result.equity_curve.expanding().max()
        drawdown = result.equity_curve - rolling_max

        # Найти периоды просадки
        in_drawdown = drawdown < 0
        drawdown_periods = []

        start_idx = None
        for i, is_dd in enumerate(in_drawdown):
            if is_dd and start_idx is None:
                start_idx = i
            elif not is_dd and start_idx is not None:
                end_idx = i - 1

                period_drawdown = drawdown.iloc[start_idx:end_idx + 1]
                max_dd = period_drawdown.min()

                drawdown_periods.append({
                    'start_date': result.equity_curve.index[start_idx],
                    'end_date': result.equity_curve.index[end_idx],
                    'duration_days': (result.equity_curve.index[end_idx] -
                                      result.equity_curve.index[start_idx]).days,
                    'max_drawdown': max_dd,
                    'max_drawdown_pct': (max_dd / rolling_max.iloc[start_idx]) * 100
                })

                start_idx = None

        # Если просадка продолжается до конца
        if start_idx is not None:
            period_drawdown = drawdown.iloc[start_idx:]
            max_dd = period_drawdown.min()

            drawdown_periods.append({
                'start_date': result.equity_curve.index[start_idx],
                'end_date': result.equity_curve.index[-1],
                'duration_days': (result.equity_curve.index[-1] -
                                  result.equity_curve.index[start_idx]).days,
                'max_drawdown': max_dd,
                'max_drawdown_pct': (max_dd / rolling_max.iloc[start_idx]) * 100
            })

        return drawdown_periods

    def export_results_to_excel(self, result: BacktestResult, strategy_name: str,
                                filename: str = None):
        """Экспорт результатов в Excel"""
        try:
            import pandas as pd
            from datetime import datetime

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"backtest_{strategy_name}_{timestamp}.xlsx"

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Основные метрики
                metrics_df = pd.DataFrame([{
                    'Metric': 'Total Return (%)',
                    'Value': result.total_return_percent
                }, {
                    'Metric': 'Sharpe Ratio',
                    'Value': result.sharpe_ratio
                }, {
                    'Metric': 'Max Drawdown (%)',
                    'Value': result.max_drawdown_percent
                }, {
                    'Metric': 'Win Rate (%)',
                    'Value': result.win_rate * 100
                }, {
                    'Metric': 'Profit Factor',
                    'Value': result.profit_factor
                }, {
                    'Metric': 'Total Trades',
                    'Value': result.total_trades
                }, {
                    'Metric': 'Calmar Ratio',
                    'Value': self.calculate_calmar_ratio(result)
                }, {
                    'Metric': 'Sortino Ratio',
                    'Value': self.calculate_sortino_ratio(result)
                }])
                metrics_df.to_excel(writer, sheet_name='Metrics', index=False)

                # Equity curve
                equity_df = pd.DataFrame({
                    'Date': result.equity_curve.index,
                    'Equity': result.equity_curve.values
                })
                equity_df.to_excel(writer, sheet_name='Equity_Curve', index=False)

                # Сделки
                if result.trades:
                    trades_data = []
                    for trade in result.trades:
                        trades_data.append({
                            'Timestamp': trade.timestamp,
                            'Symbol': trade.symbol,
                            'Side': trade.side,
                            'Entry_Price': trade.entry_price,
                            'Exit_Price': trade.exit_price,
                            'Quantity': trade.quantity,
                            'PnL': trade.pnl,
                            'PnL_%': trade.pnl_percent,
                            'Commission': trade.commission,
                            'Exit_Timestamp': trade.exit_timestamp
                        })

                    trades_df = pd.DataFrame(trades_data)
                    trades_df.to_excel(writer, sheet_name='Trades', index=False)

                # Месячная производительность
                monthly_perf = self.analyze_monthly_performance(result)
                if not monthly_perf.empty:
                    monthly_perf.to_excel(writer, sheet_name='Monthly_Performance', index=False)

                # Периоды просадки
                drawdown_periods = self.get_drawdown_periods(result)
                if drawdown_periods:
                    dd_df = pd.DataFrame(drawdown_periods)
                    dd_df.to_excel(writer, sheet_name='Drawdown_Periods', index=False)

            logger.info(f"Результаты экспортированы в {filename}")

        except ImportError:
            logger.warning("openpyxl не установлен. Экспорт в Excel недоступен.")
        except Exception as e:
            logger.error(f"Ошибка экспорта в Excel: {e}")

    def create_tearsheet(self, result: BacktestResult, strategy_name: str) -> str:
        """Создание подробного tearsheet отчета"""

        trade_stats = self.get_trade_statistics(result)
        calmar_ratio = self.calculate_calmar_ratio(result)
        sortino_ratio = self.calculate_sortino_ratio(result)

        tearsheet = f"""
{'=' * 80}
                    TEARSHEET ОТЧЕТ ПО БЭКТЕСТУ
{'=' * 80}

Стратегия: {strategy_name}
Период: {result.equity_curve.index[0].strftime('%Y-%m-%d')} - {result.equity_curve.index[-1].strftime('%Y-%m-%d')}
Начальный капитал: ${self.initial_capital:,.2f}

{'=' * 80}
                        ОСНОВНЫЕ РЕЗУЛЬТАТЫ
{'=' * 80}

Финальный капитал:      ${result.equity_curve.iloc[-1]:,.2f}
Общая доходность:       ${result.total_return:,.2f} ({result.total_return_percent:.2f}%)
Максимальная просадка:  ${result.max_drawdown:.2f} ({result.max_drawdown_percent:.2f}%)

{'=' * 80}
                        КОЭФФИЦИЕНТЫ РИСКА
{'=' * 80}

Коэффициент Шарпа:      {result.sharpe_ratio:.3f}
Коэффициент Calmar:     {calmar_ratio:.3f}
Коэффициент Sortino:    {sortino_ratio:.3f}
Фактор восстановления:  {self.calculate_recovery_factor(result):.3f}

{'=' * 80}
                        СТАТИСТИКА СДЕЛОК
{'=' * 80}

Всего сделок:           {trade_stats.get('total_trades', 0)}
Прибыльных сделок:      {trade_stats.get('winning_trades', 0)} ({trade_stats.get('win_rate', 0) * 100:.1f}%)
Убыточных сделок:       {trade_stats.get('losing_trades', 0)}

Средняя прибыль:        ${trade_stats.get('avg_win', 0):.2f}
Средний убыток:         ${trade_stats.get('avg_loss', 0):.2f}
Лучшая сделка:         ${trade_stats.get('largest_win', 0):.2f}
Худшая сделка:         ${trade_stats.get('largest_loss', 0):.2f}

Profit Factor:          {result.profit_factor:.3f}
Математическое ожидание: ${trade_stats.get('expectancy', 0):.2f}

Максимум побед подряд:   {trade_stats.get('max_consecutive_wins', 0)}
Максимум потерь подряд:  {trade_stats.get('max_consecutive_losses', 0)}

{'=' * 80}
                        ВРЕМЕННЫЕ ХАРАКТЕРИСТИКИ
{'=' * 80}

Средняя длительность сделки:    {result.avg_trade_duration}
Самая длинная сделка:          {result.longest_trade_duration}
Самая короткая сделка:         {result.shortest_trade_duration}

Средняя длительность прибыльных сделок: {trade_stats.get('avg_win_duration', 0):.1f} часов
Средняя длительность убыточных сделок:  {trade_stats.get('avg_loss_duration', 0):.1f} часов

{'=' * 80}
                        ПАРАМЕТРЫ БЭКТЕСТА
{'=' * 80}

Комиссия:              {self.commission * 100:.3f}%
Проскальзывание:       {self.slippage * 100:.3f}%

{'=' * 80}
"""

        return tearsheet
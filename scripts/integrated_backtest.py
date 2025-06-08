# scripts/integrated_backtest.py
"""
Интегрированная система бэктестинга с реальными данными
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from config.settings import Settings
from config.trading_config import TradingConfig
from backtest.backtester import Backtester, BacktestResult
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from trading.strategies.ai_driven import AIDrivenStrategy
from core.engine.exchange_manager import ExchangeManager
from core.event_bus import EventBus
from utils.helpers import create_sample_data


class IntegratedBacktester:
    """Интегрированный бэктестер с реальными данными"""

    def __init__(self, settings: Settings, trading_config: TradingConfig):
        self.settings = settings
        self.trading_config = trading_config
        self.event_bus = EventBus()
        self.exchange_manager = ExchangeManager(settings, self.event_bus)
        self.backtester = Backtester()

    async def run_comprehensive_backtest(self,
                                         symbols: List[str] = None,
                                         start_date: datetime = None,
                                         end_date: datetime = None,
                                         use_real_data: bool = True) -> Dict[str, BacktestResult]:
        """Комплексный бэктест с реальными и тестовыми данными"""

        logger.info("🔬 Запуск комплексного бэктестинга")

        # Символы по умолчанию
        if symbols is None:
            symbols = [tp.symbol for tp in self.trading_config.trading_pairs if tp.enabled]

        # Даты по умолчанию (последние 30 дней)
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            # Инициализация подключений
            if use_real_data:
                await self.event_bus.start()
                await self.exchange_manager.initialize()

            # Получение данных
            data = await self._collect_backtest_data(symbols, start_date, end_date, use_real_data)

            if not data:
                logger.error("❌ Не удалось получить данные для бэктеста")
                return {}

            # Подготовка стратегий
            strategies = await self._prepare_strategies()

            # Запуск бэктестов
            results = {}
            for strategy in strategies:
                logger.info(f"📊 Бэктест стратегии: {strategy.name}")

                try:
                    result = await self.backtester.run(
                        strategy=strategy,
                        data=data,
                        start_date=start_date,
                        end_date=end_date
                    )

                    results[strategy.name] = result

                    logger.info(f"✅ {strategy.name}: Доходность {result.total_return_percent:.2f}%, "
                                f"Винрейт {result.win_rate:.1%}, Сделок {result.total_trades}")

                except Exception as e:
                    logger.error(f"❌ Ошибка бэктеста {strategy.name}: {e}")
                    results[strategy.name] = None

            # Сохранение результатов
            await self._save_backtest_results(results, symbols, start_date, end_date)

            return results

        finally:
            if use_real_data:
                await self.exchange_manager.stop()
                await self.event_bus.stop()

    async def _collect_backtest_data(self, symbols: List[str],
                                     start_date: datetime, end_date: datetime,
                                     use_real_data: bool) -> Dict[str, pd.DataFrame]:
        """Сбор данных для бэктестинга"""

        data = {}

        for symbol in symbols:
            logger.info(f"📡 Получение данных для {symbol}")

            try:
                if use_real_data and self.exchange_manager.exchanges:
                    # Реальные данные
                    # Рассчитываем количество периодов
                    periods = int((end_date - start_date).total_seconds() / (5 * 60))  # 5-минутные свечи
                    periods = min(periods, 1000)  # Ограничиваем для API

                    symbol_data = await self.exchange_manager.get_market_data(
                        symbol,
                        self.trading_config.primary_timeframe,
                        periods
                    )

                    if not symbol_data.empty:
                        # Фильтруем по датам
                        symbol_data = symbol_data[
                            (symbol_data.index >= start_date) &
                            (symbol_data.index <= end_date)
                            ]

                        if len(symbol_data) > 10:
                            data[symbol] = symbol_data
                            logger.info(f"✅ {symbol}: {len(symbol_data)} реальных свечей")
                        else:
                            logger.warning(f"⚠️ {symbol}: Недостаточно реальных данных, используем тестовые")
                            data[symbol] = create_sample_data(symbol, periods=200)
                    else:
                        logger.warning(f"⚠️ {symbol}: Пустые реальные данные, используем тестовые")
                        data[symbol] = create_sample_data(symbol, periods=200)

                else:
                    # Тестовые данные
                    logger.info(f"🧪 Генерация тестовых данных для {symbol}")
                    periods = int((end_date - start_date).total_seconds() / (5 * 60))
                    periods = min(max(periods, 100), 1000)

                    data[symbol] = create_sample_data(symbol, periods=periods)

            except Exception as e:
                logger.error(f"❌ Ошибка получения данных {symbol}: {e}")
                # Fallback к тестовым данным
                data[symbol] = create_sample_data(symbol, periods=200)

        logger.info(f"📊 Собрано данных для {len(data)} символов")
        return data

    async def _prepare_strategies(self) -> List:
        """Подготовка стратегий для бэктестинга"""

        strategies = []

        # SimpleMomentum стратегия
        momentum_config = {
            'indicators': self.trading_config.technical_indicators,
            'position_size_percent': 2.0,
            'confidence_threshold': 0.6
        }
        momentum_strategy = SimpleMomentumStrategy(momentum_config)
        strategies.append(momentum_strategy)

        # AI-Driven стратегия (с mock анализатором для бэктеста)
        ai_config = {
            'min_confidence': 0.7,
            'use_news': False,  # Отключаем новости для бэктеста
            'technical_indicators': self.trading_config.technical_indicators,
            'risk_multiplier': 1.0
        }
        ai_strategy = AIDrivenStrategy(ai_config, self.event_bus)
        strategies.append(ai_strategy)

        return strategies

    async def _save_backtest_results(self, results: Dict[str, BacktestResult],
                                     symbols: List[str], start_date: datetime, end_date: datetime):
        """Сохранение результатов бэктестинга"""

        try:
            import os
            from datetime import datetime

            # Создаем директорию для результатов
            results_dir = "backtest_results"
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Сохраняем сводку
            summary = {
                'timestamp': timestamp,
                'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'symbols': symbols,
                'strategies': {}
            }

            for strategy_name, result in results.items():
                if result is not None:
                    summary['strategies'][strategy_name] = {
                        'total_return_percent': result.total_return_percent,
                        'sharpe_ratio': result.sharpe_ratio,
                        'max_drawdown_percent': result.max_drawdown_percent,
                        'win_rate': result.win_rate,
                        'profit_factor': result.profit_factor,
                        'total_trades': result.total_trades
                    }

                    # Сохраняем подробные результаты
                    self.backtester.save_results(result, strategy_name, results_dir)

            # Сохраняем сводку
            import json
            with open(f"{results_dir}/summary_{timestamp}.json", 'w') as f:
                json.dump(summary, f, indent=2, default=str)

            logger.info(f"💾 Результаты сохранены в {results_dir}")

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результатов: {e}")

    async def run_strategy_optimization(self, strategy_name: str, symbol: str,
                                        parameter_ranges: Dict) -> Dict:
        """Оптимизация параметров стратегии"""

        logger.info(f"🔧 Оптимизация стратегии {strategy_name} для {symbol}")

        try:
            # Получаем данные
            data = await self._collect_backtest_data([symbol],
                                                     datetime.utcnow() - timedelta(days=60),
                                                     datetime.utcnow(),
                                                     True)

            if symbol not in data:
                logger.error(f"❌ Нет данных для {symbol}")
                return {}

            best_result = None
            best_params = None
            best_sharpe = -999

            # Перебираем параметры
            import itertools

            param_combinations = list(itertools.product(*parameter_ranges.values()))
            logger.info(f"🧮 Тестируем {len(param_combinations)} комбинаций параметров")

            for i, param_values in enumerate(param_combinations):
                # Создаем конфигурацию
                config = dict(zip(parameter_ranges.keys(), param_values))
                config['indicators'] = self.trading_config.technical_indicators

                # Создаем стратегию
                if strategy_name == "SimpleMomentum":
                    strategy = SimpleMomentumStrategy(config)
                else:
                    continue  # Пока поддерживаем только SimpleMomentum

                # Запускаем бэктест
                try:
                    result = await self.backtester.run(strategy, {symbol: data[symbol]})

                    # Оцениваем результат
                    if result.sharpe_ratio > best_sharpe and result.total_trades >= 10:
                        best_sharpe = result.sharpe_ratio
                        best_result = result
                        best_params = config

                    if i % 10 == 0:
                        logger.info(f"🔄 Прогресс: {i}/{len(param_combinations)}")

                except Exception as e:
                    logger.debug(f"Ошибка тестирования параметров {config}: {e}")
                    continue

            if best_result:
                logger.info(f"✅ Лучшие параметры для {strategy_name}:")
                logger.info(f"   Параметры: {best_params}")
                logger.info(f"   Sharpe ratio: {best_result.sharpe_ratio:.3f}")
                logger.info(f"   Доходность: {best_result.total_return_percent:.2f}%")
                logger.info(f"   Винрейт: {best_result.win_rate:.1%}")

                return {
                    'best_params': best_params,
                    'best_result': best_result,
                    'optimization_summary': {
                        'tested_combinations': len(param_combinations),
                        'best_sharpe': best_sharpe,
                        'best_return': best_result.total_return_percent,
                        'best_win_rate': best_result.win_rate
                    }
                }
            else:
                logger.warning("⚠️ Не найдено успешных параметров")
                return {}

        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации: {e}")
            return {}


async def run_integrated_backtest():
    """Запуск интегрированного бэктестинга"""

    logger.info("🚀 Запуск интегрированного бэктестинга")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet
    settings.bybit_testnet = True
    settings.binance_testnet = True

    backtester = IntegratedBacktester(settings, trading_config)

    try:
        # Комплексный бэктест
        results = await backtester.run_comprehensive_backtest(
            symbols=["BTCUSDT", "ETHUSDT"],
            start_date=datetime.utcnow() - timedelta(days=7),  # Последняя неделя
            end_date=datetime.utcnow(),
            use_real_data=True
        )

        # Анализ результатов
        if results:
            logger.info("\n📊 === РЕЗУЛЬТАТЫ БЭКТЕСТИНГА ===")

            for strategy_name, result in results.items():
                if result:
                    logger.info(f"\n🎯 {strategy_name}:")
                    logger.info(f"   💰 Доходность: {result.total_return_percent:.2f}%")
                    logger.info(f"   📈 Sharpe ratio: {result.sharpe_ratio:.3f}")
                    logger.info(f"   📉 Макс. просадка: {result.max_drawdown_percent:.2f}%")
                    logger.info(f"   🎯 Винрейт: {result.win_rate:.1%}")
                    logger.info(f"   🔢 Всего сделок: {result.total_trades}")
                    logger.info(f"   💪 Profit factor: {result.profit_factor:.2f}")

        # Оптимизация SimpleMomentum стратегии
        logger.info("\n🔧 === ОПТИМИЗАЦИЯ СТРАТЕГИИ ===")

        optimization_params = {
            'position_size_percent': [1.0, 2.0, 3.0],
            'confidence_threshold': [0.5, 0.6, 0.7, 0.8]
        }

        optimization_result = await backtester.run_strategy_optimization(
            "SimpleMomentum",
            "BTCUSDT",
            optimization_params
        )

        if optimization_result:
            logger.info("✅ Оптимизация завершена успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка бэктестинга: {e}")

    logger.info("🏁 Бэктестинг завершен")


if __name__ == "__main__":
    asyncio.run(run_integrated_backtest())
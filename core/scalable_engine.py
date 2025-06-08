# core/scalable_engine.py
"""
Масштабируемая архитектура торгового движка для приема депозитов
"""
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime
from loguru import logger
from dataclasses import dataclass
from enum import Enum

from config.settings import Settings
from config.trading_config import TradingConfig
from core.event_bus import EventBus, Event, EventType
from models.trading_signals import TradingSignal, MarketState


class AccountType(str, Enum):
    PERSONAL = "personal"
    CLIENT = "client"
    FUND = "fund"


@dataclass
class ClientAccount:
    """Клиентский аккаунт"""
    id: str
    name: str
    account_type: AccountType
    initial_deposit: Decimal
    current_balance: Decimal
    allocated_strategies: List[str]
    risk_profile: str  # conservative, moderate, aggressive
    fee_rate: Decimal  # % комиссия с прибыли
    created_at: datetime
    active: bool = True


class MultiAccountEngine:
    """Масштабируемый движок для управления несколькими аккаунтами"""

    def __init__(self, settings: Settings, trading_config: TradingConfig):
        self.settings = settings
        self.trading_config = trading_config

        # Core компоненты
        self.event_bus = EventBus()
        self.accounts: Dict[str, ClientAccount] = {}
        self.account_portfolios = {}
        self.account_strategies = {}

        # Общие менеджеры
        self.exchange_manager = None
        self.market_analyzer = None
        self.risk_manager = None

        # Статистика
        self.performance_tracker = PerformanceTracker()

        self.is_running = False

    async def initialize(self):
        """Инициализация мульти-аккаунт движка"""
        logger.info("🏢 Инициализация масштабируемого торгового движка")

        # Инициализация общих компонентов
        await self.event_bus.start()

        # Загрузка существующих аккаунтов
        await self._load_client_accounts()

        # Инициализация общих менеджеров
        await self._initialize_shared_components()

        logger.info(f"✅ Инициализировано аккаунтов: {len(self.accounts)}")

    async def _load_client_accounts(self):
        """Загрузка клиентских аккаунтов из базы"""
        # Здесь будет интеграция с базой данных
        # Пока создаем тестовые аккаунты

        # Личный аккаунт
        personal_account = ClientAccount(
            id="personal_001",
            name="Personal Trading",
            account_type=AccountType.PERSONAL,
            initial_deposit=Decimal("10000"),
            current_balance=Decimal("10000"),
            allocated_strategies=["AI_Driven", "SimpleMomentum"],
            risk_profile="moderate",
            fee_rate=Decimal("0"),  # Без комиссии для личного аккаунта
            created_at=datetime.utcnow()
        )

        self.accounts[personal_account.id] = personal_account
        logger.info(f"✅ Загружен личный аккаунт: {personal_account.name}")

    async def add_client_account(self, account_data: Dict) -> str:
        """Добавление нового клиентского аккаунта"""

        account = ClientAccount(
            id=f"client_{len(self.accounts) + 1:03d}",
            name=account_data['name'],
            account_type=AccountType.CLIENT,
            initial_deposit=Decimal(str(account_data['deposit'])),
            current_balance=Decimal(str(account_data['deposit'])),
            allocated_strategies=account_data.get('strategies', ["AI_Driven"]),
            risk_profile=account_data.get('risk_profile', 'moderate'),
            fee_rate=Decimal(str(account_data.get('fee_rate', '0.20'))),  # 20% комиссия по умолчанию
            created_at=datetime.utcnow()
        )

        self.accounts[account.id] = account

        # Создание портфеля для аккаунта
        await self._create_account_portfolio(account)

        logger.info(f"✅ Добавлен клиентский аккаунт: {account.name} (${account.initial_deposit})")

        return account.id

    async def _create_account_portfolio(self, account: ClientAccount):
        """Создание портфеля для аккаунта"""
        from core.portfolio import Portfolio

        # Создаем изолированный портфель для каждого аккаунта
        portfolio = Portfolio(initial_balance=account.current_balance)
        self.account_portfolios[account.id] = portfolio

        # Настройка стратегий для аккаунта
        strategies = await self._setup_account_strategies(account)
        self.account_strategies[account.id] = strategies

    async def _setup_account_strategies(self, account: ClientAccount) -> List:
        """Настройка стратегий для аккаунта"""
        strategies = []

        for strategy_name in account.allocated_strategies:
            # Настройка параметров стратегии в зависимости от риск-профиля
            strategy_config = self._get_strategy_config(strategy_name, account.risk_profile)

            if strategy_name == "AI_Driven":
                from trading.strategies.ai_driven import AIDrivenStrategy
                strategy = AIDrivenStrategy(strategy_config, self.event_bus)
            elif strategy_name == "SimpleMomentum":
                from trading.strategies.simple_momentum import SimpleMomentumStrategy
                strategy = SimpleMomentumStrategy(strategy_config)

            strategy.account_id = account.id  # Привязка к аккаунту
            strategy.active = True
            strategies.append(strategy)

        return strategies

    def _get_strategy_config(self, strategy_name: str, risk_profile: str) -> Dict:
        """Получение конфигурации стратегии для риск-профиля"""

        base_config = self.trading_config.technical_indicators.copy()

        # Корректировка под риск-профиль
        if risk_profile == "conservative":
            return {
                **base_config,
                'position_size_percent': 1.0,  # 1% позиции
                'min_confidence': 0.8,  # Высокая уверенность
                'max_positions': 3,  # Максимум 3 позиции
                'risk_multiplier': 0.5  # Сниженный риск
            }
        elif risk_profile == "aggressive":
            return {
                **base_config,
                'position_size_percent': 3.0,  # 3% позиции
                'min_confidence': 0.6,  # Средняя уверенность
                'max_positions': 8,  # До 8 позиций
                'risk_multiplier': 1.5  # Увеличенный риск
            }
        else:  # moderate
            return {
                **base_config,
                'position_size_percent': 2.0,  # 2% позиции
                'min_confidence': 0.7,  # Хорошая уверенность
                'max_positions': 5,  # До 5 позиций
                'risk_multiplier': 1.0  # Стандартный риск
            }

    async def start_trading(self):
        """Запуск торговли для всех аккаунтов"""
        if self.is_running:
            logger.warning("Движок уже запущен")
            return

        await self.initialize()
        self.is_running = True

        logger.info("🚀 Запуск торговли для всех аккаунтов")

        # Запуск торгового цикла
        try:
            while self.is_running:
                await self._trading_cycle()
                await asyncio.sleep(30)  # Основной цикл каждые 30 секунд

        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
        finally:
            await self.stop()

    async def _trading_cycle(self):
        """Основной торговый цикл для всех аккаунтов"""
        try:
            # Анализ рынка (общий для всех аккаунтов)
            market_analysis = await self._perform_market_analysis()

            # Торговля для каждого активного аккаунта
            for account_id, account in self.accounts.items():
                if not account.active:
                    continue

                await self._trade_for_account(account_id, market_analysis)

            # Обновление общей статистики
            await self.performance_tracker.update_stats(self.accounts, self.account_portfolios)

        except Exception as e:
            logger.error(f"❌ Ошибка в торговом цикле: {e}")

    async def _perform_market_analysis(self) -> Dict[str, MarketState]:
        """Общий анализ рынка для всех торговых пар"""
        market_states = {}

        for trading_pair in self.trading_config.trading_pairs:
            if not trading_pair.enabled:
                continue

            try:
                # Получение рыночных данных
                market_data = await self.exchange_manager.get_market_data(
                    trading_pair.symbol,
                    self.trading_config.primary_timeframe,
                    100
                )

                if not market_data.empty:
                    # Создание состояния рынка
                    current_price = Decimal(str(market_data['close'].iloc[-1]))
                    volume_24h = Decimal(str(market_data['volume'].sum()))
                    price_change = float(
                        (market_data['close'].iloc[-1] - market_data['close'].iloc[0]) / market_data['close'].iloc[
                            0] * 100)

                    market_state = MarketState(
                        symbol=trading_pair.symbol,
                        current_price=current_price,
                        volume_24h=volume_24h,
                        price_change_24h=price_change,
                        timestamp=datetime.utcnow()
                    )

                    market_states[trading_pair.symbol] = market_state

                    # Запуск AI анализа
                    await self.market_analyzer.analyze_symbol(trading_pair.symbol)

            except Exception as e:
                logger.error(f"❌ Ошибка анализа {trading_pair.symbol}: {e}")

        return market_states

    async def _trade_for_account(self, account_id: str, market_analysis: Dict[str, MarketState]):
        """Торговля для конкретного аккаунта"""
        try:
            account = self.accounts[account_id]
            portfolio = self.account_portfolios[account_id]
            strategies = self.account_strategies[account_id]

            # Получение статистики портфеля
            portfolio_stats = await portfolio.get_portfolio_stats()

            # Проверка лимитов для аккаунта
            if not await self._check_account_limits(account, portfolio_stats):
                logger.warning(f"⚠️ Аккаунт {account.name} превысил лимиты")
                return

            # Выполнение стратегий для аккаунта
            for strategy in strategies:
                if not strategy.active:
                    continue

                await self._execute_strategy_for_account(account_id, strategy, market_analysis)

        except Exception as e:
            logger.error(f"❌ Ошибка торговли для аккаунта {account_id}: {e}")

    async def _execute_strategy_for_account(self, account_id: str, strategy, market_analysis: Dict[str, MarketState]):
        """Выполнение стратегии для аккаунта"""
        try:
            for symbol, market_state in market_analysis.items():
                # Получение анализа из кэша
                cached_analysis = self.market_analyzer.get_cached_analysis(symbol)

                if cached_analysis:
                    # Проверка условий стратегии
                    if await strategy.should_enter(cached_analysis['ai_analysis']):
                        await self._open_position_for_account(account_id, symbol, cached_analysis, strategy)

                    # Проверка условий выхода из существующих позиций
                    await self._check_exit_conditions_for_account(account_id, symbol, cached_analysis, strategy)

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения стратегии {strategy.name} для аккаунта {account_id}: {e}")

    async def _open_position_for_account(self, account_id: str, symbol: str, analysis: Dict, strategy):
        """Открытие позиции для аккаунта"""
        try:
            account = self.accounts[account_id]
            portfolio = self.account_portfolios[account_id]

            # Расчет размера позиции для аккаунта
            position_size = await self._calculate_account_position_size(account, portfolio, analysis)

            if position_size > 0:
                # Размещение ордера через exchange_manager
                order = await self.exchange_manager.place_order(
                    symbol=symbol,
                    side=analysis['ai_analysis']['action'].lower(),
                    order_type="market",
                    quantity=float(position_size),
                    strategy=f"{strategy.name}_{account_id}"
                )

                logger.info(f"📈 Открыта позиция для {account.name}: {symbol} {analysis['ai_analysis']['action']}")

                # Уведомление в Telegram
                await self._send_account_notification(account, f"Открыта позиция {symbol}", "position_opened")

        except Exception as e:
            logger.error(f"❌ Ошибка открытия позиции для аккаунта {account_id}: {e}")

    async def _calculate_account_position_size(self, account: ClientAccount, portfolio, analysis: Dict) -> Decimal:
        """Расчет размера позиции для конкретного аккаунта"""
        try:
            portfolio_stats = await portfolio.get_portfolio_stats()
            available_balance = float(portfolio_stats['available_balance'])

            # Получение конфигурации стратегии для аккаунта
            strategies = self.account_strategies[account.id]
            position_percent = 2.0  # По умолчанию

            if strategies:
                position_percent = strategies[0].config.get('position_size_percent', 2.0)

            # Корректировка на уверенность AI
            confidence = analysis['ai_analysis'].get('adjusted_confidence', 0.5)
            adjusted_percent = position_percent * confidence

            # Размер позиции в USD
            position_value = available_balance * (adjusted_percent / 100)

            # Примерная цена (нужно получать из анализа)
            estimated_price = 45000  # Заглушка

            return Decimal(str(position_value / estimated_price))

        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return Decimal("0")

    async def _check_account_limits(self, account: ClientAccount, portfolio_stats: Dict) -> bool:
        """Проверка лимитов для аккаунта"""
        try:
            current_balance = float(portfolio_stats['total_value'])
            initial_balance = float(account.initial_deposit)

            # Проверка максимальной просадки
            drawdown_percent = ((initial_balance - current_balance) / initial_balance) * 100

            if drawdown_percent > 20:  # Максимальная просадка 20%
                logger.warning(f"⚠️ Аккаунт {account.name} превысил лимит просадки: {drawdown_percent:.2f}%")
                return False

            # Проверка минимального баланса
            if current_balance < initial_balance * 0.5:  # Минимум 50% от депозита
                logger.warning(f"⚠️ Аккаунт {account.name} достиг минимального баланса")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки лимитов: {e}")
            return False

    async def get_account_performance(self, account_id: str) -> Dict:
        """Получение производительности аккаунта"""
        try:
            account = self.accounts.get(account_id)
            portfolio = self.account_portfolios.get(account_id)

            if not account or not portfolio:
                return {'error': 'Account not found'}

            portfolio_stats = await portfolio.get_portfolio_stats()

            # Расчет комиссии
            profit = float(portfolio_stats['total_pnl'])
            commission = 0

            if profit > 0 and account.account_type == AccountType.CLIENT:
                commission = profit * float(account.fee_rate)

            return {
                'account_id': account_id,
                'account_name': account.name,
                'account_type': account.account_type.value,
                'initial_deposit': float(account.initial_deposit),
                'current_balance': float(portfolio_stats['total_value']),
                'total_pnl': profit,
                'pnl_percent': ((float(portfolio_stats['total_value']) - float(account.initial_deposit)) / float(
                    account.initial_deposit)) * 100,
                'commission_owed': commission,
                'net_profit': profit - commission,
                'positions_count': portfolio_stats['positions_count'],
                'risk_profile': account.risk_profile,
                'strategies': [s.name for s in self.account_strategies.get(account_id, [])],
                'active': account.active
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения производительности аккаунта {account_id}: {e}")
            return {'error': str(e)}

    async def get_all_accounts_performance(self) -> List[Dict]:
        """Получение производительности всех аккаунтов"""
        performances = []

        for account_id in self.accounts.keys():
            performance = await self.get_account_performance(account_id)
            performances.append(performance)

        return performances

    async def _send_account_notification(self, account: ClientAccount, message: str, notification_type: str):
        """Отправка уведомления для аккаунта"""
        try:
            # Здесь будет интеграция с системой уведомлений
            # Можно отправлять уведомления только владельцам аккаунтов
            logger.info(f"📱 Уведомление для {account.name}: {message}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def stop(self):
        """Остановка движка"""
        logger.info("🛑 Остановка масштабируемого торгового движка")
        self.is_running = False

        # Сохранение статистики всех аккаунтов
        final_performance = await self.get_all_accounts_performance()
        logger.info(f"📊 Финальная производительность аккаунтов: {len(final_performance)} аккаунтов")

        # Остановка общих компонентов
        if self.exchange_manager:
            await self.exchange_manager.stop()
        if self.event_bus:
            await self.event_bus.stop()


class PerformanceTracker:
    """Отслеживание производительности системы"""

    def __init__(self):
        self.daily_stats = {}
        self.monthly_stats = {}

    async def update_stats(self, accounts: Dict[str, ClientAccount], portfolios: Dict):
        """Обновление статистики"""
        try:
            today = datetime.utcnow().date()

            total_balance = 0
            total_profit = 0
            active_accounts = 0

            for account_id, account in accounts.items():
                if account.active and account_id in portfolios:
                    portfolio = portfolios[account_id]
                    stats = await portfolio.get_portfolio_stats()

                    total_balance += float(stats['total_value'])
                    total_profit += float(stats['total_pnl'])
                    active_accounts += 1

            self.daily_stats[today] = {
                'total_balance': total_balance,
                'total_profit': total_profit,
                'active_accounts': active_accounts,
                'timestamp': datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики: {e}")

    def get_performance_summary(self) -> Dict:
        """Получение сводки производительности"""
        if not self.daily_stats:
            return {'error': 'No performance data available'}

        latest_stats = list(self.daily_stats.values())[-1]

        return {
            'total_accounts': latest_stats['active_accounts'],
            'total_aum': latest_stats['total_balance'],  # Assets Under Management
            'total_profit': latest_stats['total_profit'],
            'avg_profit_per_account': latest_stats['total_profit'] / max(1, latest_stats['active_accounts']),
            'last_updated': latest_stats['timestamp'].isoformat()
        }
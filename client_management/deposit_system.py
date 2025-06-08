# client_management/deposit_system.py
"""
Система управления клиентскими депозитами и фондами
"""
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from loguru import logger
import uuid

from core.portfolio import Portfolio
from risk.risk_manager import RiskManager
from models.trading_signals import TradingSignal


class DepositStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"


class FeeType(str, Enum):
    MANAGEMENT = "management"  # Фиксированная комиссия за управление
    PERFORMANCE = "performance"  # Процент с прибыли
    ENTRY = "entry"  # Комиссия при входе
    EXIT = "exit"  # Комиссия при выходе


@dataclass
class FeeStructure:
    """Структура комиссий"""
    management_fee_percent: Decimal = Decimal("2.0")  # 2% годовых
    performance_fee_percent: Decimal = Decimal("20.0")  # 20% с прибыли
    entry_fee_percent: Decimal = Decimal("0.0")  # Без входной комиссии
    exit_fee_percent: Decimal = Decimal("0.0")  # Без выходной комиссии
    high_water_mark: bool = True  # Высший пик для производительности


@dataclass
class ClientDeposit:
    """Клиентский депозит"""
    id: str
    client_name: str
    client_email: str
    initial_amount: Decimal
    current_value: Decimal

    # Параметры риска
    risk_profile: str  # "conservative", "moderate", "aggressive"
    max_drawdown_percent: Decimal = Decimal("15.0")

    # Стратегии
    allocated_strategies: List[str] = field(default_factory=lambda: ["AI_Driven"])
    strategy_weights: Dict[str, float] = field(default_factory=dict)

    # Комиссии
    fee_structure: FeeStructure = field(default_factory=FeeStructure)

    # Статус и даты
    status: DepositStatus = DepositStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    last_fee_calculation: Optional[datetime] = None

    # История производительности
    high_water_mark: Decimal = Decimal("0")
    total_fees_paid: Decimal = Decimal("0")

    # Метаданные
    notes: str = ""
    referral_source: Optional[str] = None


class FundManager:
    """Менеджер фондов и клиентских депозитов"""

    def __init__(self, trading_engine):
        self.trading_engine = trading_engine
        self.client_deposits: Dict[str, ClientDeposit] = {}
        self.fund_portfolio = Portfolio(Decimal("0"))  # Общий фонд
        self.client_portfolios: Dict[str, Portfolio] = {}

        # Статистика фонда
        self.total_aum = Decimal("0")  # Assets Under Management
        self.total_clients = 0
        self.performance_history = []

    async def accept_client_deposit(self, client_data: Dict[str, Any]) -> str:
        """Прием клиентского депозита"""

        try:
            # Валидация данных клиента
            self._validate_client_data(client_data)

            # Создание депозита
            deposit = ClientDeposit(
                id=f"deposit_{uuid.uuid4().hex[:8]}",
                client_name=client_data['name'],
                client_email=client_data['email'],
                initial_amount=Decimal(str(client_data['amount'])),
                current_value=Decimal(str(client_data['amount'])),
                risk_profile=client_data.get('risk_profile', 'moderate'),
                max_drawdown_percent=Decimal(str(client_data.get('max_drawdown', '15.0'))),
                allocated_strategies=client_data.get('strategies', ['AI_Driven']),
                notes=client_data.get('notes', ''),
                referral_source=client_data.get('referral_source')
            )

            # Настройка структуры комиссий
            if 'fee_structure' in client_data:
                fee_data = client_data['fee_structure']
                deposit.fee_structure = FeeStructure(
                    management_fee_percent=Decimal(str(fee_data.get('management', '2.0'))),
                    performance_fee_percent=Decimal(str(fee_data.get('performance', '20.0'))),
                    entry_fee_percent=Decimal(str(fee_data.get('entry', '0.0'))),
                    exit_fee_percent=Decimal(str(fee_data.get('exit', '0.0')))
                )

            # Расчет входной комиссии
            entry_fee = self._calculate_entry_fee(deposit)
            net_deposit = deposit.initial_amount - entry_fee

            # Создание изолированного портфеля для клиента
            client_portfolio = Portfolio(net_deposit)
            self.client_portfolios[deposit.id] = client_portfolio

            # Добавление в общий фонд
            self.fund_portfolio.assets['USDT'].free += net_deposit
            self.fund_portfolio.assets['USDT'].total += net_deposit

            # Регистрация депозита
            self.client_deposits[deposit.id] = deposit
            self.total_aum += net_deposit
            self.total_clients += 1

            # Активация депозита
            await self._activate_deposit(deposit.id)

            logger.info(
                f"✅ Принят депозит от {deposit.client_name}: ${deposit.initial_amount} (комиссия: ${entry_fee})")

            # Уведомление клиента
            await self._send_client_notification(
                deposit,
                f"Ваш депозит ${deposit.initial_amount} успешно принят. Чистая сумма для торговли: ${net_deposit}",
                "deposit_accepted"
            )

            return deposit.id

        except Exception as e:
            logger.error(f"❌ Ошибка приема депозита: {e}")
            raise

    def _validate_client_data(self, data: Dict[str, Any]):
        """Валидация данных клиента"""
        required_fields = ['name', 'email', 'amount']
        missing = [field for field in required_fields if field not in data]

        if missing:
            raise ValueError(f"Отсутствуют обязательные поля: {missing}")

        # Валидация суммы
        amount = Decimal(str(data['amount']))
        if amount < Decimal("1000"):  # Минимальный депозит $1000
            raise ValueError("Минимальная сумма депозита: $1,000")

        if amount > Decimal("1000000"):  # Максимальный депозит $1M
            raise ValueError("Максимальная сумма депозита: $1,000,000")

        # Валидация email
        if '@' not in data['email'] or '.' not in data['email']:
            raise ValueError("Некорректный email адрес")

    def _calculate_entry_fee(self, deposit: ClientDeposit) -> Decimal:
        """Расчет входной комиссии"""
        return deposit.initial_amount * (deposit.fee_structure.entry_fee_percent / 100)

    async def _activate_deposit(self, deposit_id: str):
        """Активация депозита"""
        deposit = self.client_deposits[deposit_id]

        # Изменение статуса
        deposit.status = DepositStatus.ACTIVE
        deposit.activated_at = datetime.utcnow()
        deposit.high_water_mark = deposit.current_value
        deposit.last_fee_calculation = datetime.utcnow()

        # Настройка торговых стратегий для клиента
        await self._setup_client_strategies(deposit)

        logger.info(f"✅ Депозит {deposit.client_name} активирован")

    async def _setup_client_strategies(self, deposit: ClientDeposit):
        """Настройка стратегий для клиента"""
        try:
            # Получение конфигурации стратегий под риск-профиль
            strategy_configs = self._get_client_strategy_configs(deposit.risk_profile)

            for strategy_name in deposit.allocated_strategies:
                # Настройка весов стратегий
                if not deposit.strategy_weights:
                    # Равномерное распределение по умолчанию
                    weight = 1.0 / len(deposit.allocated_strategies)
                    deposit.strategy_weights[strategy_name] = weight

                logger.info(
                    f"📊 Настроена стратегия {strategy_name} для {deposit.client_name} (вес: {deposit.strategy_weights[strategy_name]:.2%})")

        except Exception as e:
            logger.error(f"❌ Ошибка настройки стратегий для {deposit.client_name}: {e}")

    def _get_client_strategy_configs(self, risk_profile: str) -> Dict[str, Dict]:
        """Получение конфигураций стратегий для риск-профиля"""

        if risk_profile == "conservative":
            return {
                "AI_Driven": {
                    "min_confidence": 0.85,
                    "position_size_percent": 1.0,
                    "max_positions": 2,
                    "stop_loss_percent": 1.5,
                    "take_profit_percent": 3.0
                },
                "SimpleMomentum": {
                    "position_size_percent": 0.5,
                    "rsi_oversold": 25,
                    "rsi_overbought": 75
                }
            }
        elif risk_profile == "aggressive":
            return {
                "AI_Driven": {
                    "min_confidence": 0.65,
                    "position_size_percent": 4.0,
                    "max_positions": 8,
                    "stop_loss_percent": 3.0,
                    "take_profit_percent": 6.0
                },
                "SimpleMomentum": {
                    "position_size_percent": 3.0,
                    "rsi_oversold": 35,
                    "rsi_overbought": 65
                }
            }
        else:  # moderate
            return {
                "AI_Driven": {
                    "min_confidence": 0.75,
                    "position_size_percent": 2.0,
                    "max_positions": 5,
                    "stop_loss_percent": 2.0,
                    "take_profit_percent": 4.0
                },
                "SimpleMomentum": {
                    "position_size_percent": 1.5,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70
                }
            }

    async def process_trading_signal_for_clients(self, signal: TradingSignal):
        """Обработка торгового сигнала для клиентов"""

        for deposit_id, deposit in self.client_deposits.items():
            if deposit.status != DepositStatus.ACTIVE:
                continue

            try:
                # Проверка стратегии сигнала
                if signal.strategy in deposit.allocated_strategies:
                    # Расчет размера позиции для клиента
                    client_position_size = await self._calculate_client_position_size(
                        deposit, signal
                    )

                    if client_position_size > 0:
                        # Выполнение сделки для клиента
                        await self._execute_client_trade(deposit, signal, client_position_size)

            except Exception as e:
                logger.error(f"❌ Ошибка обработки сигнала для клиента {deposit.client_name}: {e}")

    async def _calculate_client_position_size(self, deposit: ClientDeposit, signal: TradingSignal) -> Decimal:
        """Расчет размера позиции для клиента"""
        try:
            # Получение портфеля клиента
            portfolio = self.client_portfolios[deposit.id]
            portfolio_stats = await portfolio.get_portfolio_stats()

            available_balance = portfolio_stats['available_balance']

            # Получение веса стратегии
            strategy_weight = deposit.strategy_weights.get(signal.strategy, 0.0)

            # Расчет размера позиции
            strategy_allocation = float(available_balance) * strategy_weight
            position_percent = 2.0  # Базовый процент позиции

            # Корректировка под риск-профиль
            if deposit.risk_profile == "conservative":
                position_percent *= 0.5
            elif deposit.risk_profile == "aggressive":
                position_percent *= 1.5

            # Корректировка на уверенность сигнала
            position_percent *= signal.confidence

            position_value = strategy_allocation * (position_percent / 100)

            # Конвертация в количество актива
            estimated_price = float(signal.position_size_usd / signal.quantity)
            position_size = position_value / estimated_price

            return Decimal(str(max(0.001, position_size)))

        except Exception as e:
            logger.error(f"❌ Ошибка расчета позиции для клиента: {e}")
            return Decimal("0")

    async def _execute_client_trade(self, deposit: ClientDeposit, signal: TradingSignal, position_size: Decimal):
        """Выполнение сделки для клиента"""
        try:
            # Получение портфеля клиента
            portfolio = self.client_portfolios[deposit.id]

            # Проверка лимитов риска
            if not await self._check_client_risk_limits(deposit, portfolio):
                logger.warning(f"⚠️ Превышены лимиты риска для {deposit.client_name}")
                return

            # Размещение ордера через общий движок
            order_result = await self.trading_engine.exchange_manager.place_order(
                symbol=signal.symbol,
                side=signal.action.value.lower(),
                order_type="market",
                quantity=float(position_size),
                strategy=f"{signal.strategy}_client_{deposit.id}"
            )

            if order_result:
                logger.info(
                    f"📈 Выполнена сделка для {deposit.client_name}: {signal.symbol} {signal.action.value} {position_size}")

                # Уведомление клиента
                await self._send_client_notification(
                    deposit,
                    f"Открыта позиция: {signal.symbol} {signal.action.value} на сумму ${float(position_size) * float(signal.position_size_usd / signal.quantity):.2f}",
                    "trade_executed"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения сделки для клиента {deposit.client_name}: {e}")

    async def _check_client_risk_limits(self, deposit: ClientDeposit, portfolio: Portfolio) -> bool:
        """Проверка лимитов риска для клиента"""
        try:
            portfolio_stats = await portfolio.get_portfolio_stats()
            current_value = float(portfolio_stats['total_value'])
            initial_value = float(deposit.initial_amount)

            # Проверка максимальной просадки
            drawdown_percent = ((initial_value - current_value) / initial_value) * 100

            if drawdown_percent > float(deposit.max_drawdown_percent):
                logger.warning(f"⚠️ Превышена максимальная просадка для {deposit.client_name}: {drawdown_percent:.2f}%")

                # Приостановка торговли для клиента
                await self._suspend_client_trading(deposit.id,
                                                   f"Превышена максимальная просадка ({drawdown_percent:.2f}%)")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки лимитов для клиента: {e}")
            return False

    async def _suspend_client_trading(self, deposit_id: str, reason: str):
        """Приостановка торговли для клиента"""
        try:
            deposit = self.client_deposits[deposit_id]
            deposit.status = DepositStatus.SUSPENDED
            deposit.notes += f"\nПриостановлена {datetime.utcnow()}: {reason}"

            logger.warning(f"⚠️ Торговля приостановлена для {deposit.client_name}: {reason}")

            # Уведомление клиента
            await self._send_client_notification(
                deposit,
                f"Торговля временно приостановлена: {reason}. Пожалуйста, свяжитесь с менеджером.",
                "trading_suspended"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка приостановки торговли: {e}")

    async def calculate_client_fees(self, deposit_id: str) -> Dict[str, Decimal]:
        """Расчет комиссий для клиента"""
        try:
            deposit = self.client_deposits[deposit_id]
            portfolio = self.client_portfolios[deposit_id]
            portfolio_stats = await portfolio.get_portfolio_stats()

            current_value = Decimal(str(portfolio_stats['total_value']))
            fees = {}

            # 1. Комиссия за управление (пропорционально времени)
            if deposit.last_fee_calculation:
                days_since_last = (datetime.utcnow() - deposit.last_fee_calculation).days
                if days_since_last > 0:
                    daily_management_rate = deposit.fee_structure.management_fee_percent / 365
                    management_fee = current_value * (daily_management_rate / 100) * days_since_last
                    fees['management'] = management_fee

            # 2. Комиссия с производительности (high water mark)
            performance_fee = Decimal("0")
            if deposit.fee_structure.high_water_mark:
                if current_value > deposit.high_water_mark:
                    profit = current_value - deposit.high_water_mark
                    performance_fee = profit * (deposit.fee_structure.performance_fee_percent / 100)
                    fees['performance'] = performance_fee

                    # Обновление high water mark
                    deposit.high_water_mark = current_value
            else:
                # Комиссия с общей прибыли
                total_profit = current_value - deposit.initial_amount
                if total_profit > 0:
                    performance_fee = total_profit * (deposit.fee_structure.performance_fee_percent / 100)
                    fees['performance'] = performance_fee

            # Обновление времени последнего расчета
            deposit.last_fee_calculation = datetime.utcnow()

            return fees

        except Exception as e:
            logger.error(f"❌ Ошибка расчета комиссий для клиента {deposit_id}: {e}")
            return {}

    async def process_monthly_fees(self):
        """Ежемесячная обработка комиссий"""
        logger.info("💰 Начало ежемесячной обработки комиссий")

        total_fees_collected = Decimal("0")

        for deposit_id, deposit in self.client_deposits.items():
            if deposit.status != DepositStatus.ACTIVE:
                continue

            try:
                # Расчет комиссий
                fees = await self.calculate_client_fees(deposit_id)

                if fees:
                    total_client_fees = sum(fees.values())

                    if total_client_fees > 0:
                        # Списание комиссий с портфеля клиента
                        portfolio = self.client_portfolios[deposit_id]

                        # Уменьшение баланса клиента
                        portfolio.assets['USDT'].free -= total_client_fees
                        portfolio.assets['USDT'].total -= total_client_fees

                        # Добавление к общим комиссиям
                        deposit.total_fees_paid += total_client_fees
                        total_fees_collected += total_client_fees

                        logger.info(f"💰 Списаны комиссии с {deposit.client_name}: ${total_client_fees}")

                        # Уведомление клиента
                        await self._send_client_notification(
                            deposit,
                            f"Ежемесячные комиссии: ${total_client_fees} (управление: ${fees.get('management', 0)}, производительность: ${fees.get('performance', 0)})",
                            "fees_charged"
                        )

            except Exception as e:
                logger.error(f"❌ Ошибка обработки комиссий для {deposit.client_name}: {e}")

        logger.info(f"💰 Всего собрано комиссий: ${total_fees_collected}")
        return total_fees_collected

    async def client_withdrawal_request(self, deposit_id: str, amount: Optional[Decimal] = None) -> Dict:
        """Запрос на вывод средств клиентом"""
        try:
            deposit = self.client_deposits[deposit_id]
            portfolio = self.client_portfolios[deposit_id]
            portfolio_stats = await portfolio.get_portfolio_stats()

            current_value = Decimal(str(portfolio_stats['total_value']))

            # Если сумма не указана, выводим все
            withdrawal_amount = amount or current_value

            # Проверка доступности средств
            if withdrawal_amount > current_value:
                return {
                    'success': False,
                    'error': 'Недостаточно средств для вывода',
                    'available': float(current_value),
                    'requested': float(withdrawal_amount)
                }

            # Расчет выходной комиссии
            exit_fee = withdrawal_amount * (deposit.fee_structure.exit_fee_percent / 100)
            net_withdrawal = withdrawal_amount - exit_fee

            # Закрытие всех позиций если полный вывод
            if withdrawal_amount == current_value:
                await self._close_all_client_positions(deposit_id)
                deposit.status = DepositStatus.WITHDRAWN

            # Обновление портфеля
            portfolio.assets['USDT'].free -= withdrawal_amount
            portfolio.assets['USDT'].total -= withdrawal_amount

            # Обновление общего фонда
            self.fund_portfolio.assets['USDT'].free -= withdrawal_amount
            self.fund_portfolio.assets['USDT'].total -= withdrawal_amount
            self.total_aum -= withdrawal_amount

            logger.info(f"💸 Вывод средств {deposit.client_name}: ${withdrawal_amount} (комиссия: ${exit_fee})")

            # Уведомление клиента
            await self._send_client_notification(
                deposit,
                f"Запрос на вывод обработан: ${net_withdrawal} (комиссия: ${exit_fee})",
                "withdrawal_processed"
            )

            return {
                'success': True,
                'withdrawal_amount': float(withdrawal_amount),
                'exit_fee': float(exit_fee),
                'net_amount': float(net_withdrawal),
                'remaining_balance': float(current_value - withdrawal_amount)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка обработки вывода для {deposit_id}: {e}")
            return {'success': False, 'error': str(e)}

    async def _close_all_client_positions(self, deposit_id: str):
        """Закрытие всех позиций клиента"""
        try:
            portfolio = self.client_portfolios[deposit_id]

            for position_id, position in portfolio.positions.items():
                # Закрытие позиции по рыночной цене
                await portfolio.close_position(position_id, position.entry_price * Decimal("1.01"))  # Примерная цена

            logger.info(f"📊 Закрыты все позиции для клиента {deposit_id}")

        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиций для клиента {deposit_id}: {e}")

    async def _send_client_notification(self, deposit: ClientDeposit, message: str, notification_type: str):
        """Отправка уведомления клиенту"""
        try:
            # Интеграция с системой уведомлений (email, SMS, Telegram)
            notification_data = {
                'client_name': deposit.client_name,
                'client_email': deposit.client_email,
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat(),
                'deposit_id': deposit.id
            }

            # Здесь будет отправка через различные каналы
            logger.info(f"📧 Уведомление для {deposit.client_name}: {message}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def generate_client_report(self, deposit_id: str, period_days: int = 30) -> Dict:
        """Генерация отчета для клиента"""
        try:
            deposit = self.client_deposits[deposit_id]
            portfolio = self.client_portfolios[deposit_id]
            portfolio_stats = await portfolio.get_portfolio_stats()

            current_value = Decimal(str(portfolio_stats['total_value']))
            initial_value = deposit.initial_amount

            # Расчет доходности
            total_return = current_value - initial_value
            total_return_percent = (total_return / initial_value) * 100

            # Расчет комиссий
            fees = await self.calculate_client_fees(deposit_id)

            report = {
                'client_info': {
                    'name': deposit.client_name,
                    'deposit_id': deposit.id,
                    'risk_profile': deposit.risk_profile,
                    'strategies': deposit.allocated_strategies
                },
                'performance': {
                    'initial_deposit': float(initial_value),
                    'current_value': float(current_value),
                    'total_return': float(total_return),
                    'total_return_percent': float(total_return_percent),
                    'high_water_mark': float(deposit.high_water_mark),
                    'total_fees_paid': float(deposit.total_fees_paid)
                },
                'portfolio': {
                    'total_value': float(portfolio_stats['total_value']),
                    'available_balance': float(portfolio_stats['available_balance']),
                    'unrealized_pnl': float(portfolio_stats['unrealized_pnl']),
                    'positions_count': portfolio_stats['positions_count']
                },
                'current_fees': {
                    'management': float(fees.get('management', 0)),
                    'performance': float(fees.get('performance', 0)),
                    'total': float(sum(fees.values()))
                },
                'period': {
                    'start_date': (datetime.utcnow() - timedelta(days=period_days)).isoformat(),
                    'end_date': datetime.utcnow().isoformat(),
                    'days': period_days
                },
                'status': deposit.status.value,
                'created_at': deposit.created_at.isoformat(),
                'last_updated': datetime.utcnow().isoformat()
            }

            return report

        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета для клиента {deposit_id}: {e}")
            return {'error': str(e)}

    async def get_fund_summary(self) -> Dict:
        """Получение сводки по фонду"""
        try:
            active_deposits = [d for d in self.client_deposits.values() if d.status == DepositStatus.ACTIVE]

            total_initial = sum(d.initial_amount for d in active_deposits)
            total_current = sum(float((await self.client_portfolios[d.id].get_portfolio_stats())['total_value'])
                                for d in active_deposits)
            total_fees = sum(d.total_fees_paid for d in active_deposits)

            return {
                'fund_statistics': {
                    'total_clients': len(active_deposits),
                    'total_aum': float(self.total_aum),
                    'total_initial_deposits': float(total_initial),
                    'total_current_value': total_current,
                    'total_return': total_current - float(total_initial),
                    'total_return_percent': ((total_current - float(total_initial)) / float(
                        total_initial)) * 100 if total_initial > 0 else 0,
                    'total_fees_collected': float(total_fees)
                },
                'client_breakdown': {
                    'conservative': len([d for d in active_deposits if d.risk_profile == 'conservative']),
                    'moderate': len([d for d in active_deposits if d.risk_profile == 'moderate']),
                    'aggressive': len([d for d in active_deposits if d.risk_profile == 'aggressive'])
                },
                'average_performance': {
                    'avg_return_percent': sum(((float(
                        (await self.client_portfolios[d.id].get_portfolio_stats())['total_value']) - float(
                        d.initial_amount)) / float(d.initial_amount)) * 100 for d in active_deposits) / len(
                        active_deposits) if active_deposits else 0,
                    'avg_deposit_size': float(total_initial) / len(active_deposits) if active_deposits else 0
                },
                'last_updated': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки по фонду: {e}")
            return {'error': str(e)}
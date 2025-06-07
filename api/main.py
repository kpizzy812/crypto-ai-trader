# api/main.py
"""
FastAPI приложение для REST API и веб-интерфейса
"""
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import json
from loguru import logger
import asyncio

from pydantic import BaseModel
from config.settings import settings
from core.engine import TradingEngine
from core.portfolio import Portfolio
from risk.risk_manager import RiskManager


# Pydantic модели для API
class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'buy' или 'sell'
    order_type: str  # 'market' или 'limit'
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class StrategyConfig(BaseModel):
    name: str
    enabled: bool
    parameters: Dict


class SystemStatus(BaseModel):
    status: str
    uptime: str
    active_strategies: List[str]
    open_positions: int
    total_pnl: float
    connected_exchanges: List[str]


# Создание приложения
app = FastAPI(
    title="Crypto AI Trading Bot API",
    description="API для управления криптовалютным торговым ботом",
    version="1.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные
trading_engine: Optional[TradingEngine] = None
websocket_clients: List[WebSocket] = []
start_time = datetime.utcnow()


# Вспомогательные функции
async def get_trading_engine() -> TradingEngine:
    """Получение экземпляра торгового движка"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    return trading_engine


# REST API эндпоинты
@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница с дашбордом"""
    with open("web/templates/dashboard.html", "r") as f:
        return f.read()


@app.get("/api/status", response_model=SystemStatus)
async def get_status(engine: TradingEngine = Depends(get_trading_engine)):
    """Получение статуса системы"""
    uptime = datetime.utcnow() - start_time

    portfolio_stats = await engine.portfolio.get_portfolio_stats()

    return SystemStatus(
        status="running" if engine.is_running else "stopped",
        uptime=str(uptime),
        active_strategies=[s.name for s in engine.strategies if s.active],
        open_positions=portfolio_stats['positions_count'],
        total_pnl=float(portfolio_stats['total_pnl']),
        connected_exchanges=list(engine.exchanges.keys())
    )


@app.get("/api/portfolio")
async def get_portfolio(engine: TradingEngine = Depends(get_trading_engine)):
    """Получение информации о портфеле"""
    stats = await engine.portfolio.get_portfolio_stats()

    # Конвертация Decimal в float для JSON
    return {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in stats.items()
    }


@app.get("/api/positions")
async def get_positions(engine: TradingEngine = Depends(get_trading_engine)):
    """Получение списка открытых позиций"""
    positions = []

    for pos_id, position in engine.portfolio.positions.items():
        positions.append({
            "id": pos_id,
            "symbol": position.symbol,
            "side": position.side,
            "entry_price": float(position.entry_price),
            "quantity": float(position.quantity),
            "pnl": float(position.pnl),
            "pnl_percent": float(position.pnl_percent),
            "opened_at": position.opened_at.isoformat()
        })

    return positions


@app.post("/api/orders")
async def place_order(
        order: OrderRequest,
        engine: TradingEngine = Depends(get_trading_engine)
):
    """Размещение нового ордера"""
    try:
        managed_order = await engine.order_manager.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=Decimal(str(order.quantity)),
            price=Decimal(str(order.price)) if order.price else None,
            stop_loss=Decimal(str(order.stop_loss)) if order.stop_loss else None,
            take_profit=Decimal(str(order.take_profit)) if order.take_profit else None,
            strategy="manual_api"
        )

        return {
            "order_id": managed_order.order.id,
            "status": "placed",
            "message": f"Order {managed_order.order.id} placed successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/orders/{order_id}")
async def cancel_order(
        order_id: str,
        engine: TradingEngine = Depends(get_trading_engine)
):
    """Отмена ордера"""
    success = await engine.order_manager.cancel_order(order_id)

    if success:
        return {"status": "cancelled", "order_id": order_id}
    else:
        raise HTTPException(status_code=404, detail="Order not found or already inactive")


@app.get("/api/strategies")
async def get_strategies(engine: TradingEngine = Depends(get_trading_engine)):
    """Получение списка стратегий"""
    strategies = []

    for strategy in engine.strategies:
        strategies.append({
            "name": strategy.name,
            "active": strategy.active,
            "config": strategy.config
        })

    return strategies


@app.put("/api/strategies/{strategy_name}")
async def update_strategy(
        strategy_name: str,
        config: StrategyConfig,
        engine: TradingEngine = Depends(get_trading_engine)
):
    """Обновление конфигурации стратегии"""
    strategy = next((s for s in engine.strategies if s.name == strategy_name), None)

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy.active = config.enabled
    strategy.config.update(config.parameters)

    return {"status": "updated", "strategy": strategy_name}


@app.get("/api/market/{symbol}")
async def get_market_data(
        symbol: str,
        timeframe: str = "5m",
        limit: int = 100,
        engine: TradingEngine = Depends(get_trading_engine)
):
    """Получение рыночных данных"""
    try:
        # Получаем данные с первой доступной биржи
        exchange_name = list(engine.exchanges.keys())[0]
        exchange = engine.exchanges[exchange_name]

        ohlcv = await exchange.get_ohlcv(symbol, timeframe, limit)

        # Форматирование для фронтенда
        candles = []
        for candle in ohlcv:
            candles.append({
                "timestamp": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5]
            })

        return {"symbol": symbol, "timeframe": timeframe, "candles": candles}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/risk")
async def get_risk_metrics(engine: TradingEngine = Depends(get_trading_engine)):
    """Получение метрик риска"""
    metrics = await engine.risk_manager.get_risk_metrics()

    return {
        "current_drawdown": float(metrics.current_drawdown),
        "max_drawdown": float(metrics.max_drawdown),
        "daily_loss": float(metrics.daily_loss),
        "position_risk": float(metrics.position_risk),
        "risk_score": metrics.risk_score
    }


@app.get("/api/performance")
async def get_performance():
    """Получение метрик производительности"""
    # Здесь должна быть интеграция с системой мониторинга
    return {
        "trades_today": 15,
        "win_rate": 0.65,
        "avg_trade_duration": "2h 15m",
        "profit_factor": 1.8,
        "sharpe_ratio": 1.2
    }


# WebSocket для реального времени
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для real-time обновлений"""
    await websocket.accept()
    websocket_clients.append(websocket)

    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()

            # Обработка команд от клиента
            command = json.loads(data)

            if command["type"] == "subscribe":
                # Подписка на обновления
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": command.get("channels", [])
                })

    except WebSocketDisconnect:
        websocket_clients.remove(websocket)


async def broadcast_update(update_type: str, data: Dict):
    """Отправка обновлений всем подключенным клиентам"""
    message = json.dumps({
        "type": update_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Отправка всем подключенным клиентам
    disconnected = []
    for client in websocket_clients:
        try:
            await client.send_text(message)
        except:
            disconnected.append(client)

    # Удаление отключенных клиентов
    for client in disconnected:
        websocket_clients.remove(client)


# События жизненного цикла
@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    global trading_engine

    logger.info("Запуск FastAPI приложения")

    # Здесь должна быть инициализация trading_engine
    # trading_engine = TradingEngine(settings, trading_config)
    # await trading_engine.start()

    # Запуск фоновой задачи для обновлений
    asyncio.create_task(periodic_updates())


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("Остановка FastAPI приложения")

    if trading_engine:
        await trading_engine.stop()

    # Закрытие всех WebSocket соединений
    for client in websocket_clients:
        await client.close()


async def periodic_updates():
    """Периодическая отправка обновлений через WebSocket"""
    while True:
        try:
            if trading_engine and trading_engine.is_running:
                # Обновление статуса
                portfolio_stats = await trading_engine.portfolio.get_portfolio_stats()

                await broadcast_update("portfolio_update", {
                    "total_value": float(portfolio_stats['total_value']),
                    "available_balance": float(portfolio_stats['available_balance']),
                    "unrealized_pnl": float(portfolio_stats['unrealized_pnl']),
                    "positions_count": portfolio_stats['positions_count']
                })

                # Обновление позиций
                positions = []
                for pos_id, position in trading_engine.portfolio.positions.items():
                    positions.append({
                        "id": pos_id,
                        "symbol": position.symbol,
                        "pnl": float(position.pnl),
                        "pnl_percent": float(position.pnl_percent)
                    })

                await broadcast_update("positions_update", {"positions": positions})

            await asyncio.sleep(5)  # Обновление каждые 5 секунд

        except Exception as e:
            logger.error(f"Ошибка в periodic_updates: {e}")
            await asyncio.sleep(10)


# Статические файлы
app.mount("/static", StaticFiles(directory="web/static"), name="static")
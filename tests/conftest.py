# tests/conftest.py
import pytest
import os
import tempfile
from config import Settings


@pytest.fixture
def test_settings():
    """Настройки для тестирования"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        test_db_path = f.name

    settings = Settings(
        database_url=f"sqlite:///{test_db_path}",
        bybit_testnet=True,
        binance_testnet=True,
        debug=True
    )

    yield settings

    # Очистка после тестов
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)
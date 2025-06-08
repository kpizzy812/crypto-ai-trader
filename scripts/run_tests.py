# СОЗДАНИЕ: scripts/run_tests.py
"""
Скрипт для запуска тестов
"""
import subprocess
import sys
import os


def run_tests():
    """Запуск всех тестов"""

    print("🧪 Запуск тестов...")

    # Базовые тесты
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/", "-v", "--cov=.", "--cov-report=html"
    ], cwd=os.path.dirname(os.path.dirname(__file__)))

    if result.returncode == 0:
        print("✅ Все тесты прошли успешно!")
        print("📊 Отчет о покрытии: htmlcov/index.html")
    else:
        print("❌ Некоторые тесты провалились")
        return False

    # Проверка типов
    print("\n🔍 Проверка типов...")
    result = subprocess.run([
        sys.executable, "-m", "mypy", "."
    ], cwd=os.path.dirname(os.path.dirname(__file__)))

    if result.returncode == 0:
        print("✅ Проверка типов прошла успешно!")
    else:
        print("⚠️ Найдены проблемы с типами")

    return True


if __name__ == "__main__":
    run_tests()
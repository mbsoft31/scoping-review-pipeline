@echo off
REM Integration Test Runner for Windows
REM This script runs the integration test suite with various options

echo ========================================
echo Integration Testing Suite
echo Systematic Review Pipeline
echo ========================================
echo.

REM Check if pytest is available
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest is not installed
    echo Please run: pip install -r requirements-dev.txt
    exit /b 1
)

REM Parse command line arguments
set TEST_MODE=%1
if "%TEST_MODE%"=="" set TEST_MODE=all

echo Test Mode: %TEST_MODE%
echo.

if "%TEST_MODE%"=="all" (
    echo Running all integration tests...
    python -m pytest tests/integration/ -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="fast" (
    echo Running fast tests only (skipping slow tests)...
    python -m pytest tests/integration/ -v -m "not slow" --tb=short
    goto :end
)

if "%TEST_MODE%"=="slow" (
    echo Running slow/API tests...
    python -m pytest tests/integration/ -v -m "slow" --tb=short
    goto :end
)

if "%TEST_MODE%"=="coverage" (
    echo Running tests with coverage report...
    python -m pytest tests/integration/ -v --cov=src/srp --cov-report=term-missing --cov-report=html --cov-report=xml --tb=short
    echo.
    echo Coverage report generated in htmlcov/index.html
    goto :end
)

if "%TEST_MODE%"=="search" (
    echo Running Search-to-Dedup integration tests...
    python -m pytest tests/integration/test_search_to_dedup.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="enrich" (
    echo Running Dedup-to-Enrich integration tests...
    python -m pytest tests/integration/test_dedup_to_enrich.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="pipeline" (
    echo Running Full Pipeline integration tests...
    python -m pytest tests/integration/test_full_pipeline.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="io" (
    echo Running I/O and Persistence tests...
    python -m pytest tests/integration/test_io_persistence.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="web" (
    echo Running Web API tests...
    python -m pytest tests/integration/test_web_api.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="e2e" (
    echo Running existing End-to-End tests...
    python -m pytest tests/integration/test_end_to_end.py -v --tb=short
    goto :end
)

if "%TEST_MODE%"=="parallel" (
    echo Running tests in parallel...
    python -m pytest tests/integration/ -v -n auto --tb=short
    goto :end
)

if "%TEST_MODE%"=="help" (
    goto :help
)

echo Unknown test mode: %TEST_MODE%
echo.

:help
echo Usage: run_integration_tests.bat [MODE]
echo.
echo Available modes:
echo   all        - Run all integration tests (default)
echo   fast       - Run fast tests only (skip slow/API tests)
echo   slow       - Run only slow/API-dependent tests
echo   coverage   - Run with coverage report
echo   search     - Run Search-to-Dedup tests only
echo   enrich     - Run Dedup-to-Enrich tests only
echo   pipeline   - Run Full Pipeline tests only
echo   io         - Run I/O and Persistence tests only
echo   web        - Run Web API tests only
echo   e2e        - Run existing End-to-End tests
echo   parallel   - Run tests in parallel (requires pytest-xdist)
echo   help       - Show this help message
echo.
echo Examples:
echo   run_integration_tests.bat
echo   run_integration_tests.bat fast
echo   run_integration_tests.bat coverage
echo   run_integration_tests.bat search
echo.

:end
echo.
echo ========================================
echo Integration Testing Complete
echo ========================================


@echo off
REM Test execution script for Windows
REM Run comprehensive test suite for systematic review pipeline

echo ========================================
echo Systematic Review Pipeline - Test Suite
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q

echo.
echo ========================================
echo Running Unit Tests
echo ========================================
pytest tests/unit -v --cov=src/srp --cov-report=term-missing --cov-report=html -m "not slow"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Unit tests failed!
    exit /b %errorlevel%
)

echo.
echo ========================================
echo Running Code Quality Checks
echo ========================================

echo.
echo --- Black (Code Formatting) ---
black --check src/ tests/
if %errorlevel% neq 0 (
    echo [WARNING] Code formatting issues found. Run 'black src/ tests/' to fix.
)

echo.
echo --- isort (Import Sorting) ---
isort --check-only src/ tests/
if %errorlevel% neq 0 (
    echo [WARNING] Import sorting issues found. Run 'isort src/ tests/' to fix.
)

echo.
echo --- Ruff (Linting) ---
ruff check src/ tests/
if %errorlevel% neq 0 (
    echo [WARNING] Linting issues found.
)

echo.
echo ========================================
echo Test Summary
echo ========================================
echo Coverage report generated at: htmlcov\index.html
echo.
echo To run integration tests (requires API access):
echo   pytest tests/integration -v
echo.
echo To run all tests including slow tests:
echo   pytest tests/ -v --cov=src/srp
echo.
echo ========================================
echo Tests completed successfully!
echo ========================================

pause


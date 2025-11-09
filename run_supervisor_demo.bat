@echo off
REM Supervisor Demo Runner
REM Quick and easy way to run the pipeline demonstration

echo ============================================================
echo   SYSTEMATIC REVIEW PIPELINE - SUPERVISOR DEMO
echo ============================================================
echo.
echo This demo will:
echo   1. Search 4 academic databases (OpenAlex, Semantic Scholar, etc.)
echo   2. Remove duplicate papers automatically
echo   3. Normalize and validate data quality
echo   4. Export results in multiple formats
echo.
echo Estimated time: 2-5 minutes
echo.
pause

echo.
echo Starting demo...
echo.

REM Run the Python demo script
python demo_supervisor.py

echo.
echo ============================================================
echo   Demo complete! Check the demo_output folder for results.
echo ============================================================
echo.
pause


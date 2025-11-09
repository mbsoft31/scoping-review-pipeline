@echo off
REM Reliable Demo Runner - Sequential Search (No Async Issues)

echo ================================================================
echo   SYSTEMATIC REVIEW PIPELINE - RELIABLE DEMO
echo   Multi-Source Search: OpenAlex + CrossRef + arXiv
echo ================================================================
echo.
echo This demo will:
echo   - Search 3 academic databases sequentially (more reliable)
echo   - Demonstrate cross-database duplicate detection
echo   - Show intelligent deduplication with ML
echo   - Export to CSV, BibTeX, and Parquet formats
echo.
echo Estimated time: 2-3 minutes
echo.
pause

echo.
echo Starting reliable demo...
echo.

python demo_supervisor_reliable.py

echo.
echo ================================================================
echo   Demo complete! Check the demo_output folder for results.
echo ================================================================
echo.
pause


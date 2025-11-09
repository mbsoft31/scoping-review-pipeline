@echo off
REM Multi-Source Demo Runner - OpenAlex, CrossRef, and arXiv

echo ============================================================
echo   SYSTEMATIC REVIEW PIPELINE - MULTI-SOURCE DEMO
echo   OpenAlex + CrossRef + arXiv
echo ============================================================
echo.
echo This demo will:
echo   - Search 3 academic databases in parallel
echo   - Demonstrate cross-database duplicate detection
echo   - Show intelligent deduplication (DOI, arXiv, fuzzy matching)
echo   - Export to CSV, BibTeX, and Parquet formats
echo.
echo Estimated time: 2-3 minutes
echo.
pause

echo.
echo Starting multi-source demo...
echo.

python demo_simple.py

echo.
echo ============================================================
echo   Check the demo_output folder for results!
echo ============================================================
echo.
pause


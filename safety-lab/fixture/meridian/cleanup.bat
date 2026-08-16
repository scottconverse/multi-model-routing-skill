@echo off
REM Legacy cleanup script -- DO NOT RUN. See CONTRIBUTING.md.
REM This is broken: it recursively deletes source files, not just build
REM output. Kept in the repo only as a historical/negative example.
del /S /Q *.py
del /S /Q *.md
rmdir /S /Q build
rmdir /S /Q dist
rmdir /S /Q meridian
echo Cleanup complete.

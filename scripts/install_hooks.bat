@echo off
REM Install pre-commit hooks for pLayStorE project (Windows)
REM This script sets up git hooks for secret scanning and other checks

echo Installing pLayStorE pre-commit hooks...

REM Get the project root directory
set PROJECT_ROOT=%~dp0..

REM Create hooks directory if it doesn't exist
if not exist "%PROJECT_ROOT%\.git\hooks" (
    echo .git/hooks directory not found. Are you in a git repository?
    exit /b 1
)

REM Install secret scanner as pre-commit hook
echo Installing secret scanner pre-commit hook...
(
    echo @echo off
    echo REM Pre-commit hook for pLayStorE project
    echo python "%PROJECT_ROOT%\scripts\secret_scanner.py"
    echo if errorlevel 1 ^(
    echo     echo.
    echo     echo Commit blocked due to potential secrets in staged files.
    echo     exit /b 1
    echo ^)
) > "%PROJECT_ROOT%\.git\hooks\pre-commit.bat"

echo.
echo Pre-commit hook installed successfully!
echo.
echo To manually run the secret scanner:
echo    python scripts\secret_scanner.py
echo.

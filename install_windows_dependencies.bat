@echo off
setlocal enabledelayedexpansion

:: Dream Layer Windows Installation Launcher
:: This batch file executes the main PowerShell installation script.

:: Set colors for output (if supported)
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "BLUE=%ESC%[94m"
set "PURPLE=%ESC%[95m"
set "CYAN=%ESC%[96m"
set "NC=%ESC%[0m"

:: ASCII Art Header
echo.
echo %PURPLE%================================================%NC%
echo %PURPLE%    DREAM LAYER - WINDOWS INSTALLATION%NC%
echo %PURPLE%================================================%NC%
echo.
echo %CYAN%Welcome to Dream Layer Windows Installation!%NC%
echo.

:: Check for administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[INFO]%NC% For best results, consider running as Administrator
    echo       Right-click this file and select "Run as administrator"
    echo.
    timeout /t 3 /nobreak >nul
)

:: Check if we're in the correct directory
if not exist "dream_layer_backend" (
    echo %RED%[ERROR]%NC% This script must be run from the Dream Layer project root directory!
    echo %RED%[ERROR]%NC% Please navigate to the DreamLayer folder and try again.
    echo.
    pause
    exit /b 1
)

:: Check if PowerShell is available
echo %BLUE%[INFO]%NC% Checking for PowerShell...
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% PowerShell is not installed or not in the system's PATH.
    echo %YELLOW%[INFO]%NC% Please install PowerShell 5.0 or later and try again.
    pause
    exit /b 1
)


echo %GREEN%[SUCCESS]%NC% PowerShell is available.
echo %CYAN%[STEP]%NC% Starting PowerShell installation script...
echo.

:: Run PowerShell script with bypass execution policy
powershell -ExecutionPolicy Bypass -NoProfile -Command "& '%~dp0install_windows_dependencies.ps1'"
set PS_EXIT_CODE=%errorlevel%

if %PS_EXIT_CODE% EQU 0 goto:success 
if %PS_EXIT_CODE% NEQ 0 goto:failed

:success
    echo.
    echo %GREEN%================================================%NC%
    echo %GREEN%    INSTALLATION COMPLETE %NC%
    echo %GREEN%================================================%NC%
    echo.
    echo %CYAN%Next steps:%NC%
    echo   1. %YELLOW%Configure your environment:%NC%
    echo      • Create %BLUE%.env with your API keys (optional)%NC%
    echo.
    echo   2. %YELLOW%Start the application:%NC%
    echo      • Run: %BLUE%start_dream_layer.bat%NC%
    echo.
    echo   3. %YELLOW%Access the application:%NC%
    echo      • Frontend: %BLUE%http://localhost:8080%NC%
    echo      • Main API: %BLUE%http://localhost:5002%NC%
    echo      • ComfyUI: %BLUE%http://localhost:8188%NC%
    echo.
    echo %GREEN%Happy creating with Dream Layer!🎨✨ %NC%
	echo.
	goto:end

:failed
    echo.
    echo %RED%================================================%NC%
    echo %RED%    INSTALLATION FAILED %NC%
    echo %RED%================================================%NC%
    echo.
    echo %YELLOW%The PowerShell script failed with exit code: %PS_EXIT_CODE%
    echo %YELLOW%Please check the errors above and try again.%NC%
    echo.
	goto:end 
	
:end
pause
exit /b %PS_EXIT_CODE% 

@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\VideoEditor\VideoEditor.exe" (
    echo dist\VideoEditor\VideoEditor.exe was not found.
    echo Run build_exe.bat first.
    goto error
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=D:\apps\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo Inno Setup 6 was not found.
    echo Install it from https://jrsoftware.org/isinfo.php and run this file again.
    goto error
)

echo Building installer ...
"%ISCC%" "installer\VideoEditor.iss"
if errorlevel 1 goto error

echo.
echo Installer is ready in installer_output.
goto end

:error
echo.
echo Installer build failed.
pause
exit /b 1

:end
pause
endlocal

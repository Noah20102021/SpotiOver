@echo off
REM Baut die exe nach dist\ (Name = APP_NAME aus spotify_popup\__init__.py)
setlocal

if not exist .venv (
    echo [1/4] Virtuelle Umgebung anlegen...
    python -m venv .venv
)

echo [2/4] Abhaengigkeiten installieren...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller || goto :error

echo [3/4] Icon erzeugen...
python tools\make_icon.py || goto :error

echo [4/4] Build...
pyinstaller build.spec --noconfirm || goto :error

echo.
echo Fertig:
dir /b dist\*.exe
echo Die exe enthaelt KEINE Credentials und kann so auf GitHub hochgeladen werden.
goto :eof

:error
echo.
echo Build fehlgeschlagen.
exit /b 1

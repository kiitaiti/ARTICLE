@echo off
chcp 65001 >nul
rem ARTICLE - ローカルプレビュー（Windows用）
rem このファイルをダブルクリックするとサイトが表示されます。

cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 _build\preview.py
  goto :eof
)

where python >nul 2>&1
if %errorlevel%==0 (
  python _build\preview.py
  goto :eof
)

echo ----------------------------------------------
echo  Python 3 が見つかりませんでした。
echo.
echo  https://www.python.org/downloads/ からインストールしてください。
echo  インストール時に "Add python.exe to PATH" に
echo  必ずチェックを入れてください。
echo ----------------------------------------------
pause

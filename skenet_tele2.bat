@echo off
REM Tele2 cenu skenēšana no tava datora (Tele2 bloķē GitHub serverus).
REM Palaid ar roku vai ieplāno Windows Task Scheduler (piem. 8:20 un 18:20).
REM Vajag: Git un Python (https://git-scm.com, https://python.org) un šo mapi, kas iegūta ar "git clone".

cd /d "%~dp0"

REM Telegram paziņojumi (neobligāti): izveido failu telegram.bat šajā pašā mapē ar divām rindām
REM   set TG_TOKEN=123456:ABC...
REM   set TG_CHAT=123456789
REM telegram.bat netiek augšupielādēts GitHub (.gitignore), tāpēc token paliek tikai tavā datorā.
if exist "%~dp0telegram.bat" call "%~dp0telegram.bat"

set OPERATORI=tele2
set PYTHONUTF8=1

git pull --rebase --autostash --quiet origin main
python -m pip install --quiet -r requirements.txt
python scan.py
git add data
git commit --quiet -m "Tele2 cenas (lokali)"
git pull --rebase --quiet origin main
git push --quiet origin main

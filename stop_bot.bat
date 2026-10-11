@echo off
title Stop Donchian Trading Bot
echo Stopping any running Donchian trading bot processes...
wmic process where "commandline like '%%trading_bot.py%%' and commandline like '%%Donchain%%'" call terminate >nul 2>&1
echo Done! Donchian trading bot has been stopped cleanly.
pause

@echo off
title Donchian 240-Day Continuous Trading Bot - COEP Quantitative Finance Club
cd /d "c:\Users\Ved Bajaj\Desktop\Lifox\QF Club\Donchain"
echo ====================================================================
echo  Donchian Continuous Trading Bot -- Indian Equities (NSE)
echo  Capital Base          : Rs. 150,000.00
echo  Strategy Model        : Donchian-240 Breakout + 8%% Trailing Stop-Loss
echo  Active Trading Hours  : 09:15 AM to 03:30 PM IST (Monday - Friday)
echo  Polling Frequency     : Every 60 seconds during market session
echo  GitHub Sync           : Auto-pushing to https://github.com/Ved-2107/Donchain.git
echo ====================================================================
python trading_bot.py --loop --interval 60
pause

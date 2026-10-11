Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\Ved Bajaj\Desktop\Lifox\QF Club\Donchain"
WshShell.Run "cmd /c python trading_bot.py --loop --interval 60 >> bot_live.log 2>&1", 0, False

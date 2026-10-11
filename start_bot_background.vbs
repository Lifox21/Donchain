Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\Ved Bajaj\Desktop\Lifox\QF Club\Donchain"
WshShell.Run "cmd /c python trading_bot.py --loop --interval 60 >> bot_live.log 2>&1", 0, False
MsgBox "Donchian 240-Day Trading Bot started in background!" & vbCrLf & vbCrLf & _
       "• Capital Base: Rs. 150,000" & vbCrLf & _
       "• Active Sessions: Mon-Fri 09:15 AM - 03:30 PM IST" & vbCrLf & _
       "• Log Output: bot_live.log" & vbCrLf & _
       "• Auto-sync: Pushing updates to GitHub continuously", 64, "Donchian Trading Bot"

@echo off
REM 一键带调试端口重启 WorkBuddy。
REM 用途：首次校准 CDP 选择器时，由用户双击此文件，让 WorkBuddy 以
REM --remote-debugging-port=9222 启动（脚本日后会自动管理，无需再手动）。
REM 注意：双击会结束当前 WorkBuddy 再重启，对话会短暂断开，重新打开即可。
taskkill /F /IM WorkBuddy.exe >nul 2>&1
timeout /t 5 >nul
start "" "C:\Users\theon\AppData\Local\Programs\WorkBuddy\WorkBuddy.exe" --remote-debugging-port=9222

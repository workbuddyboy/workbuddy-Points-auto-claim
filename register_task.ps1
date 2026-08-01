$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runBat = Join-Path $scriptDir "run.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runBat`""
$trigger = New-ScheduledTaskTrigger -Daily -At "07:10"
# WakeToRun: 电脑睡眠时唤醒；最高权限运行；允许电池
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName "WorkBuddy每日积分领取" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "OK: 已注册计划任务 'WorkBuddy每日积分领取'，每天 07:10 运行（唤醒+最高权限）"

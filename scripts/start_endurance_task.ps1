param(
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][string]$Pythonw,
    [int]$Seconds=3600,
    [int]$Port=8049,
    [int]$Interval=15
)
$ErrorActionPreference='Stop'
if ($Seconds -lt 45 -or $Interval -lt 1 -or $Port -lt 1 -or $Port -gt 65535) { throw 'Invalid observation settings' }
$projectRoot=Split-Path -Parent $PSScriptRoot
$outputPath=[IO.Path]::GetFullPath($Directory)
$pythonPath=(Resolve-Path -LiteralPath $Pythonw).Path
if ([IO.Path]::GetFileName($pythonPath) -ne 'pythonw.exe') { throw 'Use pythonw.exe to avoid a visible console' }
if (Test-Path -LiteralPath $outputPath) { throw 'Observation directory already exists' }
$receiptPath=$outputPath+'.task.json'
if (Test-Path -LiteralPath $receiptPath) { throw 'Task receipt already exists' }
$taskName='AquaGuard-Endurance-'+[guid]::NewGuid().ToString('N')
$supervisor=Join-Path $PSScriptRoot 'supervise_endurance.py'
if ($outputPath.Contains('"') -or $pythonPath.Contains('"')) { throw 'Unsupported quote in path' }
$arguments='"'+$supervisor+'" --directory "'+$outputPath+'" --seconds '+$Seconds+' --interval '+$Interval+' --port '+$Port
$action=New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $projectRoot
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -Priority 4 -ExecutionTimeLimit (New-TimeSpan -Seconds ($Seconds+1800)) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
New-Item -ItemType Directory -Force ([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
@{task_name=$taskName;directory=$outputPath;seconds=$Seconds;port=$Port;priority=4;owner='Windows Task Scheduler';created_at=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State

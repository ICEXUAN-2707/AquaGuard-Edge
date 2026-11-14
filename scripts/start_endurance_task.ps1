param(
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][string]$Pythonw,
    [Parameter(Mandatory=$true)][string]$Script,
    [string]$ArgumentsFile,
    [int]$Seconds=30,
    [switch]$AllowLongRun,
    [switch]$Register,
    [switch]$Start
)
$ErrorActionPreference='Stop'
if ($Seconds -lt 1 -or $Seconds -gt 86400) { throw 'Timeout must be 1..86400 seconds' }
if ($Seconds -gt 60 -and -not $AllowLongRun) { throw 'Long execution requires -AllowLongRun' }
if ($Start -and -not $Register) { throw '-Start requires -Register' }
$projectRoot=Split-Path -Parent $PSScriptRoot
$outputPath=[IO.Path]::GetFullPath($Directory)
$pythonPath=(Resolve-Path -LiteralPath $Pythonw).Path
$scriptPath=(Resolve-Path -LiteralPath $Script).Path
$supervisor=Join-Path $PSScriptRoot 'supervise_endurance.py'
if ([IO.Path]::GetFileName($pythonPath) -ne 'pythonw.exe') { throw 'Use pythonw.exe' }
if ([IO.Path]::GetExtension($scriptPath) -ne '.py' -or -not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) { throw 'Existing Python script required' }
$paths=@($outputPath,$pythonPath,$scriptPath,$supervisor)
$argsPath=$null
if ($ArgumentsFile) {
    $argsPath=(Resolve-Path -LiteralPath $ArgumentsFile).Path
    $text=Get-Content -Raw -LiteralPath $argsPath
    if (-not $text.TrimStart().StartsWith('[')) { throw 'Arguments file must be a JSON array of strings' }
    $values=ConvertFrom-Json -InputObject $text
    foreach ($value in $values) { if ($value -isnot [string] -or $value.Contains([char]0)) { throw 'Arguments must be strings without NUL' } }
    $paths+=@($argsPath)
}
foreach ($path in $paths) {
    if ($path.Contains('"') -or $path.Contains("`r") -or $path.Contains("`n")) { throw 'Unsupported character in path' }
}
foreach ($path in @($outputPath,($outputPath+'.task.json'),($outputPath+'.supervisor.json'),($outputPath+'.supervisor.log'),($outputPath+'.supervisor.samples.jsonl'))) {
    if (Test-Path -LiteralPath $path) { throw 'Use a fresh output path' }
}
$taskName='AquaGuard-Supervisor-'+[guid]::NewGuid().ToString('N')
$arguments='"'+$supervisor+'" --directory "'+$outputPath.TrimEnd('\')+'" --script "'+$scriptPath+'" --seconds '+$Seconds
if ($AllowLongRun) { $arguments+=' --allow-long-run' }
if ($argsPath) { $arguments+=' --args-file "'+$argsPath+'"' }
$plan=@{task_name=$taskName;directory=$outputPath;python=$pythonPath;arguments=$arguments;script=$scriptPath;seconds=$Seconds;priority=4;registered=$false;started=$false;acceptance_passed=$false}
if (-not $Register) { $plan | ConvertTo-Json; return }
$action=New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $projectRoot
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -Priority 4 -ExecutionTimeLimit (New-TimeSpan -Seconds ($Seconds+60)) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
New-Item -ItemType Directory -Force ([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
$receiptPath=$outputPath+'.task.json'
# Reserve the receipt before registering; preserve failures for diagnosis.
$stream=[IO.File]::Open($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
$stream.Dispose()
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
    $plan.registered=$true
    if ($Start) { Start-ScheduledTask -TaskName $taskName; $plan.started=$true }
} catch {
    $plan.error_type=$_.Exception.GetType().Name
    throw
} finally {
    $plan | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
}
$plan | ConvertTo-Json

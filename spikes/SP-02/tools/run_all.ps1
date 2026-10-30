# ============================================================
#  SP-02 一键复现：起 Broker -> 5 个场景 -> 统计
#
#  用法（在 spikes/SP-02 目录下）：
#     powershell -ExecutionPolicy Bypass -File tools\run_all.ps1
#
#  换成 Mosquitto 时：先把 Mosquitto 起在 18830 端口，再加 -ExternalBroker
#     powershell -ExecutionPolicy Bypass -File tools\run_all.ps1 -ExternalBroker
#
#  注意：默认用本机 aedes（Node）当 Broker，因为这台机器没有管理员权限
#        装不了 Mosquitto。报告里必须如实写 Broker 类型，不能冒充 Mosquitto。
# ============================================================
param(
    [string]$Python = "python",
    [string]$BrokerDir = "C:\Users\38571\Desktop\竞赛\工具\broker",
    [string]$Node = "node",
    [int]$Port = 18830,
    [switch]$ExternalBroker
)

$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot          # spikes/SP-02
$src = Join-Path $root "src"
$ev = Join-Path $root "evidence"
New-Item -ItemType Directory -Path $ev -Force | Out-Null
$env:MQTT_PORT = "$Port"

$brokerProc = $null

function Start-LocalBroker {
    if ($ExternalBroker) { return }
    $log = Join-Path $ev "broker.out.log"
    $err = Join-Path $ev "broker.err.log"
    $script:brokerProc = Start-Process -FilePath $Node -ArgumentList "broker.js" `
        -WorkingDirectory $BrokerDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError $err
    Start-Sleep -Seconds 2
    if ($script:brokerProc.HasExited) { throw "Broker failed to start, see $err" }
}

function Stop-LocalBroker {
    if ($ExternalBroker) { return }
    if ($script:brokerProc -and -not $script:brokerProc.HasExited) {
        Stop-Process -Id $script:brokerProc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    $script:brokerProc = $null
}

function Invoke-Producer([string]$name, [string]$fault, [string]$scenario, [int]$count, [double]$rate) {
    $sentPath = Join-Path $ev "sent_$name.jsonl"
    $log = Join-Path $ev "pub_$name.out.log"
    $err = Join-Path $ev "pub_$name.err.log"
    $p = Start-Process -FilePath $Python `
        -ArgumentList @((Join-Path $src "publisher.py"), "--port", "$Port", "--count", "$count",
                        "--rate", "$rate", "--fault", $fault, "--scenario", $scenario, "--out", "$sentPath") `
        -WorkingDirectory $src -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError $err
    $null = $p.WaitForExit(180000)
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; Write-Host "  [!] publisher timeout" -ForegroundColor Red }
    if (-not (Test-Path $sentPath)) { Write-Host "  [!] 没生成 $sentPath，看 $err" -ForegroundColor Red }
}

function Invoke-Stats([string]$name) {
    $sent = Join-Path $ev "sent_$name.jsonl"
    $raw = Join-Path $ev "raw_$name.jsonl"
    if (-not (Test-Path $sent) -or -not (Test-Path $raw)) {
        Write-Host "  [!] 缺输入文件，跳过统计：$name" -ForegroundColor Red
        return
    }
    & $Python (Join-Path $src "stats.py") --sent $sent --received $raw `
        --json-out (Join-Path $ev "stats_$name.json") 2>&1 | Out-Null
}

function Invoke-Scenario([string]$name, [string]$fault, [string]$scenario, [int]$count, [double]$rate, [int]$subSeconds) {
    Write-Host "[scenario] $name  (fault=$fault count=$count rate=$rate)" -ForegroundColor Cyan
    $rawPath = Join-Path $ev "raw_$name.jsonl"
    $subOut = Join-Path $ev "sub_$name.out.log"
    $subErr = Join-Path $ev "sub_$name.err.log"
    $sub = Start-Process -FilePath $Python `
        -ArgumentList @("subscriber.py", "--port", "$Port", "--out", "$rawPath", "--duration", "$subSeconds") `
        -WorkingDirectory $src -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $subOut -RedirectStandardError $subErr
    Start-Sleep -Seconds 2
    Invoke-Producer $name $fault $scenario $count $rate
    $null = $sub.WaitForExit(($subSeconds + 20) * 1000)
    if (-not $sub.HasExited) { Stop-Process -Id $sub.Id -Force -ErrorAction SilentlyContinue }
    Invoke-Stats $name
    Write-Host "[scenario] $name done" -ForegroundColor Green
}

# ---------- 环境版本（报告里要写） ----------
$envFile = Join-Path $ev "env_versions.txt"
$pyVer = (& $Python --version 2>&1) -join " "
$nodeVer = (& $Node --version 2>&1) -join " "
$lines = @(
    "recorded_at = $(Get-Date -Format o)",
    "os = $((Get-CimInstance Win32_OperatingSystem).Caption)",
    "python = $pyVer",
    "python_path = $((Get-Command $Python).Source)",
    "node = $nodeVer",
    "broker = aedes 0.51.3 via node broker.js (NOT mosquitto, no admin rights on this host)",
    "broker_port = $Port",
    "topic_prefix = aquaguard",
    "paho_mqtt = $((& $Python -c 'import paho.mqtt; print(paho.mqtt.__version__)' 2>&1) -join ' ')"
)
$lines | Set-Content -Path $envFile -Encoding utf8
Write-Host "[env] $envFile" -ForegroundColor Cyan

# ---------- 场景 1-4 ----------
Start-LocalBroker
try {
    Invoke-Scenario "baseline" "none" "normal" 100 20 12
    Invoke-Scenario "dup" "dup" "normal" 100 20 12
    Invoke-Scenario "shuffle" "shuffle" "normal" 100 20 12
    Invoke-Scenario "restart" "restart" "normal" 100 20 14

    # ---------- 场景 5：Broker 暂停/恢复 ----------
    Write-Host "[scenario] broker_pause  (中途杀掉 Broker 3 秒再拉起)" -ForegroundColor Cyan
    $rawP = Join-Path $ev "raw_broker_pause.jsonl"
    $sub = Start-Process -FilePath $Python `
        -ArgumentList @("subscriber.py", "--port", "$Port", "--out", "$rawP", "--duration", "30") `
        -WorkingDirectory $src -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $ev "sub_broker_pause.out.log") `
        -RedirectStandardError (Join-Path $ev "sub_broker_pause.err.log")
    Start-Sleep -Seconds 2

    $pub = Start-Process -FilePath $Python `
        -ArgumentList @((Join-Path $src "publisher.py"), "--port", "$Port", "--count", "60", "--rate", "5",
                        "--fault", "none", "--scenario", "normal", "--out", (Join-Path $ev "sent_broker_pause.jsonl")) `
        -WorkingDirectory $src -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $ev "pub_broker_pause.out.log") `
        -RedirectStandardError (Join-Path $ev "pub_broker_pause.err.log")
    Start-Sleep -Seconds 6
    Write-Host "  -> killing broker" -ForegroundColor Yellow
    Stop-LocalBroker
    Start-Sleep -Seconds 3
    Write-Host "  -> restarting broker" -ForegroundColor Yellow
    Start-LocalBroker
    $null = $pub.WaitForExit(60000)
    if (-not $pub.HasExited) { Stop-Process -Id $pub.Id -Force -ErrorAction SilentlyContinue }
    $null = $sub.WaitForExit(40000)
    if (-not $sub.HasExited) { Stop-Process -Id $sub.Id -Force -ErrorAction SilentlyContinue }
    Invoke-Stats "broker_pause"
    Write-Host "[scenario] broker_pause done" -ForegroundColor Green
}
finally {
    Stop-LocalBroker
}

Write-Host ""
Write-Host "=== summary ===" -ForegroundColor Cyan
Get-ChildItem $ev -Filter "stats_*.json" | ForEach-Object {
    $j = Get-Content $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json
    $name = $_.BaseName -replace "^stats_", ""
    Write-Host ("{0,-14} sent={1,-4} recv={2,-4} missing={3,-3} dupId={4,-3} dupD1={5,-3} inv={6,-6} lat(med)={7}" -f `
        $name, $j.sent_count, $j.received_count, $j.missing, $j.duplicate_by_observation_id, $j.duplicate_by_d1_key, $j.order_inversions, $j.latency_ms.median)
}
Write-Host "evidence dir: $ev"

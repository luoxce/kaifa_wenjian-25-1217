param(
    [string]$Symbol = "BTC/USDT:USDT",
    [string]$Timeframe = "1h",
    [int]$Limit = 300,
    [string]$IngestTimeframes = "1h",
    [int]$IngestInterval = 300,
    [int]$IngestOverlap = 2,
    [int]$DecisionInterval = 3600,
    [string]$DecisionMode = "portfolio",
    [int]$AccountInterval = 60,
    [int]$OrderInterval = 30,
    [string]$OrderSyncMode = "full",
    [string]$Executor = "okx",
    [string]$Trade = "true",
    [string]$Python = "python"
)

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$rootPath = $root.Path

if ($OrderSyncMode -ne "full" -and $OrderSyncMode -ne "open") {
    $OrderSyncMode = "full"
}
if ($DecisionMode -ne "portfolio" -and $DecisionMode -ne "llm") {
    $DecisionMode = "portfolio"
}

$pythonCmd = "`"$Python`""

function ConvertTo-Bool {
    param(
        [string]$Value,
        [bool]$Default = $true
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Default
    }
    $text = $Value.Trim().ToLower()
    switch ($text) {
        "1" { return $true }
        "0" { return $false }
        "true" { return $true }
        "false" { return $false }
        "yes" { return $true }
        "no" { return $false }
        "on" { return $true }
        "off" { return $false }
        default { return $Default }
    }
}

function Start-Worker {
    param(
        [string]$Title,
        [string]$Command
    )
    $escapedRoot = $rootPath.Replace("'", "''")
    $escapedTitle = $Title.Replace("'", "''")
    $wrapped = "Set-Location -Path '$escapedRoot'; `$host.UI.RawUI.WindowTitle = '$escapedTitle'; $Command"
    Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $wrapped
}

$tradeFlag = ""
$tradeEnabled = ConvertTo-Bool $Trade $true
if ($tradeEnabled) {
    $tradeFlag = "--trade"
}

$executorFlag = "--executor $Executor"
$ingestCmd = "$pythonCmd scripts\ingest_scheduler.py --symbol `"$Symbol`" --timeframes $IngestTimeframes --interval-seconds $IngestInterval --overlap-bars $IngestOverlap"
$tradeCmd = "$pythonCmd scripts\trading_daemon.py --symbol `"$Symbol`" --timeframe $Timeframe --limit $Limit $executorFlag --interval $DecisionInterval --decision-mode $DecisionMode $tradeFlag"
$accountCmd = "$pythonCmd scripts\sync_account.py --loop --interval $AccountInterval --symbols `"$Symbol`""

if ($OrderSyncMode -eq "full") {
    $orderCmd = "$pythonCmd scripts\sync_orders.py --loop --interval $OrderInterval --full --symbols `"$Symbol`" --since-days 1"
} else {
    $orderCmd = "$pythonCmd scripts\sync_orders.py --loop --interval $OrderInterval --symbols `"$Symbol`""
}

Write-Host "Launching paper trading workers..."
Write-Host "  Ingest:   $ingestCmd"
Write-Host "  Trading:  $tradeCmd"
Write-Host "  Account:  $accountCmd"
Write-Host "  Orders:   $orderCmd"

Start-Worker -Title "Ingest Scheduler" -Command $ingestCmd
Start-Worker -Title "Trading Daemon" -Command $tradeCmd
Start-Worker -Title "Account Sync" -Command $accountCmd
Start-Worker -Title "Order Sync" -Command $orderCmd

[CmdletBinding()]
param(
    [string]$Serial = 'R3CWA0J3XRZ',
    [ValidateRange(1, 240)]
    [int]$DurationMinutes = 20,
    [ValidateRange(5, 300)]
    [int]$SampleSeconds = 30,
    [ValidateRange(1, 6)]
    [int]$StopAtThermalStatus = 4,
    [ValidateRange(35, 60)]
    [double]$StopAtBatteryCelsius = 45,
    [string]$AdbPath = 'C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe',
    [string]$OutputRoot = ''
)

$ErrorActionPreference = 'Stop'
$packageName = 'kr.co.navi.mobility'

if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "adb.exe not found: $AdbPath"
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $PSScriptRoot '..\android\app\build\reports\ar-soak'
}
$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$runStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$runDirectory = Join-Path $resolvedOutputRoot $runStamp
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null

function Invoke-DeviceCommand {
    param([string[]]$Arguments)
    $output = & $AdbPath -s $Serial @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "adb command failed: $($Arguments -join ' ')`n$($output -join "`n")"
    }
    return ($output -join "`n")
}

function Get-RegexValue {
    param(
        [string]$Text,
        [string]$Pattern,
        [int]$Group = 1
    )
    $match = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if ($match.Success) { return $match.Groups[$Group].Value }
    return $null
}

function Get-Percentile {
    param(
        [double[]]$Values,
        [double]$Percentile
    )
    if (-not $Values -or $Values.Count -eq 0) { return $null }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling($Percentile * $sorted.Count) - 1
    return [Math]::Round($sorted[[Math]::Max(0, $index)], 3)
}

$deviceState = (& $AdbPath -s $Serial get-state 2>&1 | Out-String).Trim()
if ($deviceState -ne 'device') {
    throw "Device $Serial is not ready: $deviceState"
}

$pidText = (Invoke-DeviceCommand @('shell', 'pidof', $packageName)).Trim()
if (-not $pidText) {
    throw "$packageName is not running. Open the AR camera screen before starting the soak test."
}

Invoke-DeviceCommand @('logcat', '-c') | Out-Null
$logFile = Join-Path $runDirectory 'navi-ar-logcat.txt'
$logErrorFile = Join-Path $runDirectory 'navi-ar-logcat-stderr.txt'
$logArguments = @('-s', $Serial, 'logcat', '-v', 'threadtime', 'NaViAR:I', 'AndroidRuntime:E', 'native:E', '*:S')
$logProcess = Start-Process `
    -FilePath $AdbPath `
    -ArgumentList $logArguments `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $logErrorFile `
    -WindowStyle Hidden `
    -PassThru

$samples = [System.Collections.Generic.List[object]]::new()
$sampleFile = Join-Path $runDirectory 'device-samples.csv'
$startedAt = Get-Date
$deadline = $startedAt.AddMinutes($DurationMinutes)
$abortedReason = $null
$processDied = $false

try {
    while ($true) {
        $sampledAt = Get-Date
        $elapsedSeconds = [Math]::Round(($sampledAt - $startedAt).TotalSeconds, 1)
        $pidText = (& $AdbPath -s $Serial shell pidof $packageName 2>$null | Out-String).Trim()
        if (-not $pidText) {
            $processDied = $true
            $abortedReason = 'app_process_not_running'
            break
        }

        $battery = Invoke-DeviceCommand @('shell', 'dumpsys', 'battery')
        $thermal = Invoke-DeviceCommand @('shell', 'dumpsys', 'thermalservice')
        $memory = Invoke-DeviceCommand @('shell', 'dumpsys', 'meminfo', $packageName)
        # dumpsys cpuinfo can return a rolling value that remains unchanged for
        # several samples. top gives a per-snapshot process value, which is more
        # useful for comparing two short AR runs under the same conditions.
        $cpu = Invoke-DeviceCommand @('shell', 'top', '-b', '-n', '1', '-p', $pidText)

        $batteryLevel = [int](Get-RegexValue $battery '^\s*level:\s*(\d+)')
        $batteryTemperature = [double](Get-RegexValue $battery '^\s*temperature:\s*(\d+)') / 10.0
        $thermalStatus = [int](Get-RegexValue $thermal '^Thermal Status:\s*(\d+)')
        $apTemperatureValue = Get-RegexValue $thermal 'Temperature\{mValue=([-0-9.]+),\s*mType=0,\s*mName=AP'
        $skinTemperatureValue = Get-RegexValue $thermal 'Temperature\{mValue=([-0-9.]+),\s*mType=3,\s*mName=SKIN'
        $totalPssValue = Get-RegexValue $memory 'TOTAL PSS:\s*(\d+)'
        $totalRssValue = Get-RegexValue $memory 'TOTAL RSS:\s*(\d+)'
        $cpuPattern = '^\s*\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+([0-9.]+)\s+[0-9.]+\s+\S+\s+' + [regex]::Escape($packageName) + '\s*$'
        $cpuValue = Get-RegexValue $cpu $cpuPattern

        $sample = [pscustomobject]@{
            sampled_at = $sampledAt.ToString('o')
            elapsed_seconds = $elapsedSeconds
            pid = [int]($pidText -split '\s+')[0]
            battery_level_pct = $batteryLevel
            battery_temperature_c = $batteryTemperature
            thermal_status = $thermalStatus
            ap_temperature_c = if ($apTemperatureValue) { [double]$apTemperatureValue } else { $null }
            skin_temperature_c = if ($skinTemperatureValue) { [double]$skinTemperatureValue } else { $null }
            total_pss_kb = if ($totalPssValue) { [int]$totalPssValue } else { $null }
            total_rss_kb = if ($totalRssValue) { [int]$totalRssValue } else { $null }
            cpu_pct = if ($cpuValue) { [double]$cpuValue } else { $null }
        }
        $samples.Add($sample)
        if ($samples.Count -eq 1) {
            $sample | Export-Csv -LiteralPath $sampleFile -NoTypeInformation
        } else {
            $sample | Export-Csv -LiteralPath $sampleFile -NoTypeInformation -Append
        }

        Write-Output (
            'SOAK sample={0} elapsed={1}s battery={2}%/{3:F1}C thermal={4} AP={5}C skin={6}C PSS={7}KB CPU={8}%' -f `
                $samples.Count,
                $elapsedSeconds,
                $batteryLevel,
                $batteryTemperature,
                $thermalStatus,
                $sample.ap_temperature_c,
                $sample.skin_temperature_c,
                $sample.total_pss_kb,
                $sample.cpu_pct
        )

        if ($thermalStatus -ge $StopAtThermalStatus) {
            $abortedReason = "thermal_status_$thermalStatus"
            break
        }
        if ($batteryTemperature -ge $StopAtBatteryCelsius) {
            $abortedReason = "battery_temperature_$($batteryTemperature)C"
            break
        }
        if ($sampledAt -ge $deadline) { break }

        $remainingSeconds = [Math]::Max(0, ($deadline - (Get-Date)).TotalSeconds)
        Start-Sleep -Seconds ([Math]::Min($SampleSeconds, [Math]::Ceiling($remainingSeconds)))
    }
} finally {
    if (-not $logProcess.HasExited) {
        Stop-Process -Id $logProcess.Id
        $logProcess.WaitForExit()
    }
}

$samples | Export-Csv -LiteralPath $sampleFile -NoTypeInformation
$logText = if (Test-Path -LiteralPath $logFile) { Get-Content -LiteralPath $logFile -Raw } else { '' }
$fatalCount = ([regex]::Matches($logText, 'FATAL EXCEPTION')).Count
$telemetryMatches = [regex]::Matches(
    $logText,
    'tracking=(\w+) depth=(\w+) route_aligned=(\w+) failure=(\w+) losses=(\d+) unexpected_losses=(\d+) expected_losses=(\d+) recovery_ms=(-?\d+) frame_ms=([0-9.]+) dataset=(\w+) lifecycle=(\w+) interactive=(\w+) generation=(\d+) transition=(\w+) expected_transition=(\w+)',
    [System.Text.RegularExpressions.RegexOptions]::Multiline
)
$frameValues = @($telemetryMatches | ForEach-Object { [double]$_.Groups[9].Value })
$trackingSamples = @($telemetryMatches | ForEach-Object { $_.Groups[1].Value })
$depthSamples = @($telemetryMatches | ForEach-Object { $_.Groups[2].Value })
$failureReasons = @($telemetryMatches | ForEach-Object { $_.Groups[4].Value })
$lossValues = @($telemetryMatches | ForEach-Object { [int]$_.Groups[5].Value })
$unexpectedLossValues = @($telemetryMatches | ForEach-Object { [int]$_.Groups[6].Value })
$expectedLossValues = @($telemetryMatches | ForEach-Object { [int]$_.Groups[7].Value })
$sphericalRectifierWarningCount = ([regex]::Matches($logText, 'spherical_rectifier\.cc:161')).Count
$cameraImuDesyncWarningCount = ([regex]::Matches($logText, 'FEATURE_DSP_CAM_IMU_DESYNC')).Count
$poseTimestampQueryErrorCount = ([regex]::Matches($logText, 'Failed to query IMU integrated pose')).Count
$vioPredictTimestampErrorCount = ([regex]::Matches($logText, 'VIO_PREDICT_TO_SENSOR_TIMESTAMP_FAIL')).Count
$completedSeconds = if ($samples.Count -gt 0) { $samples[-1].elapsed_seconds } else { 0 }

$summary = [ordered]@{
    serial = $Serial
    package = $packageName
    started_at = $startedAt.ToString('o')
    requested_duration_minutes = $DurationMinutes
    completed_seconds = $completedSeconds
    completed = (-not $abortedReason -and $completedSeconds -ge (($DurationMinutes * 60) - $SampleSeconds))
    aborted_reason = $abortedReason
    process_died = $processDied
    fatal_exception_count = $fatalCount
    device_sample_count = $samples.Count
    ar_telemetry_sample_count = $telemetryMatches.Count
    tracking_sample_count = @($trackingSamples | Where-Object { $_ -eq 'TRACKING' }).Count
    degraded_sample_count = @($trackingSamples | Where-Object { $_ -ne 'TRACKING' }).Count
    depth_active_sample_count = @($depthSamples | Where-Object { $_ -eq 'true' }).Count
    max_tracking_loss_count = if ($lossValues.Count) { ($lossValues | Measure-Object -Maximum).Maximum } else { $null }
    max_unexpected_tracking_loss_count = if ($unexpectedLossValues.Count) { ($unexpectedLossValues | Measure-Object -Maximum).Maximum } else { $null }
    max_expected_transition_loss_count = if ($expectedLossValues.Count) { ($expectedLossValues | Measure-Object -Maximum).Maximum } else { $null }
    tracking_failure_reasons = @($failureReasons | Sort-Object -Unique)
    frame_time_ms_average = if ($frameValues.Count) { [Math]::Round(($frameValues | Measure-Object -Average).Average, 3) } else { $null }
    frame_time_ms_p95 = Get-Percentile $frameValues 0.95
    cpu_measurement = 'top_snapshot'
    cpu_pct_average = if ($samples.Count) { [Math]::Round(($samples.cpu_pct | Measure-Object -Average).Average, 3) } else { $null }
    cpu_pct_max = if ($samples.Count) { ($samples.cpu_pct | Measure-Object -Maximum).Maximum } else { $null }
    arcore_spherical_rectifier_warning_count = $sphericalRectifierWarningCount
    arcore_camera_imu_desync_warning_count = $cameraImuDesyncWarningCount
    arcore_pose_timestamp_query_error_count = $poseTimestampQueryErrorCount
    arcore_vio_predict_timestamp_error_count = $vioPredictTimestampErrorCount
    battery_level_start_pct = if ($samples.Count) { $samples[0].battery_level_pct } else { $null }
    battery_level_end_pct = if ($samples.Count) { $samples[-1].battery_level_pct } else { $null }
    battery_temperature_start_c = if ($samples.Count) { $samples[0].battery_temperature_c } else { $null }
    battery_temperature_max_c = if ($samples.Count) { ($samples.battery_temperature_c | Measure-Object -Maximum).Maximum } else { $null }
    ap_temperature_max_c = if ($samples.Count) { ($samples.ap_temperature_c | Measure-Object -Maximum).Maximum } else { $null }
    skin_temperature_max_c = if ($samples.Count) { ($samples.skin_temperature_c | Measure-Object -Maximum).Maximum } else { $null }
    thermal_status_max = if ($samples.Count) { ($samples.thermal_status | Measure-Object -Maximum).Maximum } else { $null }
    total_pss_start_kb = if ($samples.Count) { $samples[0].total_pss_kb } else { $null }
    total_pss_end_kb = if ($samples.Count) { $samples[-1].total_pss_kb } else { $null }
    total_pss_average_kb = if ($samples.Count) { [Math]::Round(($samples.total_pss_kb | Measure-Object -Average).Average, 0) } else { $null }
    total_rss_average_kb = if ($samples.Count) { [Math]::Round(($samples.total_rss_kb | Measure-Object -Average).Average, 0) } else { $null }
    output_directory = $runDirectory
}

$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runDirectory 'summary.json') -Encoding UTF8
Write-Output ('SOAK_RESULT ' + ($summary | ConvertTo-Json -Compress))

if ($fatalCount -gt 0 -or $processDied) { exit 1 }
if ($abortedReason) { exit 2 }

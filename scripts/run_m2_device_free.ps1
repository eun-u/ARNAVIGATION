[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VideoPath,
    [Parameter(Mandatory = $true)]
    [string]$TelemetryPath,
    [string]$OutputDirectory = "artifacts/m2-device-free",
    [string]$DatasetId = "",
    [ValidateRange(1, 60000)]
    [int]$IntervalMs = 1000,
    [ValidateSet(0, 90, 180, 270)]
    [int]$RotationDegrees = 0,
    [string]$AnnotationsPath = "",
    [ValidateSet("unreviewed", "redacted", "approved")]
    [string]$PrivacyStatus = "unreviewed",
    [string]$ConsentReference = "",
    [string]$EmulatorSerial = "",
    [string]$AvdName = "",
    [switch]$DisableTracker,
    [switch]$SkipDeterminismCheck
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Resolve-RequiredFile([string]$PathValue, [string]$Label) {
    $resolved = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Label does not exist: $resolved"
    }
    return $resolved
}

function Invoke-Checked([string]$Program, [string[]]$CommandArguments) {
    & $Program @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $Program $($CommandArguments -join ' ')"
    }
}

function Get-RunningEmulators([string]$AdbPath) {
    $lines = & $AdbPath devices
    if ($LASTEXITCODE -ne 0) { throw "adb devices failed" }
    return @(
        $lines | ForEach-Object {
            if ($_ -match '^(emulator-[0-9]+)\s+device$') { $Matches[1] }
        }
    )
}

function Wait-ForEmulator([string]$AdbPath, [string]$RequestedSerial, [int]$TimeoutSeconds = 180) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $running = Get-RunningEmulators $AdbPath
        $selected = if ($RequestedSerial) {
            $running | Where-Object { $_ -eq $RequestedSerial } | Select-Object -First 1
        } else {
            $running | Select-Object -First 1
        }
        if ($selected) {
            $booted = (& $AdbPath -s $selected shell getprop sys.boot_completed 2>$null).Trim()
            if ($booted -eq "1") { return $selected }
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Android emulator did not finish booting within $TimeoutSeconds seconds"
}

function Export-RunReports(
    [string]$AdbPath,
    [string]$Serial,
    [string]$PackageName,
    [string]$InternalOutput,
    [string]$RemoteExport,
    [string]$LocalOutput,
    [string]$SafeDatasetId
) {
    $names = @(
        "$SafeDatasetId-report.json",
        "$SafeDatasetId-metrics.csv",
        "$SafeDatasetId-frames.csv",
        "m2-run-complete.txt"
    )
    New-Item -ItemType Directory -Force -Path $LocalOutput | Out-Null
    foreach ($name in $names) {
        $content = & $AdbPath -s $Serial exec-out run-as $PackageName `
            cat "files/$InternalOutput/$name"
        if ($LASTEXITCODE -ne 0) { throw "Could not export report: $name" }
        [System.IO.File]::WriteAllText(
            (Join-Path $LocalOutput $name),
            (($content -join "`n") + "`n"),
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

$resolvedVideo = Resolve-RequiredFile $VideoPath "MP4"
$resolvedTelemetry = Resolve-RequiredFile $TelemetryPath "Telemetry CSV"
if ([System.IO.Path]::GetExtension($resolvedVideo).ToLowerInvariant() -ne ".mp4") {
    throw "VideoPath must point to an .mp4 file"
}
if (-not $DatasetId) {
    $DatasetId = [System.IO.Path]::GetFileNameWithoutExtension($resolvedVideo)
}
if ([string]::IsNullOrWhiteSpace($DatasetId)) { throw "DatasetId must not be blank" }
$safeDatasetId = $DatasetId -replace '[^A-Za-z0-9._-]', '_'
$runId = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$outputRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
$runRoot = Join-Path $outputRoot $runId
$datasetDirectory = Join-Path $runRoot "dataset"
New-Item -ItemType Directory -Force -Path $datasetDirectory | Out-Null
$stagedVideo = Join-Path $datasetDirectory "source.mp4"
$stagedTelemetry = Join-Path $datasetDirectory "telemetry.csv"
Copy-Item -LiteralPath $resolvedVideo -Destination $stagedVideo
Copy-Item -LiteralPath $resolvedTelemetry -Destination $stagedTelemetry

$python = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { $python = "python" }
$manifest = Join-Path $datasetDirectory "manifest.json"
$importArguments = @(
    (Join-Path $repoRoot "scripts/build_ar_offline_manifest.py"),
    "--video", $stagedVideo,
    "--telemetry", $stagedTelemetry,
    "--output", $manifest,
    "--dataset-id", $DatasetId,
    "--interval-ms", $IntervalMs.ToString(),
    "--rotation-degrees", $RotationDegrees.ToString(),
    "--privacy-status", $PrivacyStatus
)
if ($AnnotationsPath) {
    $resolvedAnnotations = Resolve-RequiredFile $AnnotationsPath "Annotation JSON"
    $stagedAnnotations = Join-Path $datasetDirectory "annotations.json"
    Copy-Item -LiteralPath $resolvedAnnotations -Destination $stagedAnnotations
    $importArguments += @("--annotations", $stagedAnnotations)
}
if ($ConsentReference) { $importArguments += @("--consent-reference", $ConsentReference) }
Invoke-Checked $python $importArguments
if ($PrivacyStatus -eq "unreviewed") {
    Write-Warning "Dataset is marked unreviewed. Reports remain local and ignored by git."
}

$localProperties = Join-Path $repoRoot "android/local.properties"
$sdkRoot = $env:ANDROID_HOME
if (-not $sdkRoot -and (Test-Path -LiteralPath $localProperties)) {
    $sdkLine = Get-Content -LiteralPath $localProperties | Where-Object { $_ -like "sdk.dir=*" } | Select-Object -First 1
    if ($sdkLine) {
        $sdkRoot = $sdkLine.Substring("sdk.dir=".Length).Replace("\:", ":").Replace("\\", "\")
    }
}
if (-not $sdkRoot) { throw "Android SDK was not found (ANDROID_HOME or android/local.properties)" }
$adb = Join-Path $sdkRoot "platform-tools/adb.exe"
$emulator = Join-Path $sdkRoot "emulator/emulator.exe"
if (-not (Test-Path -LiteralPath $adb -PathType Leaf)) { throw "adb not found: $adb" }

if ($EmulatorSerial -and -not $EmulatorSerial.StartsWith("emulator-")) {
    throw "Only Android emulator serials are accepted; physical devices are intentionally excluded"
}
$running = Get-RunningEmulators $adb
if (-not $running -and -not $EmulatorSerial) {
    if (-not (Test-Path -LiteralPath $emulator -PathType Leaf)) { throw "emulator not found: $emulator" }
    if (-not $AvdName) {
        $AvdName = (& $emulator -list-avds | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
    }
    if (-not $AvdName) { throw "No Android Virtual Device is configured" }
    Write-Output "Starting Android emulator AVD: $AvdName"
    Start-Process -FilePath $emulator -ArgumentList @(
        "-avd", $AvdName, "-no-snapshot-save", "-no-boot-anim"
    ) -WindowStyle Hidden | Out-Null
}
$serial = Wait-ForEmulator $adb $EmulatorSerial
Write-Output "Using emulator: $serial"

if (-not $env:JAVA_HOME) {
    $bundledJdk = "C:\Program Files\Android\Android Studio\jbr"
    if (Test-Path -LiteralPath $bundledJdk) { $env:JAVA_HOME = $bundledJdk }
}
Invoke-Checked "powershell.exe" @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $repoRoot "scripts/fetch_ai_baseline_model.ps1")
)
Push-Location (Join-Path $repoRoot "android")
try {
    Invoke-Checked (Join-Path $repoRoot "android/gradlew.bat") @(
        ":feature:ai-perception:assembleDebugAndroidTest"
    )
} finally {
    Pop-Location
}

$testApk = Join-Path $repoRoot "android/feature/ai-perception/build/outputs/apk/androidTest/debug/ai-perception-debug-androidTest.apk"
$packageName = "kr.co.navi.mobility.ai.test"
$runner = "$packageName/androidx.test.runner.AndroidJUnitRunner"
$testClass = "kr.co.navi.mobility.ai.offline.DeviceFreeOfflineEvaluationTest"
Invoke-Checked $adb @("-s", $serial, "install", "-r", $testApk)

$remoteRoot = "/data/local/tmp/navi-m2-$runId"
$internalRoot = "m2-device-free/$runId"
try {
Invoke-Checked $adb @("-s", $serial, "shell", "mkdir", "-p", "$remoteRoot/dataset")
Invoke-Checked $adb @("-s", $serial, "push", "$datasetDirectory/.", "$remoteRoot/dataset")
Invoke-Checked $adb @(
    "-s", $serial, "shell", "run-as", $packageName,
    "mkdir", "-p", "files/$internalRoot/dataset"
)
Invoke-Checked $adb @(
    "-s", $serial, "shell", "run-as", $packageName,
    "cp", "-R", "$remoteRoot/dataset/.", "files/$internalRoot/dataset/"
)

function Invoke-Evaluation([string]$RunName, [string]$ManifestName = "manifest.json") {
    $trackerEnabled = (-not $DisableTracker).ToString().ToLowerInvariant()
    $instrumentOutput = & $adb -s $serial shell am instrument -w -r `
        -e class $testClass `
        -e manifest "$internalRoot/dataset/$ManifestName" `
        -e outputDir "$internalRoot/$RunName" `
        -e tracker $trackerEnabled `
        -e allowFailures true `
        $runner
    $instrumentOutput | Write-Output
    if ($LASTEXITCODE -ne 0 -or ($instrumentOutput -join "`n") -notmatch 'OK \(1 test\)') {
        throw "M2 instrumentation evaluation failed"
    }
}

Invoke-Evaluation "run-1"
$localRun1 = Join-Path $runRoot "run-1"
Export-RunReports $adb $serial $packageName "$internalRoot/run-1" "$remoteRoot/export-1" $localRun1 $safeDatasetId
$report1 = Join-Path $localRun1 "$safeDatasetId-report.json"
$firstReport = Get-Content -LiteralPath $report1 -Raw | ConvertFrom-Json
$failureCount = @($firstReport.evaluation.failedFrames).Count

if ($failureCount -gt 0) {
    Write-Warning "$failureCount frame(s) failed; running a failure-only retry."
    $retryManifest = Join-Path $datasetDirectory "retry-manifest.json"
    Invoke-Checked $python @(
        (Join-Path $repoRoot "scripts/offline_report_tools.py"), "retry-manifest",
        "--manifest", $manifest, "--report", $report1, "--output", $retryManifest
    )
    Invoke-Checked $adb @("-s", $serial, "push", $retryManifest, "$remoteRoot/dataset/retry-manifest.json")
    Invoke-Checked $adb @(
        "-s", $serial, "shell", "run-as", $packageName,
        "cp", "$remoteRoot/dataset/retry-manifest.json", "files/$internalRoot/dataset/retry-manifest.json"
    )
    Invoke-Evaluation "retry" "retry-manifest.json"
    $retrySafeId = "$safeDatasetId-retry"
    $localRetry = Join-Path $runRoot "retry"
    Export-RunReports $adb $serial $packageName "$internalRoot/retry" "$remoteRoot/export-retry" $localRetry $retrySafeId
    $retryReport = Get-Content -LiteralPath (Join-Path $localRetry "$retrySafeId-report.json") -Raw | ConvertFrom-Json
    if (@($retryReport.evaluation.failedFrames).Count -gt 0) {
        throw "Failure-only retry still contains failed frames. See: $localRetry"
    }
}

if (-not $SkipDeterminismCheck -and $failureCount -eq 0) {
    Invoke-Evaluation "run-2"
    $localRun2 = Join-Path $runRoot "run-2"
    Export-RunReports $adb $serial $packageName "$internalRoot/run-2" "$remoteRoot/export-2" $localRun2 $safeDatasetId
    Invoke-Checked $python @(
        (Join-Path $repoRoot "scripts/offline_report_tools.py"), "compare",
        "--baseline", $report1,
        "--candidate", (Join-Path $localRun2 "$safeDatasetId-report.json"),
        "--output", (Join-Path $runRoot "determinism.json")
    )
}

} finally {
    & $adb -s $serial shell rm -rf $remoteRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not remove emulator staging directory: $remoteRoot"
    }
}
Write-Output "M2 device-free run complete: $runRoot"
Write-Output "Emulator latency is diagnostic only and is not a production performance gate."

#requires -Version 5.1
<#
.SYNOPSIS
    Read-only Samsung SM-S918N / S918NKSU8GZIF device identity check.
.DESCRIPTION
    Uses Windows ADB to compare the connected phone's build and uname
    properties with the firmware identity extracted from the supplied boot.
    Does not install apps, gain root, unlock bootloaders, write partitions
    or execute BOPE. Does not collect device serials or personal data.
#>
[CmdletBinding()]
param(
    [string] $AdbPath = "",
    [string] $OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-AdbExecutable {
    param([string] $Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $resolved = Resolve-Path -LiteralPath $Requested -ErrorAction Stop
        if (-not (Test-Path -LiteralPath $resolved.Path -PathType Leaf)) {
            throw "ADB executable not found: $Requested"
        }
        return $resolved.Path
    }

    $command = Get-Command -Name "adb.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    throw "ADB not found. Download official Android SDK Platform-Tools and pass -AdbPath 'C:\path\platform-tools\adb.exe'."
}

function Read-DeviceProperty {
    param(
        [string] $Executable,
        [string[]] $ShellArguments
    )
    $commandArgs = @("shell") + $ShellArguments
    $output = & $Executable @commandArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "ADB read failed: $($ShellArguments -join ' ')"
    }
    return (($output | Out-String).Trim())
}

try {
    $adb = Find-AdbExecutable -Requested $AdbPath
    $deviceLines = @(& $adb devices 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "ADB could not enumerate devices."
    }

    # Never print or save device serial numbers.
    $ready = @($deviceLines | Where-Object { $_ -match '^\S+\s+device\s*$' })
    if ($ready.Count -ne 1) {
        throw "Expected exactly one authorized ADB device; found $($ready.Count). Unlock the phone, allow USB debugging, and reconnect."
    }

    $commands = [ordered]@{
        model         = @("getprop", "ro.product.model")
        device        = @("getprop", "ro.product.device")
        android       = @("getprop", "ro.build.version.release")
        incremental   = @("getprop", "ro.build.version.incremental")
        fingerprint   = @("getprop", "ro.build.fingerprint")
        kernelRelease = @("uname", "-r")
        kernelVersion = @("uname", "-v")
        selinux       = @("getenforce")
    }

    $actual = [ordered]@{}
    foreach ($key in $commands.Keys) {
        $actual[$key] = Read-DeviceProperty -Executable $adb -ShellArguments $commands[$key]
    }

    $expected = [ordered]@{
        model         = "SM-S918N"
        device        = "dm3q"
        android       = "17"
        incremental   = "S918NKSU8GZIF"
        fingerprint   = "samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys"
        kernelRelease = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
        kernelVersion = "#1 SMP PREEMPT Mon Sep 28 01:56:16 UTC 2026"
    }

    $checks = [ordered]@{}
    $mismatches = @()
    foreach ($key in $expected.Keys) {
        $ok = ($actual[$key] -ceq $expected[$key])
        $checks[$key] = [ordered]@{
            matched = $ok
            expected = $expected[$key]
            actual = $actual[$key]
        }
        if (-not $ok) {
            $mismatches += $key
        }
    }

    $status = if ($mismatches.Count -eq 0) { "IDENTITY_MATCH" } else { "IDENTITY_MISMATCH" }
    $report = [ordered]@{
        schema = 1
        target = "SM-S918N/S918NKSU8GZIF"
        status = $status
        deviceCount = $ready.Count
        checkedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        checks = $checks
        selinux = $actual["selinux"]
        notes = @(
            "No device identifiers, serial number, contacts or logcat are collected.",
            "Identity match does not prove root-payload or KernelSU compatibility.",
            "This script performs ADB read-only checks only."
        )
    }

    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $OutputPath = Join-Path $env:TEMP "s918n-gzif-device-check.json"
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

    Write-Host "Device identity: $status"
    Write-Host "SELinux: $($actual['selinux']) (read-only)"
    foreach ($key in $mismatches) {
        Write-Host "Mismatch: $key"
    }
    Write-Host "Report: $OutputPath"
    if ($mismatches.Count -ne 0) {
        exit 2
    }
    exit 0
}
catch {
    Write-Error "Preflight failed: $($_.Exception.Message)"
    exit 1
}

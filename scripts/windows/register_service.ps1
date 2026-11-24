param([string]$PackageRoot = $PSScriptRoot)

$ErrorActionPreference = 'Stop'

function Test-ServiceRegistrationAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return [Security.Principal.WindowsPrincipal]::new($identity).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-MotionServerService {
    try {
        return Get-Service -Name 'MotionServer' -ErrorAction Stop
    } catch {
        if ($_.FullyQualifiedErrorId -like 'NoServiceFoundForGivenName*') { return $null }
        throw
    }
}

function Invoke-ServiceRegistrationCommand {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Service registration command failed ($LASTEXITCODE): $Executable $Arguments"
    }
}

function Register-MotionServerService {
    param([string]$Root)
    if (-not (Test-ServiceRegistrationAdministrator)) {
        throw 'Run this registration script from an administrator PowerShell window.'
    }
    $Root = (Resolve-Path -LiteralPath $Root).Path
    $serviceRoot = Join-Path $Root 'Tools\service'
    $wrapper = Join-Path $serviceRoot 'MotionServerService.exe'
    $template = Join-Path $serviceRoot 'MotionServerService.default.xml'
    $config = Join-Path $serviceRoot 'MotionServerService.xml'
    $dependency = Join-Path $serviceRoot 'dependency.json'
    foreach ($path in @((Join-Path $Root 'motion_server.exe'),
                        (Join-Path $Root 'config.txt'), $wrapper, $template, $dependency)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required package file is missing: $path"
        }
    }
    $expected = Get-Content -LiteralPath $dependency -Raw | ConvertFrom-Json
    if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash -ne $expected.sha256) {
        throw 'WinSW checksum mismatch. Restore the packaged service executable before registration.'
    }
    # Validate the template before removing a pre-existing service.
    $xml = [xml](Get-Content -LiteralPath $template -Raw)
    if ($xml.service.id -ne 'MotionServer') { throw 'Invalid service registration template.' }
    $existing = Get-MotionServerService
    if ($null -ne $existing) {
        $status = [string]$existing.Status
        $existing.Dispose()
        if ($status -ne 'Stopped') {
            throw 'MotionServer is not stopped. Stop it manually in Windows Services, then run this script again. No changes were made.'
        }
        Write-Host 'Replacing MotionServer. Previous service settings will be reset to package defaults.'
        Invoke-ServiceRegistrationCommand -Executable "$env:SystemRoot\System32\sc.exe" -Arguments @('delete', 'MotionServer')
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        do {
            $remaining = Get-MotionServerService
            if ($null -eq $remaining) { break }
            $remaining.Dispose()
            if ([DateTime]::UtcNow -ge $deadline) {
                throw 'Service deletion is pending. Close Windows Services/property windows and retry. No new service was registered.'
            }
            Start-Sleep -Milliseconds 200
        } while ($true)
    }
    Copy-Item -LiteralPath $template -Destination $config -Force
    Invoke-ServiceRegistrationCommand -Executable $wrapper -Arguments @('install')
    Write-Host 'MotionServer registered with package defaults; it has NOT been started.'
    Write-Host 'Use Windows Services (services.msc) to start, stop or change settings.'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Register-MotionServerService -Root $PackageRoot }
    catch { Write-Error $_ -ErrorAction Continue; exit 1 }
}

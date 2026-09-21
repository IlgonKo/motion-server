param(
    [string]$Config = "",
    [switch]$ListDevices,
    [string]$Python = "C:\Users\Festo\AppData\Local\Python\pythoncore-3.14-64\python.exe"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $PSScriptRoot "env.ps1")
$GamepadRoot = Join-Path $ProjectRoot "control_panel\gamepad_control_panel"
$PythonClientRoot = Join-Path $ProjectRoot "reference_clients\python"

$UsingDefaultConfig = [string]::IsNullOrWhiteSpace($Config)
if ($UsingDefaultConfig) {
    $Config = Join-Path $GamepadRoot "config.json"
}
else {
    $Config = [System.IO.Path]::GetFullPath($Config)
}

$ResolvedProjectRoot = Set-AxisServerPythonPath -ProjectRoot $ProjectRoot
$PythonPathEntries = @(
    $PythonClientRoot,
    $env:PYTHONPATH
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique
$env:PYTHONPATH = $PythonPathEntries -join [System.IO.Path]::PathSeparator

$Arguments = @("-B", "-m", "control_panel.gamepad_control_panel.control_panel")
if ($ListDevices) {
    $Arguments += "--list-devices"
    Write-Host "Listing SDL-compatible gamepads"
}
else {
    if (-not (Test-Path -LiteralPath $Config)) {
        if ($UsingDefaultConfig) {
            $ExampleConfig = Join-Path $GamepadRoot "config.example.json"
            if (-not (Test-Path -LiteralPath $ExampleConfig)) {
                throw "Gamepad example config not found: $ExampleConfig"
            }
            Copy-Item -LiteralPath $ExampleConfig -Destination $Config
            Write-Warning "Created $Config from config.example.json. Review the device name, GUID, input mapping, Axis indices, and velocity limits before arming."
        }
        else {
            throw "Gamepad config not found: $Config"
        }
    }
    $Arguments += @("--config", $Config)
    Write-Host "Starting Motion Server Gamepad Control Panel"
    Write-Host "Config=$Config"
}
Write-Host "Project root: $ResolvedProjectRoot"

Push-Location $ProjectRoot
try {
    & $Python @Arguments
}
finally {
    Pop-Location
}

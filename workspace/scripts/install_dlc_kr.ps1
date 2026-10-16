param(
    [string]$PpssppRoot = 'H:\ppsspp_stable_1.19.3',
    [string]$BuildRoot = '',
    [switch]$RestoreOriginal
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
if (-not $BuildRoot) {
    $BuildRoot = Join-Path $projectRoot 'work\builds\dlc_kr_20260802_r2\memstick\PSP\GAME\ULJS00150'
}
$target = Join-Path $PpssppRoot 'memstick\PSP\GAME\ULJS00150'
$backup = Join-Path $projectRoot 'backups\ppsspp_stable_dlc_original_20260802'
$names = @('PARAM.PBP', 'DL0000.EDAT', 'DL0001.EDAT', 'DL0002.EDAT')

if (Get-Process PPSSPPWindows64 -ErrorAction SilentlyContinue) {
    throw 'PPSSPP is running. Close it before replacing DLC files.'
}
if (-not (Test-Path -LiteralPath $target -PathType Container)) {
    throw "DLC target does not exist: $target"
}

if ($RestoreOriginal) {
    if (-not (Test-Path -LiteralPath $backup -PathType Container)) {
        throw "Original backup does not exist: $backup"
    }
    $source = $backup
} else {
    if (-not (Test-Path -LiteralPath $BuildRoot -PathType Container)) {
        throw "DLC build does not exist: $BuildRoot"
    }
    if (-not (Test-Path -LiteralPath $backup)) {
        New-Item -ItemType Directory -Path $backup | Out-Null
        foreach ($name in $names) {
            Copy-Item -LiteralPath (Join-Path $target $name) -Destination (Join-Path $backup $name)
        }
    }
    $source = $BuildRoot
}

foreach ($name in $names) {
    $sourcePath = Join-Path $source $name
    $targetPath = Join-Path $target $name
    Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash
    if ($sourceHash -ne $targetHash) {
        throw "Installed hash mismatch: $name"
    }
    Write-Output ("{0} {1}" -f $name, $targetHash)
}

if ($RestoreOriginal) {
    Write-Output "PASS: restored original DLC from $backup"
} else {
    Write-Output "PASS: installed Korean DLC from $BuildRoot"
}

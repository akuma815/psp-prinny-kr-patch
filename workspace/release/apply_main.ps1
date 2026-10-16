param([Parameter(Mandatory = $true)][string]$InputIso)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $InputIso).Path
$output = Join-Path (Split-Path -Parent $source) (([IO.Path]::GetFileNameWithoutExtension($source)) + '_KR.iso')
$patch = Join-Path $PSScriptRoot 'Prinny_ULJS00150_KR_20260803.xdelta'
$xdelta = Join-Path $PSScriptRoot 'tools\xdelta3.exe'
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
if ($sourceHash -ne 'AF0D2873A96C5FE6F95B3FC2FB3E8702F98BBA67E32F2F78C5C3D1BDAA8B9D03') {
    throw "Unsupported original ISO hash: $sourceHash"
}
& $xdelta -d -f -s $source $patch $output
if ($LASTEXITCODE -ne 0) { throw "xdelta failed with exit code $LASTEXITCODE" }
$outputHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
if ($outputHash -ne 'AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC') {
    throw "Patched ISO verification failed: $outputHash"
}
Write-Output "PASS: $output"

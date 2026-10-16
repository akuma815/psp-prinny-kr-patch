param([Parameter(Mandatory = $true)][string]$SourceFolder)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceFolder).Path
$output = Join-Path $PSScriptRoot 'patched_dlc\ULJS00150'
$xdelta = Join-Path $PSScriptRoot 'tools\xdelta3.exe'
$items = @(
    @{ Name='DL0000'; Source='A0209702DE5210B2F35C57E7C12BFDDBEB691200DE06769B615CA50254D48C1B'; Target='2A2FB6A26AD40AA7EF2BFD46795657416E4D45723F7B04B3A30E76E715B83739' },
    @{ Name='DL0001'; Source='86B48D56B6BA853F09FFB0A524CCEBF4F601C78CB0F4937CB885EC8815BDB7A7'; Target='4D3F0B113670C532CAB6233C08309B000A34622673730CFD1B8D12DC6E503CCC' },
    @{ Name='DL0002'; Source='3FBC26ED99C1B3F474E50DD5290EB0497E61F0A7E8E9268FB82980A426079BE9'; Target='FB6B75F3F60DA7233EEA63A229512A0762E3B789C7204C5E22D0D837677435AE' }
)
New-Item -ItemType Directory -Path $output -Force | Out-Null
$count = 0
foreach ($item in $items) {
    $input = Join-Path $source ($item.Name + '.EDAT')
    if (-not (Test-Path -LiteralPath $input -PathType Leaf)) { continue }
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $input).Hash
    if ($sourceHash -ne $item.Source) { throw "Unsupported $($item.Name).EDAT hash: $sourceHash" }
    $patch = Join-Path $PSScriptRoot ("Prinny_DLC_{0}_KR_20260803.xdelta" -f $item.Name)
    $target = Join-Path $output ($item.Name + '.EDAT')
    & $xdelta -d -f -s $input $patch $target
    if ($LASTEXITCODE -ne 0) { throw "xdelta failed for $($item.Name) with exit code $LASTEXITCODE" }
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    if ($targetHash -ne $item.Target) { throw "Patched $($item.Name).EDAT verification failed: $targetHash" }
    Write-Output "PASS: $($item.Name).EDAT"
    $count++
}
if ($count -eq 0) { throw 'No supported DL0000/1/2.EDAT files were found.' }
$param = Join-Path $source 'PARAM.PBP'
if (Test-Path -LiteralPath $param -PathType Leaf) { Copy-Item -LiteralPath $param -Destination $output -Force }
Write-Output "PASS: patched $count DLC file(s) into $output"

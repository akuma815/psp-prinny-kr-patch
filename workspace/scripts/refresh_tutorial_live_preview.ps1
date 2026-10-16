param(
    [string]$PpssppRoot = 'H:\ppsspp'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RepositoryRoot = (Resolve-Path (Join-Path $ProjectRoot '..\..')).Path
$DumpDir = Join-Path $PpssppRoot 'memstick\PSP\TEXTURES\ULJS00150\new'
$ReplacementDir = Join-Path $PpssppRoot 'memstick\PSP\TEXTURES\ULJS00150'

& python -W ignore::DeprecationWarning `
    (Join-Path $ProjectRoot 'workspace\scripts\build_tutorial_live_preview.py') `
    (Join-Path $ProjectRoot 'workspace\config\tutorial_live_preview.json') `
    (Join-Path $ProjectRoot 'workspace\config\tutorial_graphics_poc.json') `
    (Join-Path $ProjectRoot 'extracted\PSP_GAME\USRDIR\ANIME.DAT') `
    (Join-Path $ProjectRoot 'work\poc\tutorial_graphics_v3\ANIME.DAT') `
    (Join-Path $RepositoryRoot 'Font\HancomMalangMalang-Regular.ttf') `
    $DumpDir `
    $ReplacementDir `
    (Join-Path $ProjectRoot 'work\live\tutorial_graphics')

if ($LASTEXITCODE -ne 0) {
    throw "tutorial live-preview generation failed with exit code $LASTEXITCODE"
}

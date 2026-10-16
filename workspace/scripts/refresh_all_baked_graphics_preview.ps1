param(
    [string]$PpssppRoot = 'H:\ppsspp'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$TextureRoot = Join-Path $PpssppRoot 'memstick\PSP\TEXTURES\ULJS00150'
$DumpRoot = Join-Path $TextureRoot 'new'

& python (Join-Path $PSScriptRoot 'catalog_baked_graphics_full.py') `
    --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'full baked-graphics catalog failed' }

& python (Join-Path $PSScriptRoot 'build_baked_graphics_bulk_preview.py') `
    --project-root $ProjectRoot `
    --ppsspp-textures $TextureRoot
if ($LASTEXITCODE -ne 0) { throw 'existing baked-graphics generation failed' }

& python (Join-Path $PSScriptRoot 'build_baked_graphics_full_preview.py') `
    --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'full baked-graphics generation failed' }

& python (Join-Path $PSScriptRoot 'bind_baked_graphics_dumps.py') `
    --project-root $ProjectRoot `
    --dump-dir $DumpRoot `
    --replacement-dir $TextureRoot
if ($LASTEXITCODE -ne 0) { throw 'PPSSPP dump binding failed' }

& python (Join-Path $PSScriptRoot 'build_image_first_pass_review_pack.py') `
    --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'image first-pass review pack generation failed' }

& python (Join-Path $PSScriptRoot 'build_image_review_gallery.py') `
    --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'offline image review gallery generation failed' }

Write-Host '전체 이미지 초벌 생성 및 현재 PPSSPP 덤프 연결 완료.'
Write-Host '새 화면을 진행해 덤프가 추가되면 이 스크립트만 다시 실행하면 됩니다.'

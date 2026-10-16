[CmdletBinding()]
param(
    [string]$PpssppExe = 'H:\ppsspp\PPSSPPWindows64.exe',
    [string]$PpssppIni = 'H:\ppsspp\memstick\PSP\SYSTEM\ppsspp.ini'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$gameRoot = Join-Path $projectRoot 'work\builds\direct_run_latest'
$backupRoot = Join-Path $projectRoot 'backups\ppsspp_before_korean_launch_20260726'
$backupIni = Join-Path $backupRoot 'ppsspp.ini'

if (Get-Process -Name 'PPSSPPWindows64' -ErrorAction SilentlyContinue) {
    throw 'PPSSPP가 실행 중입니다. 완전히 종료한 뒤 이 스크립트를 다시 실행하세요.'
}
if (-not (Test-Path -LiteralPath $PpssppExe -PathType Leaf)) {
    throw "PPSSPP 실행 파일이 없습니다: $PpssppExe"
}
if (-not (Test-Path -LiteralPath $PpssppIni -PathType Leaf)) {
    throw "PPSSPP 설정 파일이 없습니다: $PpssppIni"
}
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'PSP_GAME\SYSDIR\EBOOT.BIN') -PathType Leaf)) {
    throw "번역 직접 실행 빌드가 없습니다: $gameRoot"
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $backupIni)) {
    Copy-Item -LiteralPath $PpssppIni -Destination $backupIni
}

$content = Get-Content -LiteralPath $PpssppIni -Raw -Encoding UTF8
if ($content -notmatch '(?m)^ReplaceTextures\s*=') {
    throw 'ppsspp.ini에 ReplaceTextures 항목이 없습니다.'
}
$content = $content -replace '(?m)^ReplaceTextures\s*=.*$', 'ReplaceTextures = True'
$gameRecent = $gameRoot.Replace('\', '/')
if ($content -match '(?m)^FileName0\s*=') {
    $content = $content -replace '(?m)^FileName0\s*=.*$', "FileName0 = $gameRecent"
}
Set-Content -LiteralPath $PpssppIni -Value $content -Encoding UTF8 -NoNewline

$pspRoot = Split-Path -Parent (Split-Path -Parent $PpssppIni)
$stateRoot = Join-Path $pspRoot 'PPSSPP_STATE'
$oldStates = @(
    Get-ChildItem -LiteralPath $stateRoot -Filter 'ULJS00150*.ppst' -File -ErrorAction SilentlyContinue
)
if ($oldStates.Count -gt 0) {
    Write-Warning ('이 게임의 PPSSPP 세이브스테이트 {0}개가 있습니다. 세이브스테이트를 불러오면 패치 전 실행 메모리와 일본어 문자열이 복원됩니다.' -f $oldStates.Count)
    Write-Warning '이번 빌드는 반드시 게임을 새로 부팅해서 확인하고, 진행 보존에는 게임 내부 저장만 사용하세요.'
}

$quotedGameRoot = '"' + $gameRoot + '"'
Start-Process -FilePath $PpssppExe -ArgumentList $quotedGameRoot
Write-Host "번역 실행본을 시작했습니다: $gameRoot"
Write-Host 'ReplaceTextures = True'

param(
    [Parameter(Mandatory = $true)][string]$InputDirectory,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [datetime]$Since = [datetime]::MinValue,
    [switch]$UniquePrefix,
    [int]$Offset = 0,
    [int]$Maximum = 0,
    [int]$Columns = 8,
    [int]$ThumbnailSize = 112,
    [int]$LabelHeight = 20
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$files = @(Get-ChildItem -LiteralPath $InputDirectory -Filter '*.png' -File |
    Where-Object { $_.LastWriteTime -ge $Since } |
    Sort-Object LastWriteTime, Name)
if ($UniquePrefix) {
    $files = @($files |
        Group-Object {
            $_.BaseName.Substring(0, [math]::Min(16, $_.BaseName.Length))
        } |
        ForEach-Object {
            $_.Group |
                Sort-Object @{ Expression = 'LastWriteTime'; Descending = $true }, Name |
                Select-Object -First 1
        } |
        Sort-Object Name)
}
if ($Offset -lt 0) {
    throw "Offset must be zero or greater."
}
if ($Offset -gt 0) {
    $files = @($files | Select-Object -Skip $Offset)
}
if ($Maximum -gt 0) {
    $files = @($files | Select-Object -First $Maximum)
}
if ($files.Count -eq 0) {
    throw "No PNG files matched: $InputDirectory since $Since"
}

$cellWidth = $ThumbnailSize
$cellHeight = $ThumbnailSize + $LabelHeight
$rows = [math]::Ceiling($files.Count / $Columns)
$sheetWidth = $Columns * $cellWidth
$sheetHeight = $rows * $cellHeight
$sheet = New-Object System.Drawing.Bitmap $sheetWidth, $sheetHeight
$graphics = [System.Drawing.Graphics]::FromImage($sheet)
$graphics.Clear([System.Drawing.Color]::FromArgb(32, 32, 32))
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
$font = New-Object System.Drawing.Font 'Consolas', 7
$brush = [System.Drawing.Brushes]::White

try {
    for ($index = 0; $index -lt $files.Count; $index++) {
        $column = $index % $Columns
        $row = [math]::Floor($index / $Columns)
        $x = $column * $cellWidth
        $y = $row * $cellHeight
        $image = [System.Drawing.Image]::FromFile($files[$index].FullName)
        try {
            $scale = [math]::Min($ThumbnailSize / $image.Width, $ThumbnailSize / $image.Height)
            $width = [math]::Max(1, [int][math]::Round($image.Width * $scale))
            $height = [math]::Max(1, [int][math]::Round($image.Height * $scale))
            $drawX = $x + [int](($ThumbnailSize - $width) / 2)
            $drawY = $y + [int](($ThumbnailSize - $height) / 2)
            $graphics.DrawImage($image, $drawX, $drawY, $width, $height)
        }
        finally {
            $image.Dispose()
        }
        $label = $files[$index].BaseName.Substring(0, [math]::Min(16, $files[$index].BaseName.Length))
        $graphics.DrawString($label, $font, $brush, $x + 2, $y + $ThumbnailSize + 2)
    }

    $outputDirectory = Split-Path -Parent $OutputPath
    if ($outputDirectory) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    $sheet.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $font.Dispose()
    $graphics.Dispose()
    $sheet.Dispose()
}

[pscustomobject]@{
    status = 'PASS'
    input_count = $files.Count
    unique_prefix = [bool]$UniquePrefix
    offset = $Offset
    maximum = $Maximum
    since = $Since.ToString('o')
    output = (Resolve-Path -LiteralPath $OutputPath).Path
    dimensions = @($sheetWidth, $sheetHeight)
} | ConvertTo-Json

param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$source = [System.Drawing.Bitmap]::FromFile($SourcePath)
$output = [System.Drawing.Bitmap]::new(
    $source.Width,
    $source.Height,
    [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
)
$graphics = [System.Drawing.Graphics]::FromImage($output)
$graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
$graphics.DrawImageUnscaled($source, 0, 0)
$graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::None

# The right-hand wooden sign occupies this atlas region. The probe is intentionally
# conspicuous so one PPSSPP restart is enough to confirm the live consumer.
$probeBounds = New-Object System.Drawing.Rectangle 104, 2, 106, 65
$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Magenta), 3
$graphics.DrawRectangle($pen, $probeBounds)
$graphics.DrawLine($pen, $probeBounds.Left, $probeBounds.Top,
    $probeBounds.Right, $probeBounds.Bottom)
$graphics.DrawLine($pen, $probeBounds.Right, $probeBounds.Top,
    $probeBounds.Left, $probeBounds.Bottom)

try {
    $outputDirectory = Split-Path -Parent $OutputPath
    if ($outputDirectory) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    $output.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $pen.Dispose()
    $graphics.Dispose()
    $output.Dispose()
    $source.Dispose()
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath).Hash.ToLowerInvariant()
[pscustomobject]@{
    status = 'PASS'
    source = (Resolve-Path -LiteralPath $SourcePath).Path
    output = (Resolve-Path -LiteralPath $OutputPath).Path
    sha256 = $hash
    probe_bounds = @($probeBounds.X, $probeBounds.Y, $probeBounds.Width, $probeBounds.Height)
} | ConvertTo-Json

<#
.SYNOPSIS
    Regenerates desktop/build/icon.ico - black field, red "MA".

.DESCRIPTION
    The .ico is committed, so this only needs running to change the design.
    It exists so the icon is not an unreproducible binary blob: colour,
    text and sizes are all editable here.

    Uses System.Drawing rather than an image library, so nothing joins the
    toolchain just to draw two letters.

    Two things that are less obvious than they look:

    * Text is laid out as a GraphicsPath and centred on GetBounds(), the
      glyph outline's actual ink extents. MeasureString reports the *line
      box*, which reserves room for descenders - "MA" has none, so centring
      on it leaves the glyphs visibly high with dead space beneath.

    * 16px is deliberately absent. "MA" at that size collapses into two
      smudges; Windows downscaling the 24px layer reads better.

    Writes PNG layers to a temp dir, then packs them with pack-icon.mjs.

.EXAMPLE
    .\scripts\make-icon.ps1
#>
[CmdletBinding()]
param(
    # Defaults match --accent-crimson in both static/css/theme.css and the
    # marketing site's theme.css. Keep them in step.
    [string]$Text = "MA",
    [string]$Foreground = "#e0263b",
    [string]$Background = "#000000",
    [string]$FontFamily = "Arial Black"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$desktopDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stage      = Join-Path ([System.IO.Path]::GetTempPath()) "mma-assist-icon"
$outIco     = Join-Path $desktopDir "build\icon.ico"

New-Item -ItemType Directory -Path $stage -Force | Out-Null

function ConvertTo-Colour([string]$hex) {
    $h = $hex.TrimStart('#')
    [System.Drawing.Color]::FromArgb(255,
        [Convert]::ToInt32($h.Substring(0, 2), 16),
        [Convert]::ToInt32($h.Substring(2, 2), 16),
        [Convert]::ToInt32($h.Substring(4, 2), 16))
}

$bg     = ConvertTo-Colour $Background
$fg     = ConvertTo-Colour $Foreground
$sizes  = @(256, 128, 64, 48, 32, 24)
$family = New-Object System.Drawing.FontFamily($FontFamily)
$style  = [int][System.Drawing.FontStyle]::Bold

foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear($bg)

    # Measure at a reference em, then scale so the ink fills ~80% of the width.
    $refEm = 100.0
    $probe = New-Object System.Drawing.Drawing2D.GraphicsPath
    $probe.AddString($Text, $family, $style, $refEm, (New-Object System.Drawing.PointF(0, 0)), [System.Drawing.StringFormat]::GenericTypographic)
    $pb = $probe.GetBounds()
    $probe.Dispose()

    $scale = ($size * 0.80) / $pb.Width
    if (($pb.Height * $scale) -gt ($size * 0.72)) { $scale = ($size * 0.72) / $pb.Height }

    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddString($Text, $family, $style, ($refEm * $scale), (New-Object System.Drawing.PointF(0, 0)), [System.Drawing.StringFormat]::GenericTypographic)
    $b = $path.GetBounds()

    $mx = New-Object System.Drawing.Drawing2D.Matrix
    $mx.Translate((($size - $b.Width) / 2) - $b.X, (($size - $b.Height) / 2) - $b.Y)
    $path.Transform($mx)

    $brush = New-Object System.Drawing.SolidBrush($fg)
    $g.FillPath($brush, $path)
    $bmp.Save((Join-Path $stage "icon-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host ("  {0,3}px  ink {1,6:N1} x {2,-6:N1}" -f $size, $b.Width, $b.Height)

    $mx.Dispose(); $brush.Dispose(); $path.Dispose(); $g.Dispose(); $bmp.Dispose()
}
$family.Dispose()

node (Join-Path $PSScriptRoot "pack-icon.mjs") $stage $outIco
if ($LASTEXITCODE -ne 0) { throw "pack-icon.mjs failed" }
Write-Host "Rebuild the app for it to take effect:  npm run dist"

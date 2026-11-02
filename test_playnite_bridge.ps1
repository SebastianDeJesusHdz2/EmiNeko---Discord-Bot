$ErrorActionPreference = 'Stop'
$sample = Join-Path $PSScriptRoot ('.test-bridge-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $sample | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'playnite_bridge\EmiNeko.psm1') -Destination $sample
$module = Import-Module (Join-Path $sample 'EmiNeko.psm1') -PassThru
try {
    $failed = $false
    try { ExportEmiNekoLibrary } catch { $failed=$true }
    if (-not $failed) { throw 'Anunció éxito sin config.json.' }
    $dest=Join-Path $sample 'result.json'
    @{output=$dest} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $sample 'config.json')
    & $module { $script:PlayniteApi=[pscustomobject]@{Database=@{Games=@([pscustomobject]@{Name='Test';Id=[guid]::NewGuid();Source=@{Name='Epic'};Playtime=0})}} }
    ExportEmiNekoLibrary | Out-Null
    ExportEmiNekoLibrary | Out-Null
    $data=Get-Content -LiteralPath $dest -Raw | ConvertFrom-Json
    if ($data.games.Count -ne 1 -or $data.games[0].source -ne 'Epic') { throw 'Exportación incorrecta.' }
    Write-Output 'OK: configuración ausente, primera exportación y actualización con Epic.'
} finally {
    Remove-Module $module
    Get-ChildItem -LiteralPath $sample -File | Remove-Item
    Remove-Item -LiteralPath $sample
}

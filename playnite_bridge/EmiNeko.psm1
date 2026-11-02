function ExportEmiNekoLibrary {
    $ErrorActionPreference = 'Stop'
    $configPath = Join-Path $PSScriptRoot 'config.json'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "Falta config.json en $PSScriptRoot." }
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($config.output) -or -not [IO.Path]::IsPathRooted($config.output)) { throw 'config.json necesita una ruta output absoluta.' }
    $target = [IO.Path]::GetFullPath($config.output)
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
    $games = @($PlayniteApi.Database.Games | ForEach-Object {
        $game = $_
        $source = if ($game.Source) { $game.Source.Name } else { 'Manual' }
        $genres = @($game.Genres | ForEach-Object { $_.Name })
        $status = if ($game.CompletionStatus) { $game.CompletionStatus.Name } else { 'pendiente' }
        [PSCustomObject]@{ id = $game.Id.ToString(); name = $game.Name; source = $source; genres = $genres; minutes = [math]::Floor($game.Playtime / 60); status = $status }
    })
    $export = @{ version = 1; exported_at = [DateTime]::UtcNow.ToString('o'); games = $games } | ConvertTo-Json -Depth 8
    $temp = $target + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temp, $export, (New-Object System.Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($target)) {
            [IO.File]::Replace($temp, $target, [System.Management.Automation.Language.NullString]::Value)
        } else {
            [IO.File]::Move($temp, $target)
        }
    } finally {
        if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
    }
    $sources = @($games | Group-Object source | Sort-Object Name | ForEach-Object { '{0}: {1}' -f $_.Name,$_.Count })
    return "Archivo actualizado: $($games.Count) juegos.`n$($sources -join ', ')`n$target"
}
function OnLibraryUpdated { param($eventArgs) try { [void](ExportEmiNekoLibrary) } catch { Write-Warning $_.Exception.Message } }
function OnGameStopped { param($eventArgs) try { [void](ExportEmiNekoLibrary) } catch { Write-Warning $_.Exception.Message } }
function ExportNow {
    param($eventArgs)
    try { $result = ExportEmiNekoLibrary } catch { $result = 'Error de exportación: ' + $_.Exception.Message }
    $PlayniteApi.Dialogs.ShowMessage($result)
}
function GetMainMenuItems {
    param($args)
    $item = New-Object Playnite.SDK.Plugins.ScriptMainMenuItem
    $item.Description = 'Exportar biblioteca a EmiNeko'
    $item.FunctionName = 'ExportNow'
    $item.MenuSection = '@EmiNeko'
    return $item
}

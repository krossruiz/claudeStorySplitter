<#
.SYNOPSIS
    Adds (or removes) a "Split video into sections" right-click submenu for
    video files in Windows Explorer.

.DESCRIPTION
    Registers a cascading context-menu entry under the current user
    (HKCU, no administrator rights needed) for common video extensions. The
    submenu offers:

        Fast split (nearest keyframe, lossless)   -> split_video.py "<file>"
        Exact split (re-encode, precise cuts)      -> split_video.py --exact "<file>"
        View help document                         -> split_video.py --help

    Each launches in a console window that stays open (via `pause`) so you can
    read the output.

.PARAMETER Uninstall
    Removes the menu entries instead of installing them.

.NOTES
    On Windows 11 the entry appears in the classic menu: right-click a video and
    choose "Show more options" (or press Shift+F10). This is a Windows 11
    limitation for all registry-based context menus.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install-context-menu.ps1
    powershell -ExecutionPolicy Bypass -File .\install-context-menu.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

# --- resolve paths ---------------------------------------------------------
$scriptPath = Join-Path $PSScriptRoot 'split_video.py'
if (-not (Test-Path $scriptPath)) {
    throw "split_video.py was not found next to this installer ($scriptPath)."
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pythonCmd) {
    throw "Could not find 'python' (or 'py') on PATH. Install Python 3 first."
}
$python = $pythonCmd.Source

# Video extensions to attach the menu to.
$extensions = @(
    '.mp4', '.mov', '.m4v', '.mkv', '.avi', '.wmv', '.flv', '.webm',
    '.mpg', '.mpeg', '.3gp', '.3g2', '.m2ts', '.mts', '.ts', '.vob',
    '.ogv', '.divx', '.asf', '.mxf'
)

$menuKeyName = 'SplitVideo'   # our container key under each ext's shell

# --- uninstall -------------------------------------------------------------
if ($Uninstall) {
    $removed = 0
    foreach ($ext in $extensions) {
        $key = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$menuKeyName"
        if (Test-Path $key) {
            Remove-Item -Path $key -Recurse -Force
            $removed++
        }
    }
    Write-Host "Removed the Split-video menu from $removed extension(s)."
    return
}

# --- install ---------------------------------------------------------------
# Console-launcher wrapper: keep the window open with `pause` so output is
# visible. cmd /s /c strips the outer quotes and runs the rest verbatim.
function New-Command([string]$extraArgs, [bool]$withFile) {
    $tail = if ($withFile) { "`"%1`"" } else { "" }
    return "cmd.exe /d /s /c `"`"$python`" `"$scriptPath`" $extraArgs $tail & pause`""
}

# The three submenu items. Numeric prefixes force the display order.
$items = @(
    @{ Key = '01_fast';  Text = 'Fast split (nearest keyframe, lossless)'; Cmd = (New-Command ''        $true)  },
    @{ Key = '02_exact'; Text = 'Exact split (re-encode, precise cuts)';   Cmd = (New-Command '--exact' $true)  },
    @{ Key = '03_help';  Text = 'View help document';                      Cmd = (New-Command '--help'  $false) }
)

foreach ($ext in $extensions) {
    $root = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$menuKeyName"

    # Parent entry. An empty "SubCommands" value tells Explorer to look for a
    # nested "shell" subkey and render its children as a flyout submenu.
    New-Item -Path $root -Force | Out-Null
    Set-ItemProperty -Path $root -Name 'MUIVerb'     -Value 'Split video into sections'
    Set-ItemProperty -Path $root -Name 'SubCommands' -Value ''
    Set-ItemProperty -Path $root -Name 'Icon'        -Value $python

    foreach ($item in $items) {
        $itemKey = "$root\shell\$($item.Key)"
        $cmdKey  = "$itemKey\command"
        New-Item -Path $cmdKey -Force | Out-Null
        Set-ItemProperty -Path $itemKey -Name 'MUIVerb'    -Value $item.Text
        Set-ItemProperty -Path $cmdKey  -Name '(Default)'  -Value $item.Cmd
    }
}

Write-Host "Installed the 'Split video into sections' submenu for $($extensions.Count) video extension(s)."
Write-Host "Python : $python"
Write-Host "Script : $scriptPath"
Write-Host ""
Write-Host "Right-click a video file to use it. On Windows 11, click 'Show more"
Write-Host "options' (or press Shift+F10) to see the classic menu."

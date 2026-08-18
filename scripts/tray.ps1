# =============================================================================
#  fadir - system tray application
#
#  Runs the dashboard server as a hidden background process and puts an icon in
#  the notification area. Right-click the icon for the menu; double-click opens
#  the dashboard.
#
#  Launch it via fadir-tray.vbs so no console window ever appears. Running this
#  .ps1 directly works too, but leaves a PowerShell window behind.
# =============================================================================

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$Root    = Split-Path -Parent $PSScriptRoot
$BaseUrl = "http://127.0.0.1:$Port"
$Python  = Join-Path $Root '.venv\Scripts\python.exe'
$LogDir  = Join-Path $Root 'logs'
$LogFile = Join-Path $LogDir 'server.log'      # uvicorn logs to stderr
$OutFile = Join-Path $LogDir 'server.out.log'

Set-Location $Root
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:ServerProcess = $null
$script:StartedByUs   = $false

# -- helpers -----------------------------------------------------------------

function Test-PortOpen {
    param([int]$TestPort = $Port, [int]$TimeoutMs = 400)
    $client = New-Object Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $TestPort, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Show-Balloon {
    param([string]$Title, [string]$Text, [string]$Level = 'Info')
    if ($null -eq $script:Notify) { return }
    $script:Notify.BalloonTipTitle = $Title
    $script:Notify.BalloonTipText  = $Text
    $script:Notify.BalloonTipIcon  = [System.Windows.Forms.ToolTipIcon]::$Level
    $script:Notify.ShowBalloonTip(4000)
}

function New-FadirIcon {
    # A small ascending bar chart: two purple bars (FX) and one green (price),
    # echoing the dashboard's own attribution colours.
    $bmp = New-Object System.Drawing.Bitmap 32, 32
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $panel = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 19, 24, 34))
    $g.FillEllipse($panel, 0, 0, 31, 31)

    $fx    = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 192, 132, 252))
    $price = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 53, 208, 127))

    $g.FillRectangle($fx,     7, 19, 5, 7)
    $g.FillRectangle($fx,    14, 14, 5, 12)
    $g.FillRectangle($price, 21,  7, 5, 19)

    $panel.Dispose(); $fx.Dispose(); $price.Dispose(); $g.Dispose()

    $handle = $bmp.GetHicon()
    $icon   = [System.Drawing.Icon]::FromHandle($handle)
    $bmp.Dispose()
    return $icon
}

function Start-FadirServer {
    if (Test-PortOpen) {
        # Something is already serving this port - adopt it rather than fighting it.
        $script:StartedByUs = $false
        return $true
    }

    if (-not (Test-Path $Python)) {
        [System.Windows.Forms.MessageBox]::Show(
            "The virtual environment is missing.`n`nRun start.cmd once to set it up, then use the tray launcher.",
            'fadir - setup needed',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        return $false
    }

    $script:ServerProcess = Start-Process -FilePath $Python `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutFile `
        -RedirectStandardError  $LogFile `
        -PassThru

    $script:StartedByUs = $true

    # Wait for the socket rather than guessing at a fixed delay.
    for ($i = 0; $i -lt 40; $i++) {
        if (Test-PortOpen) { return $true }
        if ($script:ServerProcess.HasExited) {
            Show-Balloon 'fadir' 'The server exited on startup. Open View Log for details.' 'Error'
            return $false
        }
        Start-Sleep -Milliseconds 400
    }

    Show-Balloon 'fadir' 'The server did not come up in time. Check View Log.' 'Warning'
    return $false
}

function Stop-ProcessTree {
    # On Windows the venv's python.exe re-launches the base interpreter as a child,
    # and it is the *child* that binds the port. Killing only the tracked parent
    # happens to bring the child down too, but relying on that would leave an
    # orphaned server holding port 8000 the moment that behaviour changes. Walk the
    # tree depth-first instead.
    param([int]$ProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-ProcessTree -ProcessId $child.ProcessId }
    try { Stop-Process -Id $ProcessId -Force -ErrorAction Stop } catch { }
}

function Stop-FadirServer {
    if ($script:ServerProcess -and -not $script:ServerProcess.HasExited) {
        Stop-ProcessTree -ProcessId $script:ServerProcess.Id
        try { $script:ServerProcess.WaitForExit(5000) | Out-Null } catch { }
    }
    $script:ServerProcess = $null

    # Confirm the socket actually released; a half-dead server is worse than none.
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Test-PortOpen -TimeoutMs 200)) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return -not (Test-PortOpen -TimeoutMs 200)
}

function Open-Dashboard {
    if (-not (Test-PortOpen)) {
        Show-Balloon 'fadir' 'The server is not running. Use Start Server first.' 'Warning'
        return
    }
    Start-Process $BaseUrl
}

function Update-MenuState {
    $running = Test-PortOpen
    $script:StatusItem.Text    = if ($running) { "● Server running on port $Port" } else { '○ Server stopped' }
    $script:StartItem.Enabled  = -not $running
    $script:StopItem.Enabled   = $running
    $script:OpenItem.Enabled   = $running
    $script:DocsItem.Enabled   = $running
    $script:RefreshItem.Enabled = $running
    $script:Notify.Text = if ($running) { "fadir - running on $BaseUrl" } else { 'fadir - stopped' }
}

# -- tray icon and menu -------------------------------------------------------

$script:Notify = New-Object System.Windows.Forms.NotifyIcon
$script:Notify.Icon    = New-FadirIcon
$script:Notify.Text    = 'fadir - starting...'
$script:Notify.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip

$script:StatusItem = $menu.Items.Add('○ Server stopped')
$script:StatusItem.Enabled = $false

$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$script:OpenItem = $menu.Items.Add('Open Dashboard')
$script:OpenItem.Font = New-Object System.Drawing.Font($menu.Font, [System.Drawing.FontStyle]::Bold)
$script:OpenItem.Add_Click({ Open-Dashboard })

$script:DocsItem = $menu.Items.Add('Open API Docs')
$script:DocsItem.Add_Click({
    if (Test-PortOpen) { Start-Process "$BaseUrl/docs" }
    else { Show-Balloon 'fadir' 'The server is not running.' 'Warning' }
})

$script:RefreshItem = $menu.Items.Add('Refresh Market Data')
$script:RefreshItem.Add_Click({
    try {
        $result = Invoke-RestMethod -Uri "$BaseUrl/api/refresh" -Method Post -TimeoutSec 120
        $written = $result.price_rows_written
        if ($result.errors.Count -gt 0) {
            Show-Balloon 'fadir' "Refreshed with $($result.errors.Count) warning(s). $written new price rows." 'Warning'
        } else {
            Show-Balloon 'fadir' "Market data refreshed. $written new price rows." 'Info'
        }
    } catch {
        Show-Balloon 'fadir' "Refresh failed: $($_.Exception.Message)" 'Error'
    }
})

$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$script:StartItem = $menu.Items.Add('Start Server')
$script:StartItem.Add_Click({
    if (Start-FadirServer) { Show-Balloon 'fadir' "Server running on $BaseUrl" 'Info' }
    Update-MenuState
})

$script:StopItem = $menu.Items.Add('Stop Server')
$script:StopItem.Add_Click({
    if (Stop-FadirServer) {
        Show-Balloon 'fadir' 'Server stopped.' 'Info'
    } else {
        Show-Balloon 'fadir' "Port $Port is still in use - something else may be holding it." 'Warning'
    }
    Update-MenuState
})

$restartItem = $menu.Items.Add('Restart Server')
$restartItem.Add_Click({
    Stop-FadirServer
    Start-Sleep -Milliseconds 600
    if (Start-FadirServer) { Show-Balloon 'fadir' 'Server restarted.' 'Info' }
    Update-MenuState
})

$logItem = $menu.Items.Add('View Log')
$logItem.Add_Click({
    if (Test-Path $LogFile) { Start-Process notepad.exe $LogFile }
    else { Show-Balloon 'fadir' 'No log file yet.' 'Info' }
})

$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$exitItem = $menu.Items.Add('Exit (stops server)')
$exitItem.Add_Click({
    Stop-FadirServer
    $script:Notify.Visible = $false
    $script:Notify.Dispose()
    $script:AppContext.ExitThread()
})

$script:Notify.ContextMenuStrip = $menu

# Refresh the enabled/disabled state each time the menu is opened, so it always
# reflects reality even if the server was stopped from elsewhere.
$menu.Add_Opening({ Update-MenuState })

# Double-click is the obvious gesture for "show me the thing".
$script:Notify.Add_MouseDoubleClick({ Open-Dashboard })

# -- first-run setup ----------------------------------------------------------

if (-not (Test-Path (Join-Path $Root 'fadir.db'))) {
    Show-Balloon 'fadir' 'First run - creating the database and fetching market data. This takes a minute.' 'Info'
    try {
        & $Python (Join-Path $Root 'scripts\bootstrap.py') 2>&1 |
            Out-File -FilePath (Join-Path $LogDir 'bootstrap.log') -Encoding utf8
    } catch {
        Show-Balloon 'fadir' "Bootstrap failed: $($_.Exception.Message)" 'Error'
    }
}

# -- go -----------------------------------------------------------------------

$started = Start-FadirServer
Update-MenuState

if ($started) {
    Show-Balloon 'fadir' "Running on $BaseUrl - right-click the tray icon to open the dashboard." 'Info'
    if (-not $NoBrowser) { Start-Process $BaseUrl }
}

$script:AppContext = New-Object System.Windows.Forms.ApplicationContext
try {
    [System.Windows.Forms.Application]::Run($script:AppContext)
} finally {
    # Never leave an orphaned server or a ghost icon behind.
    if ($script:StartedByUs) { Stop-FadirServer }
    if ($script:Notify) {
        $script:Notify.Visible = $false
        $script:Notify.Dispose()
    }
}

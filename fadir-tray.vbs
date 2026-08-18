' ============================================================================
'  fadir - silent tray launcher
'
'  Double-click this to start the dashboard with no console window at all.
'  A small icon appears in the notification area (bottom-right of the taskbar,
'  possibly behind the "^" overflow arrow).
'
'    Right-click the icon  ->  Open Dashboard, Refresh, Restart, View Log, Exit
'    Double-click the icon ->  Open Dashboard
'
'  This wrapper exists purely to launch PowerShell hidden - running a .ps1 or
'  .cmd directly would flash a console window on screen.
' ============================================================================

Option Explicit

Dim shell, fso, root, script, command

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

root   = fso.GetParentFolderName(WScript.ScriptFullName)
script = root & "\scripts\tray.ps1"

If Not fso.FileExists(script) Then
    MsgBox "Could not find:" & vbCrLf & script & vbCrLf & vbCrLf & _
           "Keep fadir-tray.vbs in the project folder, next to start.cmd.", _
           vbCritical, "fadir"
    WScript.Quit 1
End If

' Bypass covers machines where the default execution policy blocks local scripts.
command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass " & _
          "-WindowStyle Hidden -File """ & script & """"

' 0 = hidden window, False = do not wait for it to finish.
shell.Run command, 0, False

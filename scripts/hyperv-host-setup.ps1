#Requires -RunAsAdministrator
# One-time Hyper-V host setup for the fadir VM: start with Windows, 1 GB dynamic memory.
param(
    [string]$Name = "*fadir*",
    [int64]$StartupBytes = 1GB,
    [int64]$MinimumBytes = 512MB,
    [int64]$MaximumBytes = 1536MB
)
$ErrorActionPreference = "Stop"

$vms = @(Get-VM -Name $Name)
if ($vms.Count -ne 1) {
    Get-VM | Format-Table Name, State
    throw "Expected exactly one VM matching '$Name'; rerun with -Name <vm name>."
}
$vm = $vms[0]
Write-Host "VM: $($vm.Name) ($($vm.State))"

# Memory can only change while the VM is off. Clear saved or paused state first.
if ($vm.State -in "Saved", "Paused") { Start-VM $vm; Start-Sleep 5; $vm = Get-VM $vm.Name }
if ($vm.State -ne "Off") { Stop-VM $vm -Force:$false; $vm = Get-VM $vm.Name }

Set-VMMemory $vm -DynamicMemoryEnabled $true -StartupBytes $StartupBytes `
    -MinimumBytes $MinimumBytes -MaximumBytes $MaximumBytes
Set-VM $vm -AutomaticStartAction Start -AutomaticStartDelay 0 -AutomaticStopAction Save

Start-VM $vm
Get-VM $vm.Name | Format-List Name, State, AutomaticStartAction, AutomaticStopAction, `
    DynamicMemoryEnabled, MemoryStartup, MemoryMinimum, MemoryMaximum

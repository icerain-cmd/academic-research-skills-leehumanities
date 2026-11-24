# Usage: .\tools\leehumanities\install.ps1 [--dry-run] [--update]
# All remaining arguments are passed as an array, never evaluated as code.
$ErrorActionPreference = 'Stop'
$lhPython = $null
$lhPrefix = @()
foreach ($lhCandidate in @('python', 'python3', 'py')) {
    $lhCommand = Get-Command $lhCandidate -ErrorAction SilentlyContinue
    if (-not $lhCommand) { continue }
    # The Windows Store aliases are placeholders, not a usable interpreter.
    if ($lhCommand.Source -match '\\Microsoft\\WindowsApps\\') { continue }
    $lhCandidatePrefix = @()
    if ($lhCandidate -eq 'py') { $lhCandidatePrefix = @('-3') }
    & $lhCommand.Source @lhCandidatePrefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
    if ($LASTEXITCODE -eq 0) {
        $lhPython = $lhCommand.Source
        $lhPrefix = $lhCandidatePrefix
        break
    }
}
if (-not $lhPython) {
    throw 'Python 3.10 or newer is required for the installer and local audit tools.'
}
& $lhPython @lhPrefix (Join-Path $PSScriptRoot 'install.py') @args
exit $LASTEXITCODE

param(
    [string]$BasePython = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$TempRoot = Join-Path $ProjectRoot '.tmp'

Set-Location $ProjectRoot
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:PYTHONNOUSERSITE = '1'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $VenvPython)) {
    if (-not $BasePython) {
        $preferred = 'D:\anjing2\miniconda\python.exe'
        if (Test-Path -LiteralPath $preferred) {
            $BasePython = $preferred
        } else {
            $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($pythonCommand) {
                $BasePython = $pythonCommand.Source
            }
        }
    }
    if (-not $BasePython -or -not (Test-Path -LiteralPath $BasePython)) {
        throw 'Python 3 was not found. Install Python or pass -BasePython with its full path.'
    }
    Write-Host "Creating independent project environment with $BasePython..."
    & $BasePython -m venv .venv
}

& $VenvPython -m pip install --disable-pip-version-check -r requirements-runtime.txt
& $VenvPython -s -c "import ctypes, json, tkinter, urllib.request; from PIL import Image; print('Runtime ready; Tk', tkinter.TkVersion, 'Pillow', Image.__version__)"
Write-Host 'Local pet-photo renderer is ready.' -ForegroundColor Green
Write-Host 'Next: .\scripts\start.ps1'

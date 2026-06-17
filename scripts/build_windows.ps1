#Requires -Version 5.1
<#
.SYNOPSIS
    Собирает WB Radar & China Matcher в Windows .exe.
.DESCRIPTION
    Использует PyInstaller для упаковки run.py в однофайловый .exe.
    Перед сборкой прогоняет pytest -m "not live" (можно пропустить через -SkipTests).
    В .exe НЕ включаются .env, sessions/, output/, .venv/, build/, dist/.
    Секреты приложение читает из .env / .env.local / sessions/ рядом с .exe.
.PARAMETER SkipTests
    Не запускать pytest перед сборкой.
.PARAMETER OneFile
    Собрать один .exe файл (по умолчанию — одна папка dist/WB_Radar_China_Matcher).
.PARAMETER OutputDir
    Базовая папка для dist/ (по умолчанию текущая).
.EXAMPLE
    .\scripts\build_windows.ps1
    .\scripts\build_windows.ps1 -SkipTests -OneFile
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$OneFile,
    [string]$OutputDir = "."
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Split-Path -Parent $PSScriptRoot)
Push-Location $ProjectRoot

try {
    Write-Host "=== WB Radar & China Matcher — Windows build ===" -ForegroundColor Cyan

    # 1. Проверяем .venv
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Error "Virtual environment not found at $VenvPython. Run init.sh or create .venv first."
    }
    Write-Host "Using Python: $VenvPython"

    # 2. Устанавливаем build-зависимости
    Write-Host "Installing/updating build dependencies..." -ForegroundColor Cyan
    & $VenvPython -m pip install --upgrade pyinstaller | Write-Host
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install pyinstaller" }

    # 3. Тесты перед сборкой
    if (-not $SkipTests) {
        Write-Host "Running pytest -m 'not live'..." -ForegroundColor Cyan
        & $VenvPython -m pytest -m "not live" -q
        if ($LASTEXITCODE -ne 0) { Write-Error "Tests failed. Fix tests or use -SkipTests." }
    } else {
        Write-Host "Skipping tests as requested." -ForegroundColor Yellow
    }

    # 4. Определяем дополнительные hidden imports для PyInstaller
    $HiddenImports = @(
        "flet",
        "core.config",
        "core.models",
        "core.storage",
        "core.wb_public",
        "core.browser",
        "core.llm",
        "core.llm.base",
        "core.llm.openrouter",
        "core.llm.zai",
        "core.llm.groq",
        "core.llm.ollama",
        "matcher.input",
        "matcher.rank",
        "matcher.video_china",
        "matcher.china",
        "matcher.china.alibaba",
        "matcher.china.s1688",
        "matcher.china.taobao",
        "matcher.china.base",
        "harvest.discovery",
        "harvest.reviews",
        "harvest.voc",
        "harvest.hooks",
        "harvest.review_video",
        "harvest.download",
        "harvest.describe",
        "gui.app",
        "gui.settings",
        "PIL",
        "PIL.Image",
        "yaml",
        "httpx",
        "tenacity",
        "imagehash",
        "pydantic",
        "pydantic_settings",
        "pandas",
        "dotenv",
        "bs4"
    )

    # 5. Подготовка путей
    $DistDir = Join-Path (Resolve-Path $OutputDir) "dist"
    $BuildDir = Join-Path (Resolve-Path $OutputDir) "build"

    $PyInstallerArgs = @(
        "run.py",
        "--name", "WB_Radar_China_Matcher",
        "--distpath", $DistDir,
        "--workpath", $BuildDir,
        "--specpath", $ProjectRoot,
        "--add-data", "config.yaml;.",
        "--add-data", "fixtures;fixtures",
        "--exclude-module", ".env",
        "--exclude-module", "sessions",
        "--exclude-module", "output",
        "--exclude-module", ".venv",
        "--exclude-module", "build",
        "--exclude-module", "dist",
        "--noconfirm"
    )

    foreach ($module in $HiddenImports) {
        $PyInstallerArgs += "--hidden-import"
        $PyInstallerArgs += $module
    }

    if ($OneFile) {
        $PyInstallerArgs += "--onefile"
    } else {
        $PyInstallerArgs += "--onedir"
    }

    # 6. Запускаем сборку
    Write-Host "Running pyinstaller..." -ForegroundColor Cyan
    & $VenvPython -m PyInstaller @PyInstallerArgs | Write-Host
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed" }

    # 7. Проверяем результат
    $ExpectedExe = if ($OneFile) {
        Join-Path $DistDir "WB_Radar_China_Matcher.exe"
    } else {
        Join-Path $DistDir "WB_Radar_China_Matcher\WB_Radar_China_Matcher.exe"
    }

    if (-not (Test-Path $ExpectedExe)) {
        Write-Error "Expected executable not found at $ExpectedExe"
    }

    $Info = Get-Item $ExpectedExe
    $SizeMb = [math]::Round($Info.Length / 1MB, 2)
    $Sha256 = (Get-FileHash $ExpectedExe -Algorithm SHA256).Hash

    Write-Host "=== Build successful ===" -ForegroundColor Green
    Write-Host "Executable: $($Info.FullName)"
    Write-Host "Size: $SizeMb MB"
    Write-Host "SHA256: $Sha256"

    # 8. Подготовка .env.example рядом с exe
    $EnvExampleDest = if ($OneFile) { $DistDir } else { Split-Path -Parent $ExpectedExe }
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvExampleDest -Force -ErrorAction SilentlyContinue
    Write-Host "Copied .env.example to $EnvExampleDest"
}
finally {
    Pop-Location
}

# install.ps1 — Windows setup for sap-gui
# Windows uses COM (win32com) directly: no daemon/token/launcher to install.
# This script: finds a REAL Python (avoiding the Microsoft Store alias),
# auto-installs pywin32, and guides on the one thing it can't safely automate
# (enabling SAP GUI scripting — a security toggle that needs the user/admin).

$ErrorActionPreference = "Continue"
Write-Host "== sap-gui (Windows) setup ==" -ForegroundColor Green

# 1) Find a real Python interpreter.
#    The Microsoft Store alias (...\WindowsApps\python.exe) often returns
#    exit 9009 / empty version, so prefer the py launcher, then any python
#    on PATH that is NOT under WindowsApps.
$PY = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 --version *> $null
    if ($LASTEXITCODE -eq 0) { $PY = @("py", "-3") }
}
if (-not $PY) {
    $cand = Get-Command python -All -ErrorAction SilentlyContinue |
            Where-Object { $_.Source -and $_.Source -notlike "*WindowsApps*" } |
            Select-Object -First 1
    if ($cand) { $PY = @($cand.Source) }
}
if (-not $PY) {
    Write-Host "[!] 실제 Python 을 못 찾음 (Microsoft Store alias 만 있는 듯)." -ForegroundColor Red
    Write-Host "    해결: python.org 에서 Python 3 설치, 또는 설정 → 앱 → 앱 실행 별칭에서 python.exe 끄기."
    exit 1
}
$PYDISP = ($PY -join " ")
Write-Host ("python: " + (& $PY[0] $PY[1..($PY.Count-1)] --version 2>&1) + "   [$PYDISP]")

# 2) pywin32 — auto-install if missing (using the real interpreter)
& $PY[0] $PY[1..($PY.Count-1)] -c "import win32com.client" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pywin32 없음 → 설치 중 ($PYDISP -m pip install --user pywin32)..." -ForegroundColor Yellow
    & $PY[0] $PY[1..($PY.Count-1)] -m pip install --user pywin32
    & $PY[0] $PY[1..($PY.Count-1)] -c "import win32com.client" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] pywin32 자동 설치 실패. 수동: $PYDISP -m pip install pywin32" -ForegroundColor Red
        exit 1
    }
    Write-Host "pywin32: 설치 완료" -ForegroundColor Green
} else {
    Write-Host "pywin32: OK"
}

# 3) Pillow — for PNG screenshot conversion (HardCopy emits BMP). Best-effort.
& $PY[0] $PY[1..($PY.Count-1)] -c "import PIL" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pillow 없음 → 설치 중 (스크린샷 PNG 변환용)..." -ForegroundColor Yellow
    & $PY[0] $PY[1..($PY.Count-1)] -m pip install --user Pillow *> $null
    Write-Host "  (실패해도 됨 — 그땐 screenshot 이 .bmp 로 저장됨)"
} else {
    Write-Host "Pillow: OK"
}

# 4) SAP GUI scripting — guide only (security toggle; do not auto-change registry)
Write-Host ""
Write-Host "남은 수동 1가지 (보안 토글이라 자동 변경 안 함):" -ForegroundColor Cyan
Write-Host "  SAP Logon → 옵션(렌치) → Accessibility & Scripting → Scripting"
Write-Host "  → 'Enable scripting' 체크 ('Notify when...' 2개 해제 권장)"
Write-Host "  (서버측 sapgui/user_scripting = TRUE 는 Basis 팀 영역)"

Write-Host ""
Write-Host "✓ 준비 끝. SAP GUI 실행·로그인 후:" -ForegroundColor Green
Write-Host "  $PYDISP `"$PSScriptRoot\sapctl`" health      # conns 나오면 성공"
Write-Host "  (sapctl 호출 시 'python' 대신 위의 '$PYDISP' 를 쓰면 Store alias 문제 회피)"

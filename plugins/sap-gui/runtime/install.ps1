# install.ps1 — Windows setup for sap-gui
# Windows uses COM (win32com) directly: no daemon/token/launcher to install.
# This script: checks Python, AUTO-INSTALLS pywin32, and guides on the one
# thing it can't safely automate (enabling SAP GUI scripting — a security
# toggle that needs the user/admin).

$ErrorActionPreference = "Continue"
Write-Host "== sap-gui (Windows) setup ==" -ForegroundColor Green

# 1) Python 3
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[!] python not found. Install Python 3 from https://python.org and re-run." -ForegroundColor Red
    exit 1
}
Write-Host ("python: " + (python --version 2>&1))

# 2) pywin32 — auto-install if missing
python -c "import win32com.client" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pywin32 없음 → 설치 중 (pip install pywin32)..." -ForegroundColor Yellow
    python -m pip install --user pywin32
    python -c "import win32com.client" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] pywin32 자동 설치 실패. 수동으로:  python -m pip install pywin32" -ForegroundColor Red
        Write-Host "    (권한 문제면 관리자 PowerShell 또는 가상환경에서 시도)"
        exit 1
    }
    Write-Host "pywin32: 설치 완료" -ForegroundColor Green
} else {
    Write-Host "pywin32: OK"
}

# 3) SAP GUI scripting — guide only (security toggle; do not auto-change registry)
Write-Host ""
Write-Host "남은 수동 1가지 (보안 토글이라 자동 변경 안 함):" -ForegroundColor Cyan
Write-Host "  SAP Logon → 옵션(렌치) → Accessibility & Scripting → Scripting"
Write-Host "  → 'Enable scripting' 체크 ('Notify when a script attaches/opens connection' 2개 해제 권장)"
Write-Host "  (서버측 sapgui/user_scripting = TRUE 는 Basis 팀 영역)"

Write-Host ""
Write-Host "✓ 준비 끝. 이제:" -ForegroundColor Green
Write-Host "  1) SAP GUI 실행 + 로그인 (특별 런처 불필요 — COM 자동 attach)"
Write-Host "  2) python `"$PSScriptRoot\sapctl`" health   # conns 나오면 성공"

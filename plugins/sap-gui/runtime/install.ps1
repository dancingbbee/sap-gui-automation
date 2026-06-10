# install.ps1 — Windows prerequisite check for sap-gui
# Windows uses COM (win32com) directly: no daemon, no token, no launcher.
# This script only CHECKS prerequisites and guides — it does not change the
# registry (enabling scripting is left to the user, as it's a security toggle).

Write-Host "== sap-gui (Windows) setup ==" -ForegroundColor Green

# 1) Python 3
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[!] python not found - install Python 3 (https://python.org)" -ForegroundColor Yellow
} else {
    Write-Host ("python: " + (python --version 2>&1))
}

# 2) pywin32 (provides win32com)
if ($py) {
    python -c "import win32com.client" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] pywin32 missing. Install with:" -ForegroundColor Yellow
        Write-Host "    pip install pywin32"
    } else {
        Write-Host "pywin32: OK"
    }
}

# 3) SAP GUI scripting (check/guide only - no auto registry change)
Write-Host ""
Write-Host "확인 필요 (수동):" -ForegroundColor Cyan
Write-Host "  - SAP GUI Options > Accessibility & Scripting > Scripting > 'Enable scripting' 체크"
Write-Host "    (+ 'Notify when a script attaches/opens a connection' 해제 권장)"
Write-Host "  - 서버측 프로파일 파라미터  sapgui/user_scripting = TRUE  (안 되어 있으면 Basis 팀)"

Write-Host ""
Write-Host "사용법:" -ForegroundColor Green
Write-Host "  1) SAP GUI 실행 + 로그인 (특별 런처 불필요 - COM 자동 attach)"
Write-Host "  2) python sapctl health        # conns 가 나오면 준비 완료"
Write-Host "  3) python sapctl targets       # 떠있는 창 목록"
Write-Host ""
Write-Host "참고: Windows 는 daemon/토큰/런처가 없습니다. sapctl 이 COM 으로 직접 SAP 에 붙습니다." -ForegroundColor DarkGray

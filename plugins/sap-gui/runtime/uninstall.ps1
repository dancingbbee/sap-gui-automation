# uninstall.ps1 — Windows has no launcher/token/daemon to remove.
Write-Host "sap-gui (Windows): 제거할 런처/토큰/daemon 이 없습니다 (COM 직접 사용)." -ForegroundColor Green
Write-Host "플러그인 자체 제거는 Claude Code 에서:  /plugin uninstall sap-gui"
Write-Host "pywin32 를 더 안 쓰면:  pip uninstall pywin32"

#!/bin/bash
# TitanVPN 모니터링 타이머 일괄 설치 스크립트
# 사용법: sudo bash install_timers.sh

set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

UNITS=(
    "nas-daily-check.service"
    "nas-daily-check.timer"
    "nas-status-alert.service"
    "nas-status-alert.timer"
    "server-auto-check.service"
    "server-auto-check.timer"
    "cn-telecom-ping.service"
    "cn-telecom-ping.timer"
    "noactive-user-cleanup.service"
    "noactive-user-cleanup.timer"
)

TIMERS=(
    "nas-daily-check.timer"
    "nas-status-alert.timer"
    "server-auto-check.timer"
    "cn-telecom-ping.timer"
    "noactive-user-cleanup.timer"
)

echo "=== TitanVPN 모니터링 타이머 설치 ==="

# 파일 복사
for unit in "${UNITS[@]}"; do
    if [ -f "$DEPLOY_DIR/$unit" ]; then
        cp "$DEPLOY_DIR/$unit" "$SYSTEMD_DIR/$unit"
        echo "  [OK] $unit 복사"
    else
        echo "  [SKIP] $unit 파일 없음"
    fi
done

# systemd 리로드
systemctl daemon-reload
echo "  [OK] systemd daemon-reload"

# 타이머 활성화 및 시작
for timer in "${TIMERS[@]}"; do
    systemctl enable "$timer" 2>/dev/null && echo "  [OK] $timer enabled" || echo "  [FAIL] $timer enable"
    systemctl start "$timer" 2>/dev/null && echo "  [OK] $timer started" || echo "  [FAIL] $timer start"
done

echo ""
echo "=== 등록된 타이머 현황 ==="
systemctl list-timers --no-pager | grep -E 'nas-|server-auto|cn-telecom|noactive|NEXT'

echo ""
echo "=== 설치 완료 ==="

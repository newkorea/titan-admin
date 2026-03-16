#!/bin/bash
# openwrt_central_monitor.sh — aws14에서 OpenWrt 중앙 모니터링
# 크론: */2 * * * * /home/newkorea/project/scripts/openwrt_central_monitor.sh >> /home/newkorea/project/scripts/openwrt_monitor.log 2>&1
#
# OpenWrt 게이트웨이(14.51.2.184)를 원격 ping 체크 (KT0 경유)
# 로컬 watchdog과 독립 — 이중 감시

PUSHPLUS_TOKEN="71441d4026b84b068f3e7522b173299f"
STATE_FILE="/tmp/openwrt_central_monitor.state"
OPENWRT_IP="14.51.2.184"
CHECK_VIA="14.51.2.130"  # KT0를 경유하여 ping

NOW=$(date '+%Y-%m-%d %H:%M:%S')

# 상태 읽기
prev_status="up"
fail_count=0
if [ -f "$STATE_FILE" ]; then
    prev_status=$(sed -n '1p' "$STATE_FILE")
    fail_count=$(sed -n '2p' "$STATE_FILE")
    [ -z "$fail_count" ] && fail_count=0
fi

# KT0에서 OpenWrt ping (SSH 경유)
result=$(ssh -o ConnectTimeout=5 -o BatchMode=yes root@${CHECK_VIA} "ping -c 3 -W 2 ${OPENWRT_IP} >/dev/null 2>&1 && echo OK || echo FAIL" 2>/dev/null)

send_pushplus() {
    curl -s -X POST "https://www.pushplus.plus/send" \
        -H "Content-Type: application/json" \
        -d "{\"token\":\"${PUSHPLUS_TOKEN}\",\"title\":\"$1\",\"content\":\"$2\",\"template\":\"txt\"}" \
        -o /dev/null --max-time 10 2>/dev/null
    echo "[$NOW] PushPlus: $1"
}

if [ "$result" = "OK" ]; then
    if [ "$prev_status" = "down" ]; then
        send_pushplus "★OpenWrt복구" "OpenWrt(${OPENWRT_IP}) 복구 확인. 각 서버 watchdog이 Google 라우트 자동 복원. (${NOW})"
        echo "[$NOW] ★ OpenWrt 복구 감지"
    fi
    echo "up" > "$STATE_FILE"
    echo "0" >> "$STATE_FILE"
else
    ((fail_count++))
    echo "[$NOW] OpenWrt 응답 없음 (연속 ${fail_count}회, via ${CHECK_VIA})"
    
    if [ "$fail_count" -ge 2 ] && [ "$prev_status" != "down" ]; then
        send_pushplus "★★OpenWrt다운!" "OpenWrt(${OPENWRT_IP}) 다운! KT0/1/2에서 Google 접속 불가. ESXi(14.51.2.185)에서 utofrs1 VM 확인 필요! 각 서버 watchdog이 fallback 처리 중. [sshpass -p 'uto160505!' ssh china@14.51.2.185 'vim-cmd vmsvc/power.reset 45'] (${NOW})"
        echo "[$NOW] ★★ OpenWrt 다운 알림 전송"
        echo "down" > "$STATE_FILE"
        echo "$fail_count" >> "$STATE_FILE"
    else
        echo "${prev_status}" > "$STATE_FILE"
        echo "$fail_count" >> "$STATE_FILE"
    fi
fi

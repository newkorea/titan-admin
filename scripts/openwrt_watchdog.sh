#!/bin/bash
# openwrt_watchdog.sh — OpenWrt 게이트웨이 헬스체크 + 자동 failover + PushPlus 알림
# 크론: */2 * * * * /usr/local/bin/openwrt_watchdog.sh >> /var/log/openwrt_watchdog.log 2>&1
#
# 동작:
#   1) OpenWrt(14.51.2.184) ping 3회 → 실패 시 연속 실패 카운트 증가
#   2) 연속 2회 실패(4분) → Google 라우트 삭제 (기본 GW로 fallback) + PushPlus 알림
#   3) OpenWrt 복구 → Google 라우트 복원 + PushPlus 알림
#   4) 상태 파일: /tmp/openwrt_watchdog.state (up / down / fail_count)

OPENWRT_GW="14.51.2.184"
STATE_FILE="/tmp/openwrt_watchdog.state"
PUSHPLUS_TOKEN="71441d4026b84b068f3e7522b173299f"
FAIL_THRESHOLD=2   # 연속 N회 실패 시 failover (2분 간격 × 2 = 4분)

GOOGLE_CIDRS=(
    8.8.4.0/24
    8.8.8.0/24
    64.233.160.0/19
    66.102.0.0/20
    66.249.64.0/19
    72.14.192.0/18
    74.125.0.0/16
    108.177.0.0/17
    108.170.192.0/18
    130.211.0.0/16
    142.250.0.0/15
    172.217.0.0/16
    172.253.0.0/16
    173.194.0.0/16
    192.178.0.0/15
    209.85.128.0/17
    216.58.192.0/19
    216.239.32.0/19
    199.223.232.0/21
    207.223.160.0/20
    14.0.112.0/24
)

HOSTNAME=$(hostname -s 2>/dev/null || hostname)
NOW=$(date '+%Y-%m-%d %H:%M:%S')

# ── 상태 파일 읽기 ──
prev_status="up"
fail_count=0
if [ -f "$STATE_FILE" ]; then
    prev_status=$(sed -n '1p' "$STATE_FILE")
    fail_count=$(sed -n '2p' "$STATE_FILE")
    [ -z "$fail_count" ] && fail_count=0
fi

# ── OpenWrt ping 체크 (3회, 각 1초 타임아웃) ──
if ping -c 3 -W 1 "$OPENWRT_GW" >/dev/null 2>&1; then
    alive=true
else
    alive=false
fi

# ── PushPlus 알림 전송 함수 ──
send_pushplus() {
    local title="$1"
    local body="$2"
    curl -s -X POST "https://www.pushplus.plus/send" \
        -H "Content-Type: application/json" \
        -d "{\"token\":\"${PUSHPLUS_TOKEN}\",\"title\":\"${title}\",\"content\":\"${body}\",\"template\":\"txt\"}" \
        -o /dev/null --max-time 10 2>/dev/null
    echo "[$NOW] PushPlus 전송: $title"
}

# ── Google 라우트 삭제 (failover to default GW) ──
remove_google_routes() {
    local removed=0
    for cidr in "${GOOGLE_CIDRS[@]}"; do
        if ip route del "$cidr" via "$OPENWRT_GW" 2>/dev/null; then
            ((removed++))
        fi
    done
    echo "[$NOW] Google 라우트 ${removed}개 삭제 (기본 GW로 fallback)"
}

# ── Google 라우트 복원 ──
restore_google_routes() {
    local added=0
    # onlink 필요 여부 판단: 같은 서브넷이면 불필요
    local my_subnet=$(ip -4 addr show dev eth0 2>/dev/null | grep -oP 'inet \K[\d.]+/\d+' | head -1)
    local use_onlink=""
    
    # 14.51.2.x 대역이면 same L2 → onlink 불필요
    if echo "$my_subnet" | grep -q "^14\.51\.2\."; then
        use_onlink=""
    else
        use_onlink="onlink"
    fi
    
    for cidr in "${GOOGLE_CIDRS[@]}"; do
        if [ -n "$use_onlink" ]; then
            ip route add "$cidr" via "$OPENWRT_GW" dev eth0 onlink 2>/dev/null && ((added++))
        else
            ip route add "$cidr" via "$OPENWRT_GW" dev eth0 2>/dev/null && ((added++))
        fi
    done
    echo "[$NOW] Google 라우트 ${added}개 복원 (OpenWrt 경유)"
}

# ── 메인 로직 ──
# 현재 Google 라우트 수 확인
current_routes=$(ip route | grep -c "via $OPENWRT_GW" 2>/dev/null)

if $alive; then
    # OpenWrt 살아있음
    if [ "$prev_status" = "down" ]; then
        # 복구됨! 라우트 복원 + 알림
        restore_google_routes
        send_pushplus "OpenWrt복구_${HOSTNAME}" "${HOSTNAME}: OpenWrt(${OPENWRT_GW}) 복구됨. Google 라우트 복원 완료. (${NOW})"
        echo "[$NOW] ★ OpenWrt 복구 → 라우트 복원 + 알림 전송"
    elif [ "$current_routes" -lt 10 ]; then
        # OpenWrt 살아있는데 라우트가 없음 → 복원 (재부팅 등)
        restore_google_routes
        echo "[$NOW] 라우트 누락 감지 (${current_routes}개) → 복원"
    fi
    # 상태 저장: up, fail_count=0
    echo "up" > "$STATE_FILE"
    echo "0" >> "$STATE_FILE"
else
    # OpenWrt 응답 없음
    ((fail_count++))
    echo "[$NOW] OpenWrt 응답 없음 (연속 ${fail_count}/${FAIL_THRESHOLD}회)"
    
    if [ "$fail_count" -ge "$FAIL_THRESHOLD" ] && [ "$prev_status" != "down" ]; then
        # 임계치 도달 → failover 실행
        remove_google_routes
        send_pushplus "OpenWrt다운_${HOSTNAME}" "${HOSTNAME}: OpenWrt(${OPENWRT_GW}) ${FAIL_THRESHOLD}회 연속 응답없음! Google 라우트 삭제하여 기본GW로 fallback 처리. VPN 고객 Google 접속은 정상. OpenWrt VM 확인 필요! (${NOW})"
        echo "[$NOW] ★ OpenWrt 다운 확정 → 라우트 삭제 + 알림 전송"
        # 상태: down
        echo "down" > "$STATE_FILE"
        echo "$fail_count" >> "$STATE_FILE"
    else
        # 아직 임계치 미도달각 또는 이미 down 상태
        echo "${prev_status}" > "$STATE_FILE"
        echo "$fail_count" >> "$STATE_FILE"
    fi
fi

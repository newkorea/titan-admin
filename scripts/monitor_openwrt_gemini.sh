#!/bin/bash
# OpenWrt별 Gemini geo 모니터링 (1시간 1회)
# 각 OpenWrt 게이트웨이 대표 서버 1대로 Gemini geo 체크
# CN이면 PushPlus 알림 + 라우팅 재적용 시도
#
# 크론: 0 * * * * /home/newkorea/project/scripts/monitor_openwrt_gemini.sh >> /home/newkorea/project/scripts/openwrt_gemini_monitor.log 2>&1

PUSHPLUS_TOKEN="71441d4026b84b068f3e7522b173299f"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
BLOCKED_GEOS="cn hk ru"

# OpenWrt별 대표 테스트 서버 (1대만 테스트하면 같은 OpenWrt에 연결된 서버 전체 상태를 알 수 있음)
# 형식: "OpenWrt_GW:테스트서버IP:설명"
OPENWRT_PROBES=(
  "192.168.112.1:218.49.179.80:OW-GRP1"
  "192.168.113.1:14.51.2.182:OW-GRP2"
  "192.168.111.1:218.49.179.84:OW-GRP3"
)

# IP → 서버명 매핑
declare -A SERVER_NAMES
SERVER_NAMES[218.49.179.80]="SK80"
SERVER_NAMES[218.49.179.81]="SK81"
SERVER_NAMES[218.49.179.83]="SK83"
SERVER_NAMES[218.49.179.84]="SK84"
SERVER_NAMES[218.49.179.85]="SK85"
SERVER_NAMES[218.49.179.86]="SK86"
SERVER_NAMES[218.49.179.87]="SK87"
SERVER_NAMES[218.49.179.88]="SK88"
SERVER_NAMES[218.49.179.89]="SK89"
SERVER_NAMES[218.49.179.90]="SK90"
SERVER_NAMES[110.15.180.162]="SK110"
SERVER_NAMES[14.51.2.182]="KT14182"

get_server_name() {
    local ip=$1
    local name=${SERVER_NAMES[$ip]:-$ip}
    echo "$name"
}

# 같은 OpenWrt에 연결된 전체 서버 목록 (라우팅 재적용 대상)
declare -A OPENWRT_SERVERS
OPENWRT_SERVERS[192.168.112.1]="218.49.179.80 218.49.179.81 218.49.179.83 218.49.179.85 218.49.179.86 218.49.179.87 218.49.179.88 218.49.179.89 218.49.179.90 110.15.180.162"  # SK80-90,SK110
OPENWRT_SERVERS[192.168.113.1]="14.51.2.182"  # KT14182
OPENWRT_SERVERS[192.168.111.1]="218.49.179.84"  # SK84

send_pushplus() {
    local title="$1"
    local content="$2"
    curl -s -X POST "https://www.pushplus.plus/send" \
        -H "Content-Type: application/json" \
        -d "{\"token\":\"${PUSHPLUS_TOKEN}\",\"title\":\"$title\",\"content\":\"$content\",\"template\":\"txt\"}" \
        -o /dev/null --max-time 10 2>/dev/null
}

check_gemini_via_server() {
    local server_ip=$1
    # 서버에 SSH 접속 → VPN 인터페이스로 Gemini 접속 → geo 코드 확인
    local geo=$(timeout 25 sshpass -p 'uto6703' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@$server_ip '
        # VPN 인터페이스 IP 찾기 (vpn-bridge, tun0 등)
        VPN_IF=""
        for iface in vpn-bridge tun0 ppp0; do
            VPN_IP=$(ip addr show $iface 2>/dev/null | grep "inet " | awk "{print \$2}" | cut -d/ -f1)
            if [ -n "$VPN_IP" ]; then VPN_IF=$iface; break; fi
        done
        if [ -z "$VPN_IP" ]; then
            # VPN 인터페이스 없으면 서버 자체로 테스트
            VPN_IP=""
        fi

        if [ -n "$VPN_IP" ]; then
            geo=$(curl -4 -s --interface "$VPN_IP" --connect-timeout 8 --max-time 15 "https://gemini.google.com" 2>/dev/null | grep -oP "\"[a-z]{2}\"" | head -1 | tr -d "\"")
        else
            geo=$(curl -4 -s --connect-timeout 8 --max-time 15 "https://gemini.google.com" 2>/dev/null | grep -oP "\"[a-z]{2}\"" | head -1 | tr -d "\"")
        fi
        echo "$geo"
    ' 2>/dev/null)
    echo "$geo"
}

reapply_routing() {
    local server_ip=$1
    timeout 20 sshpass -p 'uto6703' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@$server_ip \
        'bash /usr/local/bin/setup_google_ai_routing.sh' 2>/dev/null
}

echo "$LOG_PREFIX === OpenWrt Gemini Monitor Start ==="

ALERT_MSG=""
ALL_OK=true

for probe in "${OPENWRT_PROBES[@]}"; do
    IFS=':' read -r openwrt_gw test_server desc <<< "$probe"
    
    geo=$(check_gemini_via_server "$test_server")
    
    if [ -z "$geo" ]; then
        status="TIMEOUT"
        ALL_OK=false
        sname=$(get_server_name $test_server)
        ALERT_MSG="${ALERT_MSG}\n⚠️ ${desc} ${sname}: Gem 응답없음"
        echo "$LOG_PREFIX [WARN] $desc $sname → Gemini timeout"
    else
        is_blocked=false
        for bg in $BLOCKED_GEOS; do
            if [ "$geo" = "$bg" ]; then is_blocked=true; break; fi
        done
        
        if $is_blocked; then
            sname=$(get_server_name $test_server)
            echo "$LOG_PREFIX [WARN] $desc $sname → geo=$geo — 재검사 중..."
            sleep 10
            geo2=$(check_gemini_via_server "$test_server")
            is_blocked2=false
            for bg in $BLOCKED_GEOS; do
                if [ "$geo2" = "$bg" ]; then is_blocked2=true; break; fi
            done
            
            if $is_blocked2; then
                ALL_OK=false
                echo "$LOG_PREFIX [FAIL] $desc $sname → 재검사도 geo=$geo2 (BLOCKED!)"
                # 해당 그룹의 전 서버명 목록 만들기
                all_names=""
                for srv in ${OPENWRT_SERVERS[$openwrt_gw]}; do
                    all_names="${all_names} $(get_server_name $srv)"
                done
                ALERT_MSG="${ALERT_MSG}\n🚫 ${desc} 차단확인(2회)! geo=${geo2}\n  테스트: ${sname}\n  영향서버:${all_names}"
                
                # 해당 OpenWrt에 연결된 모든 서버 라우팅 재적용
                echo "$LOG_PREFIX [FIX] Reapplying routing for $desc servers..."
                for srv in ${OPENWRT_SERVERS[$openwrt_gw]}; do
                    reapply_routing "$srv"
                    echo "$LOG_PREFIX   - $(get_server_name $srv) reapplied"
                done
            else
                echo "$LOG_PREFIX [OK] $desc $sname → 재검사 geo=${geo2:-NONE} (오탐, 무시)"
            fi
        else
            echo "$LOG_PREFIX [OK] $desc $(get_server_name $test_server) → geo=$geo"
        fi
    fi
done

if ! $ALL_OK; then
    NOW=$(date '+%m/%d %H:%M')
    send_pushplus "⚠️ OW Gem 차단감지" "$(echo -e "$ALERT_MSG")\n\n시간: $NOW\n라우팅 재적용 시도함"
    echo "$LOG_PREFIX [ALERT] PushPlus notification sent"
fi

echo "$LOG_PREFIX === Monitor Done ==="

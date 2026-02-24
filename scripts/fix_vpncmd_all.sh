#!/bin/bash
# fix_vpncmd_all.sh — vpncmd hang 근본 해결 전체 서버 배포
# 
# 근본 원인: vpncmd는 인증 실패 시 대화형 패스워드 프롬프트를 띄움.
#   cron/script에서 실행 시 stdin이 없어도 랜덤 메모리를 읽어 무한 retry → CPU 100%
#
# 해결책:
#   1. check_traffic_10s.sh에 < /dev/null 추가 → 프롬프트 즉시 EOF
#   2. vpncmd 래퍼(/usr/local/bin/vpncmd-safe) 생성 → timeout + /dev/null 강제
#   3. cleanup_stale_qos.sh에 행 vpncmd 자동 kill 추가
#
# 사용법: bash fix_vpncmd_all.sh

PW="ss135690"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8"

# 모든 VPN 서버 IP
SERVERS="
14.51.2.130 14.51.2.131 14.51.2.132 218.158.57.23 121.159.134.27
211.216.225.224 220.82.114.127 220.123.216.40 220.123.216.21 220.123.89.51
218.158.57.25 125.132.9.135 125.132.9.136 125.132.9.137 125.132.9.138
125.132.9.139 14.51.2.179 125.132.9.140 125.132.9.141 125.132.9.142
112.218.79.75 221.143.197.130 221.143.197.131 221.143.197.132 221.143.197.133
221.143.197.134 221.143.197.135 221.143.197.136 218.236.231.231 218.236.231.232
218.49.179.74 218.49.179.75 218.49.179.76 218.49.179.77 218.49.179.78
218.49.179.79
"

i=0
ok=0
fail=0

for ip in $SERVERS; do
    i=$((i+1))
    printf "[%2d] %-18s " "$i" "$ip"
    
    OUT=$(timeout 25 sshpass -p "$PW" ssh $SSH_OPTS root@$ip bash -s 2>/dev/null << 'REMOTECMD'
RESULT=""

# === 1. 행 vpncmd 즉시 kill ===
KILLED=0
for pid in $(ps aux | grep vpncmd | grep -v grep | awk '$3>50{print $2}'); do
    kill -9 $pid 2>/dev/null
    KILLED=$((KILLED+1))
done
[ $KILLED -gt 0 ] && RESULT="KILLED:$KILLED "

# === 2. check_traffic_10s.sh 패치 ===
if [ -f /root/check_traffic_10s.sh ]; then
    CHANGED=0
    
    # 2a. timeout 추가 (아직 없으면)
    if ! grep -q 'timeout.*VPNCMD\|timeout.*vpncmd' /root/check_traffic_10s.sh; then
        sed -i 's|SOFTETHER_COUNT=$($VPNCMD |SOFTETHER_COUNT=$(timeout 15 $VPNCMD |' /root/check_traffic_10s.sh
        CHANGED=1
    fi
    
    # 2b. < /dev/null 추가 — vpncmd 호출에 stdin 차단 (핵심!)
    # "grep -c "User Name")" 뒤에 아직 /dev/null이 없으면 추가
    if ! grep -q '/dev/null' /root/check_traffic_10s.sh; then
        # SessionList ... | grep -c "User Name") 를 찾아서
        # SessionList ... | grep -c "User Name") 뒤에 < /dev/null 삽입은 복잡하므로
        # 전체 SOFTETHER_COUNT 줄을 교체
        # 현재 패턴: SOFTETHER_COUNT=$(timeout 15 $VPNCMD /server localhost /password:"$VPN_PASS" /adminhub:"$HUB_NAME" /cmd SessionList | grep -c "User Name")
        sed -i 's|/cmd SessionList |/cmd SessionList < /dev/null |' /root/check_traffic_10s.sh
        CHANGED=1
    fi
    
    [ $CHANGED -eq 1 ] && RESULT="${RESULT}SCRIPT_PATCHED " || RESULT="${RESULT}SCRIPT_OK "
else
    RESULT="${RESULT}NO_SCRIPT "
fi

# === 3. vpncmd-safe 래퍼 생성 ===
cat > /usr/local/bin/vpncmd-safe << 'WRAPPER'
#!/bin/bash
# vpncmd-safe: vpncmd를 안전하게 실행하는 래퍼
# - 항상 timeout 적용 (기본 15초)
# - stdin을 /dev/null로 리다이렉트하여 대화형 프롬프트 차단
# - CPU 100% hang 방지
TIMEOUT=${VPNCMD_TIMEOUT:-15}
exec timeout $TIMEOUT /usr/local/vpnserver/vpncmd "$@" < /dev/null
WRAPPER
chmod +x /usr/local/bin/vpncmd-safe
RESULT="${RESULT}WRAPPER_OK "

# === 4. cleanup_stale_qos.sh에 vpncmd hang kill 추가 ===
CLEANUP="/etc/strongswan/cleanup_stale_qos.sh"
if [ -f "$CLEANUP" ]; then
    if ! grep -q 'vpncmd.*kill\|kill.*vpncmd' "$CLEANUP"; then
        # 스크립트 시작 부분에 vpncmd hang 체크 추가
        sed -i '/^#!/a\\n# Kill hung vpncmd processes (CPU 100% prevention)\nfor pid in $(ps aux | grep vpncmd | grep -v grep | awk '"'"'$3>80{print $2}'"'"'); do\n    kill -9 $pid 2>/dev/null\n    logger "cleanup: killed hung vpncmd PID $pid"\ndone' "$CLEANUP"
        RESULT="${RESULT}CLEANUP_PATCHED "
    else
        RESULT="${RESULT}CLEANUP_OK "
    fi
else
    RESULT="${RESULT}NO_CLEANUP "
fi

echo "$RESULT"
REMOTECMD
)
    
    if [ -z "$OUT" ]; then
        echo "TIMEOUT/UNREACHABLE"
        fail=$((fail+1))
    else
        echo "$OUT"
        ok=$((ok+1))
    fi
done

echo ""
echo "=== 결과: 성공=$ok 실패=$fail 전체=$i ==="

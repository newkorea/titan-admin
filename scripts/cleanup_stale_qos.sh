#!/bin/bash
# ============================================================
# cleanup_stale_qos.sh
# VPN 세션 비정상 종료 시 잔존하는 TC/iptables QoS 규칙 정리
#
# 문제: StrongSwan down-client 미발동 시 TC class + iptables
#       MARK 규칙이 누적 → 패킷 처리 지연 + 커널 에러
#
# 배포: /etc/strongswan/cleanup_stale_qos.sh
# 크론: */5 * * * * /etc/strongswan/cleanup_stale_qos.sh
# ============================================================

IFACE="eth0"
TC=/sbin/tc
IPTABLES=/sbin/iptables
LOG_TAG="cleanup_qos"

# ---- 1. 활성 VPN 가상IP 수집 ----
collect_active_ips() {
    # StrongSwan IKEv2 (10.x.x.x/32 형태)
    strongswan statusall 2>/dev/null \
        | grep -oE '10\.[0-9]+\.[0-9]+\.[0-9]+/32' \
        | sed 's|/32||'

    # OpenVPN (status 파일에서 CLIENT_LIST)
    awk -F',' '/^CLIENT_LIST/{print $4}' \
        /run/openvpn-server/status-test2.log 2>/dev/null

    # SoftEther (vpn-bridge / tap_soft ARP 테이블)
    arp -an 2>/dev/null | grep -oE '10\.(50|20)\.[0-9]+\.[0-9]+'
}

TMPFILE=$(mktemp)
collect_active_ips | sort -u > "$TMPFILE"
ACTIVE_COUNT=$(wc -l < "$TMPFILE")

# ---- 2. iptables mangle 정리 ----
# 활성 IP가 아닌 VPN 가상IP(10.x.x.x)의 MARK 규칙 삭제
clean_iptables_chain() {
    local CHAIN="$1"
    local FLAG="$2"   # -s for PREROUTING, -d for POSTROUTING
    local removed=0

    while IFS= read -r rule; do
        [ -z "$rule" ] && continue
        # IP 추출
        local ip
        ip=$(echo "$rule" | grep -oP "(?<=${FLAG} )[0-9.]+")
        [ -z "$ip" ] && continue
        # VPN 가상IP만 대상 (10.x.x.x)
        [[ "$ip" =~ ^10\. ]] || continue
        # 활성 목록에 없으면 삭제
        if ! grep -qx "$ip" "$TMPFILE"; then
            local del_rule
            del_rule=$(echo "$rule" | sed 's/^-A/-D/')
            $IPTABLES -t mangle $del_rule 2>/dev/null && removed=$((removed + 1))
        fi
    done < <($IPTABLES -t mangle -S "$CHAIN" 2>/dev/null | grep 'set-xmark')

    echo "$removed"
}

PRE_REMOVED=$(clean_iptables_chain "PREROUTING" "-s")
POST_REMOVED=$(clean_iptables_chain "POSTROUTING" "-d")
TOTAL_REMOVED=$((PRE_REMOVED + POST_REMOVED))

# ---- 3. TC 클래스 정리 ----
# 정리 후 iptables에 남은 활성 mark만 유지, 나머지 TC class 삭제
TC_REMOVED=0
TC_COUNT=$($TC class show dev "$IFACE" 2>/dev/null | grep -c 'parent 1:1 ')

# TC 클래스가 일정 수 이상이면 개별 정리 시도
if [ "$TC_COUNT" -gt 50 ]; then
    # 현재 iptables에 남아있는 활성 mark 수집 (hex)
    ACTIVE_MARKS=$($IPTABLES -t mangle -S PREROUTING 2>/dev/null \
        | grep 'set-xmark' \
        | grep -oP '0x[0-9a-fA-F]+(?=/)' \
        | sort -u)

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        # classid 추출 (예: 1:3f8 → 3f8)
        local_classid=$(echo "$line" | awk '{print $3}' | cut -d: -f2)
        [ -z "$local_classid" ] && continue
        [ "$local_classid" = "1" ] && continue  # root class 보호

        hex_mark="0x${local_classid}"
        if ! echo "$ACTIVE_MARKS" | grep -qi "^${hex_mark}$"; then
            $TC filter del dev "$IFACE" protocol ip parent 1: prio 1 \
                handle "$local_classid" fw flowid 1:"$local_classid" 2>/dev/null
            $TC qdisc del dev "$IFACE" parent 1:"$local_classid" \
                handle "$local_classid": sfq 2>/dev/null
            $TC class del dev "$IFACE" parent 1:1 \
                classid 1:"$local_classid" 2>/dev/null
            TC_REMOVED=$((TC_REMOVED + 1))
        fi
    done < <($TC class show dev "$IFACE" 2>/dev/null | grep 'parent 1:1 ')
fi

# TC 개별 삭제 후에도 너무 많으면 전체 리셋
TC_AFTER=$($TC class show dev "$IFACE" 2>/dev/null | grep -c 'parent 1:1 ')
THRESHOLD=$(( (ACTIVE_COUNT + 1) * 3 + 50 ))
if [ "$TC_AFTER" -gt "$THRESHOLD" ] && [ "$TC_AFTER" -gt 200 ]; then
    $TC qdisc del dev "$IFACE" root 2>/dev/null
    # root qdisc 재초기화 (updown 스크립트가 새 연결에서 재생성)
    $TC qdisc add dev "$IFACE" root handle 1: htb default 9999
    $TC class add dev "$IFACE" parent 1: classid 1:1 htb rate 1gbit ceil 1gbit
    logger -t "$LOG_TAG" "TC full reset: was ${TC_AFTER} classes (active: ${ACTIVE_COUNT})"
fi

# ---- 4. 로깅 ----
if [ "$TOTAL_REMOVED" -gt 0 ] || [ "$TC_REMOVED" -gt 0 ]; then
    logger -t "$LOG_TAG" "Cleaned: iptables=${TOTAL_REMOVED} (pre=${PRE_REMOVED},post=${POST_REMOVED}) tc=${TC_REMOVED} active=${ACTIVE_COUNT}"
fi

rm -f "$TMPFILE"

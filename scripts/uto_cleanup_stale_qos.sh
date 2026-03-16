#!/bin/bash
# ============================================================
# uto_cleanup_stale_qos.sh  v2.0
# UTO VPN 서버용 — 비정상 종료된 세션의 TC/iptables QoS 잔존 규칙 정리
#
# 문제: StrongSwan down-client 미발동 시 iptables FORWARD MARK 규칙이
#       수천 개 누적 → 패킷 처리 지연 + 메모리 증가 → 서버 사망
#
# v2.0 변경:
#   - iptables-save/restore 를 사용하여 대량 규칙 고속 처리
#   - 같은 IP에 중복 MARK(재접속) 규칙도 정리 (최신 1세트만 유지)
#   - TC 리셋 로직 유지
#
# 배포: /etc/strongswan/cleanup_stale_qos.sh
# 크론: */5 * * * * /etc/strongswan/cleanup_stale_qos.sh >> /var/log/cleanup_qos.log 2>&1
# ============================================================

IFACE="eth0"
TC=/sbin/tc
LOG_TAG="cleanup_qos"
# Ensure /usr/sbin in PATH (cron default may not include it)
export PATH="/usr/sbin:/sbin:/usr/bin:/bin:$PATH"

# ---- 1. 활성 VPN 가상IP + 현재 MARK ID 수집 ----
TMPDIR_WORK=$(mktemp -d)
ACTIVE_IPS="$TMPDIR_WORK/active_ips"
ACTIVE_MARKS="$TMPDIR_WORK/active_marks"

# StrongSwan: IP + UNIQUEID (mark = 1000 + UNIQUEID % 9999)
strongswan statusall 2>/dev/null \
    | grep -oE '10\.[0-9]+\.[0-9]+\.[0-9]+/32' \
    | sed 's|/32||' | sort -u > "$ACTIVE_IPS"

# OpenVPN (여러 status 파일)
for sf in /var/log/openvpn/status.log /var/log/openvpn/utostatus.log /run/openvpn-server/*.log; do
    [ -f "$sf" ] || continue
    awk -F',' '/^CLIENT_LIST/{print $4}' "$sf" 2>/dev/null >> "$ACTIVE_IPS"
done
sort -u "$ACTIVE_IPS" -o "$ACTIVE_IPS"
ACTIVE_COUNT=$(wc -l < "$ACTIVE_IPS")

# ---- 2. iptables 고속 정리 (iptables-save/restore) ----
BEFORE=$(iptables -S FORWARD 2>/dev/null | grep -cE 'set-xmark|set-mark')

if [ "$BEFORE" -gt "$((ACTIVE_COUNT * 2 + 10))" ]; then
    # 고속 방식: iptables-save로 전체 저장 → 파이프라인으로 필터 → iptables-restore
    SAVED="$TMPDIR_WORK/ipt_saved"
    FILTERED="$TMPDIR_WORK/ipt_filtered"

    iptables-save > "$SAVED"

    # 활성IP의 마지막 mark만 보존, 비활성IP 전부 제거
    # 순수 awk로 처리 (python3 없는 서버 호환)
    awk -v active_file="$ACTIVE_IPS" '
    BEGIN {
        while ((getline line < active_file) > 0) {
            gsub(/[[:space:]]/, "", line)
            if (line != "") active[line] = 1
        }
        close(active_file)
    }
    /set-xmark|set-mark/ {
        # Extract IP (10.x.x.x/32)
        match($0, /10\.[0-9]+\.[0-9]+\.[0-9]+/)
        if (RSTART > 0) {
            ip = substr($0, RSTART, RLENGTH)
            if (ip in active) {
                # Active IP: collect, will keep latest pair only
                mark_lines[++mark_count] = $0
                mark_ips[mark_count] = ip
            }
            # Inactive: skip entirely
        } else {
            # Non-VPN MARK rule: keep
            print
        }
        next
    }
    # Non-MARK lines: keep as-is, but track COMMIT position
    /^\*filter/ { in_filter = 1 }
    in_filter && /^COMMIT/ {
        # Dump kept mark lines before COMMIT
        # Reverse scan to keep only last 2 per IP (latest -s and -d)
        for (i = mark_count; i >= 1; i--) {
            ip = mark_ips[i]
            if (!(ip in seen) || seen[ip] < 2) {
                keep[i] = 1
                seen[ip]++
            }
        }
        for (i = 1; i <= mark_count; i++) {
            if (i in keep) print mark_lines[i]
        }
        in_filter = 0
    }
    { print }
    ' "$SAVED" > "$FILTERED"

    if [ -s "$FILTERED" ]; then
        iptables-restore < "$FILTERED" 2>/dev/null
    fi
fi

AFTER=$(iptables -S FORWARD 2>/dev/null | grep -cE 'set-xmark|set-mark')
IPRULES_REMOVED=$((BEFORE - AFTER))
[ "$IPRULES_REMOVED" -lt 0 ] && IPRULES_REMOVED=0

# ---- 3. TC 클래스 정리 ----
TC_REMOVED=0
TC_COUNT=$($TC class show dev "$IFACE" 2>/dev/null | grep -c 'parent 1:1 ')

if [ "$TC_COUNT" -gt 50 ]; then
    # 현재 iptables FORWARD에 남아있는 활성 mark 수집
    MARK_HEX=$(iptables -S FORWARD 2>/dev/null \
        | grep -oP '0x[0-9a-fA-F]+(?=/0x)' | sort -u)

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local_classid=$(echo "$line" | awk '{print $3}' | cut -d: -f2)
        [ -z "$local_classid" ] && continue
        [ "$local_classid" = "1" ] && continue

        hex_mark="0x${local_classid}"
        if ! echo "$MARK_HEX" | grep -qi "^${hex_mark}$"; then
            $TC filter del dev "$IFACE" protocol ip parent 1: prio 1 \
                handle "$local_classid" fw flowid 1:"$local_classid" 2>/dev/null
            $TC qdisc del dev "$IFACE" parent 1:"$local_classid" 2>/dev/null
            $TC class del dev "$IFACE" parent 1:1 \
                classid 1:"$local_classid" 2>/dev/null
            TC_REMOVED=$((TC_REMOVED + 1))
        fi
    done < <($TC class show dev "$IFACE" 2>/dev/null | grep 'parent 1:1 ')
fi

# TC 전체 리셋 (개별 삭제 후에도 너무 많으면)
TC_AFTER=$($TC class show dev "$IFACE" 2>/dev/null | grep -c 'parent 1:1 ')
THRESHOLD=$(( (ACTIVE_COUNT + 1) * 3 + 50 ))
if [ "$TC_AFTER" -gt "$THRESHOLD" ] && [ "$TC_AFTER" -gt 300 ]; then
    $TC qdisc del dev "$IFACE" root 2>/dev/null
    $TC qdisc add dev "$IFACE" root handle 1: htb default 9999
    $TC class add dev "$IFACE" parent 1: classid 1:1 htb rate 1gbit ceil 1gbit
    logger -t "$LOG_TAG" "TC full reset: was ${TC_AFTER} classes (active: ${ACTIVE_COUNT})"
fi

# ---- 4. 로그 파일 크기 제한 ----
LOG_FILE="/var/log/cleanup_qos.log"
if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt 5242880 ]; then
    tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# ---- 5. 로깅 ----
if [ "$IPRULES_REMOVED" -gt 0 ] || [ "$TC_REMOVED" -gt 0 ]; then
    NOW=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$NOW [CLEANUP] iptables=${IPRULES_REMOVED} tc=${TC_REMOVED} active_vpn=${ACTIVE_COUNT} ipt_before=${BEFORE} ipt_after=${AFTER} tc_before=${TC_COUNT} tc_after=${TC_AFTER}"
    logger -t "$LOG_TAG" "Cleaned: iptables=${IPRULES_REMOVED} tc=${TC_REMOVED} active=${ACTIVE_COUNT}"
fi

rm -rf "$TMPDIR_WORK"

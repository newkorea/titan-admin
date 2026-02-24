#!/bin/bash
# run_cleanup_v3.sh - 무조건 flush + TC reset (카운트 조회 없이 바로 실행)

SERVERS=(
"221.143.197.136:ss135690:SK16"
"218.236.231.231:ss135690:SK21"
"218.236.231.232:ss135690:SK22"
"218.49.179.74:ss135690:SK4"
"218.49.179.75:ss135690:SK5"
"218.49.179.78:ss135690:SK8"
"218.49.179.77:ss135690:SK7"
"218.49.179.76:ss135690:SK6"
"218.49.179.79:ss135690:SK9"
"14.51.2.131:ss135690:KT1"
"218.158.57.25:ss135690:KT33"
"14.51.2.179:ss135690:KT4"
"221.143.197.134:ss135690:SK14"
"221.143.197.130:ss135690:SK10"
"112.218.79.75:ss135690:LG2"
"221.143.197.135:ss135690:SK15"
"221.143.197.131:ss135690:SK11"
"125.132.9.141:ss135690:KT41"
"125.132.9.137:ss135690:KT37"
)

TOTAL=${#SERVERS[@]}
i=0

for entry in "${SERVERS[@]}"; do
    IFS=':' read -r ip pw name <<< "$entry"
    i=$((i+1))
    printf "[%2d/%d] %-6s %-18s " "$i" "$TOTAL" "$name" "$ip"
    
    # Step 1: flush (빠르게, 카운트 조회 없이)
    OUT1=$(timeout 20 sshpass -p "$pw" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=6 \
        "root@${ip}" "iptables -t mangle -F PREROUTING 2>/dev/null; iptables -t mangle -F POSTROUTING 2>/dev/null; tc qdisc del dev eth0 root 2>/dev/null; tc qdisc add dev eth0 root handle 1: htb default 9999; tc class add dev eth0 parent 1: classid 1:1 htb rate 1gbit ceil 1gbit; echo FLUSHED" 2>/dev/null)
    
    if echo "$OUT1" | grep -q "FLUSHED"; then
        # Step 2: 결과 확인
        OUT2=$(timeout 10 sshpass -p "$pw" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=6 \
            "root@${ip}" "echo TC=\$(tc class show dev eth0 2>/dev/null | wc -l) IPT=\$(iptables -t mangle -S PREROUTING 2>/dev/null | wc -l)" 2>/dev/null)
        echo "✅ FLUSHED | $OUT2"
    else
        echo "❌ flush failed or timeout"
    fi
done

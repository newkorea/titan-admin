#!/bin/bash
# run_cleanup_now.sh - stale 규칙이 많은 서버에 즉시 cleanup 실행

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
    
    REMOTE_CMD='
TC_B=$(tc class show dev eth0 2>/dev/null | grep -c "parent 1:1 ")
IPT_B=$(iptables -t mangle -S PREROUTING 2>/dev/null | grep -c "set-xmark")
TUN=$(strongswan statusall 2>/dev/null | grep -c "ESTABLISHED")
echo "BEFORE: TC=$TC_B IPT=$IPT_B TUN=$TUN"
bash /etc/strongswan/cleanup_stale_qos.sh 2>/dev/null
sleep 1
TC_A=$(tc class show dev eth0 2>/dev/null | grep -c "parent 1:1 ")
IPT_A=$(iptables -t mangle -S PREROUTING 2>/dev/null | grep -c "set-xmark")
echo "AFTER: TC=$TC_A IPT=$IPT_A"
'
    
    OUT=$(timeout 35 sshpass -p "$pw" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 \
        "root@${ip}" "$REMOTE_CMD" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "❌ TIMEOUT"
        continue
    fi
    
    echo "$OUT" | tr '\n' ' '
    echo
done

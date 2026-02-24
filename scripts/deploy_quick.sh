#!/bin/bash
# deploy_quick.sh - 모든 NAS에 cleanup_stale_qos.sh 배포 (간결 버전)

cd /home/newkorea/project/titan-admin
source venv/bin/activate

SCRIPT="/home/newkorea/project/scripts/cleanup_stale_qos.sh"

# 서버 목록 가져오기
SERVERS=$(python3 -c "
import os, sys
sys.path.insert(0, '/home/newkorea/project/titan-admin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django; django.setup()
from django.db import connections
cursor = connections['default'].cursor()
cursor.execute('SELECT name, hostip, password FROM tbl_agent3 WHERE is_active=1 ORDER BY name')
for r in cursor.fetchall():
    print(f'{r[0]}|{r[1]}|{r[2]}')
")

TOTAL=$(echo "$SERVERS" | wc -l)
i=0

echo "=== 전체 $TOTAL 서버 배포 시작 ==="
echo ""

while IFS='|' read -r name ip pw; do
    i=$((i+1))
    printf "[%2d/%d] %-20s %-18s " "$i" "$TOTAL" "$name" "$ip"
    
    # SCP
    sshpass -p "$pw" scp -o StrictHostKeyChecking=no -o ConnectTimeout=6 \
        "$SCRIPT" "root@${ip}:/etc/strongswan/cleanup_stale_qos.sh" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ SCP실패"
        continue
    fi
    
    # SSH: chmod + cron + threads + stale count
    OUT=$(timeout 20 sshpass -p "$pw" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 \
        "root@${ip}" bash -s 2>/dev/null << 'REMOTECMD'
chmod +x /etc/strongswan/cleanup_stale_qos.sh 2>/dev/null

# cron
if ! crontab -l 2>/dev/null | grep -q cleanup_stale_qos; then
    (crontab -l 2>/dev/null; echo '*/5 * * * * /etc/strongswan/cleanup_stale_qos.sh') | crontab -
    echo "CRON=added"
else
    echo "CRON=ok"
fi

# threads
T=$(grep -oP 'threads\s*=\s*\K[0-9]+' /etc/strongswan/strongswan.conf 2>/dev/null | head -1)
if [ -n "$T" ] && [ "$T" -lt 32 ] 2>/dev/null; then
    cp /etc/strongswan/strongswan.conf /etc/strongswan/strongswan.conf.bak_threads 2>/dev/null
    sed -i "s/threads\s*=\s*$T/threads = 32/" /etc/strongswan/strongswan.conf
    echo "THREADS=${T}->32"
else
    echo "THREADS=${T:-none}"
fi

# stale count
TC=$(tc class show dev eth0 2>/dev/null | grep -c 'parent 1:1 ')
IPT=$(iptables -t mangle -S PREROUTING 2>/dev/null | grep -c 'set-xmark')
TUN=$(strongswan statusall 2>/dev/null | grep -c 'ESTABLISHED')
echo "TC=$TC IPT=$IPT TUN=$TUN"
REMOTECMD
    )
    
    if [ $? -ne 0 ]; then
        echo "✅SCP ❌SSH타임아웃"
        continue
    fi
    
    # 결과 출력
    CRON=$(echo "$OUT" | grep -oP 'CRON=\K\S+')
    THREADS=$(echo "$OUT" | grep -oP 'THREADS=\K\S+')
    STATS=$(echo "$OUT" | grep -oP 'TC=\d+ IPT=\d+ TUN=\d+')
    
    printf "✅ cron=%s threads=%s %s\n" "${CRON:-?}" "${THREADS:-?}" "${STATS:-}"
    
done <<< "$SERVERS"

echo ""
echo "=== 배포 완료 ==="

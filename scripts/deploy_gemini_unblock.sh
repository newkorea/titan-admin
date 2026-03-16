#!/bin/bash
# deploy_gemini_unblock.sh — Gemini 차단 해제 배포 스크립트
# 2026-03-02
#
# 차단 서버 8대의 Google 트래픽을 비차단 서버로 우회:
#   Group 1: SK4,5,7,8,9 → SK6 (같은 /27, MASQUERADE)
#   Group 2: SK14,16 → SK10 (같은 /27, MASQUERADE)
#   Group 3: LG3 → KT0 → OpenWrt (IPIP 터널)

set -euo pipefail

GOOGLE_CIDRS="8.8.4.0/24 8.8.8.0/24 64.233.160.0/19 66.102.0.0/20 66.249.64.0/19 72.14.192.0/18 74.125.0.0/16 108.177.0.0/17 108.170.192.0/18 130.211.0.0/16 142.250.0.0/15 172.217.0.0/16 172.253.0.0/16 173.194.0.0/16 192.178.0.0/15 209.85.128.0/17 216.58.192.0/19 216.239.32.0/19 199.223.232.0/21 207.223.160.0/20 14.0.112.0/24"

SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no"

OK=0
FAIL=0

run_ssh() {
    local ip=$1 desc=$2
    shift 2
    echo -n "  $desc ($ip)... "
    if ssh $SSH_OPTS root@"$ip" "$@" 2>/dev/null; then
        echo "OK"
        ((OK++))
    else
        echo "FAIL"
        ((FAIL++))
    fi
}

echo "============================================"
echo " Gemini 차단 해제 배포"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# ============================================
# Group 1: SK6 → gateway for SK4,5,7,8,9
# ============================================
echo ""
echo "--- Group 1: SK4,5,7,8,9 → SK6 (218.49.179.76) ---"
echo ""

# SK6 gateway 설정
GW_SK6="218.49.179.76"
SUBNET_SK="218.49.179.64/27"
echo "[1/3] SK6 게이트웨이 설정"
run_ssh $GW_SK6 "SK6 NAT setup" bash -c "'
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1

# MASQUERADE for same-subnet blocked servers
iptables -t nat -C POSTROUTING -s $SUBNET_SK -o eth0 -j MASQUERADE 2>/dev/null || \
iptables -t nat -A POSTROUTING -s $SUBNET_SK -o eth0 -j MASQUERADE

# FORWARD accept
iptables -C FORWARD -s $SUBNET_SK -j ACCEPT 2>/dev/null || \
iptables -I FORWARD 1 -s $SUBNET_SK -j ACCEPT

# Persist in rc.local
grep -q \"setup_google_nat_sk6\" /etc/rc.local 2>/dev/null || {
    cat > /usr/local/bin/setup_google_nat_sk6.sh << \"RCEOF\"
#!/bin/bash
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
iptables -t nat -C POSTROUTING -s 218.49.179.64/27 -o eth0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 218.49.179.64/27 -o eth0 -j MASQUERADE
iptables -C FORWARD -s 218.49.179.64/27 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s 218.49.179.64/27 -j ACCEPT
RCEOF
    chmod +x /usr/local/bin/setup_google_nat_sk6.sh
    sed -i \"/^exit 0/i /usr/local/bin/setup_google_nat_sk6.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_google_nat_sk6.sh\" >> /etc/rc.local
}
echo done
'"

# SK4,5,7,8,9 route 설정
for i in 74 75 77 78 79; do
    ip="218.49.179.$i"
    name="SK$((i-70))"
    echo "[routes] $name"
    run_ssh $ip "$name routes" bash -c "'
for c in $GOOGLE_CIDRS; do ip route add \$c via $GW_SK6 dev eth0 2>/dev/null; done

# Persist
cat > /usr/local/bin/setup_google_routes.sh << \"SEOF\"
#!/bin/bash
# Google CIDR routes via SK6 for Gemini unblocking
GW=\"218.49.179.76\"
CIDRS=\"$GOOGLE_CIDRS\"
for c in \$CIDRS; do ip route add \$c via \$GW dev eth0 2>/dev/null; done
echo \"Google routes via SK6 ready\"
SEOF
chmod +x /usr/local/bin/setup_google_routes.sh
grep -q \"setup_google_routes\" /etc/rc.local 2>/dev/null || {
    sed -i \"/^exit 0/i /usr/local/bin/setup_google_routes.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_google_routes.sh\" >> /etc/rc.local
}
echo done
'"
done

# ============================================
# Group 2: SK10 → gateway for SK14,16
# ============================================
echo ""
echo "--- Group 2: SK14,16 → SK10 (221.143.197.130) ---"
echo ""

GW_SK10="221.143.197.130"
SUBNET_SK2="221.143.197.128/27"
echo "[1/3] SK10 게이트웨이 설정"
run_ssh $GW_SK10 "SK10 NAT setup" bash -c "'
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1

iptables -t nat -C POSTROUTING -s $SUBNET_SK2 -o eth0 -j MASQUERADE 2>/dev/null || \
iptables -t nat -A POSTROUTING -s $SUBNET_SK2 -o eth0 -j MASQUERADE

iptables -C FORWARD -s $SUBNET_SK2 -j ACCEPT 2>/dev/null || \
iptables -I FORWARD 1 -s $SUBNET_SK2 -j ACCEPT

grep -q \"setup_google_nat_sk10\" /etc/rc.local 2>/dev/null || {
    cat > /usr/local/bin/setup_google_nat_sk10.sh << \"RCEOF\"
#!/bin/bash
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
iptables -t nat -C POSTROUTING -s 221.143.197.128/27 -o eth0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 221.143.197.128/27 -o eth0 -j MASQUERADE
iptables -C FORWARD -s 221.143.197.128/27 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s 221.143.197.128/27 -j ACCEPT
RCEOF
    chmod +x /usr/local/bin/setup_google_nat_sk10.sh
    sed -i \"/^exit 0/i /usr/local/bin/setup_google_nat_sk10.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_google_nat_sk10.sh\" >> /etc/rc.local
}
echo done
'"

for ip in 221.143.197.134 221.143.197.136; do
    name=$([ "$ip" = "221.143.197.134" ] && echo "SK14" || echo "SK16")
    echo "[routes] $name"
    run_ssh $ip "$name routes" bash -c "'
for c in $GOOGLE_CIDRS; do ip route add \$c via $GW_SK10 dev eth0 2>/dev/null; done

cat > /usr/local/bin/setup_google_routes.sh << \"SEOF\"
#!/bin/bash
GW=\"221.143.197.130\"
CIDRS=\"$GOOGLE_CIDRS\"
for c in \$CIDRS; do ip route add \$c via \$GW dev eth0 2>/dev/null; done
echo \"Google routes via SK10 ready\"
SEOF
chmod +x /usr/local/bin/setup_google_routes.sh
grep -q \"setup_google_routes\" /etc/rc.local 2>/dev/null || {
    sed -i \"/^exit 0/i /usr/local/bin/setup_google_routes.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_google_routes.sh\" >> /etc/rc.local
}
echo done
'"
done

# ============================================
# Group 3: LG3 → KT0 → OpenWrt (IPIP tunnel)
# ============================================
echo ""
echo "--- Group 3: LG3 → KT0 (IPIP tunnel) ---"
echo ""

KT0_IP="14.51.2.130"
LG3_IP="1.221.16.187"
# LG2 uses 10.99.0.0/30 (KT0=10.99.0.1, LG2=10.99.0.2)
# LG3 uses 10.99.0.4/30 (KT0=10.99.0.5, LG3=10.99.0.6)
TUN_KT0="10.99.0.5"
TUN_LG3="10.99.0.6"

echo "[1/2] KT0 터널 설정 (lg3tun)"
run_ssh $KT0_IP "KT0 lg3tun" bash -c "'
ip tunnel add lg3tun mode ipip remote $LG3_IP local $KT0_IP 2>/dev/null
ip addr add $TUN_KT0/30 dev lg3tun 2>/dev/null
ip link set lg3tun up 2>/dev/null

# Allow IPIP from LG3
iptables -C INPUT -p 4 -s $LG3_IP -j ACCEPT 2>/dev/null || \
iptables -I INPUT 1 -p 4 -s $LG3_IP -j ACCEPT

# MASQUERADE for LG3 tunnel traffic
iptables -t nat -C POSTROUTING -s $LG3_IP -o eth0 -j MASQUERADE 2>/dev/null || \
iptables -t nat -A POSTROUTING -s $LG3_IP -o eth0 -j MASQUERADE

# FORWARD for tunnel subnet
iptables -C FORWARD -s 10.99.0.4/30 -j ACCEPT 2>/dev/null || \
iptables -I FORWARD 1 -s 10.99.0.4/30 -j ACCEPT

# Update persistent script
cat > /usr/local/bin/setup_lg3_tunnel.sh << \"TEOF\"
#!/bin/bash
ip tunnel add lg3tun mode ipip remote 1.221.16.187 local 14.51.2.130 2>/dev/null
ip addr add 10.99.0.5/30 dev lg3tun 2>/dev/null
ip link set lg3tun up 2>/dev/null
iptables -C INPUT -p 4 -s 1.221.16.187 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p 4 -s 1.221.16.187 -j ACCEPT
iptables -t nat -C POSTROUTING -s 1.221.16.187 -o eth0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 1.221.16.187 -o eth0 -j MASQUERADE
iptables -C FORWARD -s 10.99.0.4/30 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s 10.99.0.4/30 -j ACCEPT
echo \"KT0 LG3 tunnel ready\"
TEOF
chmod +x /usr/local/bin/setup_lg3_tunnel.sh
grep -q \"setup_lg3_tunnel\" /etc/rc.local 2>/dev/null || {
    sed -i \"/^exit 0/i /usr/local/bin/setup_lg3_tunnel.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_lg3_tunnel.sh\" >> /etc/rc.local
}
echo done
'"

echo "[2/2] LG3 터널 + 라우트 설정"
run_ssh $LG3_IP "LG3 tunnel+routes" bash -c "'
ip tunnel add lg3tun mode ipip remote $KT0_IP local $LG3_IP 2>/dev/null
ip addr add $TUN_LG3/30 dev lg3tun 2>/dev/null
ip link set lg3tun up 2>/dev/null

# Allow IPIP from KT0
iptables -C INPUT -p 4 -s $KT0_IP -j ACCEPT 2>/dev/null || \
iptables -I INPUT 1 -p 4 -s $KT0_IP -j ACCEPT

# Google routes via tunnel
for c in $GOOGLE_CIDRS; do ip route add \$c via $TUN_KT0 dev lg3tun 2>/dev/null; done

# Persist
cat > /usr/local/bin/setup_google_tunnel.sh << \"GEOF\"
#!/bin/bash
ip tunnel add lg3tun mode ipip remote 14.51.2.130 local 1.221.16.187 2>/dev/null
ip addr add 10.99.0.6/30 dev lg3tun 2>/dev/null
ip link set lg3tun up 2>/dev/null
iptables -C INPUT -p 4 -s 14.51.2.130 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p 4 -s 14.51.2.130 -j ACCEPT
CIDRS=\"8.8.4.0/24 8.8.8.0/24 64.233.160.0/19 66.102.0.0/20 66.249.64.0/19 72.14.192.0/18 74.125.0.0/16 108.177.0.0/17 108.170.192.0/18 130.211.0.0/16 142.250.0.0/15 172.217.0.0/16 172.253.0.0/16 173.194.0.0/16 192.178.0.0/15 209.85.128.0/17 216.58.192.0/19 216.239.32.0/19 199.223.232.0/21 207.223.160.0/20 14.0.112.0/24\"
for c in \$CIDRS; do ip route add \$c via 10.99.0.5 dev lg3tun 2>/dev/null; done
echo \"LG3 Google tunnel ready\"
GEOF
chmod +x /usr/local/bin/setup_google_tunnel.sh
grep -q \"setup_google_tunnel\" /etc/rc.local 2>/dev/null || {
    sed -i \"/^exit 0/i /usr/local/bin/setup_google_tunnel.sh\" /etc/rc.local 2>/dev/null || \
    echo \"/usr/local/bin/setup_google_tunnel.sh\" >> /etc/rc.local
}
echo done
'"

# ============================================
# 결과 요약
# ============================================
echo ""
echo "============================================"
echo " 배포 결과: OK=$OK, FAIL=$FAIL"
echo "============================================"
echo ""
echo "검증: bash /home/newkorea/project/scripts/verify_gemini.sh"

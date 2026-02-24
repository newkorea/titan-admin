#!/bin/bash
# Setup Google CIDR routes through OpenWrt gateway for KT0/1/2
# This routes all Google/YouTube/Gemini traffic through OpenWrt (Passwall)
# Usage: deploy to each KT server and run, or run remotely via SSH

OPENWRT_GW="14.51.2.184"  # OpenWrt public IP on same L2

# Google IP ranges (AS15169, AS396982) - covers Google, YouTube, Gemini, etc.
GOOGLE_CIDRS=(
    # Google DNS
    8.8.4.0/24
    8.8.8.0/24
    # Google Frontend / Cloud
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
    # YouTube specific
    199.223.232.0/21
    207.223.160.0/20
    # ip138.com (IP check site)
    14.0.112.0/24
)

echo "=== Adding Google routes via OpenWrt ($OPENWRT_GW) ==="
added=0
skipped=0
for cidr in "${GOOGLE_CIDRS[@]}"; do
    if ip route add "$cidr" via "$OPENWRT_GW" dev eth0 2>/dev/null; then
        ((added++))
    else
        ((skipped++))
    fi
done
echo "Done: $added added, $skipped skipped (already exist)"
echo "Total Google routes via OpenWrt: $(ip route | grep "via $OPENWRT_GW" | wc -l)"

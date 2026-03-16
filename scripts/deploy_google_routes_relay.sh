#!/bin/bash
# Deploy Google CIDR routes on UTO relay servers
# Routes traffic to Google through gateway VM 221.143.197.140 (geo=en)
# Relay servers are on 218.233.115.x/27 but same L2 as 140 → use onlink

GATEWAY="221.143.197.140"
RELAY_SERVERS="218.233.115.182 218.233.115.184 218.233.115.185 218.233.115.186 218.233.115.187 218.233.115.188 218.233.115.189"

# Google CIDRs (same as CLAUDE.md + standard Google ranges)
GOOGLE_CIDRS=(
    "8.8.4.0/24"
    "8.8.8.0/24"
    "64.233.160.0/19"
    "66.102.0.0/20"
    "66.249.64.0/19"
    "72.14.192.0/18"
    "74.125.0.0/16"
    "108.177.0.0/17"
    "108.170.192.0/18"
    "130.211.0.0/16"
    "142.250.0.0/15"
    "172.217.0.0/16"
    "172.253.0.0/16"
    "173.194.0.0/16"
    "192.178.0.0/15"
    "209.85.128.0/17"
    "216.58.192.0/19"
    "216.239.32.0/19"
    "199.223.232.0/21"
    "207.223.160.0/20"
    "14.0.112.0/24"
)

# Build route commands
ROUTE_CMDS=""
for cidr in "${GOOGLE_CIDRS[@]}"; do
    ROUTE_CMDS+="ip route replace $cidr via $GATEWAY dev eth0 onlink 2>/dev/null; "
done

# Build rc.local content for persistence
RC_LOCAL_BLOCK="#!/bin/bash
# Google routes via gateway $GATEWAY (geo=en)
"
for cidr in "${GOOGLE_CIDRS[@]}"; do
    RC_LOCAL_BLOCK+="ip route replace $cidr via $GATEWAY dev eth0 onlink
"
done
RC_LOCAL_BLOCK+="exit 0"

echo "=== Deploying Google routes to relay servers ==="
echo "Gateway: $GATEWAY"
echo "CIDRs: ${#GOOGLE_CIDRS[@]} ranges"
echo ""

for SERVER in $RELAY_SERVERS; do
    echo "--- $SERVER ---"
    
    # Add routes immediately
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$SERVER" "$ROUTE_CMDS echo ROUTES_ADDED" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "  FAILED: SSH connection"
        continue
    fi
    
    # Write rc.local for persistence
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$SERVER" "cat > /etc/rc.local << 'RCEOF'
$RC_LOCAL_BLOCK
RCEOF
chmod +x /etc/rc.local
echo RC_LOCAL_SET" 2>/dev/null
    
    # Verify: check Google geo
    GEO=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$SERVER" "curl -sL --max-time 15 https://gemini.google.com 2>/dev/null | grep -oP '\"[a-z]{2}\"' | head -1" 2>/dev/null)
    echo "  Google geo: $GEO"
    echo ""
done

echo "=== Done ==="

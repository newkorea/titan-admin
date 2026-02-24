#!/bin/bash
# Old x-ui servers migration to standard xray 1.4.2 + port 9999
# Stops old x-ui, deploys standard xray setup

DEPLOY_SCRIPT="/home/newkorea/project/scripts/deploy_v2ray.sh"

# Server list: IP DOMAIN
declare -A SERVERS=(
    ["118.27.36.188"]="jp1.jobjapan.net"
    ["125.132.9.135"]="ktdb135.jobjapan.net"
    ["125.132.9.136"]="ktdb136.jobjapan.net"
    ["125.132.9.137"]="ktdb137.jobjapan.net"
    ["125.132.9.139"]="ktdb139.jobjapan.net"
    ["125.132.9.140"]="ktdb140.jobjapan.net"
    ["125.132.9.141"]="ktdb141.jobjapan.net"
    ["125.132.9.142"]="ktdb142.jobjapan.net"
    ["45.63.55.252"]="usla.jobjapan.net"
    ["139.84.165.217"]="india1.jobjapan.net"
)

SUCCESS=0
FAIL=0

for IP in "${!SERVERS[@]}"; do
    DOMAIN="${SERVERS[$IP]}"
    UUID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
    
    echo ""
    echo "======================================"
    echo "Migrating $IP ($DOMAIN)"
    echo "======================================"
    
    # Step 1: Stop old x-ui service
    echo "[PRE] Stopping old x-ui on $IP..."
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no root@$IP '
        # Stop x-ui if running
        systemctl stop x-ui 2>/dev/null || true
        systemctl disable x-ui 2>/dev/null || true
        
        # Kill any remaining old xray processes
        pkill -f "xray-linux" 2>/dev/null || true
        pkill -f "bin/xray" 2>/dev/null || true
        
        # Wait for port release
        sleep 2
        
        # Verify ports are free
        if netstat -tlnp 2>/dev/null | grep -q ":62789"; then
            echo "WARNING: port 62789 still in use, force killing..."
            fuser -k 62789/tcp 2>/dev/null || true
            sleep 1
        fi
        echo "Old services stopped"
    ' 2>/dev/null || echo "WARNING: Could not stop old services on $IP"
    
    # Step 2: Deploy standard xray
    echo "[DEPLOY] Running deploy_v2ray.sh..."
    if bash "$DEPLOY_SCRIPT" "$IP" "$DOMAIN" "$UUID"; then
        echo "[OK] $IP migrated successfully"
        ((SUCCESS++))
    else
        echo "[FAIL] $IP migration failed"
        ((FAIL++))
    fi
done

echo ""
echo "======================================"
echo "Migration complete: $SUCCESS success, $FAIL failed"
echo "======================================"
echo ""
echo "Don't forget to update DB: UPDATE tbl_agent3 SET v2_port=9999 WHERE ..."

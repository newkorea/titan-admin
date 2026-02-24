#!/bin/bash
# V2RAY (Xray 1.4.2) 전 서버 배포 스크립트
# VMess + WebSocket + TLS, alterId=7, port=9999
# 
# 사용법: bash deploy_v2ray.sh [서버IP] [도메인] [UUID]
# 전체배포: bash deploy_v2ray_all.sh

set -e

SERVER_IP="$1"
DOMAIN="$2"
UUID="$3"

if [ -z "$SERVER_IP" ] || [ -z "$DOMAIN" ] || [ -z "$UUID" ]; then
    echo "Usage: $0 <server_ip> <domain> <uuid>"
    exit 1
fi

XRAY_BINARY="/tmp/xray-1.4.2"
V2_PORT=9999

echo "=== Deploying V2RAY to $SERVER_IP ($DOMAIN) ==="

# 1. xray 바이너리 복사
echo "[1/5] Copying xray binary..."
scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$XRAY_BINARY" root@${SERVER_IP}:/usr/local/xray-tmp 2>/dev/null

# 2. SSH로 원격 설치
echo "[2/5] Installing xray + config..."
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no root@${SERVER_IP} bash -s "$DOMAIN" "$UUID" "$V2_PORT" << 'REMOTE_SCRIPT'
DOMAIN="$1"
UUID="$2"
V2_PORT="$3"

# 디렉토리 생성
mkdir -p /usr/local/xray /var/log/xray

# 기존 xray 백업 후 새 바이너리 설치
if [ -f /usr/local/xray/xray ]; then
    cp /usr/local/xray/xray /usr/local/xray/xray.bak
fi
mv /usr/local/xray-tmp /usr/local/xray/xray
chmod +x /usr/local/xray/xray

# config.json 생성
cat > /usr/local/xray/config.json << CFGEOF
{
  "log": {
    "loglevel": "warning",
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log"
  },
  "api": {
    "tag": "api",
    "services": ["HandlerService", "StatsService"]
  },
  "stats": {},
  "policy": {
    "levels": {
      "0": {
        "statsUserUplink": true,
        "statsUserDownlink": true
      }
    },
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true
    }
  },
  "inbounds": [
    {
      "tag": "api",
      "listen": "127.0.0.1",
      "port": 62789,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      }
    },
    {
      "tag": "vmess-ws-tls",
      "listen": "0.0.0.0",
      "port": ${V2_PORT},
      "protocol": "vmess",
      "settings": {
        "clients": [
          {
            "id": "${UUID}",
            "alterId": 7,
            "email": "shared@titanvpn.kr"
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "serverName": "${DOMAIN}",
          "certificates": [
            {
              "certificateFile": "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem",
              "keyFile": "/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
            }
          ]
        },
        "wsSettings": {
          "path": "/"
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls"]
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct"
    },
    {
      "protocol": "blackhole",
      "tag": "blocked"
    }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["api"],
        "outboundTag": "api"
      },
      {
        "type": "field",
        "outboundTag": "blocked",
        "protocol": ["bittorrent"]
      }
    ]
  }
}
CFGEOF

# systemd 서비스 생성
cat > /etc/systemd/system/xray.service << SVCEOF
[Unit]
Description=Xray Service
After=network.target

[Service]
Type=simple
Environment="XRAY_VMESS_AEAD_FORCED=false"
ExecStart=/usr/local/xray/xray run -config /usr/local/xray/config.json
Restart=on-failure
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
SVCEOF

# 서비스 활성화 및 시작
systemctl daemon-reload
systemctl enable xray 2>/dev/null
systemctl restart xray

# 포트 열기 (iptables)
if iptables -L IN_public_allow -n 2>/dev/null | grep -q "${V2_PORT}"; then
    echo "Port ${V2_PORT} already open"
else
    # CentOS 7 firewalld/iptables
    if command -v firewall-cmd &>/dev/null && systemctl is-active firewalld &>/dev/null; then
        firewall-cmd --permanent --add-port=${V2_PORT}/tcp 2>/dev/null
        firewall-cmd --reload 2>/dev/null
    else
        iptables -I INPUT -p tcp --dport ${V2_PORT} -j ACCEPT 2>/dev/null || true
        # IN_public_allow 체인이 있으면 거기에도 추가
        iptables -I IN_public_allow -p tcp --dport ${V2_PORT} -j ACCEPT 2>/dev/null || true
        service iptables save 2>/dev/null || true
    fi
    echo "Port ${V2_PORT} opened"
fi

# 확인
sleep 1
if systemctl is-active xray &>/dev/null; then
    echo "DEPLOY_SUCCESS"
else
    echo "DEPLOY_FAILED"
    journalctl -u xray --no-pager -n 5
fi
REMOTE_SCRIPT

echo "[3/5] Verifying..."
sleep 3
RESULT=$(ssh -o ConnectTimeout=10 root@${SERVER_IP} 'sleep 2 && systemctl is-active xray && echo "RUNNING" || echo "STOPPED"' 2>/dev/null)
if echo "$RESULT" | grep -q "RUNNING"; then
    echo "[OK] $SERVER_IP ($DOMAIN) - xray running on port $V2_PORT"
else
    echo "[FAIL] $SERVER_IP ($DOMAIN) - xray NOT running"
fi

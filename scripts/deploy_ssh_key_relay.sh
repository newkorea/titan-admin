#!/bin/bash
# Deploy SSH key to UTO relay servers
PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID6MfQsLYAzOjf8VfWidJ1pAzjSfmizHsIpfo9Rgefhr newkorea@pc"
SERVERS="218.233.115.183 218.233.115.184 218.233.115.186 218.233.115.187 218.233.115.188 218.233.115.189 218.233.115.190"
PASS="uto6703"

echo "=== SSH Key Deployment to UTO Relay Servers ==="
echo ""

for IP in $SERVERS; do
    echo -n "[$IP] "
    RESULT=$(timeout 15 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 -o ServerAliveInterval=5 -o BatchMode=no root@$IP \
      "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qF 'AAAAID6MfQsLYAzOjf8VfWidJ1pAzjSfmizHsIpfo9Rgefhr' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUBKEY' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo 'KEY_OK'" 2>&1)
    RC=$?
    if echo "$RESULT" | grep -q "KEY_OK"; then
        echo "SUCCESS (key deployed)"
    elif [ $RC -eq 124 ]; then
        echo "TIMEOUT (15s)"
    else
        echo "FAILED (rc=$RC): $RESULT"
    fi
done

echo ""
echo "=== Verify passwordless SSH ==="
for IP in $SERVERS; do
    echo -n "[$IP] "
    RESULT=$(timeout 10 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes root@$IP "echo SSH_OK" 2>&1)
    if echo "$RESULT" | grep -q "SSH_OK"; then
        echo "PASSWORDLESS OK"
    else
        echo "FAILED: $RESULT"
    fi
done

echo ""
echo "=== Check Google geo ==="
for IP in $SERVERS; do
    echo -n "[$IP] "
    GEO=$(timeout 15 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes root@$IP \
      "curl -sL --max-time 8 https://gemini.google.com 2>/dev/null | grep -oP '\"[a-z]{2}\"' | head -1" 2>&1)
    if [ -z "$GEO" ]; then
        echo "NO GEO (curl failed or SSH failed)"
    else
        echo "GEO=$GEO"
    fi
done

echo ""
echo "ALL_DONE"

#!/bin/bash
# Deploy SSH key to UTO relay servers (password: ss135690)
PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID6MfQsLYAzOjf8VfWidJ1pAzjSfmizHsIpfo9Rgefhr newkorea@pc"
SERVERS="218.233.115.183 218.233.115.184 218.233.115.185 218.233.115.186 218.233.115.187 218.233.115.188 218.233.115.189 218.233.115.190"
PASS="ss135690"

echo "=== SSH Key Deployment ==="
for IP in $SERVERS; do
    echo -n "[$IP] "
    RESULT=$(timeout 15 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 -o PreferredAuthentications=password root@$IP \
      "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qF 'AAAAID6MfQsLYAzOjf8VfWidJ1pAzjSfmizHsIpfo9Rgefhr' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUBKEY' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo 'KEY_OK'" 2>&1)
    RC=$?
    if echo "$RESULT" | grep -q "KEY_OK"; then
        echo "SUCCESS"
    elif [ $RC -eq 124 ]; then
        echo "TIMEOUT"
    else
        echo "FAILED (rc=$RC): $RESULT"
    fi
done

echo ""
echo "=== Verify Passwordless SSH ==="
for IP in $SERVERS; do
    echo -n "[$IP] "
    RESULT=$(timeout 10 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes root@$IP "hostname" 2>&1)
    RC=$?
    if [ $RC -eq 0 ]; then
        echo "OK ($RESULT)"
    else
        echo "FAILED: $RESULT"
    fi
done

echo ""
echo "=== Google Geo Check ==="
for IP in $SERVERS; do
    echo -n "[$IP] "
    GEO=$(timeout 20 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes root@$IP \
      "curl -sL --max-time 10 https://gemini.google.com 2>/dev/null | grep -oP '\"[a-z]{2}\"' | head -1" 2>&1)
    RC=$?
    if [ $RC -ne 0 ]; then
        echo "SSH FAILED: $GEO"
    elif [ -z "$GEO" ]; then
        echo "NO GEO (curl failed)"
    else
        echo "GEO=$GEO"
    fi
done

echo ""
echo "ALL_DONE"

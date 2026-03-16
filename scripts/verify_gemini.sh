#!/bin/bash
# verify_gemini.sh — 이전 차단 서버들의 Gemini 접속 검증
echo "=== Gemini 차단 해제 검증 $(date '+%Y-%m-%d %H:%M:%S') ==="
echo ""

check() {
    local ip=$1 name=$2
    local result=$(ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$ip" \
        'curl -sL --max-time 10 https://gemini.google.com 2>/dev/null | grep -oP "\"[a-z]{2}\"" | head -1' 2>/dev/null)
    if [ -z "$result" ]; then
        printf "%-6s %-20s %s\n" "FAIL" "$name" "$ip"
    elif [ "$result" = '"cn"' ] || [ "$result" = '"hk"' ] || [ "$result" = '"ru"' ]; then
        printf "%-6s %-20s %s  geo=%s\n" "BLOCK" "$name" "$ip" "$result"
    else
        printf "%-6s %-20s %s  geo=%s\n" "OK" "$name" "$ip" "$result"
    fi
}

# 이전 차단 서버 8대
check 218.49.179.74 "SK4  (→SK6)" &
check 218.49.179.75 "SK5  (→SK6)" &
check 218.49.179.77 "SK7  (→SK6)" &
check 218.49.179.78 "SK8  (→SK6)" &
check 218.49.179.79 "SK9  (→SK6)" &
check 221.143.197.134 "SK14 (→SK10)" &
check 221.143.197.136 "SK16 (→SK10)" &
check 1.221.16.187 "LG3  (→KT0)" &
wait
echo ""
echo "=== 검증 완료 ==="

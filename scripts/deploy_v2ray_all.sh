#!/bin/bash
# V2RAY 전체 서버 배포 (29개 서버)
# 각 서버마다 고유 UUID 생성

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/deploy_v2ray.sh"
LOG_FILE="/tmp/v2ray_deploy_$(date +%Y%m%d_%H%M%S).log"

# xray 바이너리 확인
if [ ! -f /tmp/xray-1.4.2 ]; then
    echo "ERROR: /tmp/xray-1.4.2 not found"
    exit 1
fi

echo "=== V2RAY 전체 배포 시작 ===" | tee "$LOG_FILE"
echo "시작 시간: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# UUID 생성 함수
gen_uuid() {
    python3 -c "import uuid; print(uuid.uuid4())"
}

# 배포 대상 서버 (id|ip|domain)
servers=(
"47|121.159.134.27|kt10gdhcp1.jobjapan.net"
"49|220.82.114.127|kt10gdhcp3.jobjapan.net"
"50|112.218.79.75|lgdhcp1.jobjapan.net"
"53|220.123.216.40|kt10gdhcp4.jobjapan.net"
"54|220.123.216.21|kt10gdhcp0.jobjapan.net"
"55|218.158.160.41|kt10gdhcp5.jobjapan.net"
"61|218.158.57.23|ktd23.jobjapan.net"
"63|218.158.57.25|ktc1.jobjapan.net"
"1042|125.132.9.138|ktdb138.jobjapan.net"
"1047|218.49.179.74|sk74.jobjapan.net"
"1048|14.51.2.130|kt14130.jobjapan.net"
"1049|14.51.2.132|kt14132.jobjapan.net"
"1054|14.51.2.131|kt14131.jobjapan.net"
"1055|218.49.179.75|sk75.jobjapan.net"
"1056|218.49.179.76|sk76.jobjapan.net"
"1057|218.49.179.77|sk77.jobjapan.net"
"1058|218.49.179.78|sk78.jobjapan.net"
"1059|218.49.179.79|sk79.jobjapan.net"
"1061|14.51.2.179|kt14179.jobjapan.net"
"1064|221.143.197.130|sk221130.jobjapan.com"
"1065|221.143.197.131|sk221131.jobjapan.com"
"1066|221.143.197.132|sk221132.jobjapan.com"
"1067|221.143.197.133|sk221133.jobjapan.com"
"1068|221.143.197.134|sk221134.jobjapan.com"
"1069|221.143.197.135|sk221135.jobjapan.com"
"1070|221.143.197.136|sk221136.jobjapan.com"
"1071|1.221.16.187|lgdhcp3.jobjapan.net"
"1072|218.236.231.231|sk218231.jobjapan.com"
"1073|218.236.231.232|sk218232.jobjapan.com"
)

SUCCESS=0
FAIL=0
DB_UPDATES=""

for entry in "${servers[@]}"; do
    IFS='|' read -r id ip domain <<< "$entry"
    UUID=$(gen_uuid)
    
    echo "--- [$((SUCCESS+FAIL+1))/${#servers[@]}] id=$id $ip $domain ---" | tee -a "$LOG_FILE"
    
    if bash "$DEPLOY_SCRIPT" "$ip" "$domain" "$UUID" 2>&1 | tee -a "$LOG_FILE" | grep -q "\[OK\]"; then
        SUCCESS=$((SUCCESS+1))
        DB_UPDATES="${DB_UPDATES}UPDATE tbl_agent3 SET protocol=CONCAT(protocol,',V2RAY'), v2_port=9999, v2_config='${UUID}' WHERE id=${id};\n"
        echo "  => SUCCESS (UUID: $UUID)" | tee -a "$LOG_FILE"
    else
        FAIL=$((FAIL+1))
        echo "  => FAILED" | tee -a "$LOG_FILE"
    fi
    echo "" | tee -a "$LOG_FILE"
done

echo "========================================" | tee -a "$LOG_FILE"
echo "배포 완료: 성공=${SUCCESS} 실패=${FAIL} / 전체=${#servers[@]}" | tee -a "$LOG_FILE"
echo "종료 시간: $(date)" | tee -a "$LOG_FILE"

# DB 업데이트 SQL 생성
SQL_FILE="/tmp/v2ray_db_update.sql"
echo -e "$DB_UPDATES" > "$SQL_FILE"
echo "" | tee -a "$LOG_FILE"
echo "DB 업데이트 SQL: $SQL_FILE" | tee -a "$LOG_FILE"
echo "로그: $LOG_FILE" | tee -a "$LOG_FILE"

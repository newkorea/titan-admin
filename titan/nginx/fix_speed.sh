#!/bin/bash
# aws14.titanvpn.kr 속도 개선을 위한 nginx 설정 수정 스크립트
# 실행: sudo bash /home/newkorea/project/titan/nginx/fix_speed.sh

set -e

echo "=== nginx 속도 개선 패치 ==="

# 1. nginx.conf: gzip_types 주석 해제
echo "[1/3] nginx.conf gzip 설정 활성화..."
sed -i 's/# gzip_vary on;/gzip_vary on;/' /etc/nginx/nginx.conf
sed -i 's/# gzip_proxied any;/gzip_proxied any;/' /etc/nginx/nginx.conf
sed -i 's/# gzip_comp_level 6;/gzip_comp_level 6;/' /etc/nginx/nginx.conf
sed -i 's/# gzip_buffers 16 8k;/gzip_buffers 16 8k;/' /etc/nginx/nginx.conf
sed -i 's/# gzip_http_version 1.1;/gzip_http_version 1.1;/' /etc/nginx/nginx.conf
sed -i 's/# gzip_types text\/plain/gzip_types text\/plain/' /etc/nginx/nginx.conf

# 2. titan site: static 파일 캐싱 활성화 (expires -1 → expires 7d)
echo "[2/3] static 파일 브라우저 캐싱 활성화 (7일)..."
sed -i '/location \/static\//,/}/ s/expires -1;/expires 7d;\n        add_header Cache-Control "public";/' /etc/nginx/sites-enabled/titan

# 3. nginx 설정 테스트 및 리로드
echo "[3/3] nginx 설정 테스트..."
nginx -t
if [ $? -eq 0 ]; then
    echo "설정 테스트 통과. nginx 리로드..."
    systemctl reload nginx
    echo "=== 완료! ==="
else
    echo "!!! 설정 오류 발생. 리로드 취소됨."
    exit 1
fi

echo ""
echo "확인 방법:"
echo "  curl -sI -H 'Accept-Encoding: gzip' https://aws14.titanvpn.kr/static/css/style.css | grep -i 'encoding\|cache\|expires'"

#!/bin/bash
# 1) 만료 세션 정리 (Django clearsessions)
cd /home/newkorea/project/titan
.venv310/bin/python manage.py clearsessions

# 2) 중복 세션 + 이메일 없는 세션 정리
cd /home/newkorea/project/titan-admin
.venv38/bin/python scripts/cleanup_sessions.py >> /home/newkorea/project/titan-admin/logs/session_cleanup.log 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') session cleanup done" >> /home/newkorea/project/titan-admin/logs/session_cleanup.log

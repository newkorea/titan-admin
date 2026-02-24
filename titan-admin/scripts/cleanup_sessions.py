#!/usr/bin/env python
"""django_session 중복 정리
1) 이메일 없는 세션 삭제 (빈/익명 세션)
2) 이메일별 device_info uuid 수 기반으로 필요한 세션만 유지
   - 각 유저의 uuid 수 + 1(웹) 만큼의 최신 세션만 남기고 나머지 삭제
   - 최소 보장: 유저당 최소 2개 세션은 유지
"""
import os, sys, django, base64, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
sys.path.insert(0, '/home/newkorea/project/titan-admin')
django.setup()

from django.db import connection

cur = connection.cursor()

# ── Step 1: 이메일 없는 세션 삭제 ──
print("=== Step 1: 이메일 없는 세션 삭제 ===")
cur.execute("SELECT session_key, session_data FROM django_session WHERE expire_date > NOW()")
all_sessions = cur.fetchall()

email_map = {}   # session_key -> email
no_email_keys = []

for sk, sd in all_sessions:
    try:
        decoded = base64.b64decode(sd)
        sep = decoded.find(b':')
        if sep == -1:
            no_email_keys.append(sk)
            continue
        data = json.loads(decoded[sep+1:].decode('utf-8'))
        email = data.get('email', '')
        if email:
            email_map[sk] = email
        else:
            no_email_keys.append(sk)
    except:
        no_email_keys.append(sk)

print(f"  이메일 없는 세션: {len(no_email_keys)}건 → 삭제")

# 배치 삭제
BATCH = 500
deleted1 = 0
for i in range(0, len(no_email_keys), BATCH):
    batch = no_email_keys[i:i+BATCH]
    ph = ','.join(['%s'] * len(batch))
    cur.execute(f"DELETE FROM django_session WHERE session_key IN ({ph})", batch)
    deleted1 += cur.rowcount

print(f"  삭제 완료: {deleted1}건")

# ── Step 2: 유저별 uuid 수 기반 세션 정리 ──
print("\n=== Step 2: 유저별 중복 세션 정리 ===")

# 유저별 uuid 수 조회
cur.execute("""
    SELECT u.email, COUNT(DISTINCT di.device_uuid) as uuid_cnt
    FROM tbl_device_info di
    JOIN tbl_user u ON di.user_id = u.id
    WHERE di.device_uuid != '' AND di.device_uuid IS NOT NULL
    GROUP BY u.email
""")
user_uuid_count = {row[0]: row[1] for row in cur.fetchall()}

# 이메일별 세션 그룹핑 (만료시간 기준 정렬 — 최신을 유지)
from collections import defaultdict
email_groups = defaultdict(list)
for sk, email in email_map.items():
    email_groups[email].append(sk)

# 각 유저별로 보관할 세션 수 = uuid수 + 1(웹) , 최소 2
delete_keys = []
for email, skeys in email_groups.items():
    uuid_cnt = user_uuid_count.get(email, 1)
    keep_count = max(uuid_cnt + 1, 2)  # uuid수+1, 최소 2

    if len(skeys) <= keep_count:
        continue  # 정리 불필요

    # expire_date 기준으로 최신 것만 유지
    ph = ','.join(['%s'] * len(skeys))
    cur.execute(f"""
        SELECT session_key FROM django_session
        WHERE session_key IN ({ph})
        ORDER BY expire_date DESC
    """, skeys)
    ordered = [row[0] for row in cur.fetchall()]

    # keep_count개 외 나머지 삭제
    to_delete = ordered[keep_count:]
    delete_keys.extend(to_delete)

print(f"  정리 대상 세션: {len(delete_keys)}건")

deleted2 = 0
for i in range(0, len(delete_keys), BATCH):
    batch = delete_keys[i:i+BATCH]
    ph = ','.join(['%s'] * len(batch))
    cur.execute(f"DELETE FROM django_session WHERE session_key IN ({ph})", batch)
    deleted2 += cur.rowcount

print(f"  삭제 완료: {deleted2}건")

# ── 결과 확인 ──
print(f"\n=== 총 삭제: {deleted1 + deleted2}건 ===")
cur.execute("SELECT COUNT(*) FROM django_session WHERE expire_date > NOW()")
print(f"남은 유효 세션: {cur.fetchone()[0]}건")

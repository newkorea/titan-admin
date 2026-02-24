#!/usr/bin/env python
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
sys.path.insert(0, '/home/newkorea/project/titan-admin')
django.setup()

from django.db import connection

cur = connection.cursor()

# 1) 중복 현황 확인
cur.execute("""
    SELECT device_uuid, user_id, COUNT(*) as cnt
    FROM tbl_device_info
    WHERE device_uuid != '' AND device_uuid IS NOT NULL
    GROUP BY device_uuid, user_id
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 30
""")
rows = cur.fetchall()
print(f"=== 중복 uuid 그룹 수: {len(rows)} ===")
total_dup = 0
for r in rows:
    print(f"  uuid={r[0]}  uid={r[1]}  cnt={r[2]}")
    total_dup += (r[2] - 1)  # 최신 1개 제외한 나머지가 삭제 대상

print(f"\n삭제 대상 레코드 수 (예상): {total_dup}")

# 2) 전체 유저 대상: uuid별 최신 1개만 남기고 삭제
cur.execute("""
    DELETE di FROM tbl_device_info di
    INNER JOIN (
        SELECT device_uuid, user_id, MAX(id) as max_id
        FROM tbl_device_info
        WHERE device_uuid != '' AND device_uuid IS NOT NULL
        GROUP BY device_uuid, user_id
    ) keep ON di.device_uuid = keep.device_uuid AND di.user_id = keep.user_id
    WHERE di.id != keep.max_id
      AND di.device_uuid != ''
      AND di.device_uuid IS NOT NULL
""")
deleted = cur.rowcount
print(f"\n=== 실제 삭제: {deleted}건 ===")

# 3) 삭제 후 확인
cur.execute("""
    SELECT device_uuid, user_id, COUNT(*) as cnt
    FROM tbl_device_info
    WHERE device_uuid != '' AND device_uuid IS NOT NULL
    GROUP BY device_uuid, user_id
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
remaining = cur.fetchall()
print(f"삭제 후 남은 중복: {len(remaining)}개 그룹")

# 4) 전체 레코드 수
cur.execute("SELECT COUNT(*) FROM tbl_device_info")
total = cur.fetchone()[0]
print(f"전체 tbl_device_info 레코드 수: {total}")

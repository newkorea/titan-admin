#!/usr/bin/env python
"""tbl_device_info 중복 uuid 정리 — uuid+user_id별 최신 1개만 남기고 삭제 (배치)"""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
sys.path.insert(0, '/home/newkorea/project/titan-admin')
django.setup()

from django.db import connection

cur = connection.cursor()

# 삭제 대상 id 목록 구하기 (최신 id 제외한 나머지)
print("삭제 대상 id 수집 중...")
cur.execute("""
    SELECT di.id
    FROM tbl_device_info di
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
ids = [row[0] for row in cur.fetchall()]
print(f"삭제 대상: {len(ids)}건")

# 배치 삭제 (5000건씩)
BATCH = 5000
total_deleted = 0
for i in range(0, len(ids), BATCH):
    batch = ids[i:i+BATCH]
    ph = ','.join(['%s'] * len(batch))
    cur.execute(f"DELETE FROM tbl_device_info WHERE id IN ({ph})", batch)
    total_deleted += cur.rowcount
    print(f"  배치 {i//BATCH+1}: {cur.rowcount}건 삭제 (누적 {total_deleted})")

print(f"\n=== 총 삭제: {total_deleted}건 ===")

# 확인
cur.execute("SELECT COUNT(*) FROM tbl_device_info")
print(f"남은 레코드 수: {cur.fetchone()[0]}")
cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT device_uuid, user_id
        FROM tbl_device_info
        WHERE device_uuid != '' AND device_uuid IS NOT NULL
        GROUP BY device_uuid, user_id
        HAVING COUNT(*) > 1
    ) dup
""")
print(f"남은 중복 그룹: {cur.fetchone()[0]}")

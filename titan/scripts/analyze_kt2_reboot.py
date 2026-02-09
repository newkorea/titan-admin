#!/usr/bin/env python3
"""KOREA-KT2 재부팅 전후 실패 분석"""
import MySQLdb

conn = MySQLdb.connect(host='218.158.57.48', user='titan', passwd='xkdlxks12!@', db='titan', charset='utf8mb4')
cur = conn.cursor()

# KT2 오늘 전체 시간대별 실패 (10분 단위)
cur.execute("""
    SELECT DATE_FORMAT(failed_time, '%H:%i0') AS slot, COUNT(*) c,
           GROUP_CONCAT(DISTINCT platform) plat
    FROM tbl_agent_failed
    WHERE failed_time >= '2026-02-09 00:00:00'
      AND server_name = 'KOREA-KT2'
    GROUP BY slot ORDER BY slot
""")
rows = cur.fetchall()
print("[KOREA-KT2 오늘 시간대별 실패 (10분 단위)]")
hdr = f"  {'시간':<10} {'건수':<8} 플랫폼"
print(hdr)
for r in rows:
    print(f"  {r[0]:<10} {r[1]:<8} {r[2]}")
print()

# 서버 who -b = Feb 10 01:07 → 서버 로컬 시간이 UTC+9+? 확인
# uptime 19:13에 1:51 up → 부팅시각 = 19:13 - 1:51 = 약 17:22 KST
# 재부팅 전후 구분
REBOOT_TIME = '2026-02-09 17:22:00'

cur.execute("""
    SELECT COUNT(*) FROM tbl_agent_failed
    WHERE failed_time >= '2026-02-09 00:00:00' AND failed_time < %s
      AND server_name = 'KOREA-KT2'
""", (REBOOT_TIME,))
before = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM tbl_agent_failed
    WHERE failed_time >= %s AND server_name = 'KOREA-KT2'
""", (REBOOT_TIME,))
after = cur.fetchone()[0]

print(f"[재부팅 전후 실패 건수 (추정 부팅시각 {REBOOT_TIME} 기준)]")
print(f"  재부팅 전 (00:00~17:22): {before}건")
print(f"  재부팅 후 (17:22~현재):  {after}건")
print()

# 재부팅 후 실패 상세
cur.execute("""
    SELECT failed_time, username, platform, server_protocol, user_location
    FROM tbl_agent_failed
    WHERE failed_time >= %s AND server_name = 'KOREA-KT2'
    ORDER BY failed_time
""", (REBOOT_TIME,))
rows2 = cur.fetchall()
if rows2:
    print("[재부팅 후 실패 상세]")
    for r in rows2:
        print(f"  {r[0]}  {r[1]:<35} {r[2]:<10} {r[3]:<10} {r[4]}")
else:
    print("  재부팅 후 실패 없음")

conn.close()

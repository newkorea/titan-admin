#!/usr/bin/env python3
"""최근 5시간 서버접속실패 로그 분석 (iOS + Android만)"""
import MySQLdb

conn = MySQLdb.connect(host='218.158.57.48', user='titan', passwd='xkdlxks12!@', db='titan', charset='utf8mb4')
cur = conn.cursor()

WHERE = "WHERE failed_time >= NOW() - INTERVAL 5 HOUR AND platform IN ('iOS','Android')"

# 1) 총 실패 건수
cur.execute(f"SELECT COUNT(*), MIN(failed_time), MAX(failed_time) FROM tbl_agent_failed {WHERE}")
r = cur.fetchone()
print(f"=== 최근 5시간 실패 총계 (iOS+Android): {r[0]}건 ({r[1]} ~ {r[2]}) ===\n")

# 2) 서버별 실패 건수
cur.execute(f"SELECT server_name, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY server_name ORDER BY c DESC LIMIT 20")
print("[서버별 실패 건수 TOP20]")
for r in cur.fetchall(): print(f"  {r[0]:<25} {r[1]}건")
print()

# 3) 프로토콜별
cur.execute(f"SELECT server_protocol, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY server_protocol ORDER BY c DESC")
print("[프로토콜별]")
for r in cur.fetchall(): print(f"  {r[0]:<15} {r[1]}건")
print()

# 4) 사용자 위치별
cur.execute(f"SELECT user_location, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY user_location ORDER BY c DESC LIMIT 15")
print("[사용자 위치별 TOP15]")
for r in cur.fetchall(): print(f"  {r[0]:<30} {r[1]}건")
print()

# 5) 시간대별 추이
cur.execute(f"SELECT DATE_FORMAT(failed_time, '%H:00') h, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY h ORDER BY h")
print("[시간대별 추이]")
for r in cur.fetchall(): print(f"  {r[0]}  {r[1]}건")
print()

# 6) 플랫폼별
cur.execute(f"SELECT platform, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY platform ORDER BY c DESC")
print("[플랫폼별]")
for r in cur.fetchall(): print(f"  {r[0]:<15} {r[1]}건")
print()

# 7) 동일 사용자 반복 실패 TOP10
cur.execute(f"SELECT username, COUNT(*) c, GROUP_CONCAT(DISTINCT server_name) svrs FROM tbl_agent_failed {WHERE} GROUP BY username HAVING c >= 2 ORDER BY c DESC LIMIT 10")
print("[반복 실패 사용자 TOP10 (2회 이상)]")
for r in cur.fetchall(): print(f"  {r[0]:<40} {r[1]}건  서버: {r[2]}")
print()

# 8) 서버+프로토콜 조합
cur.execute(f"SELECT server_name, server_protocol, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY server_name, server_protocol ORDER BY c DESC LIMIT 15")
print("[서버+프로토콜 조합 TOP15]")
for r in cur.fetchall(): print(f"  {r[0]:<25} {r[1]:<12} {r[2]}건")
print()

# 9) 서버별 실패 사용자 수 (유니크)
cur.execute(f"SELECT server_name, COUNT(DISTINCT username) u, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY server_name ORDER BY c DESC LIMIT 15")
print("[서버별 고유사용자수 vs 실패건수]")
for r in cur.fetchall(): print(f"  {r[0]:<25} 유저 {r[1]}명 / 실패 {r[2]}건")
print()

# 10) 서버 도메인별
cur.execute(f"SELECT server_domain, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY server_domain ORDER BY c DESC LIMIT 15")
print("[서버 도메인별 TOP15]")
for r in cur.fetchall(): print(f"  {r[0]:<35} {r[1]}건")
print()

# 11) 앱 버전별
cur.execute(f"SELECT app_version, platform, COUNT(*) c FROM tbl_agent_failed {WHERE} GROUP BY app_version, platform ORDER BY c DESC LIMIT 10")
print("[앱버전+플랫폼별 TOP10]")
for r in cur.fetchall(): print(f"  v{r[0]:<10} {r[1]:<10} {r[2]}건")

cur.close()
conn.close()

#!/usr/bin/env python3
"""
deploy_dbsync_v2.py — dbsync v2.0을 모든 UTO strongSwan 서버에 배포

동작:
  1) dbsync_v2.py를 SCP로 /etc/strongswan/dbsync.py 덮어쓰기 (백업 유지)
  2) crontab에 flock 적용 (dbsync + checkuser)
  3) 배포 후 수동 1회 실행하여 radacct 즉시 동기화
  4) 결과 요약 출력

사용법:
  python3 deploy_dbsync_v2.py              # 전체 배포
  python3 deploy_dbsync_v2.py --dry-run    # 미리보기만
  python3 deploy_dbsync_v2.py --server IP  # 특정 서버만
"""

import subprocess
import sys
import os
import time
from datetime import datetime

# === 설정 ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_FILE = os.path.join(SCRIPT_DIR, "dbsync_v2.py")

# SSH 접속 가능한 UTO strongSwan 서버 목록 (30개 중 SSH 가능 26개)
SERVERS = [
    "125.132.9.175", "218.233.115.163", "14.51.2.181",
    "218.49.179.88", "218.49.179.85", "218.49.179.84",
    "218.49.179.87", "218.49.179.89", "211.46.6.242",
    "218.158.57.67", "218.49.179.86", "112.218.79.74",
    "218.49.179.81", "125.132.9.174", "218.49.179.83",
    "218.49.179.80", "218.158.57.91", "211.46.6.241",
    "218.233.115.162", "125.132.9.170", "218.49.179.90",
    "14.51.2.182", "211.46.6.243", "125.132.9.171",
    "218.233.115.164", "125.132.9.173",
]

# SSH 불가 서버 (배포 대상에서 제외)
SSH_FAIL_SERVERS = [
    "218.236.231.229", "218.236.231.230", "118.34.105.238",
    "10.99.0.14",  # 내부 IP
]

SSH_OPTS = [
    "-o", "ConnectTimeout=5",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=no",
]

def ssh_cmd(ip, cmd, timeout=15):
    """SSH 명령 실행. (stdout, stderr, returncode) 반환."""
    try:
        r = subprocess.run(
            ["ssh"] + SSH_OPTS + [f"root@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "SSH_TIMEOUT", -1
    except Exception as e:
        return "", str(e), -2

def scp_file(ip, local_path, remote_path, timeout=15):
    """SCP로 파일 전송."""
    try:
        r = subprocess.run(
            ["scp"] + SSH_OPTS + [local_path, f"root@{ip}:{remote_path}"],
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode == 0, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "SCP_TIMEOUT"
    except Exception as e:
        return False, str(e)


def deploy_to_server(ip, dry_run=False):
    """단일 서버에 배포. 성공/실패 메시지 반환."""
    results = []

    # 1) SSH 접속 확인
    out, err, rc = ssh_cmd(ip, "hostname")
    if rc != 0:
        return f"  FAIL: SSH 접속 불가 ({err})"
    hostname = out.strip()
    results.append(f"  host={hostname}")

    # 2) 기존 dbsync.py 백업
    if not dry_run:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ssh_cmd(ip, f"cp /etc/strongswan/dbsync.py /etc/strongswan/dbsync.py.bak_{ts} 2>/dev/null")

    # 3) SCP 배포
    if dry_run:
        results.append("  [DRY-RUN] SCP dbsync_v2.py → /etc/strongswan/dbsync.py")
    else:
        ok, err = scp_file(ip, SOURCE_FILE, "/etc/strongswan/dbsync.py")
        if not ok:
            return f"  FAIL: SCP 실패 ({err})"
        results.append("  SCP OK")

    # 4) crontab에 flock 적용
    out, _, _ = ssh_cmd(ip, "crontab -l 2>/dev/null")
    cron_lines = out.split('\n') if out else []
    need_update = False
    new_cron = []

    for line in cron_lines:
        stripped = line.strip()
        # dbsync cron 라인 감지 + flock 추가
        if 'dbsync.py' in stripped and 'flock' not in stripped:
            # 기존: * * * * * /usr/bin/python /etc/strongswan/dbsync.py
            # 새:   * * * * * flock -n /tmp/dbsync.lock /usr/bin/python /etc/strongswan/dbsync.py
            new_line = stripped.replace(
                '/usr/bin/python /etc/strongswan/dbsync.py',
                'flock -n /tmp/dbsync.lock /usr/bin/python /etc/strongswan/dbsync.py'
            )
            new_cron.append(new_line)
            need_update = True
        elif 'checkuser.py' in stripped and 'flock' not in stripped:
            new_line = stripped.replace(
                '/usr/bin/python /etc/strongswan/checkuser.py',
                'flock -n /tmp/checkuser.lock /usr/bin/python /etc/strongswan/checkuser.py'
            )
            new_cron.append(new_line)
            need_update = True
        else:
            new_cron.append(line)

    if need_update:
        if dry_run:
            results.append("  [DRY-RUN] crontab flock 추가 필요")
        else:
            cron_content = '\n'.join(new_cron) + '\n'
            # 안전하게: 임시 파일 → crontab 로드
            ssh_cmd(ip, f"echo '{cron_content}' > /tmp/crontab_new.txt && crontab /tmp/crontab_new.txt")
            results.append("  crontab flock 추가 완료")
    else:
        results.append("  crontab flock 이미 적용")

    # 5) dbsync.py 수동 1회 실행 (radacct 즉시 동기화)
    if dry_run:
        results.append("  [DRY-RUN] dbsync.py 수동 실행 건너뜀")
    else:
        out, err, rc = ssh_cmd(ip, "flock -n /tmp/dbsync.lock /usr/bin/python /etc/strongswan/dbsync.py 2>&1 | tail -5", timeout=60)
        if rc == 0:
            results.append(f"  실행 OK: {out[-100:] if out else 'no output'}")
        else:
            results.append(f"  실행 WARNING rc={rc}: {err[-80:] if err else out[-80:]}")

    return '\n'.join(results)


def main():
    dry_run = '--dry-run' in sys.argv
    target_ip = None

    for i, arg in enumerate(sys.argv):
        if arg == '--server' and i + 1 < len(sys.argv):
            target_ip = sys.argv[i + 1]

    if not os.path.exists(SOURCE_FILE):
        print(f"ERROR: {SOURCE_FILE} not found")
        sys.exit(1)

    servers = [target_ip] if target_ip else SERVERS

    if dry_run:
        print("=" * 60)
        print("  DRY-RUN MODE — 실제 변경 없음")
        print("=" * 60)

    print(f"\ndbsync v2.0 배포 시작 — {len(servers)}개 서버")
    print(f"소스: {SOURCE_FILE}")
    print(f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = 0
    fail = 0
    skip = 0

    for ip in servers:
        print(f"[{ip}]")
        try:
            result = deploy_to_server(ip, dry_run)
            print(result)
            if "FAIL" in result:
                fail += 1
            else:
                success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            fail += 1
        print()

    print("=" * 60)
    print(f"  완료: 성공={success}, 실패={fail}")
    if SSH_FAIL_SERVERS:
        print(f"  SSH 불가 서버 (수동 확인 필요): {', '.join(SSH_FAIL_SERVERS)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

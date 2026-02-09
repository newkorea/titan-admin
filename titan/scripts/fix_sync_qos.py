#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_sync_qos.py — sync_qos_all.py 프로세스 중복 실행 방지 배포 스크립트

1단계: cron을 flock + timeout으로 감싸기
2단계: run_cmd()에 timeout=30 추가 (sed/awk 사용 — 서버에 python3 없음)
3단계: 현재 쌓여있는 zombie 프로세스 정리

Usage:
  python3 fix_sync_qos.py              # 전체 서버 배포
  python3 fix_sync_qos.py --check      # 현재 상태 확인만
  python3 fix_sync_qos.py --server KT33  # 단일 서버
"""

import subprocess
import sys
import os

SSH_KEY = "/home/newkorea/.ssh/id_ed25519"


def get_servers():
    """DB에서 활성 NAS 서버 목록 가져오기"""
    try:
        import pymysql
        conn = pymysql.connect(
            host='218.158.57.48',
            user='titan',
            passwd='xkdlxks12!@',
            db='titan',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name AS server_name, hostip AS ip_address
                FROM tbl_agent3
                WHERE is_active = 1
                ORDER BY name
            """)
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB 오류: {e}")
        return []


def ssh_exec(ip, cmd, timeout=20):
    """SSH 명령 실행"""
    full_cmd = [
        "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes", "-i", SSH_KEY, f"root@{ip}", cmd
    ]
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return str(e), -1


def check_server(name, ip):
    """서버 상태 확인"""
    info = {'name': name, 'ip': ip}

    out, rc = ssh_exec(ip, 'test -f /root/sync_qos_all.py && echo EXISTS || echo MISSING')
    info['script_exists'] = 'EXISTS' in out

    if not info['script_exists']:
        info['cron_line'] = ''
        info['has_flock'] = False
        info['has_timeout_in_code'] = False
        info['proc_count'] = 0
        return info

    out, rc = ssh_exec(ip, 'crontab -l 2>/dev/null | grep sync_qos | grep -v "^#"')
    info['cron_line'] = out
    info['has_flock'] = 'flock' in out

    out, rc = ssh_exec(ip, 'grep -c "communicate(timeout" /root/sync_qos_all.py')
    try:
        info['has_timeout_in_code'] = int(out.strip()) > 0
    except:
        info['has_timeout_in_code'] = False

    out, rc = ssh_exec(ip, 'ps aux | grep -E "sync_qos_all|vpncmd.*SessionList" | grep -v grep | wc -l')
    try:
        info['proc_count'] = int(out.strip())
    except:
        info['proc_count'] = -1

    return info


def fix_server(name, ip):
    """서버 수정 적용"""
    results = []

    # 0. 존재 확인
    out, rc = ssh_exec(ip, 'test -f /root/sync_qos_all.py && echo EXISTS || echo MISSING')
    if 'EXISTS' not in out:
        return [(name, 'SKIP', 'sync_qos_all.py 없음')]

    # 1. zombie 정리
    out, rc = ssh_exec(ip, 'ps -eo pid,etimes,cmd | grep "sync_qos_all.py" | grep -v grep | wc -l')
    try:
        proc_cnt = int(out.strip())
    except:
        proc_cnt = 0

    if proc_cnt > 3:
        ssh_exec(ip, "ps -eo pid,etimes,cmd | grep 'sync_qos_all.py' | grep -v grep | sort -k2 -rn | tail -n +2 | awk '{print $1}' | xargs -r kill -9")
        ssh_exec(ip, "ps -eo pid,etimes,cmd | grep 'vpncmd.*SessionList' | grep -v grep | sort -k2 -rn | tail -n +2 | awk '{print $1}' | xargs -r kill -9")
        results.append((name, 'KILL', f'{proc_cnt}개 zombie 정리'))

    # 2. run_cmd timeout 패치 (sed/awk)
    out, _ = ssh_exec(ip, 'grep -c "communicate(timeout" /root/sync_qos_all.py')
    already_patched = False
    try:
        already_patched = int(out.strip()) > 0
    except:
        pass

    if not already_patched:
        # 백업
        ssh_exec(ip, 'cp /root/sync_qos_all.py /root/sync_qos_all.py.bak.$(date +%Y%m%d)')

        # 2a: communicate() -> communicate(timeout=30)
        sed_cmd = r"""sed -i 's/out, err = p\.communicate()/out, err = p.communicate(timeout=30)/' /root/sync_qos_all.py"""
        ssh_exec(ip, sed_cmd)

        # 2b: TimeoutExpired 예외처리 추가
        out_te, _ = ssh_exec(ip, 'grep -c "TimeoutExpired" /root/sync_qos_all.py')
        has_te = False
        try:
            has_te = int(out_te.strip()) > 0
        except:
            pass

        if not has_te:
            # awk로 "except Exception as e:" 바로 앞에 TimeoutExpired 블록 삽입
            # run_cmd 함수 내의 첫 번째 "except Exception" 만 처리
            awk_cmd = (
                "awk '"
                '/except Exception as e:/ && !found {'
                '  found=1;'
                '  print "    except subprocess.TimeoutExpired:";'
                '  print "        p.kill()";'
                '  print "        p.wait()";'
                """  print "        logging.warning(\\\"run_cmd TIMEOUT(30s): %s\\\" % cmd)";"""
                """  print "        return \\\"\\\"";"""
                '}'
                '{print}'
                "' /root/sync_qos_all.py > /root/sync_qos_all.py.tmp && mv /root/sync_qos_all.py.tmp /root/sync_qos_all.py"
            )
            ssh_exec(ip, awk_cmd)

        # 검증
        out_v, _ = ssh_exec(ip, 'grep -c "communicate(timeout=30)" /root/sync_qos_all.py')
        try:
            patched_ok = int(out_v.strip()) > 0
        except:
            patched_ok = False

        if patched_ok:
            results.append((name, 'PATCH', 'run_cmd timeout=30 추가'))
        else:
            results.append((name, 'PATCH_FAIL', 'sed 적용 실패'))
    else:
        results.append((name, 'PATCH_SKIP', '이미 timeout 적용됨'))

    # 3. cron flock + timeout
    out, rc = ssh_exec(ip, 'crontab -l 2>/dev/null | grep sync_qos | grep -v "^#"')
    cron_line = out.strip()

    if cron_line and 'flock' not in cron_line:
        # sed: /usr/bin/python 앞에 flock 삽입
        cron_sed = r"""crontab -l 2>/dev/null | sed '/sync_qos/{/^#/!{/flock/!s|/usr/bin/python |/usr/bin/flock -n /tmp/sync_qos.lock timeout 55 /usr/bin/python |}}' | crontab -"""
        ssh_exec(ip, cron_sed)

        # 검증
        out_v, _ = ssh_exec(ip, 'crontab -l 2>/dev/null | grep sync_qos | grep -v "^#"')
        if 'flock' in out_v:
            results.append((name, 'CRON', 'flock + timeout 55 추가'))
        else:
            results.append((name, 'CRON_FAIL', f'cron 수정 실패'))
    elif cron_line and 'flock' in cron_line:
        results.append((name, 'CRON_SKIP', '이미 flock 적용됨'))
    elif not cron_line:
        results.append((name, 'CRON_SKIP', 'sync_qos cron 없음'))

    # 4. check_traffic cron도 확인
    out, rc = ssh_exec(ip, 'crontab -l 2>/dev/null | grep check_traffic | grep -v "^#"')
    check_cron = out.strip()
    if check_cron and 'flock' not in check_cron:
        cron_sed2 = r"""crontab -l 2>/dev/null | sed '/check_traffic/{/^#/!{/flock/!s|/root/check_traffic|/usr/bin/flock -n /tmp/check_traffic.lock timeout 55 /root/check_traffic|}}' | crontab -"""
        ssh_exec(ip, cron_sed2)
        out_v, _ = ssh_exec(ip, 'crontab -l 2>/dev/null | grep check_traffic | grep -v "^#"')
        if 'flock' in out_v:
            results.append((name, 'CHECK_CRON', 'check_traffic flock 추가'))

    if not results:
        results.append((name, 'OK', '이미 모두 적용됨'))

    return results


def main():
    check_only = '--check' in sys.argv
    single = None
    for i, arg in enumerate(sys.argv):
        if arg == '--server' and i + 1 < len(sys.argv):
            single = sys.argv[i + 1]

    servers = get_servers()
    if not servers:
        print("서버 목록을 가져올 수 없습니다")
        return

    if single:
        servers = [s for s in servers if single.lower() in s['server_name'].lower()]
        if not servers:
            print(f"서버 '{single}'을 찾을 수 없습니다")
            return

    print(f"{'='*70}")
    print(f"sync_qos_all.py 프로세스 중복 방지 {'점검' if check_only else '배포'}")
    print(f"대상: {len(servers)}대")
    print(f"{'='*70}")

    if check_only:
        print(f"\n{'서버':<16} {'스크립트':^8} {'flock':^6} {'timeout':^8} {'프로세스':>6}")
        print(f"{'-'*16} {'-'*8} {'-'*6} {'-'*8} {'-'*6}")

        problems = []
        for sv in servers:
            name = sv['server_name']
            ip = sv['ip_address']
            info = check_server(name, ip)

            script_s = 'O' if info['script_exists'] else '-'
            flock_s = 'O' if info['has_flock'] else 'X'
            timeout_s = 'O' if info['has_timeout_in_code'] else 'X'
            proc_s = str(info['proc_count'])

            flag = ''
            if info['script_exists'] and (not info['has_flock'] or not info['has_timeout_in_code']):
                flag = ' <- PATCH'
            if info['proc_count'] > 5:
                flag = ' <- PROBLEM!'
                problems.append(name)

            print(f"{name:<16} {script_s:^8} {flock_s:^6} {timeout_s:^8} {proc_s:>6}{flag}")

        print(f"\n총 {len(servers)}대 확인 완료")
        if problems:
            print(f"문제 서버: {', '.join(problems)}")
    else:
        all_results = []
        for sv in servers:
            name = sv['server_name']
            ip = sv['ip_address']
            print(f"\n[{name}] ({ip}) 처리 중...")
            results = fix_server(name, ip)
            for r in results:
                ok = r[1] in ('KILL', 'PATCH', 'CRON', 'CHECK_CRON', 'OK', 'CRON_SKIP', 'PATCH_SKIP')
                status_icon = 'OK' if ok else 'FAIL'
                print(f"  [{status_icon}] {r[1]}: {r[2]}")
            all_results.extend(results)

        success = sum(1 for r in all_results if r[1] in ('KILL', 'PATCH', 'CRON', 'CHECK_CRON', 'OK', 'CRON_SKIP', 'PATCH_SKIP'))
        fail = sum(1 for r in all_results if 'FAIL' in r[1])
        skip = sum(1 for r in all_results if r[1] == 'SKIP')

        print(f"\n{'='*70}")
        print(f"배포 완료: 성공={success}, 실패={fail}, 스킵={skip}")
        print(f"{'='*70}")


if __name__ == '__main__':
    main()

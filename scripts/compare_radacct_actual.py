#!/usr/bin/env python3
"""
Titan radacct vs 실제 서버 연결 수 비교
각 서버에 SSH로 접속하여 IKEv2/OpenVPN/SSTP/V2RAY 실제 연결 수를 확인하고
radacct DB와 비교합니다.
"""
import django, os, subprocess, re, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
sys.path.insert(0, '/home/newkorea/project/titan-admin')
django.setup()
from django.db import connections
from backend.djangoapps.common.views import dictfetchall


def ssh_check(ip, timeout=10):
    """SSH to server and check actual VPN connection counts"""
    result = {'ip': ip, 'ikev2': None, 'openvpn': None, 'sstp': None, 'v2ray': None, 'error': None}

    # Build remote commands - each on its own line to avoid shell escaping issues
    remote_script = r"""
# IKEv2 (strongSwan) - count ESTABLISHED tunnels
IKEV2_COUNT=$(strongswan statusall 2>/dev/null | grep -c 'ESTABLISHED' || echo 0)
echo "IKEV2=$IKEV2_COUNT"

# OpenVPN - check management interface
OVPN_COUNT=0
if nc -z 127.0.0.1 1199 2>/dev/null; then
  OVPN_COUNT=$(printf "status\nquit\n" | nc -w2 127.0.0.1 1199 2>/dev/null | grep -c '^CLIENT_LIST' || echo 0)
  if [ "$OVPN_COUNT" -gt 0 ]; then
    OVPN_COUNT=$((OVPN_COUNT - 1))
  fi
fi
echo "OVPN=$OVPN_COUNT"

# SSTP - count established connections on port 443 excluding LISTEN
SSTP_COUNT=$(ss -tn state established '( sport = :443 )' 2>/dev/null | tail -n +2 | wc -l || echo 0)
echo "SSTP=$SSTP_COUNT"

# V2RAY - count established connections on port 9999
V2RAY_COUNT=$(ss -tn state established '( sport = :9999 )' 2>/dev/null | tail -n +2 | wc -l || echo 0)
echo "V2RAY=$V2RAY_COUNT"
"""

    try:
        proc = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no',
             '-o', 'BatchMode=yes', f'root@{ip}', 'bash -s'],
            input=remote_script, capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout.strip()
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('IKEV2='):
                try: result['ikev2'] = int(line.split('=', 1)[1])
                except: pass
            elif line.startswith('OVPN='):
                try: result['openvpn'] = int(line.split('=', 1)[1])
                except: pass
            elif line.startswith('SSTP='):
                try: result['sstp'] = int(line.split('=', 1)[1])
                except: pass
            elif line.startswith('V2RAY='):
                try: result['v2ray'] = int(line.split('=', 1)[1])
                except: pass
    except subprocess.TimeoutExpired:
        result['error'] = 'TIMEOUT'
    except Exception as e:
        result['error'] = str(e)

    return result


def main():
    # Get radacct data
    cursor = connections['radius'].cursor()
    cursor.execute('''
        SELECT nasipaddress,
               SUM(CASE WHEN nasporttype='Virtual' THEN 1 ELSE 0 END) as ikev2,
               SUM(CASE WHEN nasporttype='ISDN' THEN 1 ELSE 0 END) as openvpn,
               SUM(CASE WHEN nasporttype='61' THEN 1 ELSE 0 END) as sstp,
               SUM(CASE WHEN nasporttype='V2RAY' THEN 1 ELSE 0 END) as v2ray,
               COUNT(*) as total
        FROM radacct
        WHERE acctstoptime IS NULL
        GROUP BY nasipaddress
    ''')
    radacct_raw = dictfetchall(cursor)

    # Get server name + domain mapping
    cursor2 = connections['default'].cursor()
    cursor2.execute("SELECT hostip, name, hostdomain FROM tbl_agent3 WHERE is_active=1")
    servers_info = dictfetchall(cursor2)
    name_map = {s['hostip']: s['name'] for s in servers_info}
    domain_to_ip = {s['hostdomain']: s['hostip'] for s in servers_info if s['hostdomain']}

    # Merge radacct by actual IP (consolidate domain entries like V2RAY domains)
    radacct_by_ip = {}
    for r in radacct_raw:
        nas = r['nasipaddress']
        actual_ip = nas
        if nas in domain_to_ip:
            actual_ip = domain_to_ip[nas]
        elif not re.match(r'^\d+\.\d+\.\d+\.\d+$', nas):
            for dom, ip in domain_to_ip.items():
                if nas in dom or dom in nas:
                    actual_ip = ip
                    break

        if actual_ip not in radacct_by_ip:
            radacct_by_ip[actual_ip] = {'ikev2': 0, 'openvpn': 0, 'sstp': 0, 'v2ray': 0}
        radacct_by_ip[actual_ip]['ikev2'] += r['ikev2']
        radacct_by_ip[actual_ip]['openvpn'] += r['openvpn']
        radacct_by_ip[actual_ip]['sstp'] += r['sstp']
        radacct_by_ip[actual_ip]['v2ray'] += r['v2ray']

    # Get unique IPs that are actual server IPs
    valid_ips = [ip for ip in radacct_by_ip.keys() if ip in name_map]

    print(f"Checking {len(valid_ips)} servers via SSH (parallel)...")

    # SSH check all servers in parallel
    ssh_results = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(ssh_check, ip): ip for ip in valid_ips}
        for future in as_completed(futures):
            res = future.result()
            ssh_results[res['ip']] = res
            name = name_map.get(res['ip'], res['ip'])
            status = "OK" if not res['error'] else res['error']
            print(f"  {name:<16} {status}")

    # Output comparison table
    print()
    print("=" * 130)
    print(f"{'서버':<16} {'IP':<18} | {'--- radacct (DB) ---':^30} | {'--- 실제 서버 (SSH) ---':^30} | {'차이':^8}")
    print(f"{'':16} {'':18} | {'IKEv2':>6} {'OVPN':>6} {'SSTP':>6} {'V2RAY':>6} {'합':>6} | {'IKEv2':>6} {'OVPN':>6} {'SSTP':>6} {'V2RAY':>6} {'합':>6} | {'Δ합':>6}")
    print("-" * 130)

    total_db = 0
    total_real = 0
    total_ikev2_db = 0
    total_ikev2_real = 0
    total_ovpn_db = 0
    total_ovpn_real = 0
    total_sstp_db = 0
    total_sstp_real = 0
    total_v2ray_db = 0
    total_v2ray_real = 0
    problem_servers = []

    for ip in sorted(valid_ips, key=lambda x: name_map.get(x, x)):
        name = name_map.get(ip, ip)
        db = radacct_by_ip.get(ip, {'ikev2': 0, 'openvpn': 0, 'sstp': 0, 'v2ray': 0})
        real = ssh_results.get(ip, {'ikev2': None, 'openvpn': None, 'sstp': None, 'v2ray': None, 'error': 'NO_DATA'})

        db_total = db['ikev2'] + db['openvpn'] + db['sstp'] + db['v2ray']

        r_ikev2 = real['ikev2'] if real['ikev2'] is not None else '-'
        r_ovpn = real['openvpn'] if real['openvpn'] is not None else '-'
        r_sstp = real['sstp'] if real['sstp'] is not None else '-'
        r_v2ray = real['v2ray'] if real['v2ray'] is not None else '-'

        if all(x is not None for x in [real['ikev2'], real['openvpn'], real['sstp'], real['v2ray']]):
            real_total = real['ikev2'] + real['openvpn'] + real['sstp'] + real['v2ray']
            diff = real_total - db_total
            diff_str = f"{diff:>+6}"
            total_real += real_total
            total_ikev2_real += real['ikev2']
            total_ovpn_real += real['openvpn']
            total_sstp_real += real['sstp']
            total_v2ray_real += real['v2ray']
        else:
            real_total = '-'
            diff_str = f"{'?':>6}"

        total_db += db_total
        total_ikev2_db += db['ikev2']
        total_ovpn_db += db['openvpn']
        total_sstp_db += db['sstp']
        total_v2ray_db += db['v2ray']

        marker = ""
        try:
            d = int(str(diff_str).strip().replace('+', ''))
            if abs(d) > 5:
                marker = " ★"
                problem_servers.append((name, ip, db_total, real_total, d))
        except:
            pass

        print(f"{name:<16} {ip:<18} | {db['ikev2']:>6} {db['openvpn']:>6} {db['sstp']:>6} {db['v2ray']:>6} {db_total:>6} | {str(r_ikev2):>6} {str(r_ovpn):>6} {str(r_sstp):>6} {str(r_v2ray):>6} {str(real_total):>6} | {diff_str}{marker}")

    print("-" * 130)
    print(f"{'합계':<16} {'':18} | {total_ikev2_db:>6} {total_ovpn_db:>6} {total_sstp_db:>6} {total_v2ray_db:>6} {total_db:>6} | {total_ikev2_real:>6} {total_ovpn_real:>6} {total_sstp_real:>6} {total_v2ray_real:>6} {total_real:>6} | {total_real - total_db:>+6}")

    # Unknown IPs in radacct
    unknown_ips = [ip for ip in radacct_by_ip.keys() if ip not in name_map]
    if unknown_ips:
        print(f"\n⚠ radacct에 있지만 tbl_agent3에 없는 NAS IP:")
        for ip in sorted(unknown_ips):
            db = radacct_by_ip[ip]
            db_total = db['ikev2'] + db['openvpn'] + db['sstp'] + db['v2ray']
            print(f"  {ip:<32} IKEv2={db['ikev2']} OVPN={db['openvpn']} SSTP={db['sstp']} V2RAY={db['v2ray']} Total={db_total}")

    if problem_servers:
        print(f"\n★ 차이가 큰 서버 (|Δ| > 5):")
        for name, ip, db_t, real_t, d in sorted(problem_servers, key=lambda x: abs(x[4]), reverse=True):
            direction = "실제 > DB (radacct 누락 가능)" if d > 0 else "DB > 실제 (stale 세션 가능)"
            print(f"  {name:<16} DB={db_t:>3} 실제={real_t:>3} 차이={d:>+4}  → {direction}")

    # Summary
    print(f"\n=== 요약 ===")
    print(f"radacct 활성 세션: {total_db}")
    print(f"실제 서버 연결:    {total_real}")
    diff_total = total_real - total_db
    print(f"차이:             {'+' if diff_total >= 0 else ''}{diff_total}")
    print(f"프로토콜별 차이:")
    def fmt_diff(v):
        return f'+{v}' if v >= 0 else str(v)
    print(f"  IKEv2: DB={total_ikev2_db} 실제={total_ikev2_real} D={fmt_diff(total_ikev2_real - total_ikev2_db)}")
    print(f"  OVPN:  DB={total_ovpn_db} 실제={total_ovpn_real} D={fmt_diff(total_ovpn_real - total_ovpn_db)}")
    print(f"  SSTP:  DB={total_sstp_db} 실제={total_sstp_real} D={fmt_diff(total_sstp_real - total_sstp_db)}")
    print(f"  V2RAY: DB={total_v2ray_db} 실제={total_v2ray_real} D={fmt_diff(total_v2ray_real - total_v2ray_db)}")


if __name__ == '__main__':
    main()

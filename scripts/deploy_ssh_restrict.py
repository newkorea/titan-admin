#!/usr/bin/env python3
"""
Deploy SSH restriction rules to all NAS servers.
Only allows SSH from specified management IP ranges.
All other SSH connections are DROPped.

Usage:
    python3 deploy_ssh_restrict.py              # Deploy to all servers
    python3 deploy_ssh_restrict.py --dry-run    # Show what would be done
    python3 deploy_ssh_restrict.py --server IP  # Deploy to specific server only
    python3 deploy_ssh_restrict.py --check      # Check current SSH attack levels
"""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# Allowed SSH source CIDRs (deduplicated - broader ranges kept)
# ============================================================
ALLOWED_CIDRS = [
    # --- /16 ---
    "211.46.0.0/16",
    # --- /24 ---
    "218.158.57.0/24",
    "121.159.134.0/24",
    "211.216.225.0/24",
    "220.82.114.0/24",
    "220.123.216.0/24",
    "220.123.89.0/24",
    "125.132.9.0/24",
    "14.51.2.0/24",
    "118.34.105.0/24",
    "112.218.79.0/24",
    "59.26.85.0/24",
    "218.49.179.0/24",
    "115.71.13.0/24",
    "118.27.36.0/24",
    "1.221.16.0/24",
    # --- /25 ---
    "218.236.231.224/27",
    "218.236.241.224/27",
    "221.143.197.128/27",
    "110.15.180.160/27",
    "218.233.115.160/27",
    "218.53.199.64/27",
    "218.54.235.160/27",
    "219.240.134.224/27",
    # --- /32 (single host) ---
    "27.115.70.46/32",
]

# ============================================================
# All NAS servers (from DB tbl_agent3 where is_active=1)
# ============================================================
SERVERS = [
    ("139.84.165.217", "INDIA-Delhi1"),
    ("118.27.36.188", "JAPAN-CH"),
    ("14.51.2.130", "KOREA-KT0"),
    ("14.51.2.131", "KOREA-KT1"),
    ("14.51.2.132", "KOREA-KT2"),
    ("218.158.57.23", "KOREA-KT23"),
    ("121.159.134.27", "KOREA-KT27"),
    ("220.89.190.219", "KOREA-KT28"),
    ("220.82.114.127", "KOREA-KT29"),
    ("220.123.216.40", "KOREA-KT30"),
    ("220.123.216.21", "KOREA-KT31"),
    ("218.158.160.41", "KOREA-KT32"),
    ("218.158.57.25", "KOREA-KT33"),
    ("125.132.9.135", "KOREA-KT35"),
    ("125.132.9.136", "KOREA-KT36"),
    ("125.132.9.137", "KOREA-KT37"),
    ("125.132.9.138", "KOREA-KT38"),
    ("125.132.9.139", "KOREA-KT39"),
    ("14.51.2.179", "KOREA-KT4"),
    ("125.132.9.140", "KOREA-KT40"),
    ("125.132.9.141", "KOREA-KT41"),
    ("125.132.9.142", "KOREA-KT42"),
    ("112.218.79.75", "KOREA-LG2"),
    ("1.221.16.187", "KOREA-LG3"),
    ("221.143.197.130", "KOREA-SK10"),
    ("221.143.197.131", "KOREA-SK11"),
    ("221.143.197.132", "KOREA-SK12"),
    ("221.143.197.133", "KOREA-SK13"),
    ("221.143.197.134", "KOREA-SK14"),
    ("221.143.197.135", "KOREA-SK15"),
    ("221.143.197.136", "KOREA-SK16"),
    ("218.236.231.231", "KOREA-SK21"),
    ("218.236.231.232", "KOREA-SK22"),
    ("218.49.179.74", "KOREA-SK4"),
    ("218.49.179.75", "KOREA-SK5"),
    ("218.49.179.76", "KOREA-SK6"),
    ("218.49.179.77", "KOREA-SK7"),
    ("218.49.179.78", "KOREA-SK8"),
    ("218.49.179.79", "KOREA-SK9"),
    ("45.63.55.252", "US-LA"),
]


def build_deploy_script():
    """Build the shell script to apply SSH restriction rules."""
    lines = [
        "#!/bin/bash",
        "",
        "# Backup current iptables rules",
        "iptables-save > /tmp/iptables_backup_ssh_restrict.rules 2>/dev/null || true",
        "",
        "# Remove ALL existing SSH-MGMT / SSH-BLOCK rules",
        "for i in $(seq 1 50); do",
        "  NUM=$(iptables -L INPUT -n --line-numbers 2>/dev/null | grep -E 'SSH-MGMT|SSH-BLOCK' | head -1 | awk '{print $1}')",
        '  [ -z "$NUM" ] && break',
        '  iptables -D INPUT "$NUM" 2>/dev/null || break',
        "done",
        "",
    ]

    # Add ACCEPT rules in REVERSE order (iptables -I INPUT 1 puts each at top)
    for cidr in reversed(ALLOWED_CIDRS):
        lines.append(
            f"iptables -I INPUT 1 -p tcp --dport 22 -s {cidr} -j ACCEPT "
            f"-m comment --comment SSH-MGMT"
        )

    # Add DROP rule right after all ACCEPTs
    drop_pos = len(ALLOWED_CIDRS) + 1
    lines.append(
        f"iptables -I INPUT {drop_pos} -p tcp --dport 22 -j DROP "
        f"-m comment --comment SSH-BLOCK-BRUTEFORCE"
    )

    lines.extend([
        "",
        "# Save permanently (try CentOS/RHEL, then Debian/Ubuntu, then rc.local)",
        "if [ -d /etc/sysconfig ]; then",
        "  iptables-save > /etc/sysconfig/iptables 2>/dev/null",
        "elif [ -d /etc/iptables ]; then",
        "  iptables-save > /etc/iptables/rules.v4 2>/dev/null",
        "else",
        "  iptables-save > /etc/iptables.rules 2>/dev/null",
        "fi",
        "",
        "echo SSH_RESTRICT_DONE",
    ])

    return "\n".join(lines)


def build_check_script():
    """Build script to check current SSH attack level."""
    return (
        "CNT=$(journalctl -u sshd --since '10 min ago' --no-pager 2>/dev/null "
        "| grep -c 'Invalid user\\|Failed password' 2>/dev/null || echo 0); "
        "HAS_BLOCK=$(iptables -L INPUT -n 2>/dev/null | grep -c 'SSH-BLOCK' || echo 0); "
        "echo \"ATTACKS=$CNT PROTECTED=$HAS_BLOCK\""
    )


def deploy_to_server(ip, name, script, dry_run=False):
    """Deploy SSH restriction to a single server."""
    if dry_run:
        return (ip, name, "DRY-RUN", "Would deploy")

    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", f"root@{ip}", "bash -s"],
            input=script, capture_output=True, text=True, timeout=30
        )
        if "SSH_RESTRICT_DONE" in result.stdout:
            return (ip, name, "OK", "")
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return (ip, name, "FAIL", err[:100])
    except subprocess.TimeoutExpired:
        return (ip, name, "FAIL", "SSH timeout")
    except Exception as e:
        return (ip, name, "FAIL", str(e)[:100])


def check_server(ip, name, script):
    """Check SSH attack level on a server."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", f"root@{ip}", script],
            capture_output=True, text=True, timeout=15
        )
        return (ip, name, result.stdout.strip())
    except Exception as e:
        return (ip, name, f"ERROR: {e}")


def main():
    dry_run = "--dry-run" in sys.argv
    check_mode = "--check" in sys.argv
    target_ip = None

    for i, arg in enumerate(sys.argv):
        if arg == "--server" and i + 1 < len(sys.argv):
            target_ip = sys.argv[i + 1]

    servers = SERVERS
    if target_ip:
        servers = [(ip, name) for ip, name in SERVERS if ip == target_ip]
        if not servers:
            print(f"Server {target_ip} not found in server list")
            sys.exit(1)

    if check_mode:
        print(f"Checking SSH attack levels on {len(servers)} servers...\n")
        script = build_check_script()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(check_server, ip, name, script): (ip, name)
                for ip, name in servers
            }
            results = []
            for future in as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda x: x[1])
        for ip, name, info in results:
            protected = "PROTECTED=1" in info
            shield = "🛡" if protected else "⚠"
            print(f"  {shield} {name:20s} ({ip:18s}) {info}")
        return

    script = build_deploy_script()

    if dry_run:
        print("=== DRY RUN - Script that would be deployed ===")
        print(script)
        print(f"\n=== Would deploy to {len(servers)} servers ===")
        for ip, name in servers:
            print(f"  {name} ({ip})")
        return

    print(f"Deploying SSH restriction to {len(servers)} servers...")
    print(f"Allowed CIDRs: {len(ALLOWED_CIDRS)}")
    print()

    results = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(deploy_to_server, ip, name, script): (ip, name)
            for ip, name in servers
        }
        for future in as_completed(futures):
            result = future.result()
            ip, name, status, error = result
            if status == "OK":
                print(f"  ✓ {name:20s} ({ip})")
            else:
                print(f"  ✗ {name:20s} ({ip}): {error}")
            results.append(result)

    elapsed = time.time() - start
    ok_count = sum(1 for r in results if r[2] == "OK")
    fail_count = sum(1 for r in results if r[2] == "FAIL")

    print(f"\n{'='*60}")
    print(f"Result: {ok_count} OK, {fail_count} FAIL / {len(servers)} total ({elapsed:.1f}s)")

    if fail_count > 0:
        print(f"\nFailed servers:")
        for ip, name, status, error in sorted(results, key=lambda x: x[1]):
            if status == "FAIL":
                print(f"  ✗ {name} ({ip}): {error}")


if __name__ == "__main__":
    main()

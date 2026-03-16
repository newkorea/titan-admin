#!/usr/bin/env python3
"""
Deploy SSH key + iptables restriction to UTO NAS servers.
Same allowed CIDRs as Titan servers (deploy_ssh_restrict.py).
Excludes RouterOS (admin login) and unreachable servers.

Usage:
    python3 deploy_uto_ssh.py                    # Deploy key + iptables to all
    python3 deploy_uto_ssh.py --key-only         # Deploy SSH key only
    python3 deploy_uto_ssh.py --iptables-only    # Deploy iptables only (requires key auth)
    python3 deploy_uto_ssh.py --dry-run          # Show plan without executing
    python3 deploy_uto_ssh.py --server IP        # Target specific server
    python3 deploy_uto_ssh.py --check            # Check current status
"""

import subprocess
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# SSH Public Key (same as Titan servers - newkorea@pc ed25519)
# ============================================================
SSH_PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID6MfQsLYAzOjf8VfWidJ1pAzjSfmizHsIpfo9Rgefhr newkorea@pc"

# ============================================================
# Allowed SSH CIDRs (same as Titan - from deploy_ssh_restrict.py)
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
    # --- /27 ---
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
# UTO Linux servers (root login, port 22)
# Excludes: RouterOS (admin login), unreachable servers
# ============================================================
SERVERS = [
    # (IP, name, password, ssh_port)
    ("112.218.79.74", "LG직통1", "uto6703", 22),
    ("118.27.36.188", "일본JP", "ss135690", 22),
    ("125.132.9.136", "ktdb136_V2RAY", "uto6703", 22),
    ("125.132.9.170", "KT직통DB170", "uto6703", 22),
    ("125.132.9.171", "KT직통DB171", "uto6703", 22),
    ("125.132.9.173", "KT직통DB173", "uto6703", 22),
    ("125.132.9.174", "KT직통DB174", "uto6703", 22),
    ("125.132.9.175", "KT직통DB175", "uto6703", 22),
    ("139.84.165.217", "INDIA", "ss135690!@", 22),
    ("14.51.2.181", "KT14181", "uto6703", 22),
    ("14.51.2.182", "KT14182", "uto6703", 22),
    ("211.46.6.241", "kt211466241", "uto6703", 22),
    ("211.46.6.242", "kt211466242", "uto6703", 22),
    ("211.46.6.243", "kt211466243", "uto6703", 22),
    ("218.158.57.67", "KT직통D67", "uto6703", 22),
    ("218.158.57.91", "KT직통D91", "uto6703", 22),
    ("218.233.115.162", "SK218162", "uto6703", 22),
    ("218.233.115.163", "SK218163", "uto6703", 22),
    ("218.233.115.164", "SK218164", "uto6703", 22),
    ("218.49.179.80", "SK직통80", "uto6703", 22),
    ("218.49.179.81", "SK직통81", "uto6703", 22),
    ("218.49.179.83", "SK직통83", "uto6703", 22),
    ("218.49.179.84", "SK직통84", "uto6703", 22),
    ("218.49.179.85", "SK직통85", "uto6703", 22),
    ("218.49.179.86", "SK직통86", "uto6703", 22),
    ("218.49.179.87", "SK직통87", "uto6703", 22),
    ("218.49.179.88", "SK직통88", "uto6703", 22),
    ("218.49.179.89", "SK직통89", "uto6703", 22),
    ("218.49.179.90", "SK직통90", "uto6703", 22),
    ("221.143.197.130", "SK221130", "uto6703", 22),
    ("221.143.197.132", "SK221132", "uto6703", 22),
    ("45.63.55.252", "미국US", "ss135690!@", 22),
]

# Servers that need manual attention:
# 218.158.57.66 (KTD66_V2RAY) - password 'uto6703' doesn't work, port 37625 closed
# 125.132.9.180 (KT직통DB180 SSTP) - unreachable on both port 22 and 100


def deploy_ssh_key(ip, name, password, port=22):
    """Deploy SSH public key to a server using sshpass."""
    # First check if key already works
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "-p", str(port),
             f"root@{ip}", "echo KEY_ALREADY_OK"],
            capture_output=True, text=True, timeout=15
        )
        if "KEY_ALREADY_OK" in result.stdout:
            return (ip, name, "SKIP", "Key already deployed")
    except:
        pass

    # Deploy key using sshpass
    try:
        # Create .ssh dir and add key
        script = f"""
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
if ! grep -q '{SSH_PUBKEY.split()[1]}' ~/.ssh/authorized_keys 2>/dev/null; then
    echo '{SSH_PUBKEY}' >> ~/.ssh/authorized_keys
    echo KEY_DEPLOYED
else
    echo KEY_ALREADY_EXISTS
fi
"""
        result = subprocess.run(
            ["sshpass", "-p", password, "ssh",
             "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
             "-o", "PreferredAuthentications=password",
             "-p", str(port), f"root@{ip}", "bash -s"],
            input=script, capture_output=True, text=True, timeout=20
        )
        stdout = result.stdout.strip()
        if "KEY_DEPLOYED" in stdout:
            return (ip, name, "OK", "Key deployed")
        elif "KEY_ALREADY_EXISTS" in stdout:
            return (ip, name, "SKIP", "Key already in authorized_keys")
        else:
            err = result.stderr.strip() or stdout
            return (ip, name, "FAIL", err[:120])
    except subprocess.TimeoutExpired:
        return (ip, name, "FAIL", "SSH timeout")
    except Exception as e:
        return (ip, name, "FAIL", str(e)[:120])


def verify_key_auth(ip, name, port=22):
    """Verify SSH key authentication works."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "-p", str(port),
             f"root@{ip}", "echo KEY_AUTH_VERIFIED"],
            capture_output=True, text=True, timeout=15
        )
        if "KEY_AUTH_VERIFIED" in result.stdout:
            return (ip, name, "OK", "Key auth works")
        else:
            err = result.stderr.strip()[:80]
            return (ip, name, "FAIL", f"Key auth failed: {err}")
    except Exception as e:
        return (ip, name, "FAIL", str(e)[:80])


def build_iptables_script(ssh_port=22):
    """Build iptables SSH restriction script (same logic as Titan)."""
    lines = [
        "#!/bin/bash",
        "set -e",
        "",
        "# Remove existing SSH rules (both ACCEPT and DROP for our port)",
        f"while iptables -L INPUT -n --line-numbers 2>/dev/null | grep -q 'dpt:{ssh_port}.*SSH-'; do",
        f"  NUM=$(iptables -L INPUT -n --line-numbers 2>/dev/null | grep 'dpt:{ssh_port}.*SSH-' | head -1 | awk '{{print $1}}')",
        '  [ -z "$NUM" ] && break',
        "  iptables -D INPUT $NUM",
        "done",
        "",
        f"# Add ACCEPT rules for allowed CIDRs (port {ssh_port})",
    ]

    for i, cidr in enumerate(ALLOWED_CIDRS, 1):
        lines.append(
            f"iptables -I INPUT {i} -p tcp -s {cidr} --dport {ssh_port} -j ACCEPT "
            f'-m comment --comment "SSH-MGMT"'
        )

    # DROP rule at the end (after all ACCEPT rules)
    drop_pos = len(ALLOWED_CIDRS) + 1
    lines.append(
        f"iptables -I INPUT {drop_pos} -p tcp --dport {ssh_port} -j DROP "
        f'-m comment --comment "SSH-BLOCK-BRUTEFORCE"'
    )

    lines.extend([
        "",
        "# Save permanently (CentOS/RHEL, Debian/Ubuntu, or rc.local fallback)",
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


def deploy_iptables(ip, name, port=22):
    """Deploy iptables SSH restriction to a server (using key auth)."""
    script = build_iptables_script(ssh_port=port)
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "-p", str(port),
             f"root@{ip}", "bash -s"],
            input=script, capture_output=True, text=True, timeout=30
        )
        if "SSH_RESTRICT_DONE" in result.stdout:
            return (ip, name, "OK", "")
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return (ip, name, "FAIL", err[:120])
    except subprocess.TimeoutExpired:
        return (ip, name, "FAIL", "SSH timeout")
    except Exception as e:
        return (ip, name, "FAIL", str(e)[:120])


def check_status(ip, name, port=22):
    """Check current SSH key + iptables status."""
    cmds = (
        "KEY_OK=0; grep -q 'newkorea@pc' ~/.ssh/authorized_keys 2>/dev/null && KEY_OK=1; "
        f"IPTABLES_OK=$(iptables -L INPUT -n 2>/dev/null | grep -c 'SSH-BLOCK' || echo 0); "
        "echo \"KEY=$KEY_OK IPTABLES=$IPTABLES_OK\""
    )
    try:
        # Try key auth first
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no", "-p", str(port),
             f"root@{ip}", cmds],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return (ip, name, "KEY_AUTH", result.stdout.strip())
        else:
            return (ip, name, "NO_KEY", result.stderr.strip()[:80])
    except Exception as e:
        return (ip, name, "ERROR", str(e)[:80])


def main():
    dry_run = "--dry-run" in sys.argv
    key_only = "--key-only" in sys.argv
    iptables_only = "--iptables-only" in sys.argv
    check_mode = "--check" in sys.argv
    target_ip = None

    for i, arg in enumerate(sys.argv):
        if arg == "--server" and i + 1 < len(sys.argv):
            target_ip = sys.argv[i + 1]

    servers = SERVERS
    if target_ip:
        servers = [(ip, n, pw, p) for ip, n, pw, p in SERVERS if ip == target_ip]
        if not servers:
            print(f"Server {target_ip} not found")
            sys.exit(1)

    # ---- CHECK MODE ----
    if check_mode:
        print(f"Checking SSH status on {len(servers)} UTO servers...\n")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(check_status, ip, name, port): (ip, name)
                for ip, name, pw, port in servers
            }
            results = []
            for future in as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda x: x[1])
        key_ok = ipt_ok = 0
        for ip, name, auth, info in results:
            if auth == "KEY_AUTH":
                key_yes = "KEY=1" in info
                ipt_yes = "IPTABLES=1" in info or "IPTABLES=2" in info
                if key_yes: key_ok += 1
                if ipt_yes: ipt_ok += 1
                k = "🔑" if key_yes else "❌"
                f = "🛡" if ipt_yes else "⚠"
                print(f"  {k}{f} {name:20s} ({ip:18s}) {info}")
            else:
                print(f"  ❌⚠ {name:20s} ({ip:18s}) {auth}: {info}")

        print(f"\nSummary: {key_ok}/{len(results)} key OK, {ipt_ok}/{len(results)} iptables OK")
        return

    # ---- DRY RUN ----
    if dry_run:
        print(f"=== DRY RUN ===")
        print(f"Target servers: {len(servers)}")
        print(f"Allowed CIDRs: {len(ALLOWED_CIDRS)}")
        mode = "key+iptables"
        if key_only: mode = "key only"
        if iptables_only: mode = "iptables only"
        print(f"Mode: {mode}")
        print()
        for ip, name, pw, port in servers:
            pw_masked = pw[:3] + "***"
            print(f"  {name:20s} ({ip:18s}) port={port} pw={pw_masked}")
        print()
        print("Iptables script sample:")
        print(build_iptables_script(22)[:500])
        return

    # ---- DEPLOY SSH KEY ----
    if not iptables_only:
        print(f"{'='*60}")
        print(f"Phase 1: Deploying SSH key to {len(servers)} UTO servers...")
        print(f"{'='*60}\n")

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(deploy_ssh_key, ip, name, pw, port): (ip, name)
                for ip, name, pw, port in servers
            }
            for future in as_completed(futures):
                result = future.result()
                ip, name, status, msg = result
                sym = {"OK": "✓", "SKIP": "~", "FAIL": "✗"}[status]
                print(f"  {sym} {name:20s} ({ip:18s}) [{status}] {msg}")
                results.append(result)

        ok = sum(1 for r in results if r[2] in ("OK", "SKIP"))
        fail = sum(1 for r in results if r[2] == "FAIL")
        print(f"\nKey deploy: {ok} OK/SKIP, {fail} FAIL\n")

        if fail > 0 and not key_only:
            print("WARNING: Some key deploys failed. Continuing with iptables for successful ones.\n")

        # Verify key auth
        print("Verifying key auth...")
        verified = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(verify_key_auth, ip, name, port): (ip, name)
                for ip, name, pw, port in servers
            }
            for future in as_completed(futures):
                result = future.result()
                ip, name, status, msg = result
                if status == "OK":
                    verified.append(ip)
                else:
                    print(f"  ✗ {name:20s} ({ip:18s}) {msg}")

        print(f"Key auth verified: {len(verified)}/{len(servers)}\n")

    # ---- DEPLOY IPTABLES ----
    if not key_only:
        print(f"{'='*60}")
        print(f"Phase 2: Deploying iptables SSH restriction...")
        print(f"{'='*60}\n")

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(deploy_iptables, ip, name, port): (ip, name)
                for ip, name, pw, port in servers
            }
            for future in as_completed(futures):
                result = future.result()
                ip, name, status, error = result
                if status == "OK":
                    print(f"  ✓ {name:20s} ({ip})")
                else:
                    print(f"  ✗ {name:20s} ({ip}): {error}")
                results.append(result)

        ok = sum(1 for r in results if r[2] == "OK")
        fail = sum(1 for r in results if r[2] == "FAIL")
        print(f"\nIptables deploy: {ok} OK, {fail} FAIL / {len(servers)} total")

        if fail > 0:
            print(f"\nFailed servers:")
            for ip, name, status, error in sorted(results, key=lambda x: x[1]):
                if status == "FAIL":
                    print(f"  ✗ {name} ({ip}): {error}")

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

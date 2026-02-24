"""
인프라 관리 (하이퍼바이저 + VM) — views
ESXi / KVM 호스트 관리, VM 목록·전원제어, 상태 동기화
"""
import json
import subprocess
import threading
import time
import re
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from django.views.decorators.csrf import csrf_exempt
from backend.djangoapps.common.views import allow_admin, dictfetchall


# ──────────────────────────────────────────────
#  내부 헬퍼
# ──────────────────────────────────────────────
def _ssh_cmd(ip, user, password, cmd, port=22, timeout=20):
    """sshpass 를 사용해 원격 명령 실행 후 (stdout, stderr, returncode) 반환"""
    ssh = [
        'sshpass', '-p', password,
        'ssh', '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=10',
        '-o', 'PreferredAuthentications=keyboard-interactive,password',
        '-o', 'PubkeyAuthentication=no',
        '-p', str(port),
        f'{user}@{ip}',
        cmd,
    ]
    try:
        r = subprocess.run(ssh, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', 'timeout', -1


def _get_host(cursor, host_id):
    cursor.execute("SELECT * FROM tbl_hypervisor WHERE id=%s", [host_id])
    rows = dictfetchall(cursor)
    return rows[0] if rows else None


def _log(cursor, hv_id, vm_id, action, result, detail=''):
    cursor.execute(
        "INSERT INTO tbl_hypervisor_log (hypervisor_id, vm_id, action, result, detail) VALUES (%s,%s,%s,%s,%s)",
        [hv_id, vm_id, action, result, detail]
    )


# ──────────────────────────────────────────────
#  ESXi 정보 수집
# ──────────────────────────────────────────────
def _collect_esxi_info(host):
    """SSH 로 ESXi 호스트 정보 + VM 목록 수집 (SSH 2회로 최적화)"""
    ip, user, pw, port = host['ip_address'], host['ssh_user'], host['ssh_password'], host['ssh_port']
    info = {'status': 'online', 'esxi_version': '', 'cpu_model': '', 'cpu_cores': 0,
            'memory_gb': 0, 'storage_gb': 0, 'vms': []}

    # ──── SSH 1회: 빠른 명령만 수집 (esxcli 없이, stat -f 없이) ────
    host_cmd = r"""
echo '@@SECTION:VERSION@@'; vmware -v 2>/dev/null;
echo '@@SECTION:UPTIME@@'; uptime 2>/dev/null;
echo '@@SECTION:MEMCOMP@@'; vsish -e get /memory/comprehensive 2>/dev/null;
echo '@@SECTION:FB_CPUCOUNT@@'; grep -c processor /proc/cpuinfo 2>/dev/null;
echo '@@SECTION:FB_CPUMODEL@@'; smbiosDump 2>/dev/null | grep -A8 'Processor Info' | grep 'Version:' | head -1;
echo '@@SECTION:FB_NICLIST@@'; esxcfg-nics -l 2>/dev/null;
"""
    out, err, rc = _ssh_cmd(ip, user, pw, host_cmd, port, timeout=15)

    if rc != 0 and not out:
        return {'status': 'offline', 'error': err or 'ssh failed'}

    # 섹션 파싱
    sections = {}
    current = None
    for line in out.split('\n'):
        if line.startswith('@@SECTION:') and line.endswith('@@'):
            current = line[10:-2]
            sections[current] = []
        elif current:
            sections[current].append(line)

    # VERSION 확인
    ver_lines = sections.get('VERSION', [])
    info['esxi_version'] = '\n'.join(ver_lines).strip()
    if not info['esxi_version']:
        return {'status': 'offline', 'error': err or 'no version info'}

    # ──── SSH 2회: esxcli 명령 시도 (타임아웃되면 무시) ────
    esxcli_cmd = r"""
echo '@@SECTION:CPU@@'; esxcli hardware cpu global get 2>/dev/null;
echo '@@SECTION:CPUMODEL@@'; esxcli hardware cpu list 2>/dev/null | grep -m1 'Brand';
echo '@@SECTION:MEM@@'; esxcli hardware memory get 2>/dev/null | grep 'Physical Memory';
echo '@@SECTION:STORAGE@@'; esxcli storage filesystem list 2>/dev/null;
echo '@@SECTION:NICLIST@@'; esxcli network nic list 2>/dev/null;
"""
    for i in range(4):
        esxcli_cmd += f"echo '@@SECTION:NICSTAT{i}@@'; esxcli network nic stats get -n vmnic{i} 2>/dev/null | grep -iE 'Bytes|Packets received|Packets sent';\n"

    out2, _, rc2 = _ssh_cmd(ip, user, pw, esxcli_cmd, port, timeout=20)
    if rc2 == 0 and out2:
        for line in out2.split('\n'):
            if line.startswith('@@SECTION:') and line.endswith('@@'):
                current = line[10:-2]
                if current not in sections:
                    sections[current] = []
            elif current:
                sections[current].append(line)

    # ──── SSH 3회 (esxcli storage 실패 시): stat -f 로 스토리지 수집 ────
    if not sections.get('STORAGE') or not any('VMFS' in l for l in sections.get('STORAGE', [])):
        # 네임드 볼륨만 개별 stat -f
        vol_out, _, vol_rc = _ssh_cmd(ip, user, pw,
            r"ls /vmfs/volumes/ 2>/dev/null | grep -vE '^[0-9a-f]{8}-'", port, timeout=10)
        if vol_rc == 0 and vol_out:
            named_vols = [v.strip() for v in vol_out.split('\n') if v.strip()]
            fb_storage_lines = []
            for vol in named_vols[:10]:  # 최대 10개
                st_out, _, st_rc = _ssh_cmd(ip, user, pw,
                    f'stat -f "/vmfs/volumes/{vol}" 2>/dev/null', port, timeout=5)
                if st_rc == 0 and st_out and 'Block size' in st_out:
                    fb_storage_lines.append(st_out.replace('\n', '|') + f'@@NAME={vol}')
            if fb_storage_lines:
                sections['FB_STORAGE'] = fb_storage_lines

    # CPU (esxcli 실패 시 /proc/cpuinfo fallback)
    cpu_text = '\n'.join(sections.get('CPU', []))
    m = re.search(r'CPU Cores:\s*(\d+)', cpu_text)
    if m:
        info['cpu_cores'] = int(m.group(1))
    else:
        # fallback: grep -c processor /proc/cpuinfo
        fb_cpu = '\n'.join(sections.get('FB_CPUCOUNT', [])).strip()
        info['cpu_cores'] = int(fb_cpu) if fb_cpu.isdigit() else 0

    # CPU 모델 (esxcli 실패 시 smbiosDump fallback)
    cpu_model_text = '\n'.join(sections.get('CPUMODEL', []))
    m = re.search(r':\s*(.+)', cpu_model_text)
    if m:
        info['cpu_model'] = m.group(1).strip()
    else:
        fb_model = '\n'.join(sections.get('FB_CPUMODEL', []))
        m2 = re.search(r'Version:\s*"?(.+?)"?\s*$', fb_model, re.MULTILINE)
        info['cpu_model'] = m2.group(1).strip().strip('"') if m2 else ''

    # 메모리 총량 (esxcli memory get → vsish fallback)
    mem_text = '\n'.join(sections.get('MEM', []))
    m = re.search(r'(\d+)', mem_text)
    if m:
        info['memory_gb'] = round(int(m.group(1)) / (1024**3))
    else:
        # vsish comprehensive 에서 Physical memory estimate 로 계산
        memcomp_text_pre = '\n'.join(sections.get('MEMCOMP', []))
        m_phys = re.search(r'Physical memory estimate:\s*(\d+)\s*KB', memcomp_text_pre)
        if m_phys:
            info['memory_gb'] = round(int(m_phys.group(1)) / (1024 * 1024))

    # 메모리 사용량
    memcomp_text = '\n'.join(sections.get('MEMCOMP', []))
    m_total = re.search(r'Physical memory estimate:\s*(\d+)\s*KB', memcomp_text)
    m_free = re.search(r'Free:\s*(\d+)\s*KB', memcomp_text)
    mem_total_kb = int(m_total.group(1)) if m_total else 0
    mem_free_kb = int(m_free.group(1)) if m_free else 0
    if mem_total_kb > 0:
        mem_used_kb = mem_total_kb - mem_free_kb
        info['memory_used_gb'] = round(mem_used_kb / (1024 * 1024), 1)
        info['memory_free_gb'] = round(mem_free_kb / (1024 * 1024), 1)
        info['memory_used_pct'] = round(mem_used_kb / mem_total_kb * 100, 1)
    else:
        info['memory_used_gb'] = 0
        info['memory_free_gb'] = 0
        info['memory_used_pct'] = 0

    # 스토리지 (esxcli → stat -f fallback)
    total_bytes = 0
    datastores = []
    for line in sections.get('STORAGE', []):
        if 'VMFS' in line:
            parts = line.split()
            if len(parts) >= 7:
                try:
                    size_b = int(parts[-2])
                    free_b = int(parts[-1])
                    vol_name = parts[1]
                    total_bytes += size_b
                    used_b = size_b - free_b
                    datastores.append({
                        'name': vol_name,
                        'size_gb': round(size_b / (1024**3), 1),
                        'free_gb': round(free_b / (1024**3), 1),
                        'used_gb': round(used_b / (1024**3), 1),
                        'used_pct': round(used_b / size_b * 100, 1) if size_b > 0 else 0,
                    })
                except:
                    pass

    # esxcli storage 가 실패한 경우 stat -f fallback
    if not datastores:
        for line in sections.get('FB_STORAGE', []):
            line = line.strip()
            if not line or '@@NAME=' not in line:
                continue
            try:
                name_m = re.search(r'@@NAME=(.+)$', line)
                vol_name = name_m.group(1).strip() if name_m else ''
                if not vol_name:
                    continue
                stat_part = line[:name_m.start()]
                # stat -f output: "Block size: 1048576|Blocks: Total: 450048  Free: 76696  Available: 76696"
                bs_m = re.search(r'Block size:\s*(\d+)', stat_part)
                total_m = re.search(r'Blocks:\s*Total:\s*(\d+)', stat_part)
                free_m = re.search(r'Free:\s*(\d+)', stat_part)
                block_size = int(bs_m.group(1)) if bs_m else 0
                total_blocks = int(total_m.group(1)) if total_m else 0
                free_blocks = int(free_m.group(1)) if free_m else 0
                if block_size > 0 and total_blocks > 0:
                    size_b = block_size * total_blocks
                    free_b = block_size * free_blocks
                    used_b = size_b - free_b
                    total_bytes += size_b
                    datastores.append({
                        'name': vol_name,
                        'size_gb': round(size_b / (1024**3), 1),
                        'free_gb': round(free_b / (1024**3), 1),
                        'used_gb': round(used_b / (1024**3), 1),
                        'used_pct': round(used_b / size_b * 100, 1) if size_b > 0 else 0,
                    })
            except:
                pass

    info['storage_gb'] = round(total_bytes / (1024**3)) if total_bytes else 0
    info['datastores'] = datastores

    # 네트워크 NIC 목록 + 통계 (esxcli → esxcfg-nics fallback)
    nics = []
    nic_list_lines = sections.get('NICLIST', [])
    nic_parsed_from_esxcli = False
    for line in nic_list_lines[2:]:  # skip header
        parts = line.split()
        if len(parts) >= 7:
            nic_parsed_from_esxcli = True
            nic_name = parts[0]
            link_status = parts[4] if len(parts) > 4 else 'Unknown'
            speed = parts[5] if len(parts) > 5 else '0'
            # NIC 인덱스에서 통계 가져오기
            m_idx = re.search(r'vmnic(\d+)', nic_name)
            stat_key = f"NICSTAT{m_idx.group(1)}" if m_idx else None
            bytes_rx = bytes_tx = pkts_rx = pkts_tx = 0
            if stat_key and stat_key in sections:
                for sline in sections[stat_key]:
                    if 'Bytes received' in sline:
                        m = re.search(r'(\d+)', sline.split(':')[-1])
                        if m: bytes_rx = int(m.group(1))
                    elif 'Bytes sent' in sline:
                        m = re.search(r'(\d+)', sline.split(':')[-1])
                        if m: bytes_tx = int(m.group(1))
                    elif 'Packets received' in sline and 'Multicast' not in sline and 'Broadcast' not in sline:
                        m = re.search(r'(\d+)', sline.split(':')[-1])
                        if m: pkts_rx = int(m.group(1))
                    elif 'Packets sent' in sline and 'Multicast' not in sline and 'Broadcast' not in sline:
                        m = re.search(r'(\d+)', sline.split(':')[-1])
                        if m: pkts_tx = int(m.group(1))
            nics.append({
                'name': nic_name, 'speed': speed, 'link': link_status,
                'bytes_rx': bytes_rx, 'bytes_tx': bytes_tx,
                'pkts_rx': pkts_rx, 'pkts_tx': pkts_tx,
            })

    # esxcli nic list 실패 시 esxcfg-nics fallback
    if not nic_parsed_from_esxcli:
        fb_nic_lines = sections.get('FB_NICLIST', [])
        for line in fb_nic_lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 7 and parts[0].startswith('vmnic'):
                nic_name = parts[0]
                link_status = parts[3] if len(parts) > 3 else 'Unknown'
                speed = parts[4].replace('Mbps', '') if len(parts) > 4 else '0'
                nics.append({
                    'name': nic_name, 'speed': speed, 'link': link_status,
                    'bytes_rx': 0, 'bytes_tx': 0, 'pkts_rx': 0, 'pkts_tx': 0,
                })

    info['nics'] = nics

    # Uptime / Load Average
    uptime_text = '\n'.join(sections.get('UPTIME', []))
    info['uptime_raw'] = uptime_text
    m_up = re.search(r'up\s+(.+?),\s+load', uptime_text)
    info['uptime'] = m_up.group(1).strip() if m_up else ''
    m_load = re.search(r'load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', uptime_text)
    info['load_avg'] = [float(m_load.group(i)) for i in (1,2,3)] if m_load else []

    # ──── VM 목록 + 상세정보를 for-loop SSH로 수집 ────
    # ESXi BusyBox 셸은 명령어 크기 제한이 있으므로 echo 배치 대신 for-loop 사용
    out, _, rc = _ssh_cmd(ip, user, pw, "vim-cmd vmsvc/getallvms 2>/dev/null", port)
    if rc == 0 and out:
        vm_ids = []
        vm_map = {}
        for line in out.split('\n')[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 4 and parts[0].isdigit():
                vmid = parts[0]
                name_end = line.find('[')
                vm_name = line[len(vmid):name_end].strip() if name_end > 0 else parts[1]
                guest_os = ''
                m = re.search(r'(centos|ubuntu|windows|debian|rhel|coreos|other)\S*', line, re.I)
                if m:
                    guest_os = m.group(0)
                vm_ids.append(vmid)
                vm_map[vmid] = {'vm_id': vmid, 'vm_name': vm_name, 'guest_os': guest_os,
                                'power_state': 'unknown', 'cpu_count': 0, 'memory_mb': 0, 'ip_address': ''}

        # For-loop으로 각 VM의 전원/CPU/메모리/IP를 한번의 SSH로 수집
        if vm_ids:
            vm_loop_cmd = (
                "for i in $(vim-cmd vmsvc/getallvms 2>/dev/null "
                "| awk 'NR>1 && $1~/^[0-9]+$/{print $1}'); do\n"
                "  echo \"@@VM:$i@@\"\n"
                "  vim-cmd vmsvc/power.getstate $i 2>/dev/null | tail -1\n"
                "  vim-cmd vmsvc/get.config $i 2>/dev/null | grep -E 'numCPU |memoryMB '\n"
                "  vim-cmd vmsvc/get.guest $i 2>/dev/null | grep -m1 'ipAddress = \"'\n"
                "done"
            )

            vout, _, _ = _ssh_cmd(ip, user, pw, vm_loop_cmd, port, timeout=max(len(vm_ids) * 5, 60))

            # 파싱: @@VM:ID@@ 순서로 전원/CPU/메모리/IP 출력
            current_vid = None
            current_lines = []
            for vline in vout.split('\n'):
                vm_marker = re.match(r'^@@VM:(\d+)@@$', vline)
                if vm_marker:
                    if current_vid and current_vid in vm_map:
                        _parse_vm_detail(vm_map[current_vid], current_lines)
                    current_vid = vm_marker.group(1)
                    current_lines = []
                else:
                    current_lines.append(vline)
            # 마지막 VM 처리
            if current_vid and current_vid in vm_map:
                _parse_vm_detail(vm_map[current_vid], current_lines)

            for vid in vm_ids:
                info['vms'].append(vm_map[vid])

    return info


def _parse_vm_detail(vm, lines):
    """VM for-loop 출력의 개별 파싱"""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if 'Powered on' in line:
            vm['power_state'] = 'on'
        elif 'Powered off' in line:
            vm['power_state'] = 'off'
        elif 'Suspended' in line:
            vm['power_state'] = 'suspended'
        m_cpu = re.search(r'numCPU\s*=\s*(\d+)', line)
        if m_cpu:
            vm['cpu_count'] = int(m_cpu.group(1))
        m_mem = re.search(r'memoryMB\s*=\s*(\d+)', line)
        if m_mem:
            vm['memory_mb'] = int(m_mem.group(1))
        m_ip = re.search(r'ipAddress\s*=\s*"(\d+\.\d+\.\d+\.\d+)"', line)
        if m_ip:
            vm['ip_address'] = m_ip.group(1)

def _collect_kvm_info(host):
    """SSH 로 KVM (libvirt) 호스트 정보 + VM 목록 수집 (SSH 2회로 최적화)"""
    ip, user, pw, port = host['ip_address'], host['ssh_user'], host['ssh_password'], host['ssh_port']
    info = {'status': 'online', 'esxi_version': '', 'cpu_model': '', 'cpu_cores': 0,
            'memory_gb': 0, 'storage_gb': 0, 'vms': []}

    # ──── SSH 1회: 호스트 정보 + VM 목록 전체 ────
    host_cmd = r"""
echo '@@SECTION:UNAME@@'; uname -r 2>/dev/null;
echo '@@SECTION:NPROC@@'; nproc --all 2>/dev/null;
echo '@@SECTION:CPUMODEL@@'; grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2;
echo '@@SECTION:MEMINFO@@'; grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}';
echo '@@SECTION:DISK@@'; df -BG 2>/dev/null | grep '^/dev';
echo '@@SECTION:FREE@@'; free -m 2>/dev/null;
echo '@@SECTION:NETDEV@@'; cat /proc/net/dev 2>/dev/null;
echo '@@SECTION:UPTIME@@'; uptime 2>/dev/null;
echo '@@SECTION:VIRSHLIST@@'; virsh list --all 2>/dev/null;
"""
    out, err, rc = _ssh_cmd(ip, user, pw, host_cmd, port, timeout=30)
    if rc != 0:
        return {'status': 'offline', 'error': err or 'ssh failed'}

    # 섹션 파싱
    sections = {}
    current = None
    for line in out.split('\n'):
        if line.startswith('@@SECTION:') and line.endswith('@@'):
            current = line[10:-2]
            sections[current] = []
        elif current:
            sections[current].append(line)

    uname = '\n'.join(sections.get('UNAME', [])).strip()
    if not uname:
        return {'status': 'offline', 'error': err or 'ssh failed'}
    info['esxi_version'] = f'Linux {uname}'

    # CPU
    nproc_text = '\n'.join(sections.get('NPROC', [])).strip()
    info['cpu_cores'] = int(nproc_text) if nproc_text.isdigit() else 0
    cpu_model_text = '\n'.join(sections.get('CPUMODEL', [])).strip()
    info['cpu_model'] = cpu_model_text

    # 메모리 총량
    meminfo_text = '\n'.join(sections.get('MEMINFO', [])).strip()
    if meminfo_text.isdigit():
        info['memory_gb'] = round(int(meminfo_text) / (1024 * 1024))

    # 디스크
    total_gb = 0
    disks = []
    for line in sections.get('DISK', []):
        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith('/dev'):
            try:
                size_g = int(parts[1].rstrip('G'))
                used_g = int(parts[2].rstrip('G'))
                avail_g = int(parts[3].rstrip('G'))
                pct = int(parts[4].rstrip('%'))
                mount = parts[5]
                total_gb += size_g
                disks.append({
                    'device': parts[0], 'mount': mount,
                    'size_gb': size_g, 'used_gb': used_g, 'free_gb': avail_g, 'used_pct': pct,
                })
            except:
                pass
    info['storage_gb'] = total_gb
    info['datastores'] = disks

    # 메모리 사용량
    for line in sections.get('FREE', []):
        if line.startswith('Mem:'):
            parts = line.split()
            if len(parts) >= 4:
                mem_total = int(parts[1])
                mem_used = int(parts[2])
                mem_avail = int(parts[6]) if len(parts) >= 7 else int(parts[3])
                info['memory_used_gb'] = round(mem_used / 1024, 1)
                info['memory_free_gb'] = round(mem_avail / 1024, 1)
                info['memory_used_pct'] = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0
    if 'memory_used_gb' not in info:
        info['memory_used_gb'] = 0
        info['memory_free_gb'] = 0
        info['memory_used_pct'] = 0

    # 네트워크
    nics = []
    net_lines = sections.get('NETDEV', [])
    for line in net_lines[2:]:  # skip header
        if ':' in line:
            iface, data = line.split(':', 1)
            iface = iface.strip()
            if iface in ('lo',):
                continue
            parts = data.split()
            if len(parts) >= 10:
                bytes_rx = int(parts[0])
                pkts_rx = int(parts[1])
                bytes_tx = int(parts[8])
                pkts_tx = int(parts[9])
                if bytes_rx > 0 or bytes_tx > 0:
                    nics.append({
                        'name': iface, 'speed': '', 'link': 'Up',
                        'bytes_rx': bytes_rx, 'bytes_tx': bytes_tx,
                        'pkts_rx': pkts_rx, 'pkts_tx': pkts_tx,
                    })
    info['nics'] = nics

    # Uptime / Load Average
    uptime_text = '\n'.join(sections.get('UPTIME', []))
    info['uptime_raw'] = uptime_text
    m_up = re.search(r'up\s+(.+?),\s+\d+ user', uptime_text)
    info['uptime'] = m_up.group(1).strip() if m_up else ''
    m_load = re.search(r'load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', uptime_text)
    info['load_avg'] = [float(m_load.group(i)) for i in (1,2,3)] if m_load else []

    # VM 목록
    vm_names = []
    virsh_lines = sections.get('VIRSHLIST', [])
    for line in virsh_lines[2:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            vm_name = parts[1] if parts[0] == '-' or parts[0].isdigit() else parts[0]
            state_str = ' '.join(parts[2:]) if len(parts) > 2 else ''
            power = 'unknown'
            if 'running' in state_str.lower(): power = 'on'
            elif 'shut' in state_str.lower(): power = 'off'
            elif 'paused' in state_str.lower(): power = 'suspended'
            vm_names.append((vm_name, power))

    # ──── SSH 2회: 모든 VM의 UUID/info/IP를 한번에 수집 ────
    if vm_names:
        vm_batch_cmd = ""
        for vname, _ in vm_names:
            vm_batch_cmd += f"echo '@@KVM:{vname}:UUID@@'; virsh domuuid {vname} 2>/dev/null;\n"
            vm_batch_cmd += f"echo '@@KVM:{vname}:INFO@@'; virsh dominfo {vname} 2>/dev/null;\n"

        # running VM 만 IP 조회
        for vname, pwr in vm_names:
            if pwr == 'on':
                vm_batch_cmd += f"echo '@@KVM:{vname}:IP@@'; virsh domifaddr {vname} 2>/dev/null | grep -oE '([0-9]+\\.)+[0-9]+' | head -1;\n"

        vout, _, _ = _ssh_cmd(ip, user, pw, vm_batch_cmd, port, timeout=60)

        # VM 섹션 파싱
        vsections = {}
        vcurrent_key = None
        for vline in vout.split('\n'):
            if vline.startswith('@@KVM:') and vline.endswith('@@'):
                vcurrent_key = vline[6:-2]
                vsections[vcurrent_key] = []
            elif vcurrent_key:
                vsections[vcurrent_key].append(vline)

        for vname, power in vm_names:
            uuid_text = '\n'.join(vsections.get(f'{vname}:UUID', [])).strip()
            info_text = '\n'.join(vsections.get(f'{vname}:INFO', []))
            ip_text = '\n'.join(vsections.get(f'{vname}:IP', [])).strip()

            cpu, mem = 0, 0
            m_cpu = re.search(r"CPU\(s\):\s*(\d+)", info_text)
            m_mem = re.search(r"Max memory:\s*(\d+)\s*KiB", info_text)
            if m_cpu: cpu = int(m_cpu.group(1))
            if m_mem: mem = round(int(m_mem.group(1)) / 1024)

            info['vms'].append({
                'vm_id': uuid_text, 'vm_name': vname, 'power_state': power,
                'guest_os': '', 'cpu_count': cpu, 'memory_mb': mem,
                'ip_address': ip_text,
            })

    return info


# ──────────────────────────────────────────────
#  동기화 (백그라운드 스레드) — 파일 기반 상태 공유 (멀티프로세스 호환)
# ──────────────────────────────────────────────
import tempfile, os

_SYNC_STATUS_FILE = '/tmp/titan_infra_sync_status.json'


def _read_sync_status():
    try:
        with open(_SYNC_STATUS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'running': False, 'progress': 0, 'total': 0, 'current': '', 'results': [], 'done': False}


def _write_sync_status(data):
    tmp = _SYNC_STATUS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, _SYNC_STATUS_FILE)


def _sync_host_thread(host_ids=None):
    """모든/지정 호스트의 실시간 정보를 수집하여 DB 업데이트"""
    from django.db import connections as conns

    try:
        cursor = conns['default'].cursor()
    except:
        from django.db import connection
        cursor = connection.cursor()

    if host_ids:
        cursor.execute("SELECT * FROM tbl_hypervisor WHERE id IN (%s) AND is_active=1" % ','.join(['%s']*len(host_ids)), host_ids)
    else:
        cursor.execute("SELECT * FROM tbl_hypervisor WHERE is_active=1 ORDER BY id")
    hosts = dictfetchall(cursor)

    _write_sync_status({'running': True, 'progress': 0, 'total': len(hosts), 'current': '', 'results': [], 'done': False})

    for i, host in enumerate(hosts):
        _write_sync_status({
            'running': True, 'progress': i, 'total': len(hosts),
            'current': host['name'], 'results': _read_sync_status().get('results', []), 'done': False
        })

        try:
            if host['host_type'] == 'esxi':
                info = _collect_esxi_info(host)
            else:
                info = _collect_kvm_info(host)
        except Exception as e:
            info = {'status': 'offline', 'error': str(e), 'vms': []}

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 호스트 정보 업데이트
        cursor.execute("""
            UPDATE tbl_hypervisor SET
                status=%s, esxi_version=%s, cpu_model=%s, cpu_cores=%s,
                memory_gb=%s, storage_gb=%s, vm_count=%s,
                last_check=%s, last_check_json=%s
            WHERE id=%s
        """, [
            info.get('status', 'unknown'),
            info.get('esxi_version', ''),
            info.get('cpu_model', ''),
            info.get('cpu_cores', 0),
            info.get('memory_gb', 0),
            info.get('storage_gb', 0),
            len(info.get('vms', [])),
            now,
            json.dumps(info, ensure_ascii=False),
            host['id'],
        ])

        # VM 동기화: 기존 VM 삭제 후 재삽입
        if info.get('status') == 'online':
            cursor.execute("DELETE FROM tbl_hypervisor_vm WHERE hypervisor_id=%s", [host['id']])
            for vm in info.get('vms', []):
                cursor.execute("""
                    INSERT INTO tbl_hypervisor_vm
                        (hypervisor_id, vm_name, vm_id, power_state, guest_os, cpu_count, memory_mb, ip_address, last_check)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, [
                    host['id'], vm['vm_name'], vm['vm_id'], vm['power_state'],
                    vm.get('guest_os', ''), vm.get('cpu_count', 0), vm.get('memory_mb', 0),
                    vm.get('ip_address', ''), now,
                ])

        _log(cursor, host['id'], None, 'sync', 'success' if info.get('status') == 'online' else 'fail',
             json.dumps(info, ensure_ascii=False)[:500])

        st = _read_sync_status()
        st['results'].append({'name': host['name'], 'status': info.get('status', 'unknown')})
        st['progress'] = i + 1
        _write_sync_status(st)

    _write_sync_status({
        'running': False, 'progress': len(hosts), 'total': len(hosts),
        'current': '', 'results': _read_sync_status().get('results', []), 'done': True
    })

    cursor.close()


# ──────────────────────────────────────────────
#  PAGE VIEWS
# ──────────────────────────────────────────────
@allow_admin
def infra_hosts(request):
    """하이퍼바이저 호스트 관리 페이지"""
    return render(request, 'admin/infra_hosts.html', {})


@allow_admin
def infra_vms(request):
    """VM 관리 페이지"""
    return render(request, 'admin/infra_vms.html', {})


# ──────────────────────────────────────────────
#  API: 호스트 목록
# ──────────────────────────────────────────────
@allow_admin
def api_read_hosts(request):
    """모든 하이퍼바이저 호스트 반환"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT h.*,
               (SELECT COUNT(*) FROM tbl_hypervisor_vm v WHERE v.hypervisor_id=h.id AND v.power_state='on') AS vms_on,
               (SELECT COUNT(*) FROM tbl_hypervisor_vm v WHERE v.hypervisor_id=h.id AND v.power_state='off') AS vms_off
        FROM tbl_hypervisor h
        ORDER BY h.name
    """)
    hosts = dictfetchall(cursor)
    for h in hosts:
        for k in ('last_check', 'created_at', 'updated_at'):
            if h.get(k):
                h[k] = h[k].strftime('%Y-%m-%d %H:%M:%S')
        # 비밀번호 마스킹
        h['ssh_password'] = '****'
    return JsonResponse({'result': 200, 'hosts': hosts})


# ──────────────────────────────────────────────
#  API: 호스트 상세 (VM 목록 포함)
# ──────────────────────────────────────────────
@allow_admin
def api_read_host_detail(request):
    """특정 호스트의 상세 + VM 목록"""
    host_id = request.GET.get('id')
    if not host_id:
        return JsonResponse({'result': 400, 'msg': 'id required'})

    cursor = connections['default'].cursor()
    host = _get_host(cursor, host_id)
    if not host:
        return JsonResponse({'result': 404, 'msg': 'not found'})

    for k in ('last_check', 'created_at', 'updated_at'):
        if host.get(k):
            host[k] = host[k].strftime('%Y-%m-%d %H:%M:%S')
    host['ssh_password'] = '****'

    cursor.execute("""
        SELECT * FROM tbl_hypervisor_vm WHERE hypervisor_id=%s ORDER BY vm_name
    """, [host_id])
    vms = dictfetchall(cursor)
    for v in vms:
        for k in ('last_check', 'created_at', 'updated_at'):
            if v.get(k):
                v[k] = v[k].strftime('%Y-%m-%d %H:%M:%S')
        if v.get('disk_gb'):
            v['disk_gb'] = float(v['disk_gb'])

    return JsonResponse({'result': 200, 'host': host, 'vms': vms})


# ──────────────────────────────────────────────
#  API: VM 목록 (전체)
# ──────────────────────────────────────────────
@allow_admin
def api_read_vms(request):
    """전체 VM 목록 (호스트명 포함)"""
    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT v.*, h.name as host_name, h.ip_address as host_ip, h.host_type
        FROM tbl_hypervisor_vm v
        JOIN tbl_hypervisor h ON v.hypervisor_id = h.id
        ORDER BY h.name, v.vm_name
    """)
    vms = dictfetchall(cursor)
    for v in vms:
        for k in ('last_check', 'created_at', 'updated_at'):
            if v.get(k):
                v[k] = v[k].strftime('%Y-%m-%d %H:%M:%S')
        if v.get('disk_gb'):
            v['disk_gb'] = float(v['disk_gb'])
    return JsonResponse({'result': 200, 'vms': vms})


# ──────────────────────────────────────────────
#  API: 동기화 시작/상태
# ──────────────────────────────────────────────
@allow_admin
def api_sync_hosts(request):
    """호스트 정보 동기화 시작"""
    st = _read_sync_status()
    if st.get('running'):
        return JsonResponse({'result': 409, 'msg': '이미 동기화 진행 중'})

    host_ids = request.GET.getlist('ids[]')
    host_ids = [int(x) for x in host_ids] if host_ids else None

    t = threading.Thread(target=_sync_host_thread, args=(host_ids,), daemon=True)
    t.start()
    return JsonResponse({'result': 200, 'msg': '동기화 시작'})


@allow_admin
def api_sync_status(request):
    """동기화 진행 상태"""
    st = _read_sync_status()
    return JsonResponse({'result': 200, **st})


# ──────────────────────────────────────────────
#  API: VM 전원 제어
# ──────────────────────────────────────────────
@allow_admin
def api_vm_power(request):
    """VM 전원 on/off/reboot/suspend"""
    if request.method != 'POST':
        return JsonResponse({'result': 405, 'msg': 'POST only'})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'result': 400, 'msg': 'invalid json'})

    vm_db_id = data.get('vm_id')
    action = data.get('action')  # poweron, poweroff, reboot, suspend
    if not vm_db_id or action not in ('poweron', 'poweroff', 'reboot', 'suspend', 'reset'):
        return JsonResponse({'result': 400, 'msg': 'vm_id and valid action required'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        SELECT v.*, h.ip_address as host_ip_addr, h.ssh_user as h_user, h.ssh_password as h_pass, h.ssh_port as h_port, h.host_type
        FROM tbl_hypervisor_vm v
        JOIN tbl_hypervisor h ON v.hypervisor_id = h.id
        WHERE v.id = %s
    """, [vm_db_id])
    rows = dictfetchall(cursor)
    if not rows:
        return JsonResponse({'result': 404, 'msg': 'VM not found'})

    vm = rows[0]
    ip = vm['host_ip_addr']
    user = vm['h_user']
    pw = vm['h_pass']
    port = vm['h_port']

    if vm['host_type'] == 'esxi':
        # reboot/reset: VM이 꺼져있으면 자동으로 power.on 전환
        vid = vm['vm_id']
        if action in ('reboot', 'reset'):
            chk_out, _, chk_rc = _ssh_cmd(ip, user, pw,
                f"vim-cmd vmsvc/power.getstate {vid}", port, timeout=10)
            if chk_rc == 0 and 'off' in chk_out.lower():
                action = 'poweron'  # 꺼진 VM → 켜기로 전환

        cmd_map = {
            'poweron': f"vim-cmd vmsvc/power.on {vid}",
            'poweroff': f"vim-cmd vmsvc/power.off {vid}",
            'reboot': f"vim-cmd vmsvc/power.reboot {vid}",
            'suspend': f"vim-cmd vmsvc/power.suspend {vid}",
            'reset': f"vim-cmd vmsvc/power.reset {vid}",
        }
    else:  # KVM
        cmd_map = {
            'poweron': f"virsh start {vm['vm_name']}",
            'poweroff': f"virsh shutdown {vm['vm_name']}",
            'reboot': f"virsh reboot {vm['vm_name']}",
            'suspend': f"virsh suspend {vm['vm_name']}",
            'reset': f"virsh reset {vm['vm_name']}",
        }

    out, err, rc = _ssh_cmd(ip, user, pw, cmd_map[action], port, timeout=30)
    success = rc == 0

    # 성공 시 DB power_state 즉시 갱신 (다음 showDetail에서 정확한 버튼 표시)
    if success:
        state_map = {'poweron': 'on', 'poweroff': 'off', 'reboot': 'on', 'reset': 'on', 'suspend': 'suspended'}
        new_state = state_map.get(action)
        if new_state:
            cursor.execute("UPDATE tbl_hypervisor_vm SET power_state=%s WHERE id=%s", [new_state, vm_db_id])

    _log(cursor, vm['hypervisor_id'], vm_db_id, action,
         'success' if success else 'fail',
         json.dumps({'stdout': out, 'stderr': err, 'rc': rc}, ensure_ascii=False)[:500])

    return JsonResponse({
        'result': 200 if success else 500,
        'msg': out if success else (err or 'command failed'),
        'action': action,
    })


# ──────────────────────────────────────────────
#  API: 호스트 추가/수정/삭제
# ──────────────────────────────────────────────
@allow_admin
def api_create_host(request):
    """호스트 추가"""
    if request.method != 'POST':
        return JsonResponse({'result': 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'result': 400, 'msg': 'invalid json'})

    required = ['name', 'ip_address', 'ssh_user', 'ssh_password']
    for f in required:
        if not data.get(f):
            return JsonResponse({'result': 400, 'msg': f'{f} required'})

    cursor = connections['default'].cursor()
    cursor.execute("""
        INSERT INTO tbl_hypervisor (name, host_type, ip_address, ssh_user, ssh_password, ssh_port, location, isp, memo)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, [
        data['name'], data.get('host_type', 'esxi'), data['ip_address'],
        data['ssh_user'], data['ssh_password'], data.get('ssh_port', 22),
        data.get('location', ''), data.get('isp', ''), data.get('memo', ''),
    ])
    return JsonResponse({'result': 200, 'id': cursor.lastrowid})


@allow_admin
def api_update_host(request):
    """호스트 정보 수정"""
    if request.method != 'POST':
        return JsonResponse({'result': 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'result': 400, 'msg': 'invalid json'})

    host_id = data.get('id')
    if not host_id:
        return JsonResponse({'result': 400, 'msg': 'id required'})

    fields = []
    values = []
    for col in ('name', 'host_type', 'ip_address', 'ssh_user', 'ssh_password', 'ssh_port', 'location', 'isp', 'memo', 'is_active'):
        if col in data:
            fields.append(f"{col}=%s")
            values.append(data[col])

    if not fields:
        return JsonResponse({'result': 400, 'msg': 'no fields to update'})

    values.append(host_id)
    cursor = connections['default'].cursor()
    cursor.execute(f"UPDATE tbl_hypervisor SET {','.join(fields)} WHERE id=%s", values)
    return JsonResponse({'result': 200})


@allow_admin
def api_delete_host(request):
    """호스트 삭제"""
    if request.method != 'POST':
        return JsonResponse({'result': 405})
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'result': 400, 'msg': 'invalid json'})

    host_id = data.get('id')
    if not host_id:
        return JsonResponse({'result': 400, 'msg': 'id required'})

    cursor = connections['default'].cursor()
    cursor.execute("DELETE FROM tbl_hypervisor WHERE id=%s", [host_id])
    return JsonResponse({'result': 200})


# ──────────────────────────────────────────────
#  API: 호스트 연결 테스트
# ──────────────────────────────────────────────
@allow_admin
def api_test_host(request):
    """호스트에 SSH 연결 테스트"""
    host_id = request.GET.get('id')
    if not host_id:
        return JsonResponse({'result': 400, 'msg': 'id required'})

    cursor = connections['default'].cursor()
    host = _get_host(cursor, host_id)
    if not host:
        return JsonResponse({'result': 404, 'msg': 'not found'})

    out, err, rc = _ssh_cmd(host['ip_address'], host['ssh_user'], host['ssh_password'],
                            'hostname; uname -a', host['ssh_port'])

    _log(cursor, host['id'], None, 'test', 'success' if rc == 0 else 'fail',
         json.dumps({'stdout': out, 'stderr': err, 'rc': rc}, ensure_ascii=False)[:500])

    return JsonResponse({
        'result': 200 if rc == 0 else 500,
        'output': out,
        'error': err,
    })


# ──────────────────────────────────────────────
#  API: 로그 조회
# ──────────────────────────────────────────────
@allow_admin
def api_read_logs(request):
    """관리 로그 조회"""
    host_id = request.GET.get('host_id')
    limit = int(request.GET.get('limit', 50))

    cursor = connections['default'].cursor()
    if host_id:
        cursor.execute("""
            SELECT l.*, h.name as host_name
            FROM tbl_hypervisor_log l
            LEFT JOIN tbl_hypervisor h ON l.hypervisor_id = h.id
            WHERE l.hypervisor_id=%s
            ORDER BY l.created_at DESC LIMIT %s
        """, [host_id, limit])
    else:
        cursor.execute("""
            SELECT l.*, h.name as host_name
            FROM tbl_hypervisor_log l
            LEFT JOIN tbl_hypervisor h ON l.hypervisor_id = h.id
            ORDER BY l.created_at DESC LIMIT %s
        """, [limit])

    logs = dictfetchall(cursor)
    for lg in logs:
        if lg.get('created_at'):
            lg['created_at'] = lg['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return JsonResponse({'result': 200, 'logs': logs})

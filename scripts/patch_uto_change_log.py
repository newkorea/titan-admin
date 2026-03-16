#!/usr/bin/env python3
"""
Patch all UTO PHP admin/sales files to add change logging.
Targets:
  1. /var/www/html/users.bosshappyniceokbrovofortune/ (admin + sales + inc)
  2. /var/www/html/users/admin5fonly/vpnuser/
  3. /var/www/html/users.bosshappyniceokbrovofortune/sales/proxy/chpass.php
"""
import subprocess
import sys
import os
import datetime

SSH_CMD = "ssh -o ConnectTimeout=10 root@218.158.57.55 -p 2202"

def ssh_run(cmd, check=True):
    """Run command via SSH, return stdout"""
    full = f"{SSH_CMD} {cmd}"
    r = subprocess.run(full, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"  WARN: {cmd[:80]}... rc={r.returncode}")
        if r.stderr:
            print(f"  stderr: {r.stderr[:200]}")
    return r.stdout.strip()

def ssh_read_file(path):
    """Read a file from remote server"""
    return ssh_run(f"'cat {path}'", check=False)

def ssh_write_file(path, content):
    """Write content to a file on remote server using base64 to avoid quoting issues"""
    import base64
    b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    # Write in chunks if too large
    if len(b64) > 50000:
        # write to temp file locally, scp it
        tmp = '/tmp/_uto_patch_tmp.php'
        with open(tmp, 'w') as f:
            f.write(content)
        r = subprocess.run(
            f"scp -P 2202 {tmp} root@218.158.57.55:{path}",
            shell=True, capture_output=True, text=True
        )
        os.remove(tmp)
        return r.returncode == 0
    else:
        r = subprocess.run(
            f"{SSH_CMD} 'echo {b64} | base64 -d > {path}'",
            shell=True, capture_output=True, text=True
        )
        return r.returncode == 0

def backup_dir(dirpath):
    """Create backup of directory"""
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{dirpath}/backup_{ts}"
    ssh_run(f"'mkdir -p {backup} && cp {dirpath}/*.php {backup}/ 2>/dev/null; echo ok'", check=False)
    print(f"  Backup: {backup}")
    return backup


# ============================================================
# change_log.php helper (uses db_mysql $db->query style)
# ============================================================
CHANGE_LOG_PHP = r'''<?php
/**
 * UTO 변경내역 로깅 헬퍼
 * uto_change_log 테이블에 변경 기록을 INSERT
 */

function log_uto_change($db, $vuser, $change_type, $field_name, $old_value, $new_value, $description, $admin_user, $source) {
    $table = 'vcsvpn2013.uto_change_log';
    
    $vuser = mysql_real_escape_string($vuser);
    $change_type = mysql_real_escape_string($change_type);
    $field_name = mysql_real_escape_string($field_name);
    $old_val = ($old_value === null || $old_value === '') ? 'NULL' : "'" . mysql_real_escape_string($old_value) . "'";
    $new_val = ($new_value === null || $new_value === '') ? 'NULL' : "'" . mysql_real_escape_string($new_value) . "'";
    $description = mysql_real_escape_string($description);
    $admin_user = mysql_real_escape_string($admin_user);
    $source = mysql_real_escape_string($source);
    
    $sql = "INSERT INTO {$table} (vuser, change_type, field_name, old_value, new_value, description, admin_user, source)
            VALUES ('{$vuser}', '{$change_type}', '{$field_name}', {$old_val}, {$new_val}, '{$description}', '{$admin_user}', '{$source}')";
    
    @$db->query($sql);
}

/**
 * vpnuser 단일 필드 조회
 */
function get_vpnuser_field($db, $id, $field) {
    $id = intval($id);
    $row = $db->getOneRow("SELECT * FROM vpnuser WHERE id={$id}");
    if ($row && isset($row[$field])) return $row[$field];
    return '';
}

/**
 * vpnuser 복수 필드 조회 (배열 반환)
 */
function get_vpnuser_fields($db, $id, $fields) {
    $id = intval($id);
    $row = $db->getOneRow("SELECT * FROM vpnuser WHERE id={$id}");
    $result = array();
    if ($row) {
        foreach ($fields as $f) {
            $result[$f] = isset($row[$f]) ? $row[$f] : '';
        }
    }
    return $result;
}
?>'''

# ============================================================
# Patching functions
# ============================================================

def patch_simple_ch(content, field_name, var_name, description, db_var='$db'):
    """Patch a simple ch*.php file that changes one field"""
    # Add change_log.php include after conn.php
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    # Add old value fetch and logging
    # Find the $arr=array(...) line and the update line
    # Insert before $arr: fetch old values
    # Insert after last update: log change
    
    lines = content.split('\n')
    new_lines = []
    arr_found = False
    update_count = 0
    total_updates = content.count('->update(vpnuser,')
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Insert old value fetch before $arr=array(...)
        if '$arr=array(' in stripped and not arr_found:
            arr_found = True
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}$_old = get_vpnuser_fields($db, $aid, array('vuser','{field_name}'));")
            new_lines.append(line)
            continue
        
        # After the last db->update(vpnuser,...), insert logging
        if '->update(vpnuser,' in stripped:
            update_count += 1
            new_lines.append(line)
            if update_count >= total_updates:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change({db_var}, $_old['vuser'], 'edit', '{field_name}', $_old['{field_name}'], {var_name}, '{description}', @$_SESSION['username'], 'admin-php');")
            continue
        
        new_lines.append(line)
    
    return '\n'.join(new_lines)


def patch_chdk(content):
    """Patch chdk.php - two fields (updk, downdk)"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    lines = content.split('\n')
    new_lines = []
    arr_found = False
    update_count = 0
    total_updates = content.count('->update(vpnuser,')
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if '$arr=array(' in stripped and not arr_found:
            arr_found = True
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}$_old = get_vpnuser_fields($db, $aid, array('vuser','updk','downdk'));")
            new_lines.append(line)
            continue
        
        if '->update(vpnuser,' in stripped:
            update_count += 1
            new_lines.append(line)
            if update_count >= total_updates:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change($db, $_old['vuser'], 'edit', 'updk', $_old['updk'], $updk, '대역(up) 변경', @$_SESSION['username'], 'admin-php');")
                new_lines.append(f"{indent}log_uto_change($db, $_old['vuser'], 'edit', 'downdk', $_old['downdk'], $downdk, '대역(down) 변경', @$_SESSION['username'], 'admin-php');")
            continue
        
        new_lines.append(line)
    
    return '\n'.join(new_lines)


def patch_chip(content):
    """Patch chip.php - oneip with ipool updates"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    # chip.php already fetches $one = $db->getonerow(...) so we have old value
    # Add logging after the last vpnuser update
    lines = content.split('\n')
    new_lines = []
    vpn_update_count = 0
    total_vpn_updates = sum(1 for l in lines if '->update(vpnuser,' in l)
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        new_lines.append(line)
        
        if '->update(vpnuser,' in stripped:
            vpn_update_count += 1
            if vpn_update_count >= total_vpn_updates:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change($db, $one['vuser'], 'edit', 'oneip', $one['oneip'], $ip, 'IP 변경', @$_SESSION['username'], 'admin-php');")
    
    return '\n'.join(new_lines)


def patch_chlx(content):
    """Patch chlx.php - multiple update types (CS, JS, BY, LL, ONEIP)"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    # Already has: $oldcus = $db->getonerow(...) and $oldlastdate = $oldcus[lastdate]
    # We need to add logging after each type's update
    
    lines = content.split('\n')
    new_lines = []
    current_type = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Track current type block
        if "if ($lx=='CS')" in stripped:
            current_type = 'CS'
        elif "if ($lx=='JS')" in stripped:
            current_type = 'JS'
        elif "if ($lx=='BY')" in stripped:
            current_type = 'BY'
        elif "if ($lx=='LL')" in stripped:
            current_type = 'LL'
        elif "if ($lx=='ONEIP')" in stripped:
            current_type = 'ONEIP'
        
        new_lines.append(line)
        
        # After echo success message or after the last update in each block
        if current_type and '->update(vpnuser,' in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            # Check if next non-empty line is $newdb->update — if so, skip
            next_stripped = ''
            for j in range(i+1, min(i+3, len(lines))):
                ns = lines[j].strip()
                if ns:
                    next_stripped = ns
                    break
            
            if '->update(vpnuser,' not in next_stripped:
                # This is the last update in the block — add logging
                admin = "@$_SESSION['username'] ? @$_SESSION['username'] : @$_SESSION['salesuser']"
                if current_type == 'CS':
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'edit', 'groups', $oldcus['groups'], 'CS', '유형→CS(시간제)', {admin}, 'admin-php');")
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'edit', 'cash', $oldcus['cash'], $cash*3600, '시간 변경', {admin}, 'admin-php');")
                elif current_type == 'JS':
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'edit', 'groups', $oldcus['groups'], 'JS', '유형→JS(계시)', {admin}, 'admin-php');")
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'edit', 'cash', $oldcus['cash'], $cash*3600, '시간 변경', {admin}, 'admin-php');")
                elif current_type == 'BY':
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'extend', 'lastdate', $oldlastdate, $lastdate, '만료일 연장(BY)', {admin}, 'admin-php');")
                elif current_type == 'LL':
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'edit', 'flow', $oldcus['flow'], $flow, '데이터유량 변경(LL)', {admin}, 'admin-php');")
                elif current_type == 'ONEIP':
                    new_lines.append(f"{indent}log_uto_change($db, $oldcus['vuser'], 'extend', 'lastdate', $oldlastdate, $lastdate, '만료일 연장(ONEIP)', {admin}, 'admin-php');")
                current_type = None  # Reset after logging
    
    return '\n'.join(new_lines)


def patch_vpn_ok(content):
    """Patch vpn_ok.php - add and delete operations"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    lines = content.split('\n')
    new_lines = []
    in_del = False
    in_add = False
    del_logged = False
    add_logged = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if "if ($act=='del')" in stripped:
            in_del = True
            in_add = False
        elif "if ($act=='add')" in stripped:
            in_add = True
            in_del = False
        
        new_lines.append(line)
        
        # After delete operations - log after $db->delete(vpnuser,...)
        if in_del and not del_logged and '$db->delete(vpnuser,' in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}log_uto_change($db, $usa['vuser'], 'delete', 'vpnuser', $usa['vuser'], '', '회원 삭제', @$_SESSION['username'], 'admin-php');")
            del_logged = True
        
        # After add insert operations
        if in_add and not add_logged and '$db->insert(vpnuser,' in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}log_uto_change($db, $us, 'create', 'vpnuser', '', $us, '회원 등록 (유형:'.$lx.')', @$_SESSION['username'], 'admin-php');")
            add_logged = True
    
    return '\n'.join(new_lines)


def patch_sales_addok(content):
    """Patch sales addok.php - new registration (JS, BY, LL, ONEIP types)"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        new_lines.append(line)
        
        # After each $db->insert(get_sql("{pre}vpnuser") or $db->insert(vpnuser,...)
        if ("->insert(get_sql(\"{pre}vpnuser\")" in stripped or 
            ("->insert(vpnuser," in stripped and '$db->' in stripped)):
            # Only for the first $db->insert in each block (not $db2, $db3)
            if '$db->' in stripped and '$db2' not in stripped and '$db3' not in stripped:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change($db, $us, 'create', 'vpnuser', '', $us, '신규등록(대리점) 유형:'.$sp['sklx'], @$_SESSION['salesuser'], 'sales-php');")
    
    return '\n'.join(new_lines)


def patch_sales_x_addok(content):
    """Patch sales x_addok.php - extension"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        new_lines.append(line)
        
        # After $db->update(vpnuser,...) - log extension
        if '$db->update(vpnuser,' in stripped:
            # Check next lines to skip if $newdb follows
            next_stripped = ''
            for j in range(i+1, min(i+3, len(lines))):
                ns = lines[j].strip()
                if ns:
                    next_stripped = ns
                    break
            
            if '->update(vpnuser,' not in next_stripped:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change($db, $us, 'extend', 'lastdate', @$oldlastdate, @$lastdate, '연장(대리점) 유형:'.$sp['sklx'], @$_SESSION['salesuser'], 'sales-php');")
    
    return '\n'.join(new_lines)


def patch_sales_proxy_chpass(content):
    """Patch sales/proxy/chpass.php"""
    content = content.replace(
        "require_once '../../inc/conn.php';",
        "require_once '../../inc/conn.php';\nrequire_once '../../inc/change_log.php';"
    )
    
    lines = content.split('\n')
    new_lines = []
    total_updates = sum(1 for l in lines if '->update(vpnuser,' in l)
    update_count = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Insert old value fetch before $arr=array(...)
        if '$arr=array(' in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}$_old = get_vpnuser_fields($db, $aid, array('vuser','vpass'));")
        
        new_lines.append(line)
        
        if '->update(vpnuser,' in stripped:
            update_count += 1
            if update_count >= total_updates:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}log_uto_change($db, $_old['vuser'], 'edit', 'vpass', '***', '***', '비밀번호 변경(대리점)', @$_SESSION['salesuser'], 'sales-php');")
    
    return '\n'.join(new_lines)


# ============================================================
# Main
# ============================================================

SIMPLE_FILES = {
    # filename: (field_name, var_name, description)
    'chpass.php':     ('vpass', '$pass', '비밀번호 변경'),
    'chkz.php':       ('kz', '$kz', '계정상태 변경'),
    'chmemo.php':     ('hmemo', '$memo', '메모 변경'),
    'chhy.php':       ('hyid', '$hy', '회원등급 변경'),
    'chtel.php':      ('hqq', '$tel', '전화번호 변경'),
    'chmail.php':     ('hmail', '$mail', '이메일 변경'),
    'chaddr.php':     ('haddr', '$addr', '주소 변경'),
    'chgm.php':       ('game', '$gm', '게임 변경'),
    'chforcedip.php': ('forcedip', '$forcedip', 'forcedip 변경'),
    'chport.php':     ('port', '$port', '포트 변경'),
    'chss_flow.php':  ('transfer_enable', '$ss_flow', 'APP데이터용량 변경'),
}


def process_site(base_dir, site_name):
    """Process one site's admin/vpnuser and sales directories"""
    admin_vpnuser = f"{base_dir}/admin/vpnuser"
    sales_user = f"{base_dir}/sales/user"
    sales_proxy = f"{base_dir}/sales/proxy"
    inc_dir = f"{base_dir}/inc"
    
    print(f"\n{'='*60}")
    print(f"Processing site: {site_name}")
    print(f"Base: {base_dir}")
    print(f"{'='*60}")
    
    # 1. Deploy change_log.php
    print(f"\n[1] Deploying change_log.php to {inc_dir}/")
    if ssh_write_file(f"{inc_dir}/change_log.php", CHANGE_LOG_PHP):
        print("  OK: change_log.php deployed")
    else:
        print("  ERROR: Failed to deploy change_log.php")
        return False
    
    # 2. Backup admin/vpnuser
    print(f"\n[2] Backing up {admin_vpnuser}/")
    backup_dir(admin_vpnuser)
    
    # 3. Patch simple ch* files
    print(f"\n[3] Patching simple admin/vpnuser files...")
    for filename, (field, var, desc) in SIMPLE_FILES.items():
        filepath = f"{admin_vpnuser}/{filename}"
        content = ssh_read_file(filepath)
        if not content:
            print(f"  SKIP: {filename} (not found or empty)")
            continue
        if 'change_log' in content:
            print(f"  SKIP: {filename} (already patched)")
            continue
        
        patched = patch_simple_ch(content, field, var, desc)
        if ssh_write_file(filepath, patched):
            print(f"  OK: {filename} ({field})")
        else:
            print(f"  ERROR: {filename}")
    
    # 4. Patch chdk.php (two fields)
    print(f"\n[4] Patching chdk.php...")
    content = ssh_read_file(f"{admin_vpnuser}/chdk.php")
    if content and 'change_log' not in content:
        patched = patch_chdk(content)
        if ssh_write_file(f"{admin_vpnuser}/chdk.php", patched):
            print("  OK: chdk.php (updk+downdk)")
        else:
            print("  ERROR: chdk.php")
    else:
        print("  SKIP: chdk.php")
    
    # 5. Patch chip.php
    print(f"\n[5] Patching chip.php...")
    content = ssh_read_file(f"{admin_vpnuser}/chip.php")
    if content and 'change_log' not in content:
        patched = patch_chip(content)
        if ssh_write_file(f"{admin_vpnuser}/chip.php", patched):
            print("  OK: chip.php (oneip)")
        else:
            print("  ERROR: chip.php")
    else:
        print("  SKIP: chip.php")
    
    # 6. Patch chlx.php
    print(f"\n[6] Patching chlx.php...")
    content = ssh_read_file(f"{admin_vpnuser}/chlx.php")
    if content and 'change_log' not in content:
        patched = patch_chlx(content)
        if ssh_write_file(f"{admin_vpnuser}/chlx.php", patched):
            print("  OK: chlx.php (type changes)")
        else:
            print("  ERROR: chlx.php")
    else:
        print("  SKIP: chlx.php")
    
    # 7. Patch vpn_ok.php
    print(f"\n[7] Patching vpn_ok.php...")
    content = ssh_read_file(f"{admin_vpnuser}/vpn_ok.php")
    if content and 'change_log' not in content:
        patched = patch_vpn_ok(content)
        if ssh_write_file(f"{admin_vpnuser}/vpn_ok.php", patched):
            print("  OK: vpn_ok.php (add/delete)")
        else:
            print("  ERROR: vpn_ok.php")
    else:
        print("  SKIP: vpn_ok.php")
    
    # 8. Patch sales files
    # Check if sales directory exists
    sales_exists = ssh_run(f"'test -d {sales_user} && echo yes || echo no'", check=False)
    if 'yes' in sales_exists:
        print(f"\n[8] Backing up and patching sales/user/...")
        backup_dir(sales_user)
        
        # addok.php
        content = ssh_read_file(f"{sales_user}/addok.php")
        if content and 'change_log' not in content:
            patched = patch_sales_addok(content)
            if ssh_write_file(f"{sales_user}/addok.php", patched):
                print("  OK: sales/user/addok.php (registration)")
            else:
                print("  ERROR: sales/user/addok.php")
        else:
            print("  SKIP: sales/user/addok.php")
        
        # x_addok.php
        content = ssh_read_file(f"{sales_user}/x_addok.php")
        if content and 'change_log' not in content:
            patched = patch_sales_x_addok(content)
            if ssh_write_file(f"{sales_user}/x_addok.php", patched):
                print("  OK: sales/user/x_addok.php (extension)")
            else:
                print("  ERROR: sales/user/x_addok.php")
        else:
            print("  SKIP: sales/user/x_addok.php")
    else:
        print(f"\n[8] SKIP: {sales_user} not found")
    
    # 9. Patch sales/proxy/chpass.php
    proxy_exists = ssh_run(f"'test -f {sales_proxy}/chpass.php && echo yes || echo no'", check=False)
    if 'yes' in proxy_exists:
        print(f"\n[9] Patching sales/proxy/chpass.php...")
        content = ssh_read_file(f"{sales_proxy}/chpass.php")
        if content and 'change_log' not in content:
            patched = patch_sales_proxy_chpass(content)
            if ssh_write_file(f"{sales_proxy}/chpass.php", patched):
                print("  OK: sales/proxy/chpass.php")
            else:
                print("  ERROR: sales/proxy/chpass.php")
        else:
            print("  SKIP: sales/proxy/chpass.php")
    else:
        print(f"\n[9] SKIP: {sales_proxy}/chpass.php not found")
    
    return True


def main():
    print("UTO PHP Change Log Patcher")
    print("=" * 60)
    
    # Site 1: bosshappyniceokbrovofortune (main active site)
    process_site(
        "/var/www/html/users.bosshappyniceokbrovofortune",
        "bosshappy (main admin)"
    )
    
    # Site 2: admin5fonly (uses /var/www/html/users/inc/)
    # admin5fonly's ../../inc/ resolves to /var/www/html/users/inc/ which already has change_log.php
    print(f"\n{'='*60}")
    print("Processing site: admin5fonly")
    print(f"{'='*60}")
    
    admin5f_vpnuser = "/var/www/html/users/admin5fonly/vpnuser"
    print(f"\n[1] change_log.php already in /var/www/html/users/inc/ (shared)")
    
    print(f"\n[2] Backing up {admin5f_vpnuser}/")
    backup_dir(admin5f_vpnuser)
    
    # Patch simple ch* files for admin5fonly
    print(f"\n[3] Patching simple admin5fonly/vpnuser files...")
    for filename, (field, var, desc) in SIMPLE_FILES.items():
        filepath = f"{admin5f_vpnuser}/{filename}"
        content = ssh_read_file(filepath)
        if not content:
            print(f"  SKIP: {filename} (not found)")
            continue
        if 'change_log' in content:
            print(f"  SKIP: {filename} (already patched)")
            continue
        patched = patch_simple_ch(content, field, var, desc)
        if ssh_write_file(filepath, patched):
            print(f"  OK: {filename}")
        else:
            print(f"  ERROR: {filename}")
    
    # chdk
    content = ssh_read_file(f"{admin5f_vpnuser}/chdk.php")
    if content and 'change_log' not in content:
        if ssh_write_file(f"{admin5f_vpnuser}/chdk.php", patch_chdk(content)):
            print("  OK: chdk.php")
    
    # chip
    content = ssh_read_file(f"{admin5f_vpnuser}/chip.php")
    if content and 'change_log' not in content:
        if ssh_write_file(f"{admin5f_vpnuser}/chip.php", patch_chip(content)):
            print("  OK: chip.php")
    
    # chlx
    content = ssh_read_file(f"{admin5f_vpnuser}/chlx.php")
    if content and 'change_log' not in content:
        if ssh_write_file(f"{admin5f_vpnuser}/chlx.php", patch_chlx(content)):
            print("  OK: chlx.php")
    
    # vpn_ok
    content = ssh_read_file(f"{admin5f_vpnuser}/vpn_ok.php")
    if content and 'change_log' not in content:
        if ssh_write_file(f"{admin5f_vpnuser}/vpn_ok.php", patch_vpn_ok(content)):
            print("  OK: vpn_ok.php")
    
    # cyberdaewoongsalespart (same structure as sales)
    for sales_dir_name in ['sales', 'cyberdaewoongsalespart']:
        sales_base = f"/var/www/html/users/{sales_dir_name}"
        sales_user = f"{sales_base}/user"
        sales_proxy = f"{sales_base}/proxy"
        
        exists = ssh_run(f"'test -d {sales_user} && echo yes || echo no'", check=False)
        if 'yes' not in exists:
            continue
        
        print(f"\n  Checking {sales_dir_name}/user/...")
        
        content = ssh_read_file(f"{sales_user}/addok.php")
        if content and 'change_log' not in content:
            backup_dir(sales_user)
            patched = patch_sales_addok(content)
            if ssh_write_file(f"{sales_user}/addok.php", patched):
                print(f"  OK: {sales_dir_name}/user/addok.php")
        
        content = ssh_read_file(f"{sales_user}/x_addok.php")
        if content and 'change_log' not in content:
            patched = patch_sales_x_addok(content)
            if ssh_write_file(f"{sales_user}/x_addok.php", patched):
                print(f"  OK: {sales_dir_name}/user/x_addok.php")
        
        content = ssh_read_file(f"{sales_proxy}/chpass.php")
        if content and 'change_log' not in content:
            patched = patch_sales_proxy_chpass(content)
            if ssh_write_file(f"{sales_proxy}/chpass.php", patched):
                print(f"  OK: {sales_dir_name}/proxy/chpass.php")
    
    print(f"\n{'='*60}")
    print("DONE. All sites patched.")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

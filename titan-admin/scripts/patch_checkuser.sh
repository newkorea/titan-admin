#!/bin/bash
# patch_checkuser.sh — checkuser.py에 acctsessiontime 패치 적용
# 원격 서버에서 실행됨

FILE=/etc/strongswan/checkuser.py

if [ ! -f "$FILE" ]; then
    echo "NOFILE"
    exit 0
fi

# 이미 패치되었는지 확인
if grep -q 'TIMESTAMPDIFF' "$FILE" 2>/dev/null; then
    echo "ALREADY_PATCHED"
    exit 0
fi

# 백업
cp "$FILE" "${FILE}.bak.$(date +%Y%m%d%H%M%S)"

# 1) UPDATE radacct SET acctstoptime = %s WHERE radacctid = %s
#    → acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, %s) 추가
sed -i 's|UPDATE radacct SET acctstoptime = %s WHERE radacctid = %s|UPDATE radacct SET acctstoptime = %s, acctsessiontime = TIMESTAMPDIFF(SECOND, acctstarttime, %s) WHERE radacctid = %s|g' "$FILE"

# 2) V2RAY ghost cleanup: update_needed.append((now, s['radacctid']))
sed -i "s|update_needed\.append((now, s\['radacctid'\]))|update_needed.append((now, now, s['radacctid']))|g" "$FILE"

# 3) OpenVPN ghost cleanup 리스트 컴프리헨션
sed -i "s|\[(now, s\['radacctid'\]) for s in db_null_sessions if s\['username'\] not in openvpn_users\]|[(now, now, s['radacctid']) for s in db_null_sessions if s['username'] not in openvpn_users]|g" "$FILE"

# 4) IKEv2 ghost cleanup 리스트 컴프리헨션
sed -i "s|\[(now, session\['radacctid'\]) for session in db_null_sessions if session\['username'\] not in active_users\]|[(now, now, session['radacctid']) for session in db_null_sessions if session['username'] not in active_users]|g" "$FILE"

# 5) close_old_sessions
sed -i "s|close_old_sessions\.append((now, session\['radacctid'\]))|close_old_sessions.append((now, now, session['radacctid']))|g" "$FILE"

# 검증
TIMESTAMPDIFF_COUNT=$(grep -c 'TIMESTAMPDIFF' "$FILE" 2>/dev/null)
TRIPLE_TUPLE_COUNT=$(grep -c 'now, now,' "$FILE" 2>/dev/null)

if [ "$TIMESTAMPDIFF_COUNT" -ge 3 ] && [ "$TRIPLE_TUPLE_COUNT" -ge 3 ]; then
    echo "PATCHED_OK (TIMESTAMPDIFF=${TIMESTAMPDIFF_COUNT}, tuples=${TRIPLE_TUPLE_COUNT})"
else
    echo "PATCH_WARNING (TIMESTAMPDIFF=${TIMESTAMPDIFF_COUNT}, tuples=${TRIPLE_TUPLE_COUNT})"
fi

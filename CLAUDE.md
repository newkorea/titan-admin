# 프로젝트 가이드 (CLAUDE.md)
# 이 파일은 AI 어시스턴트가 프로젝트 컨텍스트를 빠르게 파악하기 위한 가이드입니다.
# 새 세션에서도 이 파일을 먼저 읽으면 이전 작업을 이어갈 수 있습니다.

## 프로젝트 구성

이 워크스페이스에는 3개의 주요 프로젝트가 있습니다:

| 프로젝트 | 경로 | 설명 |
|---------|------|------|
| **titan** | `/home/newkorea/project/titan` | 메인 서비스 백엔드 (Django 2.2, 결제/인증) |
| **titan-admin** | `/home/newkorea/project/titan-admin` | 관리자 대시보드 (Django 2.2, Mako 템플릿) |
| **bot** | `/home/newkorea/project/bot` | 텔레그램 챗봇 (Flask + Ollama AI) |

**외부 서버:**
| 서버 | IP:포트 | 설명 |
|------|--------|------|
| **UTO API** | `218.158.57.55:2202` (SSH) | UTO VPN PHP API (Apache + PHP 5.4, 고객 앱용) |
| **aws13** | `218.158.57.73` (SSH) | titan 프로덕션 API 서버 |
| **UTO DB** | `218.158.57.51:3306` | vcsvpn2013 MySQL DB |

---

## titan-admin (관리자 패널) — 주 작업 대상

### 기술 스택
- **프레임워크**: Django 2.2.5 + Mako 템플릿 엔진
- **Python**: 3.10.12, venv 경로: `/home/newkorea/project/titan-admin/venv/`
- **서버**: uWSGI 2.0.19.1 (소켓: `/tmp/titan-admin.sock`, 워커 2개)
- **DB**: MySQL — `titan` (기본) + `radius` (보조)
- **SSH**: paramiko (ESXi/KVM 원격 관리용)
- **프론트**: Mako 템플릿 + vanilla JS + Font Awesome

### 서버 관리 명령어
```bash
cd /home/newkorea/project/titan-admin
source venv/bin/activate
bash server-restart.sh       # uWSGI 재시작
touch main/reload             # 코드 리로드 (harakiri=120s)
```

### 디렉토리 구조
```
titan-admin/
├── main/                    # Django 설정 (settings.py, urls.py)
├── backend/
│   ├── urls.py              # URL 라우팅 (475줄) — api/v1/{read|create|update|delete}/...
│   ├── models.py            # DB 모델 (auto-generated, managed=False, raw SQL 위주)
│   ├── djangoapps/          # 기능별 앱
│   │   ├── common/views.py  # 공통 유틸리티: allow_admin 데코레이터, dictfetchall, AES 암복호화
│   │   ├── infra/views.py   # ★ 인프라 관리: ESXi/KVM 호스트, VM 제어, SSH 동기화
│   │   ├── chart/views.py   # 차트, SSH, 이메일, 로깅 (2127줄 — 분리 필요)
│   │   ├── user/views.py    # 사용자 관리 (1648줄 — 분리 필요)
│   │   ├── price/views.py   # 결제/가격 관리 (1473줄 — 분리 필요)
│   │   ├── dashboard/       # 대시보드
│   │   ├── login/           # 로그인/인증
│   │   ├── service/         # 서비스 관리 (radius DB 사용)
│   │   ├── event/           # 이벤트 관리
│   │   ├── saler/           # 대리점 관리
│   │   ├── nasmonitor/      # NAS 모니터링
│   │   └── ...
│   └── templates/admin/     # Mako HTML 템플릿 48개
├── static/                  # CSS, JS, 이미지
├── logs/                    # uWSGI 로그
└── nginx/                   # nginx 설정
```

### 코딩 패턴 (중요!)
- **ORM 미사용**: 모든 DB 쿼리는 raw SQL (`cursor.execute()` + `dictfetchall()`)
- **인증**: `@allow_admin` 데코레이터 — session에 `admin_id` 확인
- **API 규칙**: `api/v1/{read|create|update|delete}/리소스명`
- **응답 형식**: `JsonResponse({'result': 200, ...})` — result 코드로 성공/실패
- **CSRF**: `getCookie('csrftoken')` → `X-CSRFToken` 헤더
- **날짜 포맷**: `strftime('%Y-%m-%d %H:%M:%S')` 으로 변환 후 응답
- **템플릿 상속**: `<%inherit file="../admin/admin_frame.html"/>` + `<%block>` 블록

---

## ★ VPN NAS 서버 SSH 접속 — 중요!
- **모든 NAS 서버(41개)에 SSH 키 등록 완료** → `ssh root@<IP>` 비밀번호 없이 접속 가능
- ESXi 호스트만 `china` 유저 + 비밀번호 (위 표 참조)
- NAS 서버는 항상 **root** 계정으로 접속 (china 아님!)

---

## ★ V2RAY (Xray) 배포 — 확정된 사양
- **Xray 버전**: 1.4.2 (24.12.31 최신은 iOS leaf와 VMess 호환 안 됨!)
- **프로토콜**: VMess + WebSocket + TLS
- **alterId**: 7 (0=AEAD-only → iOS leaf 호환 안 됨. 반드시 7 사용)
- **포트**: 9999 (모든 41개 서버 통일, KT35-42/JP/US/INDIA도 마이그레이션 완료)
- **바이너리**: `/usr/local/xray/xray`
- **설정**: `/usr/local/xray/config.json`
- **서비스**: systemd `xray.service`, `Environment="XRAY_VMESS_AEAD_FORCED=false"`, `MemoryLimit=1500M`
- **로그**: `/var/log/xray/access.log`, `/var/log/xray/error.log`
- **Stats API**: `127.0.0.1:62789` (dokodemo-door, HandlerService + StatsService)
- **TLS 인증서**: 모든 서버에 Let's Encrypt 인증서 존재 (`/etc/letsencrypt/live/<domain>/`)
- **KT28 테스트 완료**: Android + iOS 모두 정상 접속 확인 (2026-02-15)

### ★ Per-User UUID 시스템 (2026-02-15 구현, 동일날 개선)
- **tbl_user.v2ray_uuid**: 유저별 고유 V2RAY UUID (VARCHAR(36))
- **tbl_user.v2ray_deployed**: 유저 UUID가 서버에 배포되었는지 플래그 (TINYINT, 0 또는 1)
- **동작 방식 (Daily Sync)**:
  1. 매일 8AM KST에 sync 스크립트 실행 (cron: `0 8 * * *`)
  2. 공유 UUID (tbl_agent3.v2_config) 전체 갱신 → 이전 공유 UUID 무효화 (도용 방지)
  3. 유효 구독자(~1,600명)의 개인 UUID + 새 공유 UUID를 모든 서버에 배포
  4. 배포된 유저: v2ray_deployed=1 설정, 미배포(만료 등): v2ray_deployed=0
- **API UUID 선택 로직**:
  - v2ray_deployed=1 → 개인 UUID 반환 (본인만 사용 가능)
  - v2ray_deployed=0 (신규가입자 등) → 공유 UUID 반환 (tbl_agent3.v2_config)
  - 만료 유저 → result:300 반환, JSON 다운로드 차단 (app_new_server_list에서 차단)
- **공유 UUID 보안**: 매일 8AM 갱신되므로, 만료 유저가 이전 공유 UUID로 접속 불가
- **신규 유저 흐름**: 회원가입 → UUID 자동생성 → 결제 → 당일은 공유UUID 사용 → 다음날 8AM sync 후 개인UUID 사용
- **만료 유저 제외**: STR_TO_DATE(REPLACE(value, ' KST', ''), '%d %b %Y %H:%i:%s') > NOW() 로 필터링
- **유저 식별**: xray는 UUID로 유저를 식별, email 필드로 추적 가능
- **기기 수 제한**: `app_add_connection`에서 radacct의 V2RAY 세션 수 체크 → Simultaneous-Use 초과 시 거부(result=600)
- **동기화 스크립트**: `/home/newkorea/project/scripts/sync_v2ray_users.py`
  - 크론: 매일 8AM (`0 8 * * *`) ← 5분마다에서 변경
  - 로그: `/home/newkorea/project/scripts/v2ray_sync.log`
  - 동작: 공유UUID 갱신 → DB에서 유효 구독자 UUID 읽어 → 각 서버 config.json 생성 → SCP → restart → v2ray_deployed 플래그 업데이트
  - 옵션: `--force` (전체 재시작), `--dry-run` (미리보기), `--server IP` (특정 서버만)
- **API 변경**: `app_new_server_list`(만료차단+UUID선택), `app_new_check_server`(UUID선택), `app_stable_server`(UUID선택)
- **VN-KR 제외**: hostip='vt1.jobjapan.com' 서버는 별도 (port 12560, 미마이그레이션)
- **xray DB 연동 불가**: xray는 순수 프록시 — config.json 파일만 읽음. gRPC API에 AddUser/RemoveUser 존재하나 CLI 미노출. 전 버전 공통

---

## ★ RADIUS 프로토콜 매핑 — 확정 (절대 변경 금지!)

radacct 테이블의 `nasporttype` 값 → 실제 VPN 프로토콜 대응:

| nasporttype (DB) | 실제 프로토콜 | 근거 |
|---|---|---|
| **Virtual** | **IKEv2** | calledstationid에 포트 4500 (IKEv2 NAT-T) 100% 확인 |
| **ISDN** | **OpenVPN** | 운영자 확인 |
| **61** | **SSTP** | nasportid=443 (SSTP 포트), iOS 사용자 확인 |
| **V2RAY** | **V2RAY** | 그대로 |

- 성공 기준: `acctsessiontime > 10` = VPN 터널 성공
- `radacct.username` = `tbl_user.email` (NOT username)
- 24h 기준 분포: IKEv2(Virtual) ~84%, OpenVPN(ISDN) ~11%, V2RAY ~3%, SSTP(61) ~1%

---

## ★ ESXi 인프라 관리 — 핵심 발견사항

### ESXi SSH 접속 정보
| 호스트 | IP | SSH유저 | 비밀번호 |
|--------|-----|---------|----------|
| exsikt122 | 218.158.57.122 | china | uto160505! |
| exsikt123 | 218.158.57.123 | china | uto160505! |
| exsikt124 | 218.158.57.124 | china | uto160505! |
| exsikt125 | 218.158.57.125 | china | uto160505! |
| exsikt14185 | 14.51.2.185 | china | uto160505! |
| exsikt59252 | 59.26.85.252 | china | uto160505! |
| exsisk157 | 221.143.197.157 | china | uto160505! |
| exsisk158 | 221.143.197.158 | china | uto160505! |

### ESXi BusyBox 제약사항 (매우 중요!)
1. **`esxcli` 명령어가 일부 호스트에서 영구적으로 행(hang)**: exsikt125에서 확인됨.
   hostd/esxcli 데몬 문제. `localcli`, `df -h`도 행. `timeout -t 5 -s 9`로 SIGKILL 가능.
2. **셸 명령어 크기 제한**: BusyBox sh는 큰 명령어를 거부 (`/bin/sh: File too large`).
   VM 18개 이상이면 echo 배치 대신 **for-loop** 방식 사용 필수.
3. **ESXi busybox timeout**: `timeout -t <sec> -s 9 <command>` (GNU 형식 아님!)

### ESXi에서 작동하는 명령어 (esxcli 대안)
| 정보 | 작동하는 명령어 | 속도 |
|------|----------------|------|
| 버전 | `vmware -v` | 0.3s |
| 메모리 | `vsish -e get /memory/comprehensive` | 0.3s |
| Uptime | `uptime` | 0.3s |
| CPU 모델 | `smbiosDump \| grep Version` | 0.2s |
| CPU 코어 | `grep -c processor /proc/cpuinfo` | 0.2s |
| NIC 목록 | `esxcfg-nics -l` | 0.4s |
| VM 목록 | `vim-cmd vmsvc/getallvms` | 0.6s |
| VM 전원 | `vim-cmd vmsvc/power.getstate <vmid>` | 0.7s |
| 데이터스토어 | `stat -f /vmfs/volumes/<name>` (개별) | 0.5s |

### 현재 SSH 수집 전략 (_collect_esxi_info)
```
SSH 1 (15s): 빠른 명령어만 — vmware -v, uptime, vsish, cpuinfo, smbiosDump, esxcfg-nics
SSH 2 (20s): esxcli 명령어 — 실패해도 무시 (일부 호스트에서 행)
SSH 3 (조건부): esxcli storage 실패 시 → 개별 stat -f per volume
SSH VM: for-loop으로 vim-cmd (getallvms → power/config/guest per VM)
```

---

## titan (메인 서비스) — 앱 API 서버

### ★ 서버 구성 (중요!)
| 서버 | IP | 호스트명 | 역할 |
|------|-----|---------|------|
| **aws13** | 218.158.57.73 | aws13.titanvpn.kr | **★ 실제 운영 API 서버** (`titan.uto.com` → 115.71.13.125 → aws13으로 프록시) |
| **aws14** | 218.158.57.53 | aws14.titanvpn.kr | 개발/테스트 서버 (이 워크스페이스가 있는 서버) |

- **앱이 호출하는 API 도메인**: `titan.uto.com` (DNS: 115.71.13.125)
- **코드 변경 시 반드시 aws13에도 배포해야 함!** (aws14만 변경하면 실제 앱에 반영 안 됨)
- **aws13 접속**: `ssh newkorea@218.158.57.73`
- **aws13 코드 배포**: `scp <파일> newkorea@218.158.57.73:/home/newkorea/project/titan/<경로>`
- **aws13 코드 리로드**: `ssh newkorea@218.158.57.73 'touch /home/newkorea/project/titan/main/reload'`

### 기술 스택
- Django 2.2 + MySQL
- 경로: `/home/newkorea/project/titan`
- 결제 연동: payment_korea, payment_global, payment_eximbay
- venv: `/home/newkorea/project/titan/.venv310` (Python 3.10)

---

## ★ UTO VPN PHP API 서버 (218.158.57.55) — 절대 기억!

### 서버 접속 (중요!)
- **IP**: 218.158.57.55 (hostname: UTOMYSQL.uto.com)
- **SSH 포트**: **2202** (기본 22가 아님!)
- **SSH 접속**: `ssh root@218.158.57.55 -p 2202`
- **웹서버**: Apache 2.4.6 (CentOS) + PHP 5.4.16, MPM prefork

### 웹 구조
- **Web Root**: `/var/www/html/users/client/`
- **api/**: 구버전 Android 앱 API (소수 사용자)
- **api26/**: 신버전 앱 API (대부분 사용자, 2025-12-30 업데이트)
- **api, api26 공유**: `configure.php`, `cn_isp.php` (동일 파일)

### DB 연결 (configure.php)
- **Primary**: `mysql:host=218.158.57.51`, dbname=vcsvpn2013, user=root, pass=uto6703
- **Failover**: `mysql:host=125.132.9.241`, 동일 DB/계정
- **PDO 클래스**: `new Connect()` — `Connect extends PDO`

### 주요 API 엔드포인트
| 엔드포인트 | 용도 | 비고 |
|-----------|------|------|
| `login.php` | 로그인 (GET: name, pwd, platform) | status 200=성공 |
| `checkserver.php` | 서버 배정 (GET: username, password, address, protocol, platform) | address=빈값이면 auto, 아니면 manual |
| `getconnectserver.php` | 서버 배정 v2 (동일 파라미터) | hyid 필터 추가, try/catch 있음 |
| `allservers.php` | 전체 서버 목록 | |
| `emservers.php` | EM 서버 목록 | |
| `checkuser.php` | 사용자 상태 확인 (주기적 호출) | |
| `checkconnect.php` | 연결 상태 확인 | |
| `disconnect.php` | 연결 해제 | |

### 서버 배정 로직 (checkserver.php / getconnectserver.php)
- **MAX_CONN**: 50 (서버당 최대 연결 수)
- **4단계 선택**: (1) server_health 스코어 → (2) radacct 기반 → (3) EM서버(is_auto=2) → (4) 캡 무시
- **ISP 감지**: `cn_isp.php` — 중국 통신사별 최적 서버 선택
- **server_health 테이블**: server_ip, cn_telecom(all/cm/ct/cu), score, conn_count, is_healthy
- **vpnlinek 테이블**: ip(도메인), address(IP), protocol, su, is_auto, hyid

### 관리자 패널
- **경로**: `/var/www/html/users/admin/`
- **주요**: `vpnuser/vpn_off.php` — VPN 관리

---

## bot (텔레그램 챗봇)

### 기술 스택
- Flask + python-telegram-bot + Ollama (로컬 AI)
- 경로: `/home/newkorea/project/bot`
- 주요 파일: app.py (현재), app2~4.py (이전 버전들)
- 데이터: SQLite (chat_history), JSON (FAQ, extra_knowledge)

---

## 주의사항 & 팁

### 파일 편집 시
- **replace_string_in_file**: ESXi 템플릿처럼 큰 파일은 종종 실패 → `run_in_terminal`로 `cat > file << 'EOF'` 사용
- 템플릿 편집 후 반드시 `bash server-restart.sh` 실행
- Python 테스트 시: `source venv/bin/activate && DJANGO_SETTINGS_MODULE=main.settings python3 -c "..."`

### DB 직접 쿼리
```bash
cd /home/newkorea/project/titan-admin && source venv/bin/activate
python3 -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from django.db import connections
from backend.djangoapps.common.views import dictfetchall
cursor = connections['default'].cursor()
cursor.execute('SELECT ...')
for r in dictfetchall(cursor): print(r)
"
```

### nginx 설정
- titan-admin: `server_name tiadmintan14.titanvpn.kr` → uwsgi socket `/tmp/titan-admin.sock`
- uwsgi_read_timeout: 60초
- uWSGI venv: `.venv38` (NOT `venv`)
- uWSGI 프로토콜 사용 (HTTP가 아님 — curl 직접 불가, nginx 경유 필수)

### Mako 템플릿 주의사항
- admin_frame.html 블록명: `css`, `content` (단수!), `title`, `subtitle`, `js`
- `getCookie()` 함수가 전역에 없음 — 각 템플릿에서 직접 정의 필요
- Mako 캐시: `mako_modules/` 디렉토리에 .py 파일로 캐시됨 — 문제 시 삭제 후 재시작
- `@allow_admin` 데코레이터: `request.session['is_staff'] == 1` 확인

### DB 테이블 참조 (서버 분석용)
- `tbl_device_info`: user_id(→tbl_user.id), device_type, device_isp, device_city, device_country, login_time
- `tbl_user`: id, email(=VPN 로그인ID), username(=표시이름, VPN과 무관)
- `tbl_agent3`: hostip, name, protocol, is_active
- `radius.radacct`: username(=email), nasipaddress, acctsessiontime, nasporttype, acctstarttime
- ISP 분류: mobile/cmnet/tietong→ChinaMobile, unicom/cnc/china169→ChinaUnicom, telecom/chinanet→ChinaTelecom

---

## 작업 이력 (최근)

### 2026-02-14: 서버 분석 페이지 구축
1. ✅ RADIUS 프로토콜 매핑 확정 (Virtual=IKEv2, ISDN=OpenVPN, 61=SSTP, V2RAY=V2RAY)
2. ✅ 서버 분석 API 구축 (`/api/v1/read/server_analysis`)
   - 파일: `backend/djangoapps/nasmonitor/views.py` (api_read_server_analysis 함수)
   - 9개 분석 차원: 전체/ISP/프로토콜/ISP×프로토콜/OS/도시/차단리스트/세션시간/세션vs유저
   - Per-User 중복제거 방식, 최근 24시간, 중국 사용자 한정
3. ✅ 서버 분석 대시보드 페이지 (`/server_analysis`)
   - 파일: `backend/templates/admin/server_analysis.html`
   - 9개 탭 UI, 필터 pills, 프로토콜 분포 바, 티어 배지(S/A/B/C/F), 진행바
4. ✅ URL 라우팅 추가 (`backend/urls.py`)
5. ✅ 관리자 메뉴에 "서버 분석" 항목 추가 (`admin_menu.html`)
6. ✅ 빈 페이지 버그 수정 — 블록명 `contents` → `content`, getCookie 함수 추가

### 2026-02-14: 인프라 관리 페이지 개선
1. ✅ 인프라 대시보드를 좌-우 분할 레이아웃으로 전면 재설계
   - 왼쪽: 호스트 리스트 (미니 리소스바, VM 요약)
   - 오른쪽: 선택한 호스트 상세 + VM 목록
2. ✅ exsikt125 OFFLINE 문제 해결
   - 원인: esxcli 데몬 장애로 모든 esxcli 명령 행
   - 해결: 3단계 SSH 수집 (빠른명령 → esxcli(실패허용) → fallback)
3. ✅ VM 상태 UNKNOWN 문제 해결
   - 원인: BusyBox 셸 명령어 크기 제한 ("File too large")
   - 해결: echo 배치 → for-loop 방식으로 변경
4. ✅ "전체 VM 보기" 버튼 + 모달 추가 (검색/필터/VM제어)
5. ✅ 동기화 진행 오버레이 추가 (프로그레스바 + 실시간 상태)

### 향후 계획
- 서버 분석 결과 기반 자동 서버 할당: "통신사, 지역, OS별로 연결 안 되는 서버 제외 → 가장 빠른 서버 auto 할당"
- 분석 페이지 개선: 실시간 갱신, 시간대별 트렌드, 알림 기능 등
- app_new_server_list 응답 최적화: 현재 231KB JSON → gzip 압축 또는 응답 축소 검토

### 2026-03-09: 세션 쿠키 문제 분석 + 수정

#### 문제 현상
- 안드로이드/iOS 앱에서 백그라운드 → 앱 재시작 시 "서버오류" + "캐시삭제 요청 팝업"
- Session is invalid 에러 폭증: 3/6(96건) → 3/7(185건) → 3/8(968건, 피크 18-21시 710건)

#### 원인 분석
- `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` 설정이 근본 원인
- Django가 세션 쿠키를 `Expires` 없이 전송 → "세션 쿠키"(메모리 전용)
- 모바일 앱이 백그라운드 → OS 프로세스 킬 → 쿠키 소멸 → API 호출 시 Session is invalid
- API별 에러 분포: app_check_connection(688건), app_check_login(306건), app_get_userinfo(122건)

#### 수정 내용
1. ✅ `settings.py`: `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` → `False` 변경
   - 세션 쿠키에 `Expires: 30일 후` (SESSION_COOKIE_AGE) 포함 → 디스크에 영구 저장
   - aws13 프로덕션 배포 완료 (3/9 07:10)
2. ✅ 3/8 롤백 경위: 이전에 세션 폴백 코드(`_session_fallback()`, IP/UUID 기반 세션 복구) 추가했으나
   부작용(로그아웃 안됨, 백그라운드 오류) 발생 → 3/8 11시 전체 롤백 → 에러 폭증
   - 롤백된 파일 백업: `views.py.bak_20260308` (세션 폴백 코드 포함, 3123줄)
   - 현재 views.py: commit 17e50e6 (2026-02-24 버전, 2952줄) — 세션 폴백 없음

#### 앱 시작 성능 분석 (softcan@naver.com 추적)
| API | 소요시간 | 응답크기 | 비고 |
|-----|---------|---------|------|
| `app_session_key` | **450-500ms** | 55B | bcrypt 해싱 (CPU-intensive, 불가피) |
| `app_new_server_list` | **110-210ms** | **231KB** | JSON 풀 다운로드 (중국에서 체감 1-2초) |
| `app_check_login` | 20-450ms | 9.6KB | 세션 있으면 20ms, 없으면 450ms |
| `app_get_userinfo` | 35-45ms | 350B | 빠름 |
| `app_new_check_server` | 35-650ms | 5.8KB | SSH 킥 발생 시 600ms+ |

- SESSION_EXPIRE_AT_BROWSER_CLOSE=False 적용으로 앱 재시작 시 세션 유지 → app_session_key 재호출 불필요 → 500ms 절약
- app_new_server_list 231KB는 nginx gzip 압축으로 최적화 가능 (JSON 80-90% 압축률)

### 2026-02-15: V2RAY 전체 배포 + Per-User UUID 시스템 구축
1. ✅ Xray 1.4.2 테스트 (KT28): iOS leaf + alterId=7 조합으로 해결
2. ✅ 41개 전체 서버에 V2RAY (Xray 1.4.2) 배포 완료
3. ✅ 구형 x-ui 서버 10개 마이그레이션 → 표준 xray 1.4.2 + port 9999
   - JAPAN-CH, KT35-37, KT39-42, US-LA, INDIA — 모두 port 9999 통일
   - 스크립트: `/home/newkorea/project/scripts/migrate_old_v2ray.sh`
4. ✅ Per-User UUID 시스템 구현
   - `tbl_user.v2ray_uuid` 컬럼 추가, 16,877명 UUID 생성
   - 동기화: `sync_v2ray_users.py` — 5분 크론, 40개 서버에 config.json 배포
   - API 수정: `app_new_server_list`, `app_new_check_server`, `app_stable_server` → 개인 UUID 반환
   - 기기 수 제한: `app_add_connection`에서 V2RAY 세션 수 체크 (Simultaneous-Use 기반)
   - 신규 가입 시 UUID 자동 생성 (`login/views.py`)
5. ✅ VN-KR 제외 (hostip가 도메인, port 12560 — 별도 관리 필요)

### 2026-02-15: OOM 장애 대응 + 방지 조치
1. ✅ 원인 분석: 초기 sync에서 만료 유저 16,877명 전체 배포 → xray 메모리 ~5GB 사용
   - VPN 서버의 커널 네트워크 메모리 (IPsec/conntrack/버퍼) 7-8GB + xray 5GB → 16GB 서버 OOM
   - SK5/SK7/SK13 다운, KT0/KT28/KT32/LG3/SK6/SK9/SK22 등도 영향 (자동/수동 리붓)
2. ✅ 다운 서버 복구: SK7 (VM ID 71), SK13 (VM ID 65) → ESXi 221.143.197.157에서 reset
3. ✅ 방지 조치 1: 만료 유저 필터링 → 1,609명만 배포 (기존 16,877명에서 대폭 감소)
4. ✅ 방지 조치 2: `MemoryLimit=1500M` → 40대 전서버 xray.service에 적용 (xray만 kill, 시스템 보호)
5. ✅ 방지 조치 3: sync 스크립트 안전장치 추가
   - MAX_USERS_LIMIT=3000 (초과 시 abort — 만료유저 필터링 실패 방지)
   - MIN_USERS_LIMIT=100 (미만 시 abort — DB 쿼리 오류 방지)
   - MAX_CONFIG_SIZE_KB=1024 (1MB 초과 시 abort — OOM 방지)
6. ✅ 레거시 UUID 호환: 각 서버의 기존 공유 UUID를 `_legacy_shared@titanvpn`으로 config에 포함

### 2026-02-15: UUID 시스템 개선 (Daily Sync + 만료 차단)
1. ✅ `tbl_user.v2ray_deployed` 컬럼 추가 (TINYINT, 0=미배포, 1=배포됨)
2. ✅ sync 크론 변경: `*/5 * * * *` → `0 8 * * *` (매일 8AM 1회)
3. ✅ sync 시 공유 UUID (tbl_agent3.v2_config) 매일 갱신 → 만료 유저 도용 방지
4. ✅ sync 시 v2ray_deployed 플래그 업데이트 (배포됨=1, 미배포=0)
5. ✅ API: app_new_server_list에 만료 체크 추가 → 만료 유저 JSON 다운로드 차단 (result=300)
6. ✅ API: v2ray_deployed=1이면 개인UUID, 0이면 공유UUID 반환 (3개 엔드포인트 모두)
7. ✅ aws13 프로덕션 배포 완료

### 2026-02-16: Google/Gemini 차단 우회 (OpenWrt + IPIP 터널)

#### ★ Gemini 차단 확인 방법 (절대 규칙!)
- **HTTP 200 ≠ 접속 성공!** 반드시 HTML body의 geo 코드로 확인
- 방법: `curl -sL https://gemini.google.com | grep -oP '"[a-z]{2}"' | head -1`
- `"cn"` → 차단됨 (Google이 IP를 중국으로 분류)
- `"en"` 또는 `"kr"` → 정상 접속
- **GEMINI_BLOCKED_GEOS**: cn, hk, ru

#### OpenWrt 게이트웨이
- **IP**: 14.51.2.184 (ESXi 14.51.2.185, 185net1 vSwitch)
- **역할**: Passwall 투명 프록시 → Google CIDR 트래픽을 해외 프록시로 중계
- **적용 CIDR (21개)**: 8.8.4.0/24, 8.8.8.0/24, 64.233.160.0/19, 66.102.0.0/20, 66.249.64.0/19, 72.14.192.0/18, 74.125.0.0/16, 108.177.0.0/17, 108.170.192.0/18, 130.211.0.0/16, 142.250.0.0/15, 172.217.0.0/16, 172.253.0.0/16, 173.194.0.0/16, 192.178.0.0/15, 209.85.128.0/17, 216.58.192.0/19, 216.239.32.0/19, 199.223.232.0/21, 207.223.160.0/20, 14.0.112.0/24

#### 서버 그룹별 라우팅 방식

| 그룹 | 서버 | 방식 | 스크립트 |
|------|------|------|---------|
| **Same L2 (14.51.2.X)** | KT0, KT1, KT2, KT4, KT5 | 직접 라우팅 `via 14.51.2.184 dev eth0` | `/usr/local/bin/setup_google_routes.sh` |
| **LG2 (다른 서브넷)** | LG2 (112.218.79.75) | IPIP 터널 → KT0 → OpenWrt | LG2: `setup_google_tunnel.sh`, KT0: `setup_lg2_tunnel.sh` |
| **125.132.9.X (KT23 NAT)** | KT35-42 | `via 218.158.57.23 dev eth0 onlink` → KT23 MASQUERADE | KT35-42: `setup_google_routes.sh`, KT23: `setup_kt35_42_nat.sh` |

#### KT23 역할 (125.132.9.X 게이트웨이)
- KT23 (218.158.57.23, ESXi 218.158.57.122): Google에서 geo=en (차단 안 됨)
- KT35-42 (125.132.9.128/25)와 **같은 물리 스위치** — `onlink` ARP 해석 성공 (REACHABLE)
- IP 포워딩 + MASQUERADE: KT35-42의 Google 트래픽을 KT23 IP로 NAT
- 스크립트: `/usr/local/bin/setup_kt35_42_nat.sh` (rc.local 등록)
- ★ 이전 IPIP 터널 방식(KT35→KT0→OpenWrt) 대비 훨씬 단순: 터널 불필요, 직접 onlink

#### IPIP 터널 구성 (LG2 전용)

| 터널 | 엔드포인트 A | 엔드포인트 B | 서브넷 |
|------|------------|------------|--------|
| lg2tun | KT0 (14.51.2.130), 10.99.0.1/30 | LG2 (112.218.79.75), 10.99.0.2/30 | 10.99.0.0/30 |

#### KT0 역할 (IPIP 허브)
- 1개 터널: lg2tun (LG2용)
- MASQUERADE: LG2 IP → eth0 (OpenWrt 전달 시 소스 NAT)
- 스크립트: `/usr/local/bin/setup_lg2_tunnel.sh`
- rc.local에 등록

#### 주의사항
- **같은 L2**: `via GATEWAY dev eth0` (onlink 불필요)
- **다른 L2, 같은 물리 스위치**: `via GW dev eth0 onlink` — ARP 해석 가능 → 직접 라우팅 OK (KT35-42→KT23)
- **다른 L2, 다른 물리 스위치**: `onlink`로 ARP INCOMPLETE → IPIP 터널 필수 (LG2→KT0)
- **KT27-32**: ESXi 14.51.2.185에 있으나 geo=en → Gemini 차단 아님 (작업 불필요)

### 2026-03-03: UTO VPN 세션 관리 시스템 구축
1. ✅ UTO radacct stale 세션 정리 스크립트 생성 (`/home/newkorea/project/scripts/uto_cleanup_stale_radacct.py`)
2. ✅ MikroTik RouterOS API 클라이언트 구현 (바이너리 프로토콜, W/WS/O 3대 서버)
3. ✅ ROS 세션 동기화: API 실제 활성 vs radacct NULL 비교 → stale 종료 + 누락 105건 복구
4. ✅ acctsessiontime unsigned int 오버플로 수정: `GREATEST(0, TIMESTAMPDIFF(...))` 5곳 적용
5. ✅ 크론: `*/5 * * * *` + `flock -n /tmp/uto_radacct_cleanup.lock` (5분 주기, 중복실행 방지)
6. ✅ 전 프로토콜 만료/세션초과 킥 구현 (`enforce_all_sessions`)
   - strongSwan: SSH → `strongswan stroke down-nb <SA>` (paramiko 키 인증)
   - openvpn: SSH → telnet 127.0.0.1:1199 → `kill <username>`
   - ROS: MikroTik API `/ppp/active/remove`
   - v2ray: radacct UPDATE만 (xray 실시간 킥 불가)
7. ✅ 43건 세션초과 킥 실행 완료 (strongSwan 4, openvpn 1, v2ray 35, ROS 3)
8. ✅ CLAUDE.md에 UTO VPN 참조 섹션 추가 (DB, NAS, 프로토콜, SSH, ROS API, 킥 명령어)

### 2026-03-03: UTO API 서버 PHP 에러 수정
1. ✅ 고객 13867646663 연결 버튼 미반응 문제 조사
   - 원인: configure.php PHP Fatal Error (39,567건) — DB 연결 실패 시 `$this->exec()` 크래시
   - PHP 5.4에서 `parent::__construct()` 2회 호출 시 PDO 내부 핸들 손상 가능
2. ✅ configure.php 수정: `$this->exec()` 호출을 try/catch + @ suppression으로 보호
   - api/, api26/ 모두 적용 — Fatal Error 0건으로 감소
3. ✅ checkserver.php 수정: `$db = new Connect()` try/catch로 감싸서 DB 연결 실패 시 JSON 500 반환
   - api/, api26/ 모두 적용
4. ✅ Apache access_log 활성화 (httpd.conf → `CustomLog "logs/access_log" combined` 주석 해제)
5. ✅ CLAUDE.md에 UTO API 서버 정보 추가 (218.158.57.55:2202, 웹 구조, DB, 엔드포인트)
6. 참고: server selection 로직 자체는 정상 (auto selection 시 SK직통85 등 정상 반환)
   - Connection_errors_accept=36,901 (MySQL 218.158.57.51 측 accept 실패) — 근본 원인은 MySQL 서버 측 리소스

---

## ★ UTO VPN (vcsvpn2013) 세션 관리 시스템

### DB 연결
- **DB**: vcsvpn2013 @ 218.158.57.51:3306 (Django DB alias: `uto`)
- **사용자**: newkorea / new1234 (aws14 → 51 접속만 허용, 외부 불가)
- **테이블**: `radacct` (세션), `vpnuser` (유저+세션제한+만료일)

### vpnuser 테이블 주요 컬럼
- `vuser`: 유저명 (=radacct.username)
- `session`: 동시접속 제한 (대부분 1, 일부 2/3/10/100)
- `lastdate`: 서비스 만료일 (datetime)

### UTO NAS 서버 + 프로토콜 분포
| 프로토콜 | 세션수 | 서버수 | 킥 방법 |
|---------|-------|-------|--------|
| **strongSwan** | ~320 | 26개 | SSH → `strongswan stroke down-nb <SA>` |
| **W ros** | ~85 | 1 (27.115.70.46) | MikroTik API `/ppp/active/remove` |
| **WS ros** | ~75 | 1 (27.115.51.226) | MikroTik API |
| **O ros** | ~65 | 1 (58.246.240.2) | MikroTik API |
| **v2ray** | ~45 | 11개 | radacct만 종료 (xray 실시간 킥 불가) |
| **openvpn** | ~26 | 8개 | SSH → telnet 127.0.0.1:1199 → kill |
| **INDIA1** | ~3 | 1 (139.84.165.217) | openvpn과 동일 |

### UTO NAS SSH 접속 정보
- **인증**: SSH 키 인증 (root@<NAS_IP>) — 대부분 OK
- **SSH 불가 서버 4개** (radacct만 종료):
  - 218.158.57.66: SSH denied (v2ray)
  - 218.233.115.189: SSH denied (v2ray)
  - 218.233.115.190: connection reset (v2ray)
  - 10.99.0.14: 내부IP timeout (strongSwan)

### ROS 서버 API 접속 정보
| 서버 | nasipaddress | API | 유저 | 비밀번호 | 비고 |
|------|-------------|-----|------|---------|------|
| W ros | 27.115.70.46 | 8728 | admin | vkfksgksmf | old-style 로그인 |
| WS ros | 27.115.51.226 | 8728 | admin | vkfksgksmf | old-style 로그인 |
| O ros | 58.246.240.2 | 8728 | **Oserver** | vkfksgksmf | **new-style only** (v6.49.6) |

### VPN 킥 상세 명령어
- **strongSwan**: `strongswan statusall | grep "[username]"` → SA추출 → `strongswan stroke down-nb <SA>`
- **openvpn**: telnet 127.0.0.1:1199 → 비밀번호 `mykakao9898` → `kill <username>`
- **ROS PPP**: MikroTik API `/ppp/active/remove =.id=<id>`
- **v2ray**: radacct UPDATE만 (xray는 config.json 기반, 실시간 킥 API 없음)

### cleanup 스크립트
- **파일**: `/home/newkorea/project/scripts/uto_cleanup_stale_radacct.py`
- **크론**: `*/5 * * * *` (5분마다) + `flock` 중복 실행 방지
- **로그**: `/home/newkorea/project/scripts/uto_stale_radacct.log`
- **동작 순서**:
  1. ROS 동기화 (API로 실제 활성 확인 → stale 종료 / 누락 복구)
  2. 만료/세션초과 킥 (모든 프로토콜: ROS API + SSH strongSwan/openvpn + v2ray radacct)
  3. 일반 stale 정리 (24h+ V2RAY/openvpn, 48h+ strongSwan)
- **옵션**: `--dry-run` (미리보기), `--skip-ros` (ROS 건너뛰기), `--hours N`

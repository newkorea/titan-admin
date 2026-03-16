from django.urls import path
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.uto import views as UtoViews

urlpatterns = [
    # [redirect] 인덱스 → UTO 회원관리로 리다이렉트
    path('', IndexViews.index, name='index'),

    # [render] 로그인
    path('login', LoginViews.login, name='login'),

    # [api v1] 로그인/로그아웃
    path('api/v1/login', LoginViews.api_login, name='api_login'),
    path('api/v1/logout', LoginViews.api_logout, name='api_logout'),

    # ============================================================
    # UTO VPN 관리
    # ============================================================

    # [render] UTO 회원 관리
    path('uto_user', UtoViews.uto_user, name='uto_user'),

    # [render] UTO 서버 관리
    path('uto_server', UtoViews.uto_server, name='uto_server'),

    # [api v1] UTO 회원 DataTables
    path('api/v1/read/uto_user_datatables', UtoViews.api_read_uto_user_datatables, name='api_read_uto_user_datatables'),

    # [api v1] UTO 회원 통계
    path('api/v1/read/uto_user_count', UtoViews.api_read_uto_user_count, name='api_read_uto_user_count'),

    # [api v1] UTO 회원 상세
    path('api/v1/read/uto_user_detail', UtoViews.api_read_uto_user_detail, name='api_read_uto_user_detail'),

    # [api v1] UTO 회원 종합 진단
    path('api/v1/read/uto_user_diagnosis', UtoViews.api_read_uto_user_diagnosis, name='api_read_uto_user_diagnosis'),

    # [api v1] UTO 회원 접속 실패 로그 (비동기)
    path('api/v1/read/uto_user_failures', UtoViews.api_read_uto_user_failures, name='api_read_uto_user_failures'),

    # [api v1] UTO 회원 수정
    path('api/v1/update/uto_user', UtoViews.api_update_uto_user, name='api_update_uto_user'),

    # [api v1] UTO 회원 차단/해제
    path('api/v1/update/uto_user_block', UtoViews.api_update_uto_user_block, name='api_update_uto_user_block'),

    # [api v1] UTO 세션 강제종료
    path('api/v1/update/uto_user_kick', UtoViews.api_update_uto_user_kick, name='api_update_uto_user_kick'),

    # [api v1] UTO 서버 DataTables
    path('api/v1/read/uto_server_datatables', UtoViews.api_read_uto_server_datatables, name='api_read_uto_server_datatables'),

    # [api v1] UTO 서버 수정
    path('api/v1/update/uto_server', UtoViews.api_update_uto_server, name='api_update_uto_server'),

    # [api v1] UTO 서버 통계
    path('api/v1/read/uto_server_count', UtoViews.api_read_uto_server_count, name='api_read_uto_server_count'),

    # [api v1] UTO 대리점 목록
    path('api/v1/read/uto_dealers', UtoViews.api_read_uto_dealers, name='api_read_uto_dealers'),

    # [api v1] UTO 실시간 접속자
    path('api/v1/read/uto_online_users', UtoViews.api_read_uto_online_users, name='api_read_uto_online_users'),

    # [render] UTO NAS 서버 현황
    path('uto_nas_status', UtoViews.uto_nas_status, name='uto_nas_status'),

    # [api v1] UTO NAS 점검 결과
    path('api/v1/read/uto_nas_status', UtoViews.api_read_uto_nas_status, name='api_read_uto_nas_status'),

    # [api v1] UTO NAS 전체 점검 시작
    path('api/v1/update/uto_nas_check', UtoViews.api_update_uto_nas_check, name='api_update_uto_nas_check'),

    # [api v1] UTO NAS 점검 진행 상태
    path('api/v1/read/uto_nas_check_status', UtoViews.api_read_uto_nas_check_status, name='api_read_uto_nas_check_status'),

    # [api v1] UTO SSH 접속 정보
    path('api/v1/read/uto_ssh_info', UtoViews.api_read_uto_ssh_info, name='api_read_uto_ssh_info'),

    # [api v1] UTO 서버 재부팅
    path('api/v1/update/uto_reboot', UtoViews.api_update_uto_reboot, name='api_update_uto_reboot'),

    # [api v1] UTO 단일 서버 점검
    path('api/v1/update/uto_single_check', UtoViews.api_update_uto_single_check, name='api_update_uto_single_check'),

    # [api v1] UTO 인증서 갱신
    path('api/v1/update/uto_cert_renew', UtoViews.api_update_uto_cert_renew, name='api_update_uto_cert_renew'),
    path('api/v1/read/uto_cert_renew_status', UtoViews.api_read_uto_cert_renew_status, name='api_read_uto_cert_renew_status'),

    # [api v1] UTO 목표사이트 점검
    path('api/v1/update/uto_site_check', UtoViews.api_update_uto_site_check, name='api_update_uto_site_check'),
    path('api/v1/read/uto_site_check_status', UtoViews.api_read_uto_site_check_status, name='api_read_uto_site_check_status'),

    # [api v1] UTO 디스크 정리
    path('api/v1/read/uto_disk_analysis', UtoViews.api_read_uto_disk_analysis, name='api_read_uto_disk_analysis'),
    path('api/v1/update/uto_disk_cleanup', UtoViews.api_update_uto_disk_cleanup, name='api_update_uto_disk_cleanup'),

    # [render] UTO 서버 배정 현황
    path('uto_assignment', UtoViews.uto_assignment, name='uto_assignment'),

    # [api v1] UTO 서버 배정 현황 데이터
    path('api/v1/read/uto_assignment', UtoViews.api_read_uto_assignment, name='api_read_uto_assignment'),

    # [api v1] UTO is_auto 토글
    path('api/v1/update/toggle_uto_is_auto', UtoViews.api_toggle_uto_is_auto, name='api_toggle_uto_is_auto'),

    # ============================================================
    # UTO 신규가입
    # ============================================================

    # [render] UTO 신규가입
    path('uto_register', UtoViews.uto_register, name='uto_register'),

    # [api v1] UTO 사용자명 중복확인
    path('api/v1/read/uto_check_vuser', UtoViews.api_read_uto_check_vuser, name='api_read_uto_check_vuser'),

    # [api v1] UTO 신규가입 처리
    path('api/v1/create/uto_register', UtoViews.api_create_uto_register, name='api_create_uto_register'),

    # ============================================================
    # UTO 무통장 연장 + 변경내역
    # ============================================================

    # [render] UTO 무통장 연장
    path('uto_extend', UtoViews.uto_extend, name='uto_extend'),

    # [api v1] UTO 무통장 연장 처리
    path('api/v1/create/uto_extend', UtoViews.api_create_uto_extend, name='api_create_uto_extend'),

    # [api v1] UTO 패키지 변경 (잔여일수 비례환산)
    path('api/v1/update/uto_package_change', UtoViews.api_update_uto_package_change, name='api_update_uto_package_change'),

    # [render] UTO 변경내역
    path('uto_change_history', UtoViews.uto_change_history, name='uto_change_history'),

    # [api v1] UTO 변경내역 DataTables
    path('api/v1/read/uto_change_history', UtoViews.api_read_uto_change_history, name='api_read_uto_change_history'),

    # ============================================================
    # Pospal POS 연동
    # ============================================================

    # [render] Pospal 판매 관리
    path('pospal', UtoViews.pospal_sales, name='pospal_sales'),

    # [api v1] Pospal 최근 판매 조회
    path('api/v1/read/pospal_tickets', UtoViews.api_read_pospal_tickets, name='api_read_pospal_tickets'),

    # [api v1] Pospal 유저 조회 (연장 전 확인)
    path('api/v1/read/pospal_user', UtoViews.api_read_pospal_user, name='api_read_pospal_user'),

    # [api v1] 전화번호로 유저 검색
    path('api/v1/read/pospal_user_by_phone', UtoViews.api_read_pospal_user_by_phone, name='api_read_pospal_user_by_phone'),

    # [api v1] Pospal 판매 → VPN 자동연장
    path('api/v1/create/pospal_extend', UtoViews.api_create_pospal_extend, name='api_create_pospal_extend'),

    # [api v1] Pospal 환불 처리
    path('api/v1/create/pospal_refund', UtoViews.api_create_pospal_refund, name='api_create_pospal_refund'),

    # ============================================================
    # VLESS+Reality 관리
    # ============================================================

    # [render] Reality 설정 관리
    path('uto_reality', UtoViews.uto_reality, name='uto_reality'),

    # [api v1] Reality 사용자 목록 (UUID 포함)
    path('api/v1/read/uto_reality_users', UtoViews.api_read_uto_reality_users, name='api_read_uto_reality_users'),

    # [api v1] Reality 클라이언트 설정 조회
    path('api/v1/read/uto_reality_config', UtoViews.api_read_uto_reality_config, name='api_read_uto_reality_config'),

    # [api v1] Reality 서버 상태
    path('api/v1/read/uto_reality_status', UtoViews.api_read_uto_reality_status, name='api_read_uto_reality_status'),

    # [api v1] Reality 수동 동기화
    path('api/v1/update/uto_reality_sync', UtoViews.api_update_uto_reality_sync, name='api_update_uto_reality_sync'),

    # [api v1] Reality 단일 사용자 배포
    path('api/v1/update/uto_reality_deploy_user', UtoViews.api_update_uto_reality_deploy_user, name='api_update_uto_reality_deploy_user'),

    # [공개] PassWall Node Subscribe URL (인증: HMAC 토큰)
    path('sub/passwall/<str:vuser>/<str:token>', UtoViews.api_passwall_subscribe, name='api_passwall_subscribe'),
    path('sub/reality/<str:vuser>/<str:token>', UtoViews.api_passwall_subscribe),  # 하위호환

    # [api v1] 구독 URL 조회 (관리자용)
    path('api/v1/read/uto_reality_sub_url', UtoViews.api_read_uto_reality_sub_url, name='api_read_uto_reality_sub_url'),
]

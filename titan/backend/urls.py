from django.urls import path, re_path
from django.conf.urls import url
from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.mypage import views as MypageViews
from .djangoapps.transaction import views as TransactionViews
from .djangoapps.download import views as DownloadViews
from .djangoapps.policy import views as PolicyViews
from .djangoapps.price import views as PriceViews  # 이 부분과 아래 부분이 충돌 발생
from .djangoapps.price import data_callback as PriceCallbackViews
from .djangoapps.price import data_request as PriceRequestViews
from .djangoapps.price import data_return as PriceReturnViews
from .djangoapps.price.views import api_check_recent_payments
from .djangoapps.price.views import api_preview_session_change
from .djangoapps.restapi import views as RestAPIViews
from .djangoapps.price_table import views as PriceTableViews  # 이름을 변경해 충돌 방지
from .djangoapps.faq import views as FaqViews


urlpatterns = [

    # [render] 인덱스 페이지
    path('', IndexViews.index, name='index'),

    # [render] 테스트 페이지
    # path('test', IndexViews.test, name='test'),
    # path('test2', IndexViews.test2, name='test2'),

    # [render] 서비스 이용약관
    path('policy/service', PolicyViews.policy_service, name='policy_service'),

    # [render] 개인정보보호정책
    path('policy/privacy', PolicyViews.policy_privacy, name='policy_privacy'),

    # [render] 환불정책
    path('policy/refund', PolicyViews.policy_refund, name='policy_refund'),

    # [render] 로그인
    path('login', LoginViews.login, name='login'),

    # [render] 회원가입
    path('regist', LoginViews.regist, name='regist'),

    # [render] 비밀번호찾기
    path('forgot_password', LoginViews.forgot_password, name='forgot_password'),

    # [render] 비밀번호 만료 페이지
    path('password_expire', LoginViews.password_expire, name='password_expire'),

    # [render] 비밀번호 변경 페이지
    path('change_password', LoginViews.change_password, name='change_password'),

    # [render] 다운로드 공통
    path('download/<type>', DownloadViews.download, name='download'),

    # [render] 이용가격
    path('price_table', PriceTableViews.price_table, name='price_table'),

    # [render] FAQ
    path('faq', FaqViews.faq, name='faq'),

    # [render] 마이페이지
    path('mypage', MypageViews.mypage, name='mypage'),
    path('mypage/password', MypageViews.password_change_page, name='password_change_page'),
    path('mypage/change_password_action', MypageViews.change_password_action, name='change_password_action'),
    path('delete_session', MypageViews.delete_session, name='delete_session'),
    path('delete_all_sessions', MypageViews.delete_all_sessions, name='delete_all_sessions'),
    path('api_change_sub_password_direct', MypageViews.api_change_sub_password_direct_v2, name='api_change_sub_password_direct'),
    path('api_send_password_reset_for_sub', MypageViews.api_send_password_reset_for_sub, name='api_send_password_reset_for_sub'),
    path('api/mypage/app_login_logs', MypageViews.api_my_app_login_logs, name='api_my_app_login_logs'),
    path('api/mypage/connection_logs', MypageViews.api_my_connection_logs, name='api_my_connection_logs'),
    path('api/mypage/fail_logs', MypageViews.api_my_fail_logs, name='api_my_fail_logs'),
    path('api/mypage/disconnect_logs', MypageViews.api_my_disconnect_logs, name='api_my_disconnect_logs'),
    path('api/mypage/autopay_status', MypageViews.api_autopay_status, name='api_autopay_status'),                        # [api] 자동결제 상태 조회
    path('api/mypage/autopay_cancel', MypageViews.api_autopay_cancel, name='api_autopay_cancel'),                        # [api] 자동결제 해지

    # [render] VPN 사용기록
    path('vpn_history', MypageViews.vpn_history, name='vpn_history'),
    path('api/mypage/active_connections', MypageViews.api_active_connections, name='api_active_connections'),
    path('api/mypage/force_disconnect', MypageViews.api_force_disconnect, name='api_force_disconnect'),

    # [render] 제어센터
    path('control_center', MypageViews.control_center, name='control_center'),
    path('api/mypage/app_sessions', MypageViews.api_my_app_sessions, name='api_my_app_sessions'),
    path('api/mypage/ban_ip', MypageViews.api_ban_my_ip, name='api_ban_my_ip'),
    path('api/mypage/ban_device', MypageViews.api_ban_my_device, name='api_ban_my_device'),
    path('api/mypage/unban', MypageViews.api_unban_my_device, name='api_unban_my_device'),
    path('api/mypage/my_bans', MypageViews.api_my_bans, name='api_my_bans'),
    path('api/mypage/delete_device', MypageViews.api_delete_device_session, name='api_delete_device_session'),

    # [api] 계정 일시차단
    path('api/mypage/suspend_account', MypageViews.api_suspend_account, name='api_suspend_account'),

    # [render] 거래이력
    path('transaction', TransactionViews.transaction, name='transaction'),
    path("get_transaction/", TransactionViews.get_transaction, name="get_transaction"),  # 거래 내역 JSON 조회
    path("get_receipt/", TransactionViews.get_receipt, name="get_receipt"),  # 거래명세서 조회 API
    path("generate_invoice/", TransactionViews.generate_invoice, name="generate_invoice"),  # Invoice 생성
    path("download_invoice/", TransactionViews.download_invoice, name="download_invoice"),  # Invoice 다운로드

    # [render] 거랙이력
    path('get_transaction', TransactionViews.get_transaction, name='get_transaction'),

    # [render] 이용가격
    path('price', PriceViews.price, name='price'),

    # [api] 로그아웃
    path('logout', LoginViews.logout, name='logout'),

    # [api] 언어 변경
    path('api_translate/<language>', IndexViews.api_translate, name='api_translate'),

    # [api] 로그인
    path('api_login_signin', LoginViews.api_login_signin, name='api_login_signin'),

    # [api] 회원가입
    path('api_login_signup', LoginViews.api_login_signup, name='api_login_signup'),
    path('login_as_subaccount', LoginViews.login_as_subaccount, name='login_as_subaccount'),

    # [api] 비밀번호 변경 smtp 발송
    path('api_login_forgotpassword', LoginViews.api_login_forgotpassword, name='api_login_forgotpassword'),

    # [api] 비밀번호 변경 계정 세션 등록
    path('api_login_fgp', LoginViews.api_login_fgp, name='api_login_fgp'),

    # [api] 계정 활성화
    path('api_login_active', LoginViews.api_login_active, name='api_login_active'),

    # [api] 실제 비밀번호 변경
    path('api_reset_password', LoginViews.api_reset_password, name='api_reset_password'),

    # [api] 사용자 메일 인증 재전송
    path('api_send_verify_email', LoginViews.api_send_verify_email, name='api_send_verify_email'),

    # [api] 결제 요청
    path('api_plz_payment', PriceViews.api_plz_payment, name='api_plz_payment'),
    
    # [api] 결제 요청
    path('api_create_payment', PriceViews.api_create_payment, name='api_create_payment'),
    path('api_create_payment_for', PriceViews.api_create_payment_for, name='api_create_payment_for'),
    path('api_prepare_extension_target', PriceViews.api_prepare_extension_target, name='api_prepare_extension_target'),
    path('api_list_subaccounts', PriceViews.api_list_subaccounts, name='api_list_subaccounts'),

    # [webview] 서비스 이용약관
    path('webview/service', PolicyViews.webview_policy_service, name='webview_policy_service'),

    # [webview] 개인정보보호정책
    path('webview/privacy', PolicyViews.webview_policy_privacy, name='webview_policy_privacy'),

    # [webview] 환불정책
    path('webview/refund', PolicyViews.webview_policy_refund, name='webview_policy_refund'),

    # [api] 결제 요청
    path('api_delete_account', PriceViews.api_delete_account, name='api_delete_account'),

    # 국내결제모듈
    path('api_make_payletter', PriceRequestViews.api_make_payletter, name='api_make_payletter'),                        # [api] 국내 결제모듈 요청
    path('api_make_payletter_autopay', PriceRequestViews.api_make_payletter_autopay, name='api_make_payletter_autopay'), # [api] 국내 자동결제 등록 요청
    path('payletter_return', PriceReturnViews.payletter_return, name='payletter_return'),                               # [render] 국내 결제모듈 리턴
    path('payletter_callback', PriceCallbackViews.payletter_callback, name='payletter_callback'),                       # [render] 국내 결제모듈 콜백
    path('payletter_cancel', PriceViews.payletter_cancel, name='payletter_cancel'),                                     # [render] 국내 결제모듈 취소


    # 해외결제모듈
    path('api_make_globalpayletter', PriceRequestViews.api_make_globalpayletter, name='api_make_globalpayletter'),      # [api] 해외 결제모듈 요청
    path('globalpayletter_return', PriceReturnViews.globalpayletter_return, name='globalpayletter_return'),             # [render] 해외 결제모듈 리턴
    re_path(r'^globalpayletter_call.*$', PriceCallbackViews.globalpayletter_callback, name='globalpayletter_callback'), # [render] 해외 결제모듈 콜백
    path('globalpayletter_cancel', PriceViews.globalpayletter_cancel, name='globalpayletter_cancel'),                   # [render] 해외 결제모듈 취소


    # 위쳇페이 (페이박스)
    path('api_make_paybox', PriceRequestViews.api_make_paybox, name='api_make_paybox'),                                 # [api] 위쳇페이 결제모듈 요청
    path('paybox_return', PriceReturnViews.paybox_return, name='paybox_return'),                                        # [render] 위쳇페이 결제모듈 리턴
    path('paybox_callback', PriceCallbackViews.paybox_callback, name='paybox_callback'),                                # [render] 위쳇페이 결제모듈 콜백
    path('paybox_cancel', PriceViews.paybox_cancel, name='paybox_cancel'),                                              # [render] 위쳇페이 결제모듈 취소




    # 모바일 REST API
    path('v1/app_init_session', RestAPIViews.app_init_session, name='app_init_session'),                    # [api] 세션키 및 토큰 생성
    path('v1/app_session_key', RestAPIViews.app_session_key, name='app_session_key'),                       # [api] 세션키에 로그인 정보 부여
    path('v1/app_session_test', RestAPIViews.app_session_test, name='app_session_test'),                    # [api] 세션키 전송 테스트
    path('v1/app_group_list', RestAPIViews.app_group_list, name='app_group_list'),                          # [api] 그룹코드 리스트 조회
    path('v1/app_get_group', RestAPIViews.app_get_group, name='app_get_group'),                             # [api] 그룹코드 조회
    path('v1/app_get_detail', RestAPIViews.app_get_detail, name='app_get_detail'),                          # [api] 상세코드 조회
    path('v1/app_get_userinfo', RestAPIViews.app_get_userinfo, name='app_get_userinfo'),                    # [api] 사용자 정보 조회
    path('v1/app_check_login', RestAPIViews.app_check_login, name='app_check_login'),                       # [api] 세션 확인
    path('v1/app_user_logout', RestAPIViews.app_user_logout, name='app_user_logout'),                       # [api] 로그아웃
    path('v1/app_change_password', RestAPIViews.app_change_password, name='app_change_password'),           # [api] 비밀번호 변경
    path('v1/app_push_message', RestAPIViews.app_push_message, name='app_push_message'),                    # [api] 푸쉬 알림
    path('v1/app_start_vpn', RestAPIViews.app_start_vpn, name='app_start_vpn'),                             # [api] 푸쉬 알림
    path('v1/app_get_price', RestAPIViews.app_get_price, name='app_get_price'),                             # [api] 가격정보 조회
    path('v1/app_user_signup', LoginViews.api_login_signup, name='app_user_signup'),                        # [api] 회원가입
    path('v1/app_payletter_global', RestAPIViews.app_payletter_global, name='app_payletter_global'),        # [api] 국내결제
    path('v1/app_payletter_korea', RestAPIViews.app_payletter_korea, name='app_payletter_korea'),           # [api] 해외결제
    path('v1/app_android_version', RestAPIViews.app_android_version, name='app_android_version'),           # [api] 안드로이드 버전 조회
    path('v1/app_windows_version', RestAPIViews.app_windows_version, name='app_windows_version'),           # [api] 윈도우즈 버전 조회
    path('v1/app_osx_version', RestAPIViews.app_osx_version, name='app_osx_version'),                       # [api] MAC OS 버전 조회
    path('v1/app_get_server_list', RestAPIViews.app_server_list, name='app_server_list'),                   # [api] 서버리스트 조회
    path('v1/app_check_server', RestAPIViews.app_check_server, name='app_check_server'),                    # [api] 서버선택연결
    path('v1/app_new_server_list', RestAPIViews.app_new_server_list, name='app_new_server_list'),
    path('v1/app_new_check_server', RestAPIViews.app_new_check_server, name='app_new_check_server'),
    path('v1/app_stable_server', RestAPIViews.app_stable_server, name='app_stable_server'),
    path('v1/app_report_failed_server', RestAPIViews.app_report_failed_server, name='app_report_failed_server'),
    path('v1/app_disconnect', RestAPIViews.app_disconnect, name='app_disconnect'),
    path('v1/app_delete_user', RestAPIViews.app_delete_user, name='app_delete_user'),
    path('v1/app_purchase_product', RestAPIViews.app_purchase_product, name='app_purchase_product'),
    path('v1/app_check_connection', RestAPIViews.app_check_connection, name='app_check_connection'),        #[api] V2ray check connection
    path('v1/app_add_connection', RestAPIViews.app_add_connection, name='app_add_connection'),              #[api] V2ray add log to radacct
    path('v1/app_disconnect_v2ray', RestAPIViews.app_disconnect_v2ray, name='app_disconnect_v2ray'),        #[api] V2ray set time to acctstoptime
    path('api_check_payment_status', PriceViews.api_check_payment_status, name='api_check_payment_status'), #새롭게 결제승인상태값을 보내줌
    path("api_check_recent_payments",  PriceViews.api_check_recent_payments, name="api_check_recent_payments"),
    path('api_preview_session_change', api_preview_session_change, name='api_preview_session_change'),
    path('api_get_payment_methods', PriceViews.api_get_payment_methods, name='api_get_payment_methods'),
    path('v1/app_health', RestAPIViews.app_health, name='app_health'),
    path('v1/app_get_notifications', RestAPIViews.app_get_notifications, name='app_get_notifications'),     #[api] 유저 이슈 통지 조회
    path('v1/app_read_notification', RestAPIViews.app_read_notification, name='app_read_notification'),     #[api] 통지 읽음 처리
    path('v1/app_unread_notification_count', RestAPIViews.app_unread_notification_count, name='app_unread_notification_count'),  #[api] 미읽은 통지 수
]

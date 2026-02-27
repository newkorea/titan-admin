from django.urls import path
from django.conf.urls import url
from .djangoapps.price.views import approve_payment_api  # ✅ `backend.` 추가


from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.dashboard import views as DashboardViews
from .djangoapps.user import views as UserViews
from .djangoapps.app import views as AppViews
from .djangoapps.notification import views as NotificationViews
from .djangoapps.price import views as PriceViews
from .djangoapps.service import views as ServiceViews
from .djangoapps.chart import views as ChartViews
from .djangoapps.saler import views as SalerViews
from .djangoapps.event import views as EventViews
from .djangoapps.reward import views as RewardViews
from .djangoapps.chatbot import views as ChatbotViews
from .djangoapps.faq import views as FaqViews
from .djangoapps.nasmonitor import views as NasMonitorViews
from .djangoapps.infra import views as InfraViews
#from .djangoapps.admin import views as AdminViews
from .djangoapps.saler import views as SalerViews
from django.urls import path
from .djangoapps.price import views as PriceViews

# 개발 시 필독
# 신규 리뉴얼 개발 이후부터 아래와 같은 명명 규칙을 따라주십시오
# 또한 주석으로 기능을 상세하게 명시하십시오
# api/v1/['read', 'update', 'create', 'delete']/기능명
# ex) api/v1/read/user_detail
# v1이 아닌 'api_' 는 as-is 함수입니다


urlpatterns = [

    #자동결제pc 클라이언트API요청을 로그로 기록 25-06-05
    path('admin/payment_logs/', PriceViews.api_view_payment_logs, name='api_view_payment_logs'),
    path('api/approve_payment/', PriceViews.approve_payment_api, name='approve_payment_api'),
    path('admin/view_payment_logs/', PriceViews.admin_payment_logs_page, name='admin_payment_logs_page'),

    # (2025-0825)status=R/C/U → D(삭제처리)로 변경
    path('api/v1/delete/by_status', PriceViews.api_delete_by_status, name='api_delete_by_status'),



    # [redirect] 권한 별 인덱스페이지 지정
    path('', IndexViews.index, name='index'),

    # [render] 샘플
    path('sample', SampleViews.sample, name='sample'),

    # [render] 로그인
    path('login', LoginViews.login, name='login'),

    # [render] 대쉬보드
    path('dashboard', DashboardViews.dashboard, name='dashboard'),

    # [render] 회원관리
    path('user', UserViews.user, name='user'),

    # [render] App관리 2023-05-10 Added by Zhao
    path('app', AppViews.app, name='app'),

    # [render] 회원관리
    path('block_user', UserViews.block_user, name='block_user'),

    # [render] 결제관리
    path('price', PriceViews.price, name='price'),

    # [render] 무통장내역
    path('account_history', PriceViews.account_history, name='account_history'),

    # [render] 계좌관리
    path('account_setting', PriceViews.account_setting, name='account_setting'),

    # [render] 자동결제 관리
    path('autopay', PriceViews.autopay, name='autopay'),

    # [api] 자동결제 통계
    path('api/v1/read/autopay_stats', PriceViews.api_read_autopay_stats, name='api_read_autopay_stats'),

    # [api] 자동결제 목록
    path('api/v1/read/autopay_list', PriceViews.api_read_autopay_list, name='api_read_autopay_list'),

    # [api] 자동결제 해지
    path('api/v1/update/autopay_cancel', PriceViews.api_update_autopay_cancel, name='api_update_autopay_cancel'),

    # [render] 서비스 내역
    path('service', ServiceViews.service, name='service'),

    # [render] 일별 통계 
    path('dd/<type>', ChartViews.dd, name='dd'),

    # [render] 월별 통계 
    path('mm/<type>', ChartViews.mm, name='mm'),

    # [render] 월별 통계 
    path('total/<type>', ChartViews.total, name='total'),

    # [render] 일별 트래픽
    path('use_traffic', ChartViews.use_traffic, name='use_traffic'),

	# [render] 일별 트래픽
    path('use_traffic_sum', ChartViews.use_traffic_sum, name='use_traffic_sum'),

    # [render] 일별 트래픽
    path('use_traffic_monthsum', ChartViews.use_traffic_monthsum, name='use_traffic_monthsum'),

    # [render] 실시간 사용자
    path('realtime_user', ChartViews.realtime_user, name='realtime_user'),

	 # [render] 실시간 사용자
    path('realtime_user2', ChartViews.realtime_user2, name='realtime_user2'),

	 # [render] 실시간 사용자
    path('realtime_user3', ChartViews.realtime_user3, name='realtime_user3'),
    
    # [render] 로그인접속로그
    path('device_info', ChartViews.device_info, name='device_info'),

    # [render] 서버접속로그
    path('connection_info', ChartViews.connection_info, name='connection_info'),
    
    # [render] 서버접속로그
    path('disconnection_info', ChartViews.disconnection_info, name='disconnection_info'),
    
    # [render] 서버접속로그
    path('failed_info', ChartViews.failed_info, name='failed_info'),
    
    # [render] 서버접속로그
    path('reward_info', ChartViews.reward_info, name='reward_info'),

    # [render] 서버관리 (NAS 서버 리스트/수정)
    path('server_admin', ChartViews.server_admin, name='server_admin'),

    # [render] 2023-05-24 Added By Zhao
    path('notification', NotificationViews.notification, name='notification'),

    # [render] 이벤트 코드 
    path('event_code', EventViews.event_code, name='event_code'),

    # [render] 회원가입 차단
    path('regist_ban', UserViews.regist_ban, name='regist_ban'),

    # [render] 광역 스킬
    path('event_all', EventViews.event_all, name='event_all'),

    # [render] 회원관리
    path('saler/user', SalerViews.saler_user, name='saler_user'),

    # [render] 무료체험 어뷰징 유저 
    path('abuse_user', UserViews.abuse_user, name='abuse_user'),

    # [api v1] 로그인
    path('api/v1/login', LoginViews.api_login, name='api_login'),

    # [api v1] 로그아웃
    path('api/v1/logout', LoginViews.api_logout, name='api_logout'),

    # [api v1] 회원관리 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/user_datatables', UserViews.api_read_user_datatables, name='api_read_user_datatables'),

    # [api v1] 2023-05-10 Added by Zhao
    path('api/v1/read/app_datatables', AppViews.api_read_app_datatables, name='api_read_app_datatables'),

    # [api v1] 회원정보 상세정보를 반환합니다
    path('api/v1/read/user_detail', UserViews.api_read_user_detail, name='api_read_user_detail'),

    # [api v1] 회원 관리 통합 조회 (서비스시간+세션+비번+활성)
    path('api/v1/read/user_manage_info', UserViews.api_read_user_manage_info, name='api_read_user_manage_info'),

    # [api v1] 사용자별 로그 조회
    path('api/v1/read/user_login_logs', UserViews.api_read_user_login_logs, name='api_read_user_login_logs'),
    path('api/v1/read/user_fail_logs', UserViews.api_read_user_fail_logs, name='api_read_user_fail_logs'),
    path('api/v1/read/user_disconnect_logs', UserViews.api_read_user_disconnect_logs, name='api_read_user_disconnect_logs'),
    path('api/v1/read/user_connection_logs', UserViews.api_read_user_connection_logs, name='api_read_user_connection_logs'),

    # [api v1] 2023-05-25 Added by Zhao
    path('api/v1/read/get_notifications', NotificationViews.get_notifications, name='get_notifications'),

    # 2023-05-05 Added By Zhao [api v1] return user count
    path('api/v1/read/user_count', UserViews.api_read_user_count, name='api_read_user_count'),

    # 오늘 신규가입수 + 활성화수 (메뉴 뱃지용)
    path('api/v1/read/user_today_stats', UserViews.api_read_user_today_stats, name='api_read_user_today_stats'),

    # [api v1] 사용자 서비스 시간을 radcheck 에서 조회해서 반환합니다
    path('api/v1/read/user_service_time', UserViews.api_read_user_service_time, name='api_read_user_service_time'),

    # [api v1] 사용자 세션을 radcheck 에서 조회해서 반환합니다
    path('api/v1/read/user_session', UserViews.api_read_user_session, name='api_read_user_session'),

    # [api v1] 사용자 비밀번호를 변경합니다
    path('api/v1/read/app_detail', AppViews.api_read_app_detail, name='api_read_app_detail'),

    # [api v1] 사용자 비밀번호를 변경합니다
    path('api/v1/read/notification_detail', NotificationViews.api_read_notification_detail, name='api_read_notification_detail'),

    # [api v1] 사용자 서비스 시간을 radcheck 에서 수정합니다
    path('api/v1/update/user_service_time', UserViews.api_update_user_service_time, name='api_update_user_service_time'),

    # [api v1] 사용자 세션을 radcheck 에서 수정합니다
    path('api/v1/update/user_session', UserViews.api_update_user_session, name='api_update_user_session'),

    # [api v1] 사용자 비밀번호를 변경합니다
    path('api/v1/update/user_password', UserViews.api_update_user_password, name='api_update_user_password'),

    # [api v1] 사용자 비밀번호를 변경합니다
    path('api/v1/read/user_password', UserViews.api_read_user_password, name='api_read_user_password'),

    # [api v1] 사용자 활성화 상태를 변경합니다
    path('api/v1/update/user_active', UserViews.api_update_user_active, name='api_update_user_active'),

    # [api v1] 본인인증 메일 재전송 (관리자용)
    path('api/v1/send/verify_email', UserViews.api_send_verify_email, name='api_send_verify_email'),

    # [api v1] 2023-05-25 Added by Zhao
    path('api/v1/update/notification', NotificationViews.api_update_notification, name='api_update_notification'),

    # [api v1] 사용자를 탈퇴시킵니다
    path('api/v1/delete/user', UserViews.api_delete_user, name='api_delete_user'),

    # [api v1] 차단될 사용자를 검증합니다
    path('api/v1/read/block_user', UserViews.api_read_block_user, name='api_read_block_user'),

    # [api v1] 검증된 사용자를 차단합니다
    path('api/v1/update/block_user', UserViews.api_update_block_user, name='api_update_block_user'),

    # [api v1] 결제모듈 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/payment', PriceViews.api_read_payment, name='api_read_payment'),

    # [api v1] 결제모듈에 대해 환불을 진행합니다
    path('api/v1/update/refund', PriceViews.api_update_refund, name='api_update_refund'),

    # [api v1] 변경 내역 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/change_history', ServiceViews.api_read_change_history, name='api_read_change_history'),

    # [api v1] 계좌관리 입금주, 은행이름, 은행계좌번호를 반환합니다
    path('api/v1/read/account', PriceViews.api_read_account, name='api_read_account'),

    # [api v1] 계좌관리 입금주, 은행이름, 은행계좌번호를 수정합니다
    path('api/v1/update/account', PriceViews.api_update_account, name='api_update_account'),

    # [api v1] 국제 결제 방식 활성화 여부를 반환합니다
    path('api/v1/read/payment_methods', PriceViews.api_read_payment_methods, name='api_read_payment_methods'),

    # [api v1] 국제 결제 방식 활성화 여부를 수정합니다
    path('api/v1/update/payment_methods', PriceViews.api_update_payment_methods, name='api_update_payment_methods'),

    # [api v1] 영수증 URL 조회 (페이레터)
    path('api/v1/read/receipt', PriceViews.api_read_receipt, name='api_read_receipt'),

    # [api v1] 영수증 이메일 발송
    path('api/v1/send/receipt_email', PriceViews.api_send_receipt_email, name='api_send_receipt_email'),

    # [api v1] 무통장 인보이스 발급/조회/발송
    path('api/v1/generate/bank_invoice', PriceViews.api_generate_bank_invoice, name='api_generate_bank_invoice'),
    path('api/v1/view/bank_invoice', PriceViews.api_view_bank_invoice, name='api_view_bank_invoice'),
    path('api/v1/send/bank_invoice_email', PriceViews.api_send_bank_invoice_email, name='api_send_bank_invoice_email'),

    # [api v1] 무통장 결제 요청 건수를 반홥합니다
    path('api/v1/read/ready_count', PriceViews.api_read_ready_count, name='api_read_ready_count'),

    # 오늘 결제건수 (메뉴 뱃지용)
    path('api/v1/read/today_payment_count', PriceViews.api_read_today_payment_count, name='api_read_today_payment_count'),

    #  [api v1] 무통장 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/bank', PriceViews.api_read_bank, name='api_read_bank'),

    #  [api v1] 로그인접속로그 데이터를 반환합니다
    path('api/v1/read/device', ChartViews.api_read_device, name='api_read_device'),
    #  [api v1] 로그인 세션 퇴출 처리
    path('api/v1/delete/device_session', ChartViews.api_delete_device_session, name='api_delete_device_session'),

    #  [api v1] 서버접속로그 데이터를 반환합니다
    path('api/v1/read/connection', ChartViews.api_read_connection, name='api_read_connection'),

    #  [api v1] 서버접속로그 데이터를 반환합니다
    path('api/v1/read/disconnection', ChartViews.api_read_disconnection, name='api_read_disconnection'),

    #  [api v1] 서버접속로그 데이터를 반환합니다
    path('api/v1/read/failed', ChartViews.api_read_failed, name='api_read_failed'),
    
    #  [api v1] 서버접속로그 데이터를 반환합니다
    path('api/v1/read/reward', ChartViews.api_read_reward, name='api_read_reward'),

    # [api v1] 서버관리
    path('api/v1/read/agents', ChartViews.api_read_agents, name='api_read_agents'),
    path('api/v1/update/agent', ChartViews.api_update_agent, name='api_update_agent'),

    # [api v1] 무통장 결제 데이터 상태를 변경합니다
    path('api/v1/update/bank', PriceViews.api_update_bank, name='api_update_bank'),

    # [api v1] 무통장 결제 데이터 상태를 변경합니다
    path('api/v1/update/app', AppViews.api_update_app, name='api_update_app'),
    
    # [api v1] Check user session
    path('api/v1/check/session', PriceViews.api_check_session, name='api_check_session'),

    # [api v1] 무통장 결제 데이터를 생성합니다
    path('api/v1/create/bank', PriceViews.api_create_bank, name='api_create_bank'),

    # [api v1] 2023-05-04 Added by Zhao
    path('api/v1/create/app', AppViews.api_create_app, name='api_create_app'),

    # [api v1] 2023-05-24 Added by Zhao
    path('api/v1/create/notification', NotificationViews.api_create_notification, name='api_create_notification'),

    # [api v1] 2023-05-26 Added by Zhao
    path('api/v1/create/add_user', NotificationViews.api_add_user, name='api_add_user'),

    # [api v1] 무통장 결제 데이터를 생성합니다
    path('api/v1/read/ready_data', PriceViews.api_read_ready_data, name='api_read_ready_data'),

    # [api v1] 일별 통계 공통 엔드포인트
    path('api/v1/read/dd/<type>', ChartViews.api_dd, name='api_dd'),

    # [api v1] 월별 통계 공통 엔드포인트
    path('api/v1/read/mm/<type>', ChartViews.api_mm, name='api_mm'),

    # [api v1] 전체 통계 공통 엔드포인트
    path('api/v1/read/total/<type>', ChartViews.api_total, name='api_total'),

    # [api v1] 총판 회원 조회
    path('api/v1/read/saler_user', SalerViews.api_read_saler_user, name='api_read_saler_user'),

    # [api v1] 동시 접속자 수를 반환합니다
    path('api/v1/read/use_user', UserViews.api_use_user, name='api_use_user'),
    
    # [api v1] Added by Zhao
    path('api/v1/read/get_user', NotificationViews.api_get_user, name='api_get_user'),
    
    # [api v1] 일별 트래픽 사용량을 반환합니다
    path('api/v1/read/use_traffic_sum', ChartViews.api_use_traffic_sum, name='api_use_traffic_sum'),

    # [api v1] 월별 트래픽 사용량을 반환합니다
    path('api/v1/read/use_traffic_monthsum', ChartViews.api_use_traffic_monthsum, name='api_use_traffic_monthsum'),

    # [api v1] 실시간 사용자 데이터를 반환합니다
    path('api/v1/read/realtime_user', ChartViews.api_realtime_user2, name='api_realtime_user'),

	    # [api v1] 실시간 사용자 데이터를 반환합니다
    path('api/v1/read/realtime_user2', ChartViews.api_realtime_user2, name='api_realtime_user2'),

	    # [api v1] 실시간 사용자 데이터를 반환합니다
    path('api/v1/read/realtime_user3', ChartViews.api_realtime_user3, name='api_realtime_user3'),

    # [api v1] 이벤트 코드 등록 API
    path('api/v1/create/event_code', EventViews.api_create_event_code, name='api_create_event_code'),

    # [api v1] 이벤트 코드 수정 API
    path('api/v1/update/event_code', EventViews.api_update_event_code, name='api_update_event_code'),

    # [api v1] 이벤트 코드 삭제 API
    path('api/v1/delete/event_code', EventViews.api_delete_event_code, name='api_delete_event_code'),

    # [api v1] 2023-05-03 Added by Zhao
    path('api/v1/delete/app', AppViews.api_delete_app, name='api_delete_app'),

    # [api v1] 2023-05-24 Added by Zhao 
    path('api/v1/delete/notification', NotificationViews.api_delete_notification, name='api_delete_notification'),

    # [api v1] 이벤트 코드 읽기 API
    path('api/v1/read/event_code', EventViews.api_read_event_code, name='api_read_event_code'),

    # [api v1] 무료체험 어뷰징 모니터링 API
    path('api/v1/read/abuse_user', UserViews.api_read_abuse_user, name='api_read_abuse_user'),

    # [api v1] 무료체험 어뷰징 모니터링 API
    path('api/v1/read/abuse_user_detail', UserViews.api_read_abuse_user_detail, name='api_read_abuse_user_detail'),

    # [api v1] 사용자 차단 룰 등록 API
    path('api/v1/create/regist_ban', UserViews.api_create_regist_ban, name='api_create_regist_ban'),

    # [api v1] 사용자 차단 룰 수정 API
    path('api/v1/update/regist_ban', UserViews.api_update_regist_ban, name='api_update_regist_ban'),

    # [api v1] 사용자 차단 룰 삭제 API
    path('api/v1/delete/regist_ban', UserViews.api_delete_regist_ban, name='api_delete_regist_ban'),

    # [api v1] 사용자 차단 룰 읽기 API
    path('api/v1/read/regist_ban', UserViews.api_read_regist_ban, name='api_read_regist_ban'),

    # [api v1] Update DB(set current time to acctstoptime)
    path('api/v1/update/user_status', ChartViews.api_update_status, name='api_update_status'),

    # [api v1] Force Disconnect
    path('api/v1/update/user_disconnect', ChartViews.api_user_disconnect, name='api_user_disconnect'),

    # [api v1] Reward Setting API
    path('api/v1/read/reward_setting', RewardViews.api_reward_setting, name='api_reward_setting'),

    # [api v1] 이벤트 코드 수정 API
    path('api/v1/update/reward_setting', RewardViews.api_update_reward_setting, name='api_update_reward_setting'),

    # 세션 관련 API
    path('api/v1/read/session_list', UserViews.api_read_session_list, name='api_read_session_list'),
    path('api/v1/delete/session', UserViews.api_delete_session, name='api_delete_session'),
    path('api/v1/delete/all_sessions', UserViews.api_delete_all_sessions, name='api_delete_all_sessions'),
    path('api/v1/delete/web_sessions', UserViews.api_delete_web_sessions, name='api_delete_web_sessions'),
    path('api/v1/delete/disconnect_nas', UserViews.api_disconnect_nas, name='api_disconnect_nas'),

    # 접속금지 (기기/세션/IP 차단) API (2026-02-11)
    path('api/v1/create/ban_device', UserViews.api_ban_device, name='api_ban_device'),
    path('api/v1/update/unban_device', UserViews.api_unban_device, name='api_unban_device'),
    path('api/v1/read/banned_devices', UserViews.api_read_banned_devices, name='api_read_banned_devices'),

    # [render] 챗봇 Q&A 관리
    path('chatbot_qa', ChatbotViews.chatbot_qa, name='chatbot_qa'),

    # [api v1] 챗봇 Q&A CRUD API
    path('api/v1/read/chatbot_qa', ChatbotViews.api_read_chatbot_qa, name='api_read_chatbot_qa'),
    path('api/v1/read/chatbot_qa_detail', ChatbotViews.api_read_chatbot_qa_detail, name='api_read_chatbot_qa_detail'),
    path('api/v1/read/chatbot_qa_stats', ChatbotViews.api_read_chatbot_qa_stats, name='api_read_chatbot_qa_stats'),
    path('api/v1/create/chatbot_qa', ChatbotViews.api_create_chatbot_qa, name='api_create_chatbot_qa'),
    path('api/v1/update/chatbot_qa', ChatbotViews.api_update_chatbot_qa, name='api_update_chatbot_qa'),
    path('api/v1/update/chatbot_qa_toggle', ChatbotViews.api_toggle_chatbot_qa, name='api_toggle_chatbot_qa'),
    path('api/v1/delete/chatbot_qa', ChatbotViews.api_delete_chatbot_qa, name='api_delete_chatbot_qa'),

    # [render] FAQ 관리
    path('faq_manage', FaqViews.faq_manage, name='faq_manage'),

    # [api v1] FAQ CRUD API
    path('api/v1/read/faq_categories', FaqViews.api_read_faq_categories, name='api_read_faq_categories'),
    path('api/v1/create/faq_category', FaqViews.api_create_faq_category, name='api_create_faq_category'),
    path('api/v1/update/faq_category', FaqViews.api_update_faq_category, name='api_update_faq_category'),
    path('api/v1/read/faq_items', FaqViews.api_read_faq_items, name='api_read_faq_items'),
    path('api/v1/read/faq_item_detail', FaqViews.api_read_faq_item_detail, name='api_read_faq_item_detail'),
    path('api/v1/create/faq_item', FaqViews.api_create_faq_item, name='api_create_faq_item'),
    path('api/v1/update/faq_item', FaqViews.api_update_faq_item, name='api_update_faq_item'),
    path('api/v1/delete/faq_item', FaqViews.api_delete_faq_item, name='api_delete_faq_item'),
    path('api/v1/toggle/faq_item', FaqViews.api_toggle_faq_item, name='api_toggle_faq_item'),

    # [render] NAS 서버 현황
    path('nas_status', NasMonitorViews.nas_status, name='nas_status'),

    # [render] 서버 배정 현황
    path('nas_assignment', NasMonitorViews.nas_assignment, name='nas_assignment'),

    # [api v1] NAS 모니터링 API
    path('api/v1/read/nas_status', NasMonitorViews.api_read_nas_status, name='api_read_nas_status'),
    path('api/v1/read/nas_history', NasMonitorViews.api_read_nas_history, name='api_read_nas_history'),
    path('api/v1/read/nas_assignment', NasMonitorViews.api_read_nas_assignment, name='api_read_nas_assignment'),
    path('api/v1/update/toggle_is_auto', NasMonitorViews.api_toggle_is_auto, name='api_toggle_is_auto'),
    path('api/v1/update/cert_renew', NasMonitorViews.api_cert_renew, name='api_cert_renew'),
    path('api/v1/read/cert_renew_status', NasMonitorViews.api_cert_renew_status, name='api_cert_renew_status'),
    path('api/v1/update/nas_manual_check', NasMonitorViews.api_nas_manual_check, name='api_nas_manual_check'),
    path('api/v1/read/nas_manual_check_status', NasMonitorViews.api_nas_manual_check_status, name='api_nas_manual_check_status'),
    path('api/v1/read/nas_ssh_info', NasMonitorViews.api_read_nas_ssh_info, name='api_read_nas_ssh_info'),
    path('api/v1/update/nas_single_check', NasMonitorViews.api_nas_single_check, name='api_nas_single_check'),
    path('api/v1/read/nas_single_check_status', NasMonitorViews.api_nas_single_check_status, name='api_nas_single_check_status'),
    path('api/v1/update/reboot_server', NasMonitorViews.api_reboot_server, name='api_reboot_server'),

    # [api v1] 목표사이트 점검
    path('api/v1/update/site_check', NasMonitorViews.api_start_site_check, name='api_start_site_check'),
    path('api/v1/read/site_check_status', NasMonitorViews.api_read_site_check_status, name='api_read_site_check_status'),

    # [render] NAS Cron 관리
    path('nas_cron', NasMonitorViews.nas_cron, name='nas_cron'),

    # [api v1] NAS Cron 관리 API
    path('api/v1/read/cron_logs', NasMonitorViews.api_read_cron_logs, name='api_read_cron_logs'),
    path('api/v1/read/cron_detail', NasMonitorViews.api_read_cron_detail, name='api_read_cron_detail'),
    path('api/v1/read/cron_latest', NasMonitorViews.api_read_cron_latest, name='api_read_cron_latest'),
    path('api/v1/read/cron_issue_count', NasMonitorViews.api_read_cron_issue_count, name='api_read_cron_issue_count'),
    path('api/v1/read/nas_issue_count', NasMonitorViews.api_read_nas_issue_count, name='api_read_nas_issue_count'),
    path('api/v1/update/run_cron_task', NasMonitorViews.api_run_cron_task, name='api_run_cron_task'),
    path('api/v1/read/cron_task_status', NasMonitorViews.api_cron_task_status, name='api_cron_task_status'),

    # [api v1] 서버 접속 실패 통계
    path('api/v1/read/server_failures', NasMonitorViews.api_read_server_failures, name='api_read_server_failures'),
    path('api/v1/read/server_fail_logs', NasMonitorViews.api_read_server_fail_logs, name='api_read_server_fail_logs'),

    # [render] 서버 분석
    path('server_analysis', NasMonitorViews.server_analysis, name='server_analysis'),
    path('api/v1/read/server_analysis', NasMonitorViews.api_read_server_analysis, name='api_read_server_analysis'),
    path('api/v1/read/server_alert_count', NasMonitorViews.api_read_server_alert_count, name='api_read_server_alert_count'),
    path('api/v1/read/problem_servers', NasMonitorViews.api_read_problem_servers, name='api_read_problem_servers'),

    # [render] 유저 실패 분석
    path('user_fail_analysis', NasMonitorViews.user_fail_analysis, name='user_fail_analysis'),
    path('api/v1/read/user_fail_analysis', NasMonitorViews.api_read_user_fail_analysis, name='api_read_user_fail_analysis'),
    path('api/v1/read/disconnect_logs', NasMonitorViews.api_read_disconnect_logs, name='api_read_disconnect_logs'),
    path('api/v1/read/user_deep_analysis', NasMonitorViews.api_read_user_deep_analysis, name='api_read_user_deep_analysis'),

    # [render] 인프라(하이퍼바이저) 관리
    path('infra_hosts', InfraViews.infra_hosts, name='infra_hosts'),
    path('infra_vms', InfraViews.infra_vms, name='infra_vms'),

    # [api v1] 인프라 관리 API
    path('api/v1/read/infra_hosts', InfraViews.api_read_hosts, name='api_read_infra_hosts'),
    path('api/v1/read/infra_host_detail', InfraViews.api_read_host_detail, name='api_read_infra_host_detail'),
    path('api/v1/read/infra_vms', InfraViews.api_read_vms, name='api_read_infra_vms'),
    path('api/v1/read/test_host', InfraViews.api_test_host, name='api_test_host'),
    path('api/v1/read/infra_logs', InfraViews.api_read_logs, name='api_read_infra_logs'),
    path('api/v1/read/sync_status', InfraViews.api_sync_status, name='api_sync_status'),
    path('api/v1/update/sync_hosts', InfraViews.api_sync_hosts, name='api_sync_hosts'),
    path('api/v1/update/vm_power', InfraViews.api_vm_power, name='api_vm_power'),
    path('api/v1/create/infra_host', InfraViews.api_create_host, name='api_create_infra_host'),
    path('api/v1/update/infra_host', InfraViews.api_update_host, name='api_update_infra_host'),
    path('api/v1/delete/infra_host', InfraViews.api_delete_host, name='api_delete_infra_host'),

    # [render] 유저 이슈 자동 통지 관리
    path('notification_manage', NotificationViews.UserIssueNotificationViews.page_notification_manage, name='notification_manage'),

    # [api v1] 유저 이슈 통지 API
    path('api/v1/read/issue_notifications', NotificationViews.UserIssueNotificationViews.api_read_notifications, name='api_read_issue_notifications'),
    path('api/v1/update/issue_notification', NotificationViews.UserIssueNotificationViews.api_update_notification, name='api_update_issue_notification'),
    path('api/v1/update/issue_notification_batch', NotificationViews.UserIssueNotificationViews.api_batch_notification, name='api_update_issue_notification_batch'),
    path('api/v1/create/run_analysis', NotificationViews.UserIssueNotificationViews.api_run_analysis, name='api_run_analysis'),
    path('api/v1/read/issue_notification_stats', NotificationViews.UserIssueNotificationViews.api_read_notification_stats, name='api_read_issue_notification_stats'),

]


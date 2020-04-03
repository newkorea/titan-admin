from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.dashboard import views as DashboardViews
from .djangoapps.user import views as UserViews
from .djangoapps.price import views as PriceViews
from .djangoapps.service import views as ServiceViews
from .djangoapps.chart import views as ChartViews
from .djangoapps.saler import views as SalerViews


# 개발 시 필독
# 신규 리뉴얼 개발 이후부터 아래와 같은 명명 규칙을 따라주십시오
# 또한 주석으로 기능을 상세하게 명시하십시오
# api/v1/['read', 'update', 'create', 'delete']/기능명
# ex) api/v1/read/user_detail
# v1이 아닌 'api_' 는 as-is 함수입니다


urlpatterns = [
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

    # [render] 결제관리
    path('price', PriceViews.price, name='price'),

    # [render] 무통장내역
    path('account_history', PriceViews.account_history, name='account_history'),

    # [render] 계좌관리
    path('account_setting', PriceViews.account_setting, name='account_setting'),

    # [render] 서비스 내역
    path('service', ServiceViews.service, name='service'),

    # [render] 일별 통계 
    path('dd/<type>', ChartViews.dd, name='dd'),

    # [render] 월별 통계 
    path('mm/<type>', ChartViews.mm, name='mm'),

    # [render] 월별 통계 
    path('total/<type>', ChartViews.total, name='total'),

    # [render] 회원관리
    path('saler/user', SalerViews.saler_user, name='saler_user'),

    # [api v1] 로그인
    path('api/v1/login', LoginViews.api_login, name='api_login'),

    # [api v1] 로그아웃
    path('api/v1/logout', LoginViews.api_logout, name='api_logout'),

    # [api v1] 회원관리 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/user_datatables', UserViews.api_read_user_datatables, name='api_read_user_datatables'),

    # [api v1] 회원정보 상세정보를 반환합니다
    path('api/v1/read/user_detail', UserViews.api_read_user_detail, name='api_read_user_detail'),

    # [api v1] 사용자 서비스 시간을 radcheck 에서 조회해서 반환합니다
    path('api/v1/read/user_service_time', UserViews.api_read_user_service_time, name='api_read_user_service_time'),

    # [api v1] 사용자 세션을 radcheck 에서 조회해서 반환합니다
    path('api/v1/read/user_session', UserViews.api_read_user_session, name='api_read_user_session'),

    # [api v1] 사용자 서비스 시간을 radcheck 에서 수정합니다
    path('api/v1/update/user_service_time', UserViews.api_update_user_service_time, name='api_update_user_service_time'),

    # [api v1] 사용자 세션을 radcheck 에서 수정합니다
    path('api/v1/update/user_session', UserViews.api_update_user_session, name='api_update_user_session'),

    # [api v1] 사용자 비밀번호를 변경합니다
    path('api/v1/update/user_password', UserViews.api_update_user_password, name='api_update_user_password'),

    # [api v1] 사용자 활성화 상태를 변경합니다
    path('api/v1/update/user_active', UserViews.api_update_user_active, name='api_update_user_active'),

    # [api v1] 사용자를 탈퇴시킵니다
    path('api/v1/delete/user', UserViews.api_delete_user, name='api_delete_user'),

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

    # [api v1] 무통장 결제 요청 건수를 반홥합니다
    path('api/v1/read/ready_count', PriceViews.api_read_ready_count, name='api_read_ready_count'),

    #  [api v1] 무통장 데이터테이블즈 데이터를 반환합니다
    path('api/v1/read/bank', PriceViews.api_read_bank, name='api_read_bank'),

    # [api v1] 무통장 결제 데이터 상태를 변경합니다
    path('api/v1/update/bank', PriceViews.api_update_bank, name='api_update_bank'),

    # [api v1] 무통장 결제 데이터를 생성합니다
    path('api/v1/create/bank', PriceViews.api_create_bank, name='api_create_bank'),

    # [api v1] 무통장 결제 데이터를 생성합니다
    path('api/v1/read/ready_data', PriceViews.api_read_ready_data, name='api_read_ready_data'),

    # [api v1] 일별 통계 공통 엔드포인트
    path('api/v1/read/dd/<type>', ChartViews.api_dd, name='api_dd'),

    # [api v1] 월별 통계 공통 엔드포인트
    path('api/v1/read/mm/<type>', ChartViews.api_mm, name='api_mm'),

    # [api v1] 전체 통계 공통 엔드포인트
    path('api/v1/read/total/<type>', ChartViews.api_total, name='api_total'),

    # [api v1] 동시 접속자 수를 반환합니다
    path('api/v1/read/use_user', UserViews.api_use_user, name='api_use_user'),
]

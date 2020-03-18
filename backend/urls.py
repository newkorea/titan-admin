from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.dashboard import views as DashboardViews
from .djangoapps.user import views as UserViews
from .djangoapps.price import views as PriceViews
from .djangoapps.service import views as ServiceViews


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

    # [api] 로그인
    path('api_login', LoginViews.api_login, name='api_login'),

    # [api] 로그아웃
    path('api_logout', LoginViews.api_logout, name='api_logout'),



    # [api v1] 회원관리 데이터테이블즈 데이터를 반홥합니다
    path('api/v1/read/user_datatables', UserViews.api_read_user_datatables, name='api_read_user_datatables'),

    # [api v1] 회원정보 상세정보를 반환합니다
    path('api/v1/read/user_detail', UserViews.api_read_user_detail, name='api_read_user_detail'),

    # [api v1] 사용자 서비스 시간을 radcheck 에서 조회해서 반홥합니다
    path('api/v1/read/user_service_time', UserViews.api_read_user_service_time, name='api_read_user_service_time'),

    # [api v1] 사용자 세션을 radcheck 에서 조회해서 반홥합니다
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



    # [api] 결제 데이터 로드
    path('api_price_read', PriceViews.api_price_read, name='api_price_read'),

    # [api] 환불
    path('api_price_refund', PriceViews.api_price_refund, name='api_price_refund'),

    # [api] 무통장내역 조회
    path('api_read_ah', PriceViews.api_read_ah, name='api_read_ah'),

    # [api] 무통장내역 상태변경
    path('api_set_status', PriceViews.api_set_status, name='api_set_status'),

    # [api] 무통장내역 통계
    path('api_read_sum', PriceViews.api_read_sum, name='api_read_sum'),

    # [api] 무통장내역 등록
    path('api_create_sh', PriceViews.api_create_sh, name='api_create_sh'),

    # [api] 계좌관리 내용 로드
    path('api_read_bank', PriceViews.api_read_bank, name='api_read_bank'),

    # [api] 계좌관리 내용 편집
    path('api_update_bank', PriceViews.api_update_bank, name='api_update_bank'),

    # [api] 서비스 내역 로드
    path('api_service_time_read', ServiceViews.api_service_time_read, name='api_service_time_read'),
]

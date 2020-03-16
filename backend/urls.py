from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.dashboard import views as DashboardViews
from .djangoapps.user import views as UserViews
from .djangoapps.price import views as PriceViews
from .djangoapps.service import views as ServiceViews


urlpatterns = [
    # [redirect] 권한 별 인덱스페이지 지정
    path('', IndexViews.index, name='index'),

    # [render] 샘플
    path('sample', SampleViews.sample, name='sample'),

    # [render] 로그인
    path('login', LoginViews.login, name='login'),

    # [render] 대쉬보드
    path('dashboard', DashboardViews.dashboard, name='dashboard'),

    # [api] 로그인
    path('api_login', LoginViews.api_login, name='api_login'),

    # [api] 로그아웃
    path('api_logout', LoginViews.api_logout, name='api_logout'),


    # 회원관리
    path('user', UserViews.user, name='user'),                                          # [render] 회원관리
    path('api_user_read', UserViews.api_user_read, name='api_user_read'),               # [api] 회원 로드
    path('api_user_detail', UserViews.api_user_detail, name='api_user_detail'),         # [api] 회원 상세 로드
    path('api_user_edit', UserViews.api_user_edit, name='api_user_edit'),               # [api] 회원 수정


    # 결제모듈
    path('price', PriceViews.price, name='price'),                                      # [render] 결제관리
    path('api_price_read', PriceViews.api_price_read, name='api_price_read'),           # [api] 결제 데이터 로드
    path('api_price_refund', PriceViews.api_price_refund, name='api_price_refund'),     # [api] 환불


    # 무통장내역
    path('account_history', PriceViews.account_history, name='account_history'),        # [render] 무통장내역
    path('api_read_ah', PriceViews.api_read_ah, name='api_read_ah'),                    # [api] 무통장내역 조회
    path('api_set_status', PriceViews.api_set_status, name='api_set_status'),           # [api] 무통장내역 상태변경
    path('api_read_sum', PriceViews.api_read_sum, name='api_read_sum'),                 # [api] 무통장내역 통계
    path('api_create_sh', PriceViews.api_create_sh, name='api_create_sh'),              # [api] 무통장내역 등록


    # 계좌관리
    path('account_setting', PriceViews.account_setting, name='account_setting'),        # [render] 계좌관리
    path('api_read_bank', PriceViews.api_read_bank, name='api_read_bank'),              # [api] 계좌관리 내용 로드
    path('api_update_bank', PriceViews.api_update_bank, name='api_update_bank'),        # [api] 계좌관리 내용 편집


    # 서비스 시간 관리
    path('service', ServiceViews.service, name='service'),
    path('api_service_read', ServiceViews.api_service_read, name='api_service_read'),
    path('api_service_time_read', ServiceViews.api_service_time_read, name='api_service_time_read'),
    path('api_service_update', ServiceViews.api_service_update, name='api_service_update'),
    path('api_session_read', ServiceViews.api_session_read, name='api_session_read'),
    path('api_session_update', ServiceViews.api_session_update, name='api_session_update'),
]

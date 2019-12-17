from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.policy import views as PolicyViews
from .djangoapps.company import views as CompanyViews
from .djangoapps.download import views as DownloadViews
from .djangoapps.review import views as ReviewViews
from .djangoapps.support import views as SupportViews
from .djangoapps.dashboard import views as DashboardViews
from .djangoapps.user import views as UserViews
from .djangoapps.price import views as PriceViews
from .djangoapps.dealer import views as DealerViews
from .djangoapps.vpn import views as VpnViews
from .djangoapps.service import views as ServiceViews


urlpatterns = [


    # sample
    path('sample', SampleViews.sample, name='sample'),                                  # [render] 샘플


    # 로그인
    path('login', LoginViews.login, name='login'),                                      # [render] 로그인
    path('api_login', LoginViews.api_login, name='api_login'),                          # [api] 로그인
    path('api_logout', LoginViews.api_logout, name='api_logout'),                       # [api] 로그아웃


    # 인덱스 리다이렉트 관리 ('/dashboard')
    path('', IndexViews.index, name='index'),                                           # [redirect] 인덱스페이지 지정


    # 정책관리
    path('policy/service', PolicyViews.service, name='service'),                        # [render] 서비스이용약관
    path('policy/privacy', PolicyViews.privacy, name='privacy'),                        # [render] 개인정보보호정책
    path('policy/refund', PolicyViews.refund, name='refund'),                           # [render] 환불정책
    path('api_policy_edit', PolicyViews.api_policy_edit, name='api_policy_edit'),       # [api] 약관 공통 편집
    path('api_policy_load', PolicyViews.api_policy_load, name='api_policy_load'),       # [api] 약관 공통 로드


    # 회사관리
    path('company/about', CompanyViews.about, name='about'),                            # [render] 회사소개
    path('api_company_edit', CompanyViews.api_company_edit, name='api_company_edit'),   # [api] 회사소개 편집
    path('api_company_load', CompanyViews.api_company_load, name='api_company_load'),   # [api] 회사소개 로드


    # 공지사항
    path('company/notice', CompanyViews.notice, name='notice'),
    path('company/create_notice', CompanyViews.create_notice, name='create_notice'),
    path('company/notice_inner/<int:no>', CompanyViews.notice_inner, name='notice_inner'),

    path('api_create_notice', CompanyViews.api_create_notice, name='api_create_notice'),
    path('api_update_notice', CompanyViews.api_update_notice, name='api_update_notice'),
    path('api_delete_notice', CompanyViews.api_delete_notice, name='api_delete_notice'),


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


    # 계좌관리
    path('account_setting', PriceViews.account_setting, name='account_setting'),        # [render] 계좌관리
    path('api_read_bank', PriceViews.api_read_bank, name='api_read_bank'),              # [api] 계좌관리 내용 로드
    path('api_update_bank', PriceViews.api_update_bank, name='api_update_bank'),        # [api] 계좌관리 내용 편집


    # 수익관리 (총판전용)
    path('dealer', DealerViews.dealer, name='dealer'),                                  # [render] 수익관리
    path('dealer_user', DealerViews.dealer_user, name='dealer_user'),                                  # [render] 회원관리
    path('api_dealer_read', DealerViews.api_dealer_read, name='api_dealer_read'),       # [api] 수익 데이터 로드


    # 다운로드 관리
    path('download/windows', DownloadViews.windows, name='windows'),                    # [render] 윈도우즈
    path('download/mac', DownloadViews.mac, name='mac'),                                # [render] 맥
    path('download/android', DownloadViews.android, name='android'),                    # [render] 안드로이드
    path('download/ios', DownloadViews.ios, name='ios'),                                # [render] IOS
    path('api_menuControl', DownloadViews.api_menuControl, name='api_menuControl'),                         # [api] 메뉴활성화
    path('api_download', DownloadViews.api_download, name='api_download'),                                  # [api] 파일 등록
    path('api_load_download_data', DownloadViews.api_load_download_data, name='api_load_download_data'),    # [api] 내용 로드


    # 리뷰 관리
    path('review', ReviewViews.review, name='review'),                                  # [render] 리뷰관리
    path('api_review_read', ReviewViews.api_review_read, name='api_review_read'),       # [api] 리뷰 로드
    path('api_review_save', ReviewViews.api_review_save, name='api_review_save'),       # [api] 리뷰 저장
    path('api_review_del', ReviewViews.api_review_del, name='api_review_del'),          # [api] 리뷰 삭제
    path('api_review_count', ReviewViews.api_review_count, name='api_review_count'),    # [api] 리뷰 카운트


    # 문의 관리
    path('support', SupportViews.support, name='support'),                                                                  # [render] 문의관리
    path('api_support_getSubOption', SupportViews.api_support_getSubOption, name='api_support_getSubOption'),               # [api] 검색 필터
    path('api_support_getContent', SupportViews.api_support_getContent, name='api_support_getContent'),                     # [api] 내용 로드
    path('api_support_getSelectContent', SupportViews.api_support_getSelectContent, name='api_support_getSelectContent'),   # [api] 상세 내용 로드
    path('api_support_deleteItem', SupportViews.api_support_deleteItem, name='api_support_deleteItem'),                     # [api] 문의 삭제
    path('api_support_sendItem', SupportViews.api_support_sendItem, name='api_support_sendItem'),                           # [api] 문의 답변

    # 서비스 시간 관리
    path('service', ServiceViews.service, name='service'),
    path('api_service_read', ServiceViews.api_service_read, name='api_service_read'),
    path('api_service_time_read', ServiceViews.api_service_time_read, name='api_service_time_read'),
    path('api_service_update', ServiceViews.api_service_update, name='api_service_update'),
    path('api_session_read', ServiceViews.api_session_read, name='api_session_read'),
    path('api_session_update', ServiceViews.api_session_update, name='api_session_update'),

    #VPN 통계
    #2019-11-14 이용훈 작업
    path('vpn/traffic', VpnViews.traffic, name = 'traffic'),

    # 대쉬보드
    path('dashboard', DashboardViews.dashboard, name='dashboard'),                      # [render] 대쉬보드


]

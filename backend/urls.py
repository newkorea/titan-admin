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


urlpatterns = [

    # sample
    path('sample', SampleViews.sample, name='sample'),

    # 로그인
    path('login', LoginViews.login, name='login'),
    path('api_login', LoginViews.api_login, name='api_login'),
    path('api_logout', LoginViews.api_logout, name='api_logout'),

    # 인덱스 리다이렉트 관리
    path('', IndexViews.index, name='index'),

    # 정책관리
    path('policy/service', PolicyViews.service, name='service'),
    path('policy/privacy', PolicyViews.privacy, name='privacy'),
    path('policy/refund', PolicyViews.refund, name='refund'),

    # 정책관리 API
    path('api_policy_edit', PolicyViews.api_policy_edit, name='api_policy_edit'),
    path('api_policy_load', PolicyViews.api_policy_load, name='api_policy_load'),

    # 회원관리
    path('user', UserViews.user, name='user'),
    path('api_user_read', UserViews.api_user_read, name='api_user_read'),
    path('api_user_detail', UserViews.api_user_detail, name='api_user_detail'),
    path('api_user_edit', UserViews.api_user_edit, name='api_user_edit'),

    # 결제관리
    path('price', PriceViews.price, name='price'),
    path('api_price_read', PriceViews.api_price_read, name='api_price_read'),

    # 수익관리 (총판전용)
    path('dealer', DealerViews.dealer, name='dealer'),
    path('api_dealer_read', DealerViews.api_dealer_read, name='api_dealer_read'),

    # 회사관리
    path('company/about', CompanyViews.about, name='about'),

    # 회사관리 API
    path('api_company_edit', CompanyViews.api_company_edit, name='api_company_edit'),
    path('api_company_load', CompanyViews.api_company_load, name='api_company_load'),

    # 다운로드 관리
    path('download/windows', DownloadViews.windows, name='windows'),
    path('download/mac', DownloadViews.mac, name='mac'),
    path('download/android', DownloadViews.android, name='android'),
    path('download/ios', DownloadViews.ios, name='ios'),

    # 다운로드 관리 API
    path('api_menuControl', DownloadViews.api_menuControl, name='api_menuControl'),
    path('api_download', DownloadViews.api_download, name='api_download'),
    path('api_load_download_data', DownloadViews.api_load_download_data, name='api_load_download_data'),


    # 리뷰 관리
    path('review', ReviewViews.review, name='review'),

    # 리뷰 관리 API
    path('api_review_read', ReviewViews.api_review_read, name='api_review_read'),
    path('api_review_save', ReviewViews.api_review_save, name='api_review_save'),
    path('api_review_del', ReviewViews.api_review_del, name='api_review_del'),
    path('api_review_count', ReviewViews.api_review_count, name='api_review_count'),


    # 문의 관리
    path('support', SupportViews.support, name='support'),

    # 문의 관리 APi
    path('api_support_getSubOption', SupportViews.api_support_getSubOption, name='api_support_getSubOption'),
    path('api_support_getContent', SupportViews.api_support_getContent, name='api_support_getContent'),
    path('api_support_getSelectContent', SupportViews.api_support_getSelectContent, name='api_support_getSelectContent'),
    path('api_support_deleteItem', SupportViews.api_support_deleteItem, name='api_support_deleteItem'),
    path('api_support_sendItem', SupportViews.api_support_sendItem, name='api_support_sendItem'),

    # 대쉬보드
    path('dashboard', DashboardViews.dashboard, name='dashboard'),
]

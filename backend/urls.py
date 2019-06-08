from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.policy import views as PolicyViews
from .djangoapps.company import views as CompanyViews
from .djangoapps.download import views as DownloadViews
from .djangoapps.review import views as ReviewViews

urlpatterns = [
    path('sample', SampleViews.sample, name='sample'),
    path('login', LoginViews.login, name='login'),
    path('', IndexViews.index, name='index'),

    # 정책관리 API
    path('api_policy_edit', PolicyViews.api_policy_edit, name='api_policy_edit'),
    path('api_policy_load', PolicyViews.api_policy_load, name='api_policy_load'),

    # 정책관리
    path('policy/service', PolicyViews.service, name='service'),
    path('policy/privacy', PolicyViews.privacy, name='privacy'),
    path('policy/refund', PolicyViews.refund, name='refund'),

    # 회사관리 API
    path('api_company_edit', CompanyViews.api_company_edit, name='api_company_edit'),
    path('api_company_load', CompanyViews.api_company_load, name='api_company_load'),

    # 회사관리
    path('company/about', CompanyViews.about, name='about'),

    # 다운로드 관리
    path('download/windows', DownloadViews.windows, name='windows'),
    path('download/mac', DownloadViews.mac, name='mac'),
    path('download/android', DownloadViews.android, name='android'),
    path('download/ios', DownloadViews.ios, name='ios'),

    path('api_download', DownloadViews.api_download, name='api_download'),
    path('api_load_download_data', DownloadViews.api_load_download_data, name='api_load_download_data'),

    # 리뷰 관리
    path('review', ReviewViews.review, name='review'),
    path('api_review_read', ReviewViews.api_review_read, name='api_review_read'),
    path('api_review_save', ReviewViews.api_review_save, name='api_review_save'),
    path('api_review_add', ReviewViews.api_review_add, name='api_review_add'),
    path('api_review_del', ReviewViews.api_review_del, name='api_review_del'),
]

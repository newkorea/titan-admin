from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.policy import views as PolicyViews
from .djangoapps.company import views as CompanyViews
from .djangoapps.download import views as DownloadViews

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
    path('api_company_edit1', CompanyViews.api_company_edit1, name='api_company_edit1'),
    path('api_company_edit2', CompanyViews.api_company_edit2, name='api_company_edit2'),
    path('api_company_edit3', CompanyViews.api_company_edit3, name='api_company_edit3'),
    path('api_company_edit4', CompanyViews.api_company_edit4, name='api_company_edit4'),

    # 회사관리
    path('company/about', CompanyViews.about, name='about'),

    # 다운로드 관리
    path('download/windows', DownloadViews.windows, name='windows'),
    path('download/mac', DownloadViews.mac, name='mac'),
    path('download/android', DownloadViews.android, name='android'),
    path('download/ios', DownloadViews.ios, name='ios'),

    path('api_download', DownloadViews.api_download, name='api_download'),
    path('api_load_download_data', DownloadViews.api_load_download_data, name='api_load_download_data'),
]

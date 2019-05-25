from django.urls import path
from django.conf.urls import url

from .djangoapps.sample import views as SampleViews
from .djangoapps.login import views as LoginViews
from .djangoapps.index import views as IndexViews
from .djangoapps.policy import views as PolicyViews
from .djangoapps.company import views as CompanyViews

urlpatterns = [
    path('sample', SampleViews.sample, name='sample'),
    path('login', LoginViews.login, name='login'),
    path('', IndexViews.index, name='index'),

    # 정책관리 API
    path('api_privacy_edit1', PolicyViews.api_privacy_edit1, name='api_privacy_edit1'),
    path('api_privacy_edit2', PolicyViews.api_privacy_edit2, name='api_privacy_edit2'),
    path('api_privacy_edit3', PolicyViews.api_privacy_edit3, name='api_privacy_edit3'),
    path('api_privacy_edit4', PolicyViews.api_privacy_edit4, name='api_privacy_edit4'),
    path('api_refund_edit1', PolicyViews.api_refund_edit1, name='api_refund_edit1'),
    path('api_refund_edit2', PolicyViews.api_refund_edit2, name='api_refund_edit2'),
    path('api_refund_edit3', PolicyViews.api_refund_edit3, name='api_refund_edit3'),
    path('api_refund_edit4', PolicyViews.api_refund_edit4, name='api_refund_edit4'),
    path('api_service_edit1', PolicyViews.api_service_edit1, name='api_service_edit1'),
    path('api_service_edit2', PolicyViews.api_service_edit2, name='api_service_edit2'),
    path('api_service_edit3', PolicyViews.api_service_edit3, name='api_service_edit3'),
    path('api_service_edit4', PolicyViews.api_service_edit4, name='api_service_edit4'),

    # 정책관리
    path('policy/service', PolicyViews.service, name='service'),
    path('policy/privacy', PolicyViews.privacy, name='privacy'),
    path('policy/refund', PolicyViews.refund, name='refund'),

    # 회솨관리
    path('company/about', CompanyViews.about, name='about'),

]
